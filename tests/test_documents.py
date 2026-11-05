import base64
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

import kararecall
from publication import active_root
from integrations import ServiceError
from settings import Settings
from web_server import Corpus, make_handler
from worker import run_cycle
from worker_documents import extract_document, pdf_text


def pdf_bytes(pages):
    """Minimal PDF with a standard font and explicit page boundaries."""
    kids = ' '.join(f'{4+i*2} 0 R' for i in range(len(pages)))
    objects = ['<< /Type /Catalog /Pages 2 0 R >>', f'<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>',
               '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    for index,text in enumerate(pages):
        stream = f'BT /F1 18 Tf 50 700 Td ({text}) Tj ET\n'
        objects.extend([f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {5+2*index} 0 R >>',
                        f'<< /Length {len(stream)} >>\nstream\n{stream}endstream'])
    output = b'%PDF-1.4\n'
    offsets = []
    for number,obj in enumerate(objects,1):
        offsets.append(len(output))
        output += f'{number} 0 obj\n{obj}\nendobj\n'.encode()
    xref = len(output)
    output += f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode()
    for offset in offsets:
        output += f'{offset:010} 00000 n \n'.encode()
    return output + f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


def bookmark(kind, asset_id='asset-one'):
    return {'id':'fixture-document','createdAt':'2026-11-05T12:00:00Z',
            'content':{'type':'asset','assetType':kind,'assetId':asset_id,'fileName':'Document de test'},'assets':[]}


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.settings = Settings(root=self.root,sync_enabled=True,karakeep_url='https://example.invalid',karakeep_key='fixture-only')
        self.downloads = []

    def tearDown(self):
        self.temporary.cleanup()

    def cycle(self, row, content, **kwargs):
        def download(asset_id, destination, *, max_mb):
            self.assertLessEqual(max_mb,20)
            self.downloads.append(asset_id)
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(content)
        with patch('worker.Karakeep.bookmarks',return_value=iter([row])),patch('worker.Karakeep.download',side_effect=download):
            return run_cycle(self.settings,**kwargs)

    def catalog(self):
        return kararecall.read_json(active_root(self.root)/'data/catalog.json')

    def test_manual_import_stays_metadata_only_and_saved_original_requires_auth(self):
        row = bookmark('image')
        self.cycle(row,b'original image fixture',catalog_only=True)
        self.assertEqual(self.downloads,[])
        self.assertIsNone(self.catalog()['sources'][0]['processing']['attachment'])
        with patch('worker_documents.chat') as model:
            self.cycle(row,b'original image fixture')
        model.assert_not_called()
        self.assertEqual(self.catalog()['sources'][0]['stages']['document'],'original_only')
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Corpus(self.root),'fixture','fixture-password'))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        auth='Basic '+base64.b64encode(b'fixture:fixture-password').decode()
        def get(path,key=None):
            with_connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            try:
                with_connection.request('GET',path,headers={'Authorization':key} if key else {})
                response=with_connection.getresponse()
                return response.status,dict(response.getheaders()),response.read()
            finally:
                with_connection.close()
        try:
            url='/download/document/fixture-document/asset-one'
            self.assertEqual(get(url)[0],401)
            status,headers,body=get(url,auth)
            self.assertEqual((status,body),(200,b'original image fixture'))
            self.assertIn('attachment',headers['Content-Disposition'])
            self.assertEqual(get('/assets/data/documents/fixture-document/asset-one.bin',auth)[0],404)
            self.assertEqual(get('/download/document/another-source/asset-one',auth)[0],404)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)

    @unittest.skipUnless(shutil.which('pdftotext'), 'Poppler est fourni dans le worker Docker')
    def test_pdf_page_numbers_coverage_and_old_proofs_survive_replacement(self):
        self.settings.pdf_max_pages=2
        row=bookmark('pdf')
        self.assertEqual(self.cycle(row,pdf_bytes(['','Le capteur mesure la salinite','Page hors budget']))['processed'],1)
        first=self.catalog()['sources'][0]
        proof=next(e for e in first['evidence'] if e['kind']=='pdf-page')
        self.assertEqual(proof['page'],2)
        self.assertTrue(first['processing']['attachment']['truncated'])
        self.assertEqual(kararecall.search('salinité',self.catalog())[0]['snippets'][0]['page'],2)
        self.assertEqual(self.cycle(row,b'not downloaded')['processed'],0)
        self.assertEqual(self.downloads,['asset-one'])
        self.cycle(bookmark('pdf','asset-two'),pdf_bytes(['Nouvelle version du document']))
        selected=active_root(self.root)
        updated=self.catalog()['sources'][0]
        archived=next(e for e in updated['evidence'] if e['id']==proof['id'])
        self.assertTrue(archived['archived'])
        self.assertTrue((selected/archived['attachment']['file']).is_file())
        self.assertEqual(kararecall.search('salinité',self.catalog()),[])
        blank=self.root/'blank.pdf'
        blank.write_bytes(pdf_bytes(['']))
        self.assertEqual(pdf_text(blank,2)['status'],'no_text')

    def test_image_ocr_requires_opt_in_and_reuses_success(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow est fourni dans le worker Docker')
        image=self.root/'fixture.png'
        Image.new('RGB',(20,20),'white').save(image)
        self.settings.image_ocr_enabled=True
        self.settings.vision_model='fixture-vision'
        self.settings.vision_url='https://example.invalid'
        row=bookmark('image')
        answer={'choices':[{'message':{'content':json.dumps({'text':'Jauge hydraulique'})}}]}
        with patch('integrations.request_json',return_value=answer) as model:
            self.assertEqual(self.cycle(row,image.read_bytes())['processed'],1)
            self.assertEqual(self.cycle(row,image.read_bytes())['processed'],0)
            self.assertEqual(model.call_count,1)
            image_url=model.call_args.args[2]['messages'][0]['content'][1]['image_url']['url']
            self.assertTrue(image_url.startswith('data:image/jpeg;base64,'))
        source=self.catalog()['sources'][0]
        proof=next(e for e in source['evidence'] if e['kind']=='image-text')
        self.assertEqual(proof['text'],'Jauge hydraulique')
        self.assertTrue((active_root(self.root)/proof['image']).is_file())
        self.assertEqual(self.downloads,['asset-one'])

    @unittest.skipUnless(shutil.which('pdftoppm') and shutil.which('pdftotext'), 'Poppler est fourni dans le worker Docker')
    def test_pdf_ocr_budget_and_retry_preserve_page_provenance(self):
        self.settings.pdf_ocr_enabled=True
        self.settings.pdf_ocr_max_pages=2
        self.settings.vision_model='fixture-vision'
        self.settings.vision_url='https://example.invalid'
        row=bookmark('pdf')
        content=pdf_bytes(['', 'Texte natif', '', ''])
        answer={'choices':[{'message':{'content':json.dumps({'text':'Texte OCR'})}}]}
        with patch('integrations.request_json',side_effect=[answer,ServiceError('Interruption de test')]) as model:
            self.assertEqual(self.cycle(row,content)['failed'],1)
            self.assertEqual(model.call_count,2)
            payload=model.call_args.args[2]['messages'][0]['content'][1]['image_url']['url']
            self.assertTrue(base64.b64decode(payload.split(',',1)[1]).startswith(b'\xff\xd8'))
        source=self.catalog()['sources'][0]
        self.assertEqual(source['processing']['attachment']['status'],'partial')
        pages={proof['page']:proof for proof in source['evidence'] if proof['kind']=='pdf-page'}
        self.assertEqual(set(pages),{1,2})
        self.assertEqual(pages[1]['recognition']['model'],'fixture-vision')
        self.assertIsNone(pages[2]['recognition']['model'])
        self.assertTrue((active_root(self.root)/pages[1]['image']).is_file())
        original=self.root/'fixture.pdf'
        original.write_bytes(content)
        with patch('integrations.request_json',return_value=answer) as model:
            output=self.root/'resume'
            self.assertEqual(extract_document(source,original,output,self.settings),'complete')
            self.assertEqual(model.call_count,1)
        artifact=kararecall.read_json(output/'document.json')
        self.assertTrue(artifact['truncated'])
        self.assertEqual([page['page'] for page in artifact['ocr_pages']],[1,3])
