import base64
import http.client
from http.server import ThreadingHTTPServer
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

import kararecall
from content_support import coverage, inventory
from integrations import normalize_bookmark, ServiceError
from publication import active_root
from settings import Settings
from web_server import Corpus, make_handler
from worker import run_cycle,has_content_evidence
from worker_documents import extract_document


def matrix():
    variants=[('article',{'type':'link','url':'https://example.org','htmlContent':'<p>Technique solaire.</p>'}),
        ('note',{'type':'text','text':'Organiser mon jardin.'}),
        ('pdf',{'type':'asset','assetType':'pdf','assetId':'pdf-original'}),
        ('linkedpdf',{'type':'link','url':'https://example.org/guide','pdfAssetId':'linked-pdf'}),
        ('image',{'type':'asset','assetType':'image','assetId':'image-original'}),
        ('youtube',{'type':'link','url':'https://www.youtube.com/watch?v=fixture'}),
        ('instagram',{'type':'link','url':'https://www.instagram.com/reel/fixture/'}),
        ('video',{'type':'link','url':'https://example.org/movie','videoAssetId':'video-original'}),
        ('audio',{'type':'asset','assetType':'audio','assetId':'audio-original'}),
        ('office',{'type':'asset','assetType':'docx','assetId':'office-original'}),
        ('unknown',{'type':'unknown'}),
        ('pending',{'type':'link','url':'https://example.org/wait','crawlStatus':'pending'}),
        ('failed',{'type':'link','url':'https://example.org/failed','crawlStatus':'failure'})]
    return [{'id':'matrix-'+name,'title':'Repère '+name,'createdAt':'2026-11-01T12:00:00Z','content':content,
             'assets':[],'tags':[]} for name,content in variants]


class ContentMatrixTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.settings=Settings(root=self.root,karakeep_url='https://example.invalid',karakeep_key='fixture',sync_enabled=True,download_media=False)
    def tearDown(self):self.temp.cleanup()
    def data(self):return kararecall.read_json(active_root(self.root)/'data/catalog.json')

    def test_all_types_are_imported_once_searchable_exportable_with_honest_coverage(self):
        with patch('worker.Karakeep.bookmarks',side_effect=lambda:iter(matrix())),patch('worker.Karakeep.download') as dl,patch('worker.synthesize') as model:
            run_cycle(self.settings,catalog_only=True)
            before=active_root(self.root);run_cycle(self.settings,catalog_only=True)
            self.assertEqual(active_root(self.root),before);dl.assert_not_called();model.assert_not_called()
        sources={s['id']:s for s in self.data()['sources']}
        self.assertEqual(len(sources),13)
        for sid,source in sources.items():
            self.assertTrue((before/'vault/sources'/(sid+'.md')).is_file())
            self.assertIn(sid,[r['id'] for r in kararecall.search(source['title'],self.data(),100)])
        self.assertEqual(sources['matrix-linkedpdf']['document_asset_id'],'linked-pdf')
        self.assertEqual(coverage(sources['matrix-article'])['state'],'content')
        for name in ('audio','office','unknown'):self.assertEqual(coverage(sources['matrix-'+name])['state'],'unsupported')
        for name in ('youtube','instagram'):
            info=coverage(sources['matrix-'+name]);self.assertEqual(info['kind'],'remote_video');self.assertEqual(info['state'],'metadata')
        report=inventory(list(sources.values()))
        self.assertEqual(sum(report['states'].values()),13)
        for value in ('matrix-','example.org','Repère'):self.assertNotIn(value,json.dumps(report))

    def test_video_and_truncated_documents_never_claim_complete_coverage_from_a_summary_alone(self):
        self.assertTrue(has_content_evidence([{'kind':'pdf-page','text':'Texte natif'}]))
        self.assertFalse(has_content_evidence([{'kind':'caption','text':'Titre seul'}]))
        self.assertFalse(has_content_evidence([{'kind':'pdf-page','text':'Ancien texte','archived':True}]))
        source={'bookmark_type':'link','assets':[{'id':'video','type':'video'}],'reading':{'text':'Résumé'},'processing':{}}
        self.assertEqual(coverage(source)['state'],'partial')
        source['processing'].update(audio_transcribed=True,ocr_sampled=True)
        self.assertEqual(coverage(source)['state'],'analyzed')
        self.assertIn('échantillonnage',' '.join(coverage(source)['limitations']))
        source['stages']={'vision':'failed'};self.assertEqual(coverage(source)['state'],'partial')
        document={'bookmark_type':'asset','asset_type':'pdf','document_asset_id':'pdf','page_text':'Texte',
                  'reading':{'text':'Résumé'},'processing':{'attachment':{'truncated':True}}}
        self.assertEqual(coverage(document)['state'],'partial')
        document['processing']={};document['assets']=[{'id':'unread','type':'fullPageArchive'}]
        self.assertEqual(coverage(document)['state'],'partial')

    def test_unsupported_file_never_spends_an_inference_call(self):
        self.settings.llm_enabled=True;self.settings.llm_model='test';self.settings.llm_url='https://example.invalid'
        with patch('worker.Karakeep.bookmarks',return_value=iter([matrix()[8]])),patch('worker.synthesize') as model:
            run_cycle(self.settings);model.assert_not_called()
        self.assertEqual(self.data()['sources'][0]['stages']['llm'],'unsupported')

    def test_coverage_filters_are_applied_before_pagination_and_routes_are_protected(self):
        with patch('worker.Karakeep.bookmarks',return_value=iter(matrix())):run_cycle(self.settings,catalog_only=True)
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Corpus(self.root),'test','fixture'))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def get(path,auth=True):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
            headers={'Authorization':'Basic '+base64.b64encode(b'test:fixture').decode()} if auth else {}
            connection.request('GET',path,headers=headers);response=connection.getresponse();body=response.read();connection.close()
            return response.status,json.loads(body) if response.status!=401 else None
        try:
            self.assertEqual(get('/api/administration',False)[0],401)
            code,page=get('/api/sources?support=unsupported&limit=1&offset=1')
            self.assertEqual(code,200);self.assertEqual(page['total'],3);self.assertEqual(len(page['sources']),1)
            self.assertEqual(page['sources'][0]['coverage_state']['state'],'unsupported')
            self.assertEqual(get('/api/sources?support=invalid')[0],400)
            code,report=get('/api/administration/diagnostic');self.assertEqual(code,200)
            self.assertEqual(report['content_coverage']['total'],13)
            self.assertNotIn('matrix-',json.dumps(report))
        finally:server.shutdown();server.server_close();thread.join(5)


