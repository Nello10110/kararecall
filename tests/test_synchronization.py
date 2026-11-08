from datetime import datetime, timedelta, timezone
import base64
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from kararecall import core, synchronization
from kararecall.controls import action_status, request_action, process_actions, pause_automation, library_paused
from kararecall.integrations import normalize_bookmark, ServiceError
from kararecall.overview import overview, diagnostic
from kararecall.publication import active_root, generation
from kararecall.settings import Settings, initialize
from kararecall.web_server import Corpus, make_handler
from kararecall.worker import run_cycle


def raw(sid,**content):
    return {'id':sid,'createdAt':'2026-11-01T00:00:00Z','title':'Un favori '+sid,'tags':[],
            'content':dict(type='link',url='https://example.org/'+sid,text='Un article sur le jardin.',**content),'assets':[]}


class SynchronizationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        initialize(self.root)
        self.settings=Settings(root=self.root,karakeep_url='https://example.invalid',karakeep_key='fixture-secret',sync_enabled=False)
    def tearDown(self):self.temp.cleanup()
    def view(self):
        root=active_root(self.root);data=core.read_json(root/'data/catalog.json')
        return overview(self.root,data,root)
    def import_rows(self,rows):
        with patch('kararecall.worker.Karakeep.bookmarks',return_value=iter(rows)):
            return run_cycle(self.settings,catalog_only=True)

    def test_unknown_is_not_zero_and_empty_remote_is_observed_zero(self):
        state=self.view()['synchronization']
        self.assertIsNone(state['last_success']);self.assertEqual(state['local_total'],0)
        with patch('kararecall.synchronization.Karakeep.bookmarks',return_value=iter([])):
            synchronization.check(self.settings)
        state=self.view()['synchronization'];self.assertEqual(state['last_success']['karakeep_total'],0)
        self.assertTrue(state['comparison_current'])

    def test_same_totals_can_have_missing_and_local_only_ids(self):
        self.import_rows([raw('one'),raw('two')])
        with patch('kararecall.synchronization.Karakeep.bookmarks',return_value=iter([raw('two'),raw('three'),raw('three')])):
            result=synchronization.check(self.settings)
        self.assertEqual((result['karakeep_total'],result['local_total']),(2,2))
        self.assertEqual((result['missing'],result['local_only'],result['present']),(1,1,1))
        self.assertEqual(len(core.read_json(active_root(self.root)/'data/sources.json')),2)

    def test_count_only_check_has_no_ai_download_publication_or_worker_validation(self):
        self.settings.llm_enabled=True  # Deliberately lacks LLM endpoint/model.
        pause_automation(self.root,True)
        before=(self.root/'data/catalog.json').read_bytes()
        job=request_action(self.root,'sync_check')
        self.assertEqual(request_action(self.root,'sync_check')['id'],job['id'])
        with patch('kararecall.synchronization.Karakeep.bookmarks',return_value=iter([raw('one')])),patch('kararecall.integrations.chat') as model,patch('kararecall.integrations.Karakeep.download') as download,patch('kararecall.settings.Settings.validate_worker') as validate:
            self.assertTrue(process_actions(self.settings));model.assert_not_called();download.assert_not_called();validate.assert_not_called()
        self.assertEqual((self.root/'data/catalog.json').read_bytes(),before)
        self.assertFalse((self.root/'data/current.json').exists())
        self.assertEqual(action_status(self.root)['jobs'][-1]['state'],'completed')
        self.assertTrue(library_paused(self.root))
        self.assertEqual(self.view()['synchronization']['last_success']['missing'],1)
        with self.assertRaises(ValueError):request_action(self.root,'sync_check',source_id='one')

    def test_complete_history_updates_counters_even_when_periodic_sync_disabled(self):
        self.settings.url_filter='excluded.example';self.settings.tag_filter='excluded'
        self.import_rows([raw('one'),raw('two')])
        state=self.view()['synchronization'];snapshot=state['last_success']
        self.assertEqual((snapshot['karakeep_total'],snapshot['local_total'],snapshot['missing']),(2,2,0))
        self.assertEqual(snapshot['excluded'],2);self.assertTrue(snapshot['filtered']);self.assertTrue(state['last_import_at'])
        self.assertEqual(self.view()['summary']['summarized'],0)

    def test_periodic_filters_report_full_remote_count_and_exclusions(self):
        self.settings.sync_enabled=True;self.settings.download_media=False;self.settings.url_filter='/one'
        with patch('kararecall.worker.Karakeep.bookmarks',return_value=iter([raw('one'),raw('two')])):
            run_cycle(self.settings)
        result=self.view()['synchronization']['last_success']
        self.assertEqual((result['karakeep_total'],result['local_total'],result['missing'],result['excluded']),(2,1,1,1))
        self.assertEqual(result['missing_in_scope'],0)

    def test_partial_pagination_failure_preserves_last_complete_snapshot_and_redacts_error(self):
        self.import_rows([raw('one')]);before=self.view()['synchronization']['last_success']
        def broken():
            yield raw('two')
            raise ServiceError('Service unavailable fixture-secret')
        with patch('kararecall.synchronization.Karakeep.bookmarks',side_effect=broken):
            with self.assertRaises(ServiceError):synchronization.check(self.settings)
        result=self.view()['synchronization']
        self.assertEqual(result['last_success'],before);self.assertEqual(result['state'],'error')
        self.assertNotIn('fixture-secret',json.dumps(result))
        self.assertEqual(self.view()['summary']['sources'],1)
        # The ordinary import path must preserve the same invariant.
        with patch('kararecall.worker.Karakeep.bookmarks',side_effect=broken):
            with self.assertRaises(ServiceError):run_cycle(self.settings,catalog_only=True)
        self.assertEqual(self.view()['synchronization']['last_success'],before)

    def test_current_publication_and_stale_timestamp_are_distinguished(self):
        self.import_rows([raw('one')]);self.assertTrue(self.view()['synchronization']['comparison_current'])
        with generation(self.root) as (draft,publish):publish()
        self.assertFalse(self.view()['synchronization']['comparison_current'])
        path=self.root/'data/sync-status.json';value=core.read_json(path)
        value['last_success']['observed_at']=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        value.update(state='running',started_at=value['last_success']['observed_at'],updated_at=value['last_success']['observed_at'])
        core.write_json(path,value)
        state=self.view()['synchronization'];self.assertTrue(state['stale']);self.assertEqual(state['state'],'interrupted')

    def test_content_updates_ignore_expiring_urls_and_locally_hydrated_text(self):
        local=normalize_bookmark(raw('one'));remote=dict(local,raw_file='different-expiring-image-url.json')
        self.assertFalse(synchronization.content_changed(remote,local))
        local.update(page_text='HTML récupéré séparément',page_origin={'kind':'karakeep_html_asset'})
        remote['page_text']='';self.assertFalse(synchronization.content_changed(remote,local))
        remote['description']='Description modifiée';self.assertTrue(synchronization.content_changed(remote,local))
        self.import_rows([raw('one')])
        with patch('kararecall.synchronization.Karakeep.bookmarks',return_value=iter([raw('one',description='Modifiée')])):
            self.assertEqual(synchronization.check(self.settings)['updates'],1)

    def test_shareable_sync_projection_contains_no_favorites_ids_urls_or_free_form_error(self):
        self.import_rows([raw('private-source-name')])
        synchronization.failed(self.root,'private-free-form-error')
        report=diagnostic(self.view())
        text=json.dumps(report)
        for secret in ('private-source-name','fixture-secret','https://example.org','private-free-form-error','local_revision'):
            self.assertNotIn(secret,text)
        self.assertTrue(report['synchronization']['error'])

    def test_new_action_requires_authentication_and_csrf_on_empty_library(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Corpus(self.root),'user','fixture'))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(method,path,headers=None,body=None):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
            connection.request(method,path,body=body,headers=headers or {})
            response=connection.getresponse();data=response.read();connection.close()
            return response.status,data
        try:
            headers={'Authorization':'Basic '+base64.b64encode(b'user:fixture').decode(),'Content-Type':'application/json'}
            self.assertEqual(request('POST','/api/actions',body='{"kind":"sync_check"}')[0],401)
            self.assertEqual(request('POST','/api/actions',headers,'{"kind":"sync_check"}')[0],403)
            _,body=request('GET','/api/control',headers)
            headers['X-KaraRecall-CSRF']=json.loads(body)['csrf_token']
            self.assertEqual(request('POST','/api/actions',headers,'{"kind":"sync_check"}')[0],202)
        finally:server.shutdown();server.server_close();thread.join(5)
