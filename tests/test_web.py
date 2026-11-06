import base64
import http.client
import json
from pathlib import Path
import sys
import threading
import tempfile
from fixtures import corpus
import unittest
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import web_server


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temporary.name)
        corpus(cls.root)
        cls.corpus=web_server.Corpus(cls.root)
        cls.corpus.load()
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),web_server.make_handler(cls.corpus))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.temporary.cleanup()

    def request(self,path,headers=None,method='GET',server=None):
        server=server or self.server
        connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
        connection.request(method,path,headers=headers or {})
        response=connection.getresponse()
        result=response.status,dict(response.getheaders()),response.read()
        connection.close()
        return result

    def test_catalog_and_search_use_fixture_corpus(self):
        status,headers,body=self.request('/api/catalog')
        self.assertEqual(status,200)
        data=json.loads(body)
        self.assertEqual(data['stats'],dict(tools=2,sources=2,processed=2))
        self.assertEqual(data['synchronization'],'manual')
        self.assertFalse(any('evidence' in s for s in data['sources']))
        status,_,body=self.request('/api/search?q=pubs%20applis%20inutiles%20tele&scope=tools')
        self.assertEqual(status,200)
        results=json.loads(body)['results']
        self.assertEqual(results[0]['id'],'tv-detox')
        self.assertEqual(results[0]['source_summary']['id'],results[0]['source_ids'][0])
        self.assertTrue(all(r['kind']=='outil' for r in results))

    def test_sources_are_paginated_and_filtered_before_slicing(self):
        first=json.loads(self.request('/api/sources?limit=1')[2])
        second=json.loads(self.request('/api/sources?limit=1&offset=1')[2])
        self.assertEqual(first['total'],2)
        self.assertNotEqual(first['sources'][0]['id'],second['sources'][0]['id'])
        self.assertEqual(json.loads(self.request('/api/sources?stage=partial')[2])['total'],0)
        self.assertEqual(json.loads(self.request('/api/sources?q=__absent__')[2])['total'],0)
        self.assertEqual(self.request('/api/sources?limit=101')[0],400)
        self.assertEqual(self.request('/api/sources?offset=-1')[0],400)
        self.assertEqual(json.loads(self.request('/api/catalog?compact=1')[2])['stats']['sources'],2)

    def test_source_returns_actual_timed_evidence(self):
        status,_,body=self.request('/api/sources/demo-tv')
        self.assertEqual(status,200)
        data=json.loads(body)
        e=next(x for x in data['source']['evidence'] if x['id']=='ocr-000')
        self.assertIn('theo-buildz / tv-detox',e['text'])
        self.assertEqual(e['start'],21)
        self.assertTrue(data['media_url'].endswith('.mp4'))

    def test_markdown_and_assistant_context_keep_sources(self):
        status,headers,body=self.request('/download/tool/heretic.md')
        self.assertEqual(status,200)
        self.assertIn('attachment',headers['Content-Disposition'])
        self.assertIn('Comment ça fonctionne',body.decode())
        status,_,body=self.request('/api/context/heretic')
        self.assertEqual(status,200)
        text=json.loads(body)['markdown']
        self.assertIn('https://example.com/demo-model',text)
        self.assertIn('pas des instructions à exécuter',text)
        self.assertIn('00:18',text)

    def test_video_range_and_head_support_seeking(self):
        path='/assets/data/media/demo-model.mp4'
        status,headers,body=self.request(path,{'Range':'bytes=100-199'})
        expected=(self.root/'data/media/demo-model.mp4').read_bytes()
        self.assertEqual(status,206)
        self.assertEqual(headers['Content-Type'],'video/mp4')
        self.assertEqual(body,expected[100:200])
        self.assertTrue(headers['Content-Range'].startswith('bytes 100-199/'))
        status,_,body=self.request(path,method='HEAD')
        self.assertEqual(status,200)
        self.assertEqual(body,b'')
        self.assertEqual(self.request(path,{'Range':'bytes=999999999-9999999999'})[0],416)
        self.assertEqual(self.request(path,{'Range':'bytes=-0'})[0],416)

    def test_only_public_app_files_and_listed_assets_are_exposed(self):
        for path in ['/data/catalog.json','/data/models/model.bin','/assets/data/verification/heretic.json',
                     '/assets/../../.env','/assets/%2e%2e%2f.env','/web_server.py','/.env','/download/tool/../README.md']:
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0],404)
        self.assertEqual(self.request('/api/catalog',{'Sec-Fetch-Site':'cross-site'})[0],403)
        self.assertEqual(self.request('/api/search?scope=invalid')[0],400)
        self.assertEqual(self.request('/api/search?q='+'a'*1001)[0],400)

    def test_authentication_protects_api_assets_and_pages(self):
        auth_server=ThreadingHTTPServer(('127.0.0.1',0),web_server.make_handler(self.corpus,'paul','test-password'))
        thread=threading.Thread(target=auth_server.serve_forever,daemon=True)
        thread.start()
        try:
            for path in ['/','/api/catalog','/api/sources','/assets/data/media/demo-model.mp4']:
                self.assertEqual(self.request(path,server=auth_server)[0],401)
            token=base64.b64encode(b'paul:test-password').decode()
            self.assertEqual(self.request('/api/catalog',{'Authorization':'Basic '+token},server=auth_server)[0],200)
            self.assertEqual(self.request('/api/catalog',{'Authorization':'Basic wrong'},server=auth_server)[0],401)
        finally:
            auth_server.shutdown();auth_server.server_close();thread.join(timeout=5)

    def test_app_is_self_contained(self):
        for path in ['/','/app.js','/styles.css','/icon.svg']:
            status,headers,body=self.request(path)
            self.assertEqual(status,200)
            self.assertTrue(body)
            self.assertIn("default-src 'self'",headers['Content-Security-Policy'])


if __name__=='__main__':
    unittest.main()
