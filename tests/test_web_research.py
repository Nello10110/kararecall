import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import kararecall
from editorial import edit_tool
from fixtures import corpus
from publication import active_root
from settings import Settings
from usage import UsageLedger
from web_research import ResearchHTTPError, identity, public_url, run_research
from web_server import context_for
from test_editorial import change


class WebResearchTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.root=Path(self.temporary.name)
        self.config=Settings(root=self.root,web_research_enabled=True,web_research_key='test-only')
        corpus(self.root)
        self.path=self.root/'data/entities.json'
        self.entity=kararecall.read_json(self.path)[0]
        self.entity['name']='Fixture Widget'
        self.entity['links'][0].update(url='https://github.com/example/fixture-widget',status='source_link_unchecked')
        kararecall.write_json(self.path,[self.entity])

    def tearDown(self):
        self.temporary.cleanup()

    def test_reads_at_most_two_matching_pages_and_shares_the_result(self):
        duplicate=copy.deepcopy(self.entity)
        duplicate['id']='duplicate-widget'
        kararecall.write_json(self.path,[self.entity,duplicate])
        rows=[{'url':'http://127.0.0.1/private'},{'url':'https://github.com/unrelated/fixture-widget'},
              *({'url':'https://github.com/example/fixture-widget/'+part} for part in ('docs','usage','releases'))]
        answers=[{'results':rows},{'content':'Description de test.'},ResearchHTTPError(404)]
        with patch('web_research.provider_request',side_effect=answers) as request:
            self.assertEqual(run_research(self.config)['state'],'complete')
            self.assertEqual(run_research(self.config)['state'],'idle')
        self.assertEqual([call.args[0] for call in request.call_args_list],['search','fetch','fetch'])
        self.assertEqual(request.call_args_list[0].args[2],{'query':'"Fixture Widget" documentation','count':5,'need_content':False})
        self.assertEqual(request.call_args_list[1].args[2]['url'],'https://github.com/example/fixture-widget/docs')
        selected=active_root(self.root)
        data=kararecall.read_json(selected/'data/catalog.json')
        research=data['entities'][0]['web_research']
        self.assertEqual(research,data['entities'][1]['web_research'])
        self.assertEqual([page['status'] for page in research['pages']],['read','unavailable'])
        self.assertTrue((selected/research['trace_file']).is_file())
        self.assertTrue(all(claim['status']=='source_claim' for claim in kararecall.entity_claims(data['entities'][0])))
        self.assertIn('Description de test.',context_for(data['entities'][0],{s['id']:s for s in data['sources']}))
        usage=UsageLedger(self.root,self.config).summary()
        self.assertEqual(usage['web_calls'],3)
        self.assertAlmostEqual(usage['web_accounted_usd'],0.00225)
        target=data['entities'][0]
        with self.assertRaises(ValueError):
            edit_tool(self.root,target['id'],change(target,documentation={
                'url':research['pages'][1]['url'],'details':{'operation':'Texte de test'}}))
        edit_tool(self.root,target['id'],change(target,documentation={
            'url':research['pages'][0]['url'],'details':{'operation':'Fonctionnement relu'}}))
        updated=kararecall.read_json(active_root(self.root)/'data/entities.json')[0]
        note=updated['details']['operation'][-1]
        self.assertEqual(note['status'],'documented')
        self.assertEqual(note['verification_file'],research['trace_file'])

    def test_french_description_uses_only_read_pages_and_resumes_after_quota(self):
        from usage import BudgetExceeded
        self.config.llm_enabled=True;self.config.llm_url='https://example.invalid';self.config.llm_model='fixture'
        url='https://github.com/example/fixture-widget/docs'
        with patch('web_research.provider_request',side_effect=[{'results':[{'url':url}]},{'content':'A local document organizer.'}]),patch('web_research.chat',side_effect=BudgetExceeded('quota')):
            self.assertEqual(run_research(self.config)['state'],'paused')
        with patch('web_research.provider_request') as provider,patch('web_research.chat',return_value=json.dumps({'text':'Un outil pour organiser ses documents en local.','urls':[url]})) as model:
            self.assertEqual(run_research(self.config)['state'],'complete')
            provider.assert_not_called();self.assertIn('en français',model.call_args.args[3][0]['content'])
        root=active_root(self.root)
        result=kararecall.read_json(root/'data/entities.json')[0]['web_research']
        self.assertEqual(result['summary']['urls'],[url]);self.assertEqual(result['summary']['language'],'fr')
        self.assertTrue((root/result['trace_file']).is_file())
        self.assertIn('organiser ses documents',context_for(kararecall.read_json(root/'data/catalog.json')['entities'][0],{row['id']:row for row in kararecall.read_json(root/'data/catalog.json')['sources']}))

    def test_quota_pause_reuses_completed_search(self):
        self.config.daily_call_limit=1
        rows={'results':[{'url':'https://github.com/example/fixture-widget'}]}
        with patch('web_research.provider_request',return_value=rows) as request:
            self.assertEqual(run_research(self.config)['state'],'paused')
            self.assertEqual(request.call_count,1)
        key,*_=identity(self.entity)
        path=self.root/'data/research-cache'/(key+'.json')
        job=kararecall.read_json(path)
        job['retry_at']=0
        kararecall.write_json(path,job)
        self.config.daily_call_limit=2
        with patch('web_research.provider_request',return_value={'content':'Page de test'}) as request:
            self.assertEqual(run_research(self.config)['state'],'complete')
            self.assertEqual(request.call_args.args[0],'fetch')

    def test_unanchored_homonyms_are_kept_without_fetching(self):
        self.entity['name']='Orbit'
        self.entity['links']=[]
        kararecall.write_json(self.path,[self.entity])
        rows={'results':[{'url':'https://orbit.com/docs'},{'url':'https://github.com/other/orbit'}]}
        with patch('web_research.provider_request',return_value=rows) as request:
            self.assertEqual(run_research(self.config)['pages'],0)
            request.assert_called_once()
        selected=active_root(self.root)
        self.assertEqual(kararecall.read_json(selected/'data/entities.json')[0]['web_research']['identity'],'ambiguous')

    def test_disabled_and_private_or_secret_urls_never_reach_the_service(self):
        for url in ('http://127.0.0.1/a','http://169.254.169.254/x','http://localhost/x','https://nas.internal/x',
                    'https://user:secret@example.com/x','https://example.com/?token=secret',
                    'https://example.com/%40hidden','https://example.com:443/x','https://example.com/truncated...'):
            self.assertIsNone(public_url(url),url)
        self.config.web_research_enabled=False
        with patch('web_research.provider_request') as request:
            self.assertEqual(run_research(self.config),{'state':'disabled'})
            request.assert_not_called()
