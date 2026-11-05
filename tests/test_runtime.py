import copy
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

import cerveau
from integrations import ServiceError,normalize_bookmark
from settings import Settings,initialize,load_env
from worker import run_cycle,check_connections,redacted


class ConfigurationTests(unittest.TestCase):
    def test_fresh_volume_starts_empty_and_preserves_existing_data(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            initialize(root)
            self.assertEqual(cerveau.read_json(root/'data/catalog.json')['sources'],[])
            self.assertTrue((root/'vault/INDEX.md').is_file())
            cerveau.write_json(root/'data/entities.json',[{'personal':'preserved'}])
            initialize(root)
            self.assertEqual(cerveau.read_json(root/'data/entities.json'),[{'personal':'preserved'}])

    def test_env_is_not_shell_and_environment_wins(self):
        with tempfile.TemporaryDirectory() as name:
            env=Path(name)/'.env'
            env.write_text('MEMOIRE_TEST_A="hello world"\nMEMOIRE_TEST_B=$(touch /not-executed)\n')
            with patch.dict(os.environ,{'MEMOIRE_TEST_A':'existing'},clear=True):
                load_env(env)
                self.assertEqual(os.environ['MEMOIRE_TEST_A'],'existing')
                self.assertEqual(os.environ['MEMOIRE_TEST_B'],'$(touch /not-executed)')

    def test_worker_configuration_and_redaction(self):
        settings=Settings(root=Path('/tmp'),sync_enabled=True,karakeep_key='very-private-token')
        with self.assertRaisesRegex(ValueError,'KARAKEEP_BASE_URL'):
            settings.validate_worker()
        self.assertNotIn('very-private-token',repr(settings))
        self.assertEqual(redacted('received very-private-token',settings),'received [secret masqué]')
        with patch.dict(os.environ,{'LLM_BASE_URL':'https://example.com/v1','LLM_API_KEY':'test-only','VISION_BASE_URL':'','VISION_API_KEY':''},clear=True):
            config=Settings.from_env()
            self.assertEqual(config.vision_url,config.llm_url)
            self.assertEqual(config.vision_key,config.llm_key)
        with patch.dict(os.environ,{'LLM_BASE_URL':'https://username:password@example.com/v1'},clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.requests=[]
        self.bad_refs=False
        self.repeat_cursor=False
        self.forbid=False
        owner=self
        class Mock(BaseHTTPRequestHandler):
            def log_message(self,*args):
                pass
            def respond(self,data,status=200):
                raw=json.dumps(data).encode()
                self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
            def do_GET(self):
                owner.requests.append(('GET',self.path,self.headers.get('Authorization')))
                if owner.forbid:
                    return self.respond({'error':'do not log this private-token'},401)
                if self.path.startswith('/api/v1/bookmarks'):
                    second='cursor=second' in self.path
                    sid='two' if second else 'one'
                    bookmark={'id':sid,'createdAt':'2026-11-01T12:00:00Z','modifiedAt':'2026-11-01T12:00:00Z','title':'Une lampe pour le bureau',
                        'content':{'type':'link','url':'https://example.com/lamp','description':'Lampe Flux, pour éclairer un bureau. https://example.com/lamp'},
                        'tags':[{'name':'Éclairage'}],'assets':[],'summary':'Résumé Karakeep non vérifié'}
                    return self.respond({'bookmarks':[bookmark],'nextCursor':'second' if not second or owner.repeat_cursor else None})
                if self.path=='/v1/models':
                    return self.respond({'data':[{'id':'test-model'}]})
                return self.respond({},404)
            def do_POST(self):
                owner.requests.append(('POST',self.path,self.headers.get('Authorization')))
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                assert payload['model']=='test-model'
                answer={'tools':[{'name':'Lampe Flux','description':'Une lampe qui éclaire le bureau.',
                    'aliases':['éclairage','bureau'],'evidence_ids':['invented' if owner.bad_refs else 'caption'],
                    'details':dict(description='Une lampe.',usefulness='Éclairer le bureau.',operation='Le fonctionnement détaillé n’est pas précisé.',limitations='Données issues de la source ; à relire.'),
                    'links':[{'url':'https://example.com/lamp','label':'Lien dans la source','purpose':'Approfondir'},
                             {'url':'https://invented.example.com','label':'Invention','purpose':'À refuser'}]}]}
                return self.respond({'choices':[{'message':{'content':json.dumps(answer)}}]})
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Mock)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        base='http://127.0.0.1:'+str(self.server.server_port)
        self.config=Settings(root=self.root,karakeep_url=base,karakeep_key='private-token',sync_enabled=True,
            download_media=False,llm_enabled=True,llm_url=base+'/v1',llm_key='llm-test-key',llm_model='test-model')

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5);self.temp.cleanup()

    def test_paged_read_only_sync_and_llm_are_idempotent(self):
        self.assertEqual(run_cycle(self.config),dict(synced=2,processed=2,failed=0))
        catalog=cerveau.read_json(self.root/'data/catalog.json')
        self.assertEqual(len(catalog['sources']),2)
        self.assertEqual(len(catalog['entities']),2)
        self.assertTrue(all(e['curation']=='machine-generated' for e in catalog['entities']))
        self.assertTrue(all(not s['processing']['audio_transcribed'] for s in catalog['sources']))
        for e in catalog['entities']:
            self.assertEqual(len(e['links']),1)
            self.assertEqual(e['links'][0]['url'],'https://example.com/lamp')
            self.assertTrue(all(c['status']=='source_claim' for c in cerveau.entity_claims(e)))
        self.assertEqual(run_cycle(self.config),dict(synced=2,processed=0,failed=0))
        self.assertTrue(all(method=='GET' for method,path,_ in self.requests if path.startswith('/api/v1/')))
        self.assertTrue(all(auth=='Bearer private-token' for method,path,auth in self.requests if path.startswith('/api/v1/')))
        self.assertEqual(len([r for r in self.requests if r[0]=='POST']),2)

    def test_invented_references_fail_without_publishing_and_are_retried_later(self):
        self.bad_refs=True
        result=run_cycle(self.config)
        self.assertEqual(result['failed'],2)
        self.assertEqual(cerveau.read_json(self.root/'data/entities.json'),[])
        self.assertEqual(run_cycle(self.config)['failed'],0)
        with sqlite3.connect(self.root/'data/worker.sqlite') as db:
            states=db.execute('SELECT state,attempts,next_retry FROM jobs').fetchall()
        self.assertTrue(all(s[0]=='failed' and s[1]==1 and s[2]>0 for s in states))

    def test_cursor_loop_does_not_publish_partial_snapshot(self):
        self.repeat_cursor=True
        with self.assertRaisesRegex(ServiceError,'curseur'):
            run_cycle(self.config)
        self.assertEqual(cerveau.read_json(self.root/'data/sources.json'),[])

    def test_errors_do_not_expose_upstream_body_or_token(self):
        self.forbid=True
        with self.assertRaises(ServiceError) as raised:
            run_cycle(self.config)
        self.assertNotIn('private-token',str(raised.exception))
        self.assertNotIn('do not log',str(raised.exception))

    def test_connection_check_uses_no_personal_prompt(self):
        result=check_connections(self.config)
        self.assertEqual(result['karakeep'],'ok (GET uniquement)')
        self.assertEqual(result['llm'],'modèle annoncé')
        self.assertTrue(all(method=='GET' for method,_,_ in self.requests))

    def test_disabled_worker_has_no_network_effect(self):
        self.config.sync_enabled=False
        self.assertEqual(run_cycle(self.config),dict(synced=0,processed=0,failed=0))
        self.assertEqual(self.requests,[])

    def test_changed_asset_preserves_old_media_and_metadata(self):
        initialize(self.root)
        raw={'id':'one','createdAt':'2026-11-01T12:00:00Z','content':{'videoAssetId':'old-video'},'assets':[]}
        old=normalize_bookmark(raw)
        cerveau.write_json(self.root/'data/sources.json',[old])
        media=self.root/'data/media/one.mp4'
        media.parent.mkdir(parents=True);media.write_bytes(b'old-media')
        new=copy.deepcopy(raw);new['content']['videoAssetId']='new-video'
        with patch('worker.Karakeep.bookmarks',return_value=iter([new])):
            result=run_cycle(self.config)
        self.assertEqual(result,dict(synced=0,processed=0,failed=1))
        self.assertEqual(media.read_bytes(),b'old-media')
        self.assertEqual(cerveau.read_json(self.root/'data/sources.json'),[old])
        self.assertEqual(cerveau.read_json(self.root/'data/service-status.json')['blocked_media_updates'],1)


if __name__=='__main__':
    unittest.main()