@unittest.skipUnless(importlib.util.find_spec('PIL'),'Pillow supplied in worker')
class ImageMatrixTests(unittest.TestCase):
    def test_image_formats_animation_limits_and_cache(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);settings=Settings(root=root,image_ocr_enabled=True,vision_url='https://example.invalid',vision_model='test')
            source={'id':'image','document_asset_id':'asset','asset_type':'image'}
            for fmt in ('JPEG','PNG','WEBP','GIF'):
                original=root/(fmt+'.bin');Image.new('RGB',(24,24),'white').save(original,fmt)
                output=root/fmt
                with patch('worker_documents.recognize_image',return_value='Repère hydrique') as model:
                    self.assertEqual(extract_document(source,original,output,settings),'complete')
                    self.assertEqual(extract_document(source,original,output,settings),'complete');self.assertEqual(model.call_count,1)
                self.assertFalse(kararecall.read_json(output/'document.json')['truncated'])
            original=root/'animated.gif'
            Image.new('RGB',(24,24),'white').save(original,'GIF',save_all=True,append_images=[Image.new('RGB',(24,24),'black')],duration=100)
            with patch('worker_documents.recognize_image',return_value='Première image') as model:
                extract_document(source,original,root/'animated',settings);self.assertEqual(model.call_count,1)
            artifact=kararecall.read_json(root/'animated/document.json')
            self.assertTrue(artifact['truncated']);self.assertEqual(artifact['frames_scanned'],1);self.assertEqual(artifact['frames_total'],2)
            original=root/'unsupported.bmp';Image.new('RGB',(24,24)).save(original,'BMP')
            with patch('worker_documents.recognize_image') as model:
                with self.assertRaises(ServiceError):extract_document(source,original,root/'unsupported',settings)
                model.assert_not_called()


@unittest.skipUnless(shutil.which('pdftotext'),'Poppler supplied in worker')
class LinkedPDFTests(unittest.TestCase):
    def test_pdf_link_is_extracted_even_with_inline_page_text_and_errors_stay_visible(self):
        from test_documents import pdf_bytes
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);settings=Settings(root=root,karakeep_url='https://example.invalid',karakeep_key='test',sync_enabled=True)
            settings.llm_enabled=True;settings.llm_url='https://example.invalid';settings.llm_model='test'
            raw=matrix()[3];raw['content'].update(htmlContent='<p>Une présentation du guide.</p>',crawlStatus='success')
            def download(_,destination,**kwargs):
                destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(pdf_bytes(['Un capteur de pression.']))
            def answer(*args,**kwargs):
                rows=json.loads(args[3][-1]['content'])['evidence'];proof=next(row for row in rows if row['kind']=='pdf-page')
                return json.dumps({'tools':[],'reading':{'summary':'Un capteur de pression.','source_language':'fr','evidence_ids':[proof['id']]}})
            with patch('worker.Karakeep.bookmarks',side_effect=lambda:iter([raw])),patch('worker.Karakeep.download',side_effect=download),patch('worker.chat',side_effect=answer):
                self.assertEqual(run_cycle(settings)['processed'],1)
                source=kararecall.read_json(active_root(root)/'data/catalog.json')['sources'][0]
                self.assertTrue(any(row['kind']=='pdf-page' for row in source['evidence']))
                self.assertTrue(any(row['kind']=='page' for row in source['evidence']))
                self.assertEqual(source['processing']['attachment']['status'],'complete')
                self.assertEqual(source['stages']['llm'],'complete')
                self.assertIn('#pdf-page-',source['reading']['evidence'][0])
                raw['content']['pdfAssetId']='broken'
                with patch('worker.Karakeep.download',side_effect=lambda _,p,**kw:(p.parent.mkdir(parents=True,exist_ok=True),p.write_bytes(b'not a PDF'))):
                    self.assertEqual(run_cycle(settings)['failed'],1)
                current=kararecall.read_json(active_root(root)/'data/catalog.json')['sources'][0]
                self.assertEqual(current['stages']['document'],'failed')
                self.assertTrue(any(row.get('archived') and row['kind']=='pdf-page' for row in current['evidence']))
