import base64
import http.client
from http.server import ThreadingHTTPServer
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

import kararecall
from integrations import Karakeep, ServiceError, normalize_bookmark
from publication import active_root, generation
from settings import Settings
from source_enrichment import acquire_page, make_preview, preview_target, save_preview, thumbnail_bytes
from web_server import Corpus, make_handler, source_summary
from worker import run_cycle, run_local_llm


def bookmark(**content):
    return {'id':'site-fixture','createdAt':'2026-11-01T12:00:00Z','assets':[],
            'content':dict(type='link',url='https://example.org/article',title='Un article de test',**content)}


class SourceEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.config=Settings(root=self.root,karakeep_url='https://example.invalid',karakeep_key='test-only',
                             sync_enabled=True,download_media=False)
    def tearDown(self):self.temp.cleanup()
    def source(self):return kararecall.read_json(active_root(self.root)/'data/catalog.json')['sources'][0]

    def test_separate_html_is_acquired_cited_searchable_and_not_repeated(self):
        raw=bookmark(contentAssetId='html-one',imageAssetId='banner-one',screenshotAssetId='screen-one')
        self.config.llm_enabled=True;self.config.llm_url='https://example.invalid';self.config.llm_model='test'
        def download(asset,path,**kwargs):
            self.assertEqual(asset,'html-one');self.assertEqual(kwargs['max_mb'],8)
            path.write_bytes(b'<article><p>Une batterie thermique pour le jardin.</p><script>NE PAS EXECUTER</script></article>')
        def response(*args,**kwargs):
            payload=json.loads(args[3][-1]['content']);row=next(r for r in payload['evidence'] if r['kind']=='page')
            return json.dumps({'tools':[],'reading':{'summary':'Stocker de la chaleur au jardin.',
                'source_language':'fr','evidence_ids':[row['id']],'keywords':['thermique']}})
        with patch('worker.Karakeep.bookmarks',side_effect=lambda:iter([raw])),patch('worker.Karakeep.download',side_effect=download) as dl,patch('worker.chat',side_effect=response) as chat:
            # History still promises no download or inference.
            run_cycle(self.config,catalog_only=True);dl.assert_not_called();chat.assert_not_called()
            self.assertEqual(self.source()['content_status'],'metadata_only')
            self.assertEqual(run_cycle(self.config)['processed'],1)
            first=active_root(self.root);source=self.source()
            self.assertEqual(source['stages']['page'],'complete');self.assertEqual(source['stages']['llm'],'complete')
            self.assertNotIn('NE PAS EXECUTER',source['page_text'])
            page=next(e for e in source['evidence'] if e['kind']=='page')
            self.assertEqual(page['page_origin']['sha256'],source['page_origin']['sha256'])
            self.assertEqual(source['reading']['evidence'],['site-fixture#'+page['id']])
            self.assertTrue((first/source['page_origin']['file']).is_file())
            self.assertEqual(source['preview_asset_ids'],['banner-one','screen-one'])
            self.assertEqual(run_cycle(self.config)['processed'],0)
            self.assertEqual(active_root(self.root),first);self.assertEqual(dl.call_count,1);self.assertEqual(chat.call_count,1)
            # Import cannot erase the separately retrieved article.
            run_cycle(self.config,catalog_only=True);self.assertEqual(self.source()['page_text'],source['page_text'])
            self.assertEqual(active_root(self.root),first)
        data=kararecall.read_json(first/'data/catalog.json')
        self.assertEqual(kararecall.search('thermique',data)[0]['id'],'site-fixture')

    def test_failed_page_read_is_visible_retryable_and_never_summarized_as_full_article(self):
        raw=bookmark(contentAssetId='html-one')
        self.config.llm_enabled=True;self.config.llm_url='https://example.invalid';self.config.llm_model='test'
        with patch('worker.Karakeep.bookmarks',side_effect=lambda:iter([raw])),patch('worker.Karakeep.download',side_effect=ServiceError('Lecture indisponible')),patch('worker.synthesize') as llm:
            self.assertEqual(run_cycle(self.config)['failed'],1)
            source=self.source();self.assertEqual(source['stages']['page'],'failed')
            self.assertEqual(source['stages']['llm'],'waiting');self.assertNotIn('reading',source);llm.assert_not_called()
        with patch('worker.Karakeep.bookmarks',return_value=iter([raw])),patch('worker.Karakeep.download',side_effect=lambda _,p,**kw:p.write_bytes(b'<p>Contenu maintenant disponible.</p>')),patch('worker.synthesize',return_value=[]):
            self.assertEqual(run_cycle(self.config,force_id='site-fixture')['processed'],1)
            self.assertEqual(self.source()['stages']['page'],'complete')

    def test_readable_content_endpoint_is_used_only_for_successful_crawl_without_inline_body(self):
        raw=bookmark(crawlStatus='success')
        with patch('worker.Karakeep.bookmarks',side_effect=lambda:iter([raw])),patch('integrations.request_json',return_value={'content':'Texte fourni par Karakeep.','contentVersion':'v1'}) as req:
            run_cycle(self.config)
            self.assertIn('/bookmarks/site-fixture/content?',req.call_args.args[0])
            self.assertEqual(req.call_args.args[1],'test-only')
            self.assertEqual(self.source()['page_origin']['kind'],'karakeep_readable_content')
            run_cycle(self.config);self.assertEqual(req.call_count,1)

    def test_readable_content_pagination_is_bounded_and_rejects_repeated_cursor(self):
        with patch('integrations.request_json',side_effect=[{'content':'Début','nextCursor':'next'},{'content':' fin','nextCursor':None}]) as req:
            parts=Karakeep(self.config).page_content('site-fixture')
            self.assertEqual(''.join(p['content'] for p in parts),'Début fin')
            self.assertIn('cursor=next',req.call_args.args[0])
        with patch('integrations.request_json',return_value={'content':'texte','nextCursor':'same'}):
            with self.assertRaises(ServiceError):Karakeep(self.config).page_content('site-fixture')

    def test_video_does_not_depend_on_a_readable_web_page(self):
        raw=bookmark(crawlStatus='success',videoAssetId='video-one')
        with patch('worker.Karakeep.bookmarks',return_value=iter([raw])),patch('worker.Karakeep.page_content') as page:
            self.assertEqual(run_cycle(self.config)['processed'],1)
            page.assert_not_called()
            self.assertNotIn('page',self.source()['stages'])

    def test_title_only_waits_without_ai_then_new_upstream_text_is_analysed(self):
        raw=bookmark(crawlStatus='pending')
        self.config.llm_enabled=True;self.config.llm_url='https://example.invalid';self.config.llm_model='test'
        with patch('worker.Karakeep.bookmarks',side_effect=lambda:iter([raw])),patch('worker.synthesize',return_value=[]) as llm,patch('worker.Karakeep.page_content') as read:
            self.assertEqual(run_cycle(self.config)['processed'],0)
            self.assertEqual(self.source()['stages']['llm'],'waiting_content')
            self.assertEqual(run_cycle(self.config)['processed'],0);llm.assert_not_called();read.assert_not_called()
            with self.assertRaisesRegex(ValueError,'texte de cette page'):
                run_local_llm(self.config,'site-fixture')
            llm.assert_not_called()
            raw['content']['htmlContent']='<p>Le texte est disponible.</p>'
            self.assertEqual(run_cycle(self.config)['processed'],1);self.assertEqual(llm.call_count,1)
            self.assertIsNone(self.source().get('page_origin'))

    def test_old_metadata_only_done_job_is_revisited_once(self):
        raw=bookmark(contentAssetId='html-one');source=normalize_bookmark(raw)
        # Simulate an older job fingerprint without the new content contract.
        with patch('worker.Karakeep.bookmarks',side_effect=lambda:iter([raw])),patch('worker.Karakeep.download',side_effect=lambda _,p,**kw:p.write_bytes(b'<p>Un ancien site enfin lisible.</p>')):
            run_cycle(self.config,catalog_only=True)
            db=sqlite3.connect(self.root/'data/worker.sqlite')
            db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?,?)',('site-fixture','legacy-fingerprint','done',1,0,'','2026-11-01'))
            db.commit();db.close()
            self.assertEqual(run_cycle(self.config)['processed'],1)
            self.assertEqual(run_cycle(self.config)['processed'],0)

    def test_all_source_kinds_have_private_thumbnail_and_missing_image_falls_back(self):
        source=normalize_bookmark(bookmark())
        source.update(evidence=[],processing={'media_downloaded':False})
        for kind,url in [('link','https://example.org/'),('link','https://youtu.be/example'),('text',''),('asset','')]:
            source.update(bookmark_type=kind,url=url)
            raw,mime=thumbnail_bytes(source,self.root)
            self.assertIn('svg',mime);self.assertIn(b'Aper',raw)
            self.assertTrue(source_summary(source)['thumbnail'].endswith('/thumbnail'))
        source['preview']={'file':'../../.env','sha256':'a'*64}
        source['evidence']=[{'id':'test','kind':'ocr','image':'data/extracted/site-fixture/missing.jpg','text':''}]
        self.assertIn('svg',thumbnail_bytes(source,self.root)[1])

    def test_thumbnail_endpoint_preserves_auth_and_never_downloads_on_read(self):
        with patch('worker.Karakeep.bookmarks',return_value=iter([bookmark()])):run_cycle(self.config,catalog_only=True)
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Corpus(self.root),'test','secret'))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with patch('integrations.request') as network:
                for headers,status in [({},401),({'Authorization':'Basic '+base64.b64encode(b'test:secret').decode()},200)]:
                    client=http.client.HTTPConnection('127.0.0.1',server.server_port)
                    client.request('GET','/api/sources/site-fixture/thumbnail',headers=headers)
                    response=client.getresponse();body=response.read();self.assertEqual(response.status,status)
                    if status==200:
                        self.assertIn('image/svg+xml',response.getheader('Content-Type'))
                        self.assertIn(b'Aper',body)
                    client.close()
                network.assert_not_called()
        finally:server.shutdown();server.server_close();thread.join(5)


