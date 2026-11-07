import base64
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import kararecall
from controls import action_status, library_paused, process_actions, request_action, request_history
from curation import clean_text, short_text, translate_evidence
from fixtures import corpus
from publication import active_root
from settings import Settings
from usage import BudgetExceeded, UsageLedger
from web_server import Corpus, make_handler, source_summary
from worker import run_cycle


def response(*args, **kwargs):
    packet=json.loads(args[3][-1]['content'])
    return json.dumps({'tools':[], 'reading':{'title':'Organiser ses outils',
        'summary':'Organiser ses outils et conserver les informations utiles. '*10,
        'source_language':'fr','keywords':['organisation'],
        'evidence_ids':[packet['evidence'][0]['id']]}})


class CurationControlsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        corpus(self.root)
        self.settings=Settings(root=self.root,llm_enabled=True,llm_url='https://example.invalid/v1',llm_model='fixture')

    def tearDown(self):self.temp.cleanup()

    def test_cleanup_preserves_facts_and_original_evidence(self):
        text='Exports PDF disponibles.\n#viral #fyp #tools\nFollow me for more tips\nCode promo : EXEMPLE\nLa publicité est bloquée par cet outil.'
        clean=clean_text(text)
        self.assertEqual(clean,'Exports PDF disponibles.\nLa publicité est bloquée par cet outil.')
        self.assertLessEqual(len(short_text('Un contenu explicatif. '*100)),180)
        self.assertIn('#viral',text)

    def test_bulk_llm_works_without_sync_or_karakeep_and_keeps_real_proofs(self):
        original=kararecall.read_json(self.root/'data/catalog.json')
        job=request_action(self.root,'llm')
        self.assertEqual(request_action(self.root,'llm')['id'],job['id'])
        with patch('worker.Karakeep.bookmarks') as remote,patch('worker.chat',side_effect=response) as model:
            self.assertTrue(process_actions(self.settings))
            self.assertEqual(action_status(self.root)['jobs'][-1]['cursor'],1)
            self.assertTrue(process_actions(self.settings))
            self.assertFalse(process_actions(self.settings))
            self.assertEqual(model.call_count,2);remote.assert_not_called()
        state=action_status(self.root)['jobs'][-1]
        self.assertEqual(state['state'],'completed');self.assertEqual(state['total'],2)
        current=kararecall.read_json(active_root(self.root)/'data/catalog.json')
        for source in current['sources']:
            self.assertLessEqual(len(source['reading']['text']),180)
            self.assertEqual(source['reading']['language'],'fr')
            self.assertEqual(source_summary(source)['title'],'Organiser ses outils')
            self.assertEqual(source['stages']['llm'],'complete')
            previous=next(row for row in original['sources'] if row['id']==source['id'])
            self.assertEqual([row['text'] for row in source['evidence'] if not row.get('archived')],
                             [row['text'] for row in previous['evidence']])
        # Existing non-machine editorial cards are retained.
        self.assertEqual(len(current['entities']),len(original['entities']))

    def test_quota_pause_resumes_without_repeating_completed_sources(self):
        request_action(self.root,'llm')
        with patch('worker.run_local_llm',side_effect=[None,BudgetExceeded('quota')]) as run:
            process_actions(self.settings);process_actions(self.settings)
            self.assertEqual(run.call_count,2)
        job=action_status(self.root)['jobs'][-1]
        self.assertEqual((job['cursor'],job['state']),(1,'paused'))
        self.assertFalse(process_actions(self.settings))
        value=kararecall.read_json(self.root/'data/control/actions.json');value['jobs'][-1]['retry_at']=0
        kararecall.write_json(self.root/'data/control/actions.json',value)
        with patch('worker.run_local_llm') as run:
            process_actions(self.settings)
            self.assertEqual(run.call_args.args[1],job['ids'][1])
        self.assertEqual(action_status(self.root)['jobs'][-1]['state'],'completed')

    def test_restart_after_publication_does_not_pay_twice_for_same_command(self):
        from controls import _update_action
        request_action(self.root,'llm',source_id='demo-model')
        def crash_after_publication(root,identifier,**changes):
            if changes.get('state')=='completed':raise OSError('Simulated crash before queue acknowledgement')
            return _update_action(root,identifier,**changes)
        with patch('worker.chat',side_effect=response) as model,patch('controls._update_action',side_effect=crash_after_publication):
            with self.assertRaises(OSError):process_actions(self.settings)
            self.assertEqual(model.call_count,1)
        self.assertEqual(action_status(self.root)['jobs'][-1]['cursor'],0)
        with patch('worker.chat') as model:
            process_actions(self.settings);model.assert_not_called()
        self.assertEqual(action_status(self.root)['jobs'][-1]['state'],'completed')

    def test_clear_is_confirmed_local_and_preserves_ledger_and_older_generation(self):
        with self.assertRaises(ValueError):request_action(self.root,'clear')
        ledger=UsageLedger(self.root,self.settings)
        before=ledger.path.read_bytes()
        old=active_root(self.root)
        request_action(self.root,'llm')
        request_action(self.root,'clear',confirmation='VIDER')
        self.assertTrue(library_paused(self.root))
        with self.assertRaises(ValueError):request_history(self.root)
        process_actions(self.settings)
        current=kararecall.read_json(active_root(self.root)/'data/catalog.json')
        self.assertEqual(current['sources'],[]);self.assertEqual(current['entities'],[])
        self.assertTrue((old/'data/catalog.json').is_file())
        self.assertEqual(ledger.path.read_bytes(),before)
        self.settings.sync_enabled=True
        self.settings.karakeep_url='https://example.invalid';self.settings.karakeep_key='test-only'
        with patch('worker.Karakeep.bookmarks') as remote:
            self.assertEqual(run_cycle(self.settings)['synced'],0);remote.assert_not_called()
        request_history(self.root)
        self.assertFalse(library_paused(self.root))

    def test_complete_refresh_pauses_and_resumes_without_forcing_paid_extractions_again(self):
        request_action(self.root,'refresh',source_id='demo-model')
        sources=kararecall.read_json(self.root/'data/sources.json')
        next(row for row in sources if row['id']=='demo-model')['stages']={'vision':'paused','llm':'waiting'}
        kararecall.write_json(self.root/'data/sources.json',sources)
        with patch('worker.run_cycle',return_value={'failed':1}) as run:
            process_actions(self.settings)
            self.assertEqual(run.call_args.kwargs['force_stage'],'all')
        job=action_status(self.root)['jobs'][-1]
        self.assertEqual(job['state'],'paused')
        data=kararecall.read_json(self.root/'data/control/actions.json');data['jobs'][-1]['retry_at']=0
        kararecall.write_json(self.root/'data/control/actions.json',data)
        with patch('worker.run_cycle',return_value={'failed':0}) as run:
            process_actions(self.settings)
            self.assertEqual(run.call_args.kwargs['force_stage'],'resume')
        self.assertEqual(action_status(self.root)['jobs'][-1]['state'],'completed')

    def test_translation_resumes_cached_chunks_with_provenance(self):
        source={'id':'translated','reading':{'source_language':'en'}}
        proofs=[{'id':'page-abc','kind':'page','text':'Saved text. '*200}]
        with patch('curation.chat',side_effect=['{"text":"Texte français initial."}',BudgetExceeded('quota')]) as model:
            with self.assertRaises(BudgetExceeded):translate_evidence(source,proofs,self.settings,None)
            self.assertEqual(model.call_count,2)
        with patch('curation.chat',return_value='{"text":"Suite traduite."}') as model:
            result=translate_evidence(source,proofs,self.settings,None)
            self.assertEqual(model.call_count,1)
        self.assertIn('Texte français initial.',result['page-abc']['text'])
        self.assertEqual(result['page-abc']['evidence'],['translated#page-abc'])
        self.assertTrue(proofs[0]['text'].startswith('Saved text.'))

    def test_short_proofs_share_one_translation_call_and_cannot_swap_references(self):
        source={'id':'translated','reading':{'source_language':'mixed'}}
        proofs=[{'id':'asr-one','kind':'asr','text':'First excerpt.'},{'id':'ocr-two','kind':'ocr','text':'Second excerpt.'}]
        result={'translations':[{'id':'p0','text':'Premier extrait.'},{'id':'p1','text':'Second extrait.'}]}
        with patch('curation.chat',return_value=json.dumps(result)) as model:
            translated=translate_evidence(source,proofs,self.settings,None)
            self.assertEqual(model.call_count,1)
        self.assertEqual(translated['asr-one']['text'],'Premier extrait.')
        self.assertEqual(translated['ocr-two']['evidence'],['translated#ocr-two'])
        source['id']='other-source'
        from integrations import ServiceError
        with patch('curation.chat',return_value=json.dumps({'translations':[{'id':'invented','text':'Texte inventé.'}]})):
            with self.assertRaises(ServiceError):translate_evidence(source,proofs,self.settings,None)

    def test_invalid_source_and_missing_config_are_reported_without_remote_calls(self):
        with self.assertRaises(ValueError):request_action(self.root,'refresh',source_id='absent')
        request_action(self.root,'llm',source_id='demo-model')
        self.settings.llm_enabled=False
        with patch('worker.chat') as model:
            process_actions(self.settings);model.assert_not_called()
        state=action_status(self.root)['jobs'][-1]
        self.assertEqual(state['state'],'error');self.assertIn('LLM_ENABLED',state['message'])

    def test_new_admin_endpoint_requires_auth_csrf_origin_and_typed_clear_confirmation(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Corpus(self.root),'test','local-password'))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        auth='Basic '+base64.b64encode(b'test:local-password').decode()
        def send(method,path,payload=None,**headers):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            connection.request(method,path,None if payload is None else json.dumps(payload),{'Authorization':auth,**headers})
            response=connection.getresponse();data=json.loads(response.read());connection.close()
            return response.status,data
        try:
            # Unauthenticated response is intentionally plain text.
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
            connection.request('POST','/api/actions','{}');r=connection.getresponse();r.read();connection.close()
            self.assertEqual(r.status,401)
            self.assertEqual(send('POST','/api/actions',{'kind':'llm'})[0],403)
            token=send('GET','/api/control')[1]['csrf_token']
            headers={'X-KaraRecall-CSRF':token,'Content-Type':'application/json'}
            self.assertEqual(send('POST','/api/actions',{'kind':'llm'},Origin='https://attacker.invalid',**headers)[0],403)
            self.assertEqual(send('POST','/api/actions',{'kind':'llm','command':'execute'},**headers)[0],400)
            self.assertEqual(send('POST','/api/actions',{'kind':'clear'},**headers)[0],400)
            status,job=send('POST','/api/actions',{'kind':'llm','source_id':'demo-model'},**headers)
            self.assertEqual(status,202);self.assertEqual(job['state'],'queued')
            state=send('GET','/api/catalog')[1]
            self.assertEqual(state['actions']['jobs'][-1]['id'],job['id'])
            self.assertEqual(state['reading_count'],0)
        finally:server.shutdown();server.server_close();thread.join(timeout=5)
