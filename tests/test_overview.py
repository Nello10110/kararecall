import base64
from datetime import datetime, timezone
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import kararecall
from controls import request_action, process_actions, cancel_action, pause_automation, library_paused
from fixtures import corpus
from integrations import normalize_bookmark
from overview import overview, diagnostic, public_configuration
from settings import Settings
from web_server import Corpus, make_handler


class OverviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);corpus(self.root)

    def tearDown(self):self.temp.cleanup()

    def data(self):return kararecall.read_json(self.root/'data/catalog.json')

    def test_real_counts_attention_and_seven_day_chart_do_not_invent_activity(self):
        data=self.data()
        for source in data['sources']:source['created_at']=datetime.now(timezone.utc).isoformat()
        data['sources'][0]['stages']={'asr':'failed','vision':'paused'}
        report=overview(self.root,data,self.root)
        self.assertEqual(report['summary']['sources'],2)
        self.assertEqual(report['summary']['attention'],1)
        self.assertEqual(report['summary']['failed'],1)
        self.assertEqual(report['summary']['paused'],1)
        self.assertEqual(len(report['additions']),7)
        self.assertEqual(sum(row['count'] for row in report['additions']),2)
        self.assertEqual(report['source_types']['video'],2)
        self.assertEqual(report['storage']['backup_status'],'not_observed')
        self.assertIn('worker_unknown',[row['id'] for row in report['alerts']])

    def test_diagnostic_has_no_favorites_secrets_models_urls_or_free_form_errors(self):
        secret='fake-private-credential-for-test'
        config=Settings(root=self.root,karakeep_url='https://private-host.invalid/api',karakeep_key=secret,
                        llm_enabled=True,llm_url='https://api.deepseek.com',llm_key=secret,llm_model='private-model-name')
        public=public_configuration(config)
        self.assertNotIn(secret,json.dumps(public));self.assertNotIn('private-host',json.dumps(public))
        self.assertEqual(public['llm']['provider'],'DeepSeek')
        self.assertTrue(public['llm']['configured'])
        kararecall.write_json(self.root/'data/service-status.json',{'state':'error','message':secret,'configuration':public})
        report=overview(self.root,self.data(),self.root)
        exported=json.dumps(diagnostic(report))
        for value in [secret,'private-model-name','https://','demo-model','Auteur de démonstration']:
            self.assertNotIn(value,exported)
        self.assertEqual(diagnostic(report)['summary']['sources'],2)

    def test_worker_failures_and_disabled_synthesis_are_visible_without_false_healthy_state(self):
        kararecall.write_json(self.root/'data/service-status.json',{'state':'error','llm_enabled':False,
            'heartbeat_at':datetime.now(timezone.utc).isoformat(),'application_version':'0.0.1','message':'Connexion inaccessible.'})
        report=overview(self.root,self.data(),self.root)
        ids={row['id'] for row in report['alerts']}
        self.assertIn('worker_error',ids);self.assertIn('llm_disabled',ids);self.assertIn('version_mismatch',ids)
        self.assertNotIn('worker_unknown',ids)

    def test_cancellation_preserves_in_flight_results_and_prevents_next_items(self):
        config=Settings(root=self.root)
        job=request_action(self.root,'llm')
        def run(*args):cancel_action(self.root,job['id'])
        with patch('worker.run_local_llm',side_effect=run) as model:
            self.assertTrue(process_actions(config))
            self.assertFalse(process_actions(config))
            self.assertEqual(model.call_count,1)
        from controls import action_status
        self.assertEqual(action_status(self.root)['jobs'][-1]['state'],'cancelled')

    def test_pause_is_durable_and_cannot_resume_during_confirmed_clear(self):
        pause_automation(self.root,True);self.assertTrue(library_paused(self.root))
        pause_automation(self.root,False);self.assertFalse(library_paused(self.root))
        with self.assertRaises(ValueError):pause_automation(self.root,'false')
        job=request_action(self.root,'clear',confirmation='VIDER')
        with self.assertRaises(ValueError):pause_automation(self.root,False)
        with self.assertRaises(ValueError):cancel_action(self.root,job['id'])

    def test_manual_import_does_not_resume_an_explicit_automation_pause(self):
        from controls import request_history, process_history, history_status
        pause_automation(self.root,True)
        request_history(self.root)
        self.assertTrue(library_paused(self.root))
        with patch('worker.run_cycle',return_value={'synced':2,'processed':0,'failed':0}) as collect:
            self.assertTrue(process_history(Settings(root=self.root),collect))
            self.assertTrue(collect.call_args.kwargs['catalog_only'])
        self.assertTrue(library_paused(self.root))
        self.assertIn('reste suspendue',history_status(self.root)['message'])

    def test_connection_check_records_read_only_results_without_inference(self):
        job=request_action(self.root,'check')
        self.assertEqual(job['total'],1)
        with patch('worker.check_connections',return_value={'karakeep':'ok (GET uniquement)','llm':'modèle annoncé'}) as check,patch('worker.chat') as inference:
            self.assertTrue(process_actions(Settings(root=self.root)))
            check.assert_called_once();inference.assert_not_called()
        result=kararecall.read_json(self.root/'data/connection-check.json')
        self.assertEqual(result['state'],'completed');self.assertIn('checked_at',result)
        self.assertEqual(result['results']['llm'],'modèle annoncé')

    def test_worker_metadata_is_public_and_separate_from_credentials(self):
        from worker import status
        config=Settings(root=self.root,llm_url='https://api.deepseek.com',llm_model='test-model',llm_key='fake-secret',llm_enabled=True)
        status(config,state='idle')
        worker=kararecall.read_json(self.root/'data/service-status.json')
        self.assertNotIn('fake-secret',json.dumps(worker))
        self.assertTrue(worker['configuration']['llm']['configured'])
        self.assertEqual(worker['configuration']['batch_size'],3)


class OverviewHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);corpus(self.root)
        raw={'id':'fixture-note','createdAt':'2026-11-08T12:00:00Z','content':{'type':'text','text':'Une note de démonstration sur le rangement.'}}
        note=normalize_bookmark(raw);kararecall.write_json(self.root/note['raw_file'],raw)
        sources=kararecall.read_json(self.root/'data/sources.json');sources.append(note)
        sources[0]['stages']={'vision':'paused'}
        kararecall.write_json(self.root/'data/sources.json',sources);kararecall.build(self.root)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Corpus(self.root),'test','local-password'))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.auth='Basic '+base64.b64encode(b'test:local-password').decode()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5);self.temp.cleanup()

    def send(self,path,payload=None,**headers):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        conn.request('GET' if payload is None else 'POST',path,None if payload is None else json.dumps(payload),{'Authorization':self.auth,**headers})
        response=conn.getresponse();body=response.read();status=response.status;header=dict(response.getheaders());conn.close()
        try:body=json.loads(body)
        except ValueError:body=body.decode()
        return status,body,header

    def test_new_read_routes_and_assets_require_auth_and_catalog_export_is_explicit(self):
        for path in ['/api/overview','/api/administration','/api/administration/diagnostic','/download/catalog.json','/glass.css','/workspace.js']:
            self.assertEqual(self.send(path,Authorization='bad')[0],401)
            self.assertEqual(self.send(path)[0],200)
        status,body,headers=self.send('/api/administration/diagnostic')
        self.assertEqual(body['application'],'KaraRecall')
        self.assertIn('attachment',headers['Content-Disposition'])
        self.assertNotIn('sources',body)
        self.assertEqual(len(self.send('/download/catalog.json')[1]['sources']),3)

    def test_filters_apply_before_pagination_and_unknown_values_are_rejected(self):
        notes=self.send('/api/sources?type=note&limit=1')[1]
        self.assertEqual(notes['total'],1);self.assertEqual(notes['sources'][0]['id'],'fixture-note')
        self.assertEqual(self.send('/api/sources?stage=paused')[1]['total'],1)
        self.assertEqual(self.send('/api/sources?stage=pending')[1]['total'],3)
        self.assertEqual(self.send('/api/sources?type=invalid')[0],400)
        self.assertEqual(self.send('/api/sources?sort=invalid')[0],400)
        recent=self.send('/api/sources?limit=1')[1]['sources'][0]['id']
        oldest=self.send('/api/sources?limit=1&sort=oldest')[1]['sources'][0]['id']
        self.assertNotEqual(recent,oldest)

    def test_search_keeps_original_proof_but_marks_missing_french_translation(self):
        raw={'id':'english-demo','createdAt':'2026-11-08T12:00:00Z','content':{'type':'link','url':'https://example.invalid/widgets','title':'Demonstration widgets','htmlContent':'<p>These widgets organize documents.</p>'}}
        source=normalize_bookmark(raw);kararecall.write_json(self.root/source['raw_file'],raw)
        rows=kararecall.read_json(self.root/'data/sources.json');rows.append(source)
        kararecall.write_json(self.root/'data/sources.json',rows);kararecall.build(self.root)
        result=next(row for row in self.send('/api/search?q=widgets')[1]['results'] if row['id']=='english-demo')
        proof=result['snippets'][0]
        self.assertIn('widgets',proof['text'].lower())
        self.assertEqual(proof['display_state'],'translation_pending')
        self.assertEqual(proof['display_text'],'')

    def test_native_jauges_do_not_require_relaxing_inline_style_protection(self):
        status,script,headers=self.send('/workspace.js')
        self.assertEqual(status,200)
        self.assertNotIn('unsafe-inline',headers['Content-Security-Policy'])
        self.assertNotIn('style=',script)
        self.assertIn('<progress',script)

    def test_management_requires_csrf_origin_and_strict_payload(self):
        self.assertEqual(self.send('/api/automation',{'paused':True})[0],403)
        token=self.send('/api/control')[1]['csrf_token'];headers={'X-KaraRecall-CSRF':token,'Content-Type':'application/json'}
        self.assertEqual(self.send('/api/automation',{'paused':True},Origin='https://attacker.invalid',**headers)[0],403)
        self.assertEqual(self.send('/api/automation',{'paused':True,'command':'execute'},**headers)[0],400)
        self.assertEqual(self.send('/api/automation',{'paused':True},**headers)[0],200)
        self.assertTrue(self.send('/api/overview')[1]['actions']['library_paused'])
        status,job,_=self.send('/api/actions',{'kind':'llm'},**headers);self.assertEqual(status,202)
        path='/api/actions/'+job['id']+'/cancel'
        self.assertEqual(self.send(path,{})[0],403)
        self.assertEqual(self.send(path,{},**headers)[1]['state'],'cancelled')
