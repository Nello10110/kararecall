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
from controls import request_history, history_status, process_history
from integrations import normalize_bookmark, chat, ServiceError
from publication import active_root
from settings import Settings
from web_server import Corpus, make_handler, source_summary
from worker import run_cycle


def bookmarks():
    shared={'createdAt':'2026-11-01T12:00:00Z','assets':[],'tags':[]}
    return [dict(shared,id='article',content={'type':'link','url':'https://example.com/article',
        'title':'Stocker l’énergie','htmlContent':'<article><p>Stockage thermique &amp; solaire</p><script>FAUX TEXTE</script><a href="https://example.com/source">Détails</a></article>'},note='À étudier en hiver',archived=True),
        dict(shared,id='note',content={'type':'text','text':'Mon idée de jardin potager'}),
        dict(shared,id='pdf',content={'type':'asset','assetType':'pdf','assetId':'file','fileName':'Facture.pdf','content':None}),
        dict(shared,id='image',content={'type':'asset','assetType':'image','assetId':'picture','content':'Texte déjà extrait par Karakeep'})]


class AllBookmarksTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.config=Settings(root=self.root,karakeep_url='https://example.invalid',karakeep_key='test-only',sync_enabled=True,download_media=False)
    def tearDown(self):self.temp.cleanup()

    def test_mixed_content_and_personal_notes_are_searchable_without_llm(self):
        with patch('worker.Karakeep.bookmarks',side_effect=lambda:iter(bookmarks())):
            self.assertEqual(run_cycle(self.config),{'synced':4,'processed':3,'failed':0})
            run_cycle(self.config)
            published=active_root(self.root)
            self.assertEqual(run_cycle(self.config)['processed'],0)
            self.assertEqual(active_root(self.root),published)
        data=kararecall.read_json(published/'data/catalog.json');sources={s['id']:s for s in data['sources']}
        self.assertTrue(sources['article']['archived'])
        self.assertIn('Stockage thermique & solaire',sources['article']['page_text'])
        self.assertIn('https://example.com/source',sources['article']['page_text'])
        self.assertNotIn('FAUX TEXTE',sources['article']['page_text'])
        self.assertTrue(any(e['kind']=='note' for e in sources['article']['evidence']))
        self.assertTrue(any(e['kind']=='text' for e in sources['note']['evidence']))
        self.assertTrue(any(e['kind']=='document' for e in sources['image']['evidence']))
        self.assertEqual(sources['pdf']['content_status'],'metadata_only')
        self.assertFalse(sources['pdf']['processing']['audio_transcribed'])
        self.assertEqual(source_summary(sources['note'])['author'],'Note personnelle')
        for query,sid in [('thermique','article'),('hiver','article'),('potager','note'),('Facture','pdf'),('extrait','image')]:
            self.assertIn(sid,[r['id'] for r in kararecall.search(query,data,20)])

    def test_manual_history_ignores_filters_and_auto_switch_without_ai_or_download(self):
        self.config.sync_enabled=False;self.config.url_filter='instagram.com';self.config.tag_filter='excluded'
        self.config.llm_enabled=True  # Deliberately unconfigured: catalogue import needs only Karakeep.
        self.config.download_media=True
        first=request_history(self.root);self.assertEqual(request_history(self.root)['id'],first['id'])
        with patch('worker.Karakeep.bookmarks',side_effect=lambda:iter(bookmarks())),patch('worker.synthesize') as llm,patch('worker.Karakeep.download') as download:
            self.assertTrue(process_history(self.config,run_cycle))
            self.assertFalse(process_history(self.config,run_cycle))
            self.assertFalse(llm.called);self.assertFalse(download.called)
            self.assertEqual(history_status(self.root)['synced'],4)
            selected=active_root(self.root)
            request_history(self.root);process_history(self.config,run_cycle)
            self.assertEqual(active_root(self.root),selected)
        self.assertEqual(history_status(self.root)['state'],'completed')
        self.assertEqual(history_status(self.root)['processed'],0)
        self.assertFalse((self.root/'data/usage.sqlite').exists() and kararecall.read_json(self.root/'data/usage-summary.json',{}).get('calls',0))

    def test_history_error_keeps_previous_publication_and_redacts_keys(self):
        request_history(self.root)
        def failed():
            yield bookmarks()[0]
            raise ServiceError('Unavailable '+self.config.karakeep_key)
        with patch('worker.Karakeep.bookmarks',side_effect=failed):process_history(self.config,run_cycle)
        state=history_status(self.root)
        self.assertEqual(state['state'],'error');self.assertNotIn(self.config.karakeep_key,state['message'])
        self.assertEqual(kararecall.read_json(active_root(self.root)/'data/sources.json'),[])
        # A crashed running request is safely replayed after restart.
        request_history(self.root)
        from controls import update_history
        update_history(self.root,state='running')
        with patch('worker.Karakeep.bookmarks',return_value=iter(bookmarks())):process_history(self.config,run_cycle)
        self.assertEqual(history_status(self.root)['state'],'completed')

    def test_article_summary_does_not_require_an_identified_tool_and_cites_real_proofs(self):
        self.config.llm_enabled=True;self.config.llm_url='https://example.invalid';self.config.llm_model='test'
        def response(*args,**kwargs):
            rows=json.loads(args[3][-1]['content'])['evidence']
            page=next(e for e in rows if e['kind']=='page')
            return json.dumps({'reading':{'summary':'Méthode de stockage de chaleur.','evidence_ids':[page['id']],'keywords':['calorifique']},'tools':[]})
        with patch('worker.Karakeep.bookmarks',side_effect=lambda:iter(bookmarks()[:1])),patch('worker.chat',side_effect=response):
            self.assertEqual(run_cycle(self.config)['processed'],1)
            selected=active_root(self.root)
            self.assertEqual(run_cycle(self.config)['processed'],0)
            self.assertEqual(active_root(self.root),selected)
        data=kararecall.read_json(selected/'data/catalog.json')
        self.assertEqual(data['entities'],[])
        self.assertEqual(kararecall.search('calorifique',data)[0]['id'],'article')
        self.assertTrue(data['sources'][0]['reading']['evidence'][0].startswith('article#page-'))
        self.assertIn('Résumé de lecture',(selected/'vault/sources/article.md').read_text())
        bad=data['sources'][0];bad['reading']['evidence']=['article#invented']
        with self.assertRaises(ValueError):kararecall.validate_reading(bad,{'article':bad})

    def test_deepseek_payload_uses_max_tokens_and_explicit_thinking_control(self):
        response={'choices':[{'message':{'content':'{}'},'finish_reason':'stop'}]}
        with patch('integrations.request_json',return_value=response) as request:
            chat('https://api.deepseek.com','test-only','deepseek-flash',[],thinking='disabled',token_limit_param='max_tokens',max_tokens=600)
        payload=request.call_args.args[2]
        self.assertEqual(payload['thinking'],{'type':'disabled'})
        self.assertEqual(payload['max_tokens'],600);self.assertNotIn('max_completion_tokens',payload)

    def test_repeated_bookmark_across_pages_does_not_repeat_inference(self):
        self.config.llm_enabled=True;self.config.llm_url='https://example.invalid';self.config.llm_model='test'
        def response(*args,**kwargs):
            page=next(e for e in json.loads(args[3][-1]['content'])['evidence'] if e['kind']=='page')
            return json.dumps({'reading':{'summary':'Stockage thermique.','evidence_ids':[page['id']]},'tools':[]})
        with patch('worker.Karakeep.bookmarks',return_value=iter([bookmarks()[0],bookmarks()[0]])),patch('worker.chat',side_effect=response) as model:
            self.assertEqual(run_cycle(self.config),{'synced':1,'processed':1,'failed':0})
            self.assertEqual(model.call_count,1)