@unittest.skipUnless(importlib.util.find_spec('PIL'),'Pillow optional worker dependency')
class PreviewWorkerTests(unittest.TestCase):
    def test_preview_is_independent_of_ocr_and_survives_new_generation(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);config=Settings(root=root,karakeep_url='https://example.invalid',karakeep_key='test',sync_enabled=True,download_media=True)
            raw=bookmark(imageAssetId='banner-one',text='Un article sans vidéo.')
            data=BytesIO();Image.new('RGB',(1800,1200),'green').save(data,'PNG')
            def download(_,path,**kw):path.write_bytes(data.getvalue())
            with patch('worker.Karakeep.bookmarks',side_effect=lambda:iter([raw])),patch('worker.Karakeep.download',side_effect=download) as dl,patch('worker.synthesize') as llm:
                run_cycle(config)
                selected=active_root(root);source=kararecall.read_json(selected/'data/catalog.json')['sources'][0]
                target=preview_target(selected,source);self.assertTrue(target.is_file())
                with Image.open(target) as image:self.assertEqual(image.size,(960,640));self.assertEqual(image.format,'JPEG')
                self.assertEqual(thumbnail_bytes(source,selected)[1],'image/jpeg')
                self.assertEqual(run_cycle(config)['processed'],0);self.assertEqual(dl.call_count,1);llm.assert_not_called()
                # New image asset refreshes previews, without repeating inference.
                raw['content']['imageAssetId']='banner-two'
                run_cycle(config)
                updated=active_root(root);self.assertNotEqual(updated,selected)
                self.assertEqual((selected/ source['preview']['file']).read_bytes(),target.read_bytes())
                self.assertTrue(preview_target(updated,kararecall.read_json(updated/'data/catalog.json')['sources'][0]))
                llm.assert_not_called()

    def test_bad_banner_tries_screenshot_and_bad_images_get_generic_cover(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'data').mkdir()
            source=normalize_bookmark(bookmark(imageAssetId='bad',screenshotAssetId='good'))
            class Client:
                def download(self,asset,path,**kw):
                    if asset=='bad':path.write_text('<svg onload="evil()"/>')
                    else:Image.new('RGB',(24,24),'blue').save(path,'PNG')
            preview=make_preview(source,Client(),root)
            self.assertEqual(preview['asset_id'],'good')
            source['preview']=preview;preview_target(root,source).write_bytes(b'corrupt')
            self.assertIn('svg',thumbnail_bytes(source,root)[1])

    @unittest.skipUnless(importlib.util.find_spec('av'),'PyAV optional worker dependency')
    def test_video_frame_without_vision_or_transcription(self):
        import av
        from PIL import Image
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'data/media').mkdir(parents=True)
            source=normalize_bookmark(bookmark(videoAssetId='video-one'))
            with av.open(str(root/'data/media/site-fixture.mp4'),'w') as output:
                stream=output.add_stream('mpeg4',rate=10);stream.width=64;stream.height=64;stream.pix_fmt='yuv420p'
                for _ in range(6):
                    for packet in stream.encode(av.VideoFrame.from_image(Image.new('RGB',(64,64),'red'))):output.mux(packet)
                for packet in stream.encode():output.mux(packet)
            preview=make_preview(source,None,root)
            self.assertEqual(preview['kind'],'video_frame')
            self.assertTrue((root/preview['file']).is_file())


if __name__=='__main__':unittest.main()
