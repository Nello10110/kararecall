import base64
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

import kararecall
from editorial import EditConflict, edit_tool, revision
from fixtures import corpus
from publication import active_root
from web_server import Corpus, make_handler


def change(entity, **extra):
    return {'revision':revision(entity),'name':entity['name'],'description':entity['description'],
            'aliases':entity['aliases'],'details':{key:[row['text'] for row in entity.get('details',{}).get(key,[])]
                for key,_ in kararecall.DETAIL_SECTIONS},
            'links':[{'label':link['label'],'url':link['url']} for link in entity['links']],
            'reviewed':True,**extra}


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.root=Path(self.temporary.name)
        self.tools=corpus(self.root)['entities']

    def tearDown(self):
        self.temporary.cleanup()

    def test_edit_preserves_evidence_and_refuses_stale_revision(self):
        original=self.tools[0]
        patch=change(original,name='Outil relu',links=[{'label':'Documentation','url':'https://example.com/new'}])
        edit_tool(self.root,original['id'],patch)
        selected=active_root(self.root)
        edited=kararecall.read_json(selected/'data/entities.json')[0]
        self.assertEqual(edited['name'],'Outil relu')
        self.assertEqual(edited['claims'],original['claims'])
        self.assertEqual(edited['curation'],'user-reviewed')
        link=edited['links'][0]
        self.assertEqual(link['status'],'user_link_unchecked')
        self.assertNotIn('evidence',link)
        event=kararecall.read_json(selected/edited['editorial_history'][0])
        self.assertEqual(event['before'],original)
        with self.assertRaises(EditConflict):edit_tool(self.root,original['id'],patch)
        self.assertEqual(active_root(self.root),selected)
        with self.assertRaises(ValueError):
            edit_tool(self.root,edited['id'],change(edited,links=[{'label':'Interdit','url':'javascript:alert(1)'}]))

    def test_post_requires_auth_and_csrf_and_merge_preserves_old_routes(self):
        primary,other=self.tools
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Corpus(self.root),'test','test-password'))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        authorization='Basic '+base64.b64encode(b'test:test-password').decode()
        def request(method,path,body=None,headers=None):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            try:
                connection.request(method,path,body,headers or {})
                response=connection.getresponse()
                return response.status,response.read()
            finally:
                connection.close()
        try:
            path='/api/tools/'+primary['id']+'/edit'
            body=json.dumps(change(primary,merge_id=other['id'],merge_revision=revision(other)))
            self.assertEqual(request('POST',path,body)[0],401)
            headers={'Authorization':authorization,'Content-Type':'application/json'}
            self.assertEqual(request('POST',path,body,headers)[0],403)
            control=json.loads(request('GET','/api/control',headers=headers)[1])
            headers['X-KaraRecall-CSRF']=control['csrf_token']
            self.assertEqual(request('POST',path,body,headers)[0],200)
            status,payload=request('GET','/api/tools/'+other['id'],headers=headers)
            self.assertEqual(status,200)
            entity=json.loads(payload)['entity']
            self.assertEqual(entity['id'],primary['id'])
            self.assertEqual(set(entity['source_ids']),set(primary['source_ids']+other['source_ids']))
            self.assertEqual(len(entity['claims']),2)
            self.assertEqual(request('GET','/download/tool/'+other['id']+'.md',headers=headers)[0],200)
            status,payload=request('GET','/api/editorial/'+primary['id'],headers=headers)
            self.assertEqual(status,200)
            self.assertEqual(json.loads(payload)['merged'],other)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)