class HistoryHTTPTests(unittest.TestCase):
    def test_command_requires_auth_csrf_and_fixed_payload_and_survives_web_restart(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Corpus(root),'paul','test-only'))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            auth='Basic '+base64.b64encode(b'paul:test-only').decode()
            def send(method,path,body=None,**extra):
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                connection.request(method,path,body,headers={'Authorization':auth,**extra})
                response=connection.getresponse();raw=response.read()
                try:body=json.loads(raw)
                except ValueError:body=raw.decode()
                result=response.status,body;connection.close();return result
            try:
                self.assertEqual(send('POST','/api/import-history','{}',**{'Authorization':'bad'})[0],401)
                self.assertEqual(send('POST','/api/import-history','{}')[0],403)
                csrf=send('GET','/api/control')[1]['csrf_token']
                headers={'X-KaraRecall-CSRF':csrf,'Content-Type':'application/json'}
                self.assertEqual(send('POST','/api/import-history','{}',**headers,Origin='https://attacker.invalid')[0],403)
                self.assertEqual(send('POST','/api/import-history','{"command":"rm"}',**headers)[0],400)
                self.assertEqual(send('POST','/api/import-history','x'*1025,**headers)[0],400)
                self.assertEqual(send('POST','/api/other','{}',**headers)[0],404)
                status,first=send('POST','/api/import-history','{}',**headers)
                self.assertEqual(status,202);self.assertEqual(first['state'],'queued')
                self.assertEqual(send('POST','/api/import-history','{}',**headers)[1]['id'],first['id'])
                self.assertEqual(history_status(root)['id'],first['id'])
                self.assertNotIn('test-only',json.dumps(send('GET','/api/catalog')[1]))
                server.shutdown();server.server_close();thread.join(timeout=5)
                server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Corpus(root),'paul','test-only'))
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                restarted=send('GET','/api/control')[1]
                self.assertEqual(restarted['history_import']['id'],first['id'])
                self.assertNotEqual(restarted['csrf_token'],csrf)
                self.assertEqual(send('POST','/api/import-history','{}',**headers)[0],403)
            finally:server.shutdown();server.server_close();thread.join(timeout=5)
