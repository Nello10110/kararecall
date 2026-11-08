"""Article writing is tested with synthetic proofs and simulated provider responses."""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kararecall import digests
from kararecall import digest_delivery
from kararecall import digest_writer
from kararecall import core as kararecall
from fixtures import corpus
from kararecall.settings import Settings


class DigestWriterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,{'DIGEST_ENABLED':'true','DIGEST_WRITE_ARTICLES':'true',
                                      'DIGEST_INITIAL_HISTORY':'false','DIGEST_MONTHLY':'false'},clear=True)
        self.env.start();corpus(self.root)
        self.settings=Settings(root=self.root,llm_enabled=True,llm_url='https://example.invalid',llm_model='fixture',download_media=False)
        self.edition=digests.generate(self.root,'weekly','2026-11-02')

    def tearDown(self):
        self.env.stop();self.temp.cleanup()

    def response(self,url,key,payload,timeout):
        packet=json.loads(payload['messages'][-1]['content'])
        ref=packet['proofs'][0]['ref']
        text={'title':'Un article issu des preuves','paragraphs':[
            {'text':'Le premier paragraphe développe le sujet présenté par la source.','evidence':[ref]},
            {'text':'Le second paragraphe explique son usage et conserve ses limites.','evidence':[ref]}]}
        return {'choices':[{'message':{'content':json.dumps(text)}}],'usage':{'prompt_tokens':50,'completion_tokens':60}}

    def test_written_articles_keep_references_and_reuse_cached_work(self):
        with patch('kararecall.integrations.request_json',side_effect=self.response) as provider:
            state=digest_writer.write_edition(self.root,self.edition['id'],self.settings,max_items=1)
            self.assertEqual(state,'pending')
            self.assertEqual(provider.call_count,1)
            state=digest_writer.write_edition(self.root,self.edition['id'],self.settings)
            self.assertEqual(state,'ready')
            self.assertEqual(provider.call_count,2)
            written=digests.load(self.root,self.edition['id'])
            self.assertIn('Le second paragraphe',digests.article_html(self.root,written))
            self.assertNotIn('À quoi ça sert',digests.article_html(self.root,written))
            digests.generate(self.root,'weekly','2026-11-02',refresh=True)
            self.assertEqual(digest_writer.write_edition(self.root,self.edition['id'],self.settings),'ready')
            self.assertEqual(provider.call_count,2)
        self.assertTrue(all(p['evidence'] for item in written['items'] for p in item['paragraphs']))

    def test_budget_pause_resumes_without_rewriting_finished_article(self):
        self.settings.daily_call_limit=1
        with patch('kararecall.integrations.request_json',side_effect=self.response) as provider:
            self.assertEqual(digest_writer.write_edition(self.root,self.edition['id'],self.settings),'paused')
            self.assertEqual(provider.call_count,1)
            partial=digests.load(self.root,self.edition['id'])
            self.assertEqual(sum(bool(item.get('paragraphs')) for item in partial['items']),1)
            partial['writing']['retry_at']=0;digests.save(self.root,partial)
            self.settings.daily_call_limit=10
            self.assertEqual(digest_writer.write_edition(self.root,self.edition['id'],self.settings),'ready')
            self.assertEqual(provider.call_count,2)

    def test_invented_reference_prevents_automatic_publication(self):
        def wrong(*args,**kwargs):
            response=self.response(*args,**kwargs)
            data=json.loads(response['choices'][0]['message']['content'])
            data['paragraphs'][0]['evidence']=['missing#invented']
            response['choices'][0]['message']['content']=json.dumps(data)
            return response
        with patch('kararecall.digest_writer.Settings.from_env',return_value=self.settings),patch('kararecall.integrations.request_json',side_effect=wrong):
            digest_delivery.process(self.root,datetime(2026,11,2,9,tzinfo=timezone.utc))
        edition=digests.load(self.root,self.edition['id'])
        self.assertFalse(edition['approved'])
        self.assertEqual(edition['writing']['state'],'retry')
        self.assertFalse(any(item.get('paragraphs') for item in edition['items']))

    def test_edit_during_provider_call_is_preserved(self):
        def edit_then_respond(*args,**kwargs):
            current=digests.load(self.root,self.edition['id'])
            payload={key:copy.deepcopy(current[key]) for key in ('revision','title','intro','items')}
            payload['intro']='Introduction corrigée pendant l’appel.'
            digests.revise(self.root,current['id'],payload)
            return self.response(*args,**kwargs)
        with patch('kararecall.integrations.request_json',side_effect=edit_then_respond):
            self.assertEqual(digest_writer.write_edition(self.root,self.edition['id'],self.settings),'changed')
        current=digests.load(self.root,self.edition['id'])
        self.assertEqual(current['intro'],'Introduction corrigée pendant l’appel.')
        self.assertFalse(any(item.get('paragraphs') for item in current['items']))

    def test_first_edition_uses_history_and_waits_for_actual_writer_configuration(self):
        os.environ.update(DIGEST_INITIAL_HISTORY='true')
        with patch('kararecall.digest_writer.Settings.from_env',return_value=Settings(root=self.root)):
            digest_delivery.process(self.root,datetime(2026,11,7,9,tzinfo=timezone.utc))
        initial=next(row for row in digests.list_editions(self.root) if row['kind']=='initial')
        self.assertEqual(len(initial['items']),2)
        self.assertEqual(initial['writing']['state'],'waiting_configuration')
        self.assertFalse(initial['approved'])
