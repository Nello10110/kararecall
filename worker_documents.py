"""Bounded extraction from a PDF or standalone image attached in Karakeep."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import warnings

from integrations import ServiceError, recognize_image, OCR_CONTRACT, json_object_mode, check_id
from publication import file_hash


MAX_DOCUMENT_MB = 20
MAX_PAGE_CHARS = 40_000
MAX_IMAGE_PIXELS = 20_000_000

# Apply limits in the child before executing Poppler. Avoid preexec_fn in the worker.
PDF_EXEC = '''
import os, resource, sys
for limit, value in ((resource.RLIMIT_AS, 256 * 1024**2),
                     (resource.RLIMIT_FSIZE, 2 * 1024**2), (resource.RLIMIT_CPU, 15)):
    resource.setrlimit(limit, (value, value))
os.execv(sys.argv[1], sys.argv[1:])
'''


def document_path(root, sid, asset_id):
    return root / 'data/documents' / check_id(sid) / (check_id(asset_id) + '.bin')


def attachment_target(root, sid, attachment):
    relative = attachment['file']
    match = re.fullmatch(r'data/documents/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]{1,120})\.bin', relative)
    if not match or match[1] != sid or attachment.get('kind') not in ('pdf', 'image'):
        raise ValueError('Chemin de pièce jointe non autorisé.')
    target = document_path(root, sid, match[2]).resolve()
    target.relative_to(root.resolve() / 'data/documents' / sid)
    return target


def attachment_extension(target, kind):
    if kind == 'pdf':
        return '.pdf'
    with target.open('rb') as stream:
        header = stream.read(12)
    if header.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if header.startswith((b'GIF87a', b'GIF89a')):
        return '.gif'
    if header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        return '.webp'
    return '.bin'


def load_document_evidence(source, root, extracted):
    import kararecall

    asset_id = source.get('document_asset_id')
    if not asset_id:
        return [], None
    sid, kind = source['id'], source['asset_type']
    original = document_path(root, sid, asset_id)
    artifact = kararecall.read_json(extracted / 'document.json', {})
    if artifact.get('asset_id') != asset_id:
        artifact = {}  # A previous asset's proofs remain in the evidence archive.
    if not original.is_file():
        if artifact:
            raise ValueError('Original de pièce jointe absent.')
        return [], None
    digest = file_hash(original)
    if artifact and (artifact.get('sha256') != digest or artifact.get('kind') != kind):
        raise ValueError('Empreinte de pièce jointe incohérente.')
    attachment = {'file':original.relative_to(root).as_posix(), 'kind':kind, 'sha256':digest}
    processing = {**attachment, 'status':artifact.get('status', 'saved'), 'truncated':artifact.get('truncated',False),
                  'pages_scanned':artifact.get('pages_scanned',0)}
    for key in ('frames_scanned','frames_total'):
        if key in artifact:processing[key]=artifact[key]
    provenance = {'attachment':attachment, 'recognition':{k:artifact.get(k) for k in ('engine','model','cache_key')}}
    rows = []
    if kind == 'pdf':
        for page in artifact.get('pages', []):
            rows.append({'id':f"pdf-page-{page['page']}", 'kind':'pdf-page', 'page':page['page'], 'text':page['text'], **provenance})
        for page in artifact.get('ocr_pages', []):
            number, preview = page['page'], page['preview']
            if not re.fullmatch(r'pdf-page-[0-9]+-[a-f0-9]{64}\.jpg', preview):
                raise ValueError('Aperçu de page PDF invalide.')
            rows.append({'id':f'pdf-page-{number}-ocr', 'kind':'pdf-page', 'page':number, 'text':page['text'],
                         'image':(extracted / preview).relative_to(root).as_posix(), 'attachment':attachment,
                         'recognition':{'engine':page['engine'],'model':page['model'],'cache_key':artifact['cache_key']}})
        if 'ocr_pages' in artifact:
            processing['ocr_pages'] = len(artifact['ocr_pages'])
    elif artifact.get('preview'):
        preview = artifact['preview']
        if not re.fullmatch(r'document-[a-f0-9]{64}\.jpg', preview):
            raise ValueError('Aperçu de pièce jointe invalide.')
        rows.append({'id':'image-text', 'kind':'image-text', 'text':artifact['text'],
                     'image':(extracted / preview).relative_to(root).as_posix(), **provenance})
    return rows, processing


def extraction_config(kind, settings):
    vision = [settings.vision_url, settings.vision_model, settings.vision_max_tokens,
              settings.vision_reasoning, settings.vision_thinking, settings.token_limit_param,
              OCR_CONTRACT, json_object_mode(settings.vision_url)]
    if kind == 'pdf':
        config = ['pdf-v1', settings.pdf_max_pages]
        if settings.pdf_ocr_enabled:
            config.extend(['ocr-v1', settings.pdf_ocr_max_pages, *vision])
        return config
    return ['image-v2-first-frame', settings.image_ocr_enabled, *vision]


def run_poppler(tool, args):
    executable = shutil.which(tool)
    if not executable:
        raise ServiceError('Extracteur PDF indisponible. Reconstruire le worker avec Docker.')
    try:
        subprocess.run([sys.executable, '-c', PDF_EXEC, executable, *args], check=True, timeout=25,
                       env={'PATH':os.defpath,'LANG':'C.UTF-8'}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        raise ServiceError('Lecture PDF impossible dans les limites prévues. Vérifier si le fichier est protégé, endommagé ou trop complexe.') from None


def pdf_text(original, max_pages):
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / 'pages.txt'
        run_poppler('pdftotext', ['-f','1','-l',str(max_pages + 1),'-enc','UTF-8',str(original),str(output)])
        pages = output.read_text(encoding='utf-8').split('\f')
    if pages and pages[-1] == '':
        pages.pop()
    sampled = pages[:max_pages]
    return {
        'engine': 'poppler-pdftotext',
        'status': 'complete' if any(page.strip() for page in sampled) else 'no_text',
        'pages_scanned': len(sampled),
        'truncated': len(pages) > max_pages or any(len(page.strip()) > MAX_PAGE_CHARS for page in sampled),
        'pages': [{'page': number, 'text': page.strip()[:MAX_PAGE_CHARS]} for number, page in enumerate(sampled, 1) if page.strip()],
    }


def image_text(original, preview, settings, ledger):
    from PIL import Image, ImageOps

    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(original, formats=['JPEG', 'PNG', 'WEBP', 'GIF']) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ServiceError('OCR image limité à 20 mégapixels.')
                frames=getattr(image,'n_frames',1)
                image.seek(0)
                image = ImageOps.exif_transpose(image)
                image.thumbnail((1280, 1280))
                # Composite transparency on white and discard original metadata.
                rgba = image.convert('RGBA')
                clean = Image.new('RGB', rgba.size, 'white')
                clean.paste(rgba, mask=rgba.getchannel('A'))
                clean.save(preview, 'JPEG', quality=85)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, ValueError):
        raise ServiceError('Image illisible ou format non pris en charge. JPEG, PNG, WebP et GIF sont acceptés ; seule la première image d’une animation est lue.') from None
    return dict(recognize_jpeg(preview, settings, ledger),truncated=frames>1,frames_scanned=1,frames_total=frames)


def recognize_jpeg(preview, settings, ledger):
    text = recognize_image(settings.vision_url, settings.vision_key, settings.vision_model,
        preview.read_bytes(), settings.timeout, max_tokens=settings.vision_max_tokens,
        reasoning=settings.vision_reasoning, thinking=settings.vision_thinking,
        token_limit_param=settings.token_limit_param, ledger=ledger).strip()
    return {'engine':'configured-vision-api', 'model':settings.vision_model, 'preview':preview.name,
            'status':'complete' if text else 'no_text', 'text':text}


def pdf_ocr(original, output, result, settings, ledger, cache, cache_key):
    import kararecall

    populated = {page['page'] for page in result['pages']}
    blank = [number for number in range(1, result['pages_scanned'] + 1) if number not in populated]
    result['ocr_pages'] = []
    result['truncated'] |= len(blank) > settings.pdf_ocr_max_pages
    for number in blank[:settings.pdf_ocr_max_pages]:
        preview = cache / f'pdf-page-{number}-{cache_key}.jpg'
        record = cache / f'{number}.json'
        cached = kararecall.read_json(record, {})
        if not cached or not preview.is_file():
            with tempfile.TemporaryDirectory() as directory:
                prefix = Path(directory) / 'page'
                run_poppler('pdftoppm', ['-f',str(number),'-l',str(number),'-scale-to','1280',
                                         '-singlefile','-jpeg',str(original),str(prefix)])
                generated = prefix.with_suffix('.jpg')
                if not generated.is_file():
                    raise ServiceError('Aperçu PDF indisponible.')
                cache.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(generated, preview)
            cached = {'page':number, **recognize_jpeg(preview, settings, ledger)}
            kararecall.write_json(record, cached)
        shutil.copyfile(preview, output / preview.name)
        result['ocr_pages'].append(cached)
    if any(page['text'] for page in result['ocr_pages']):
        result['status'] = 'complete'


def extract_document(source, original, output, settings, ledger=None, force=False):
    import kararecall

    asset_id, kind = source['document_asset_id'], source['asset_type']
    digest = file_hash(original)
    config = extraction_config(kind, settings)
    cache_key = hashlib.sha256(json.dumps([digest, config]).encode()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / 'document.json'
    old = kararecall.read_json(artifact, {})
    if not force and old.get('asset_id') == asset_id and old.get('cache_key') == cache_key and old.get('status') != 'partial':
        return old['status']
    metadata = {'asset_id':asset_id, 'kind':kind, 'sha256':digest, 'cache_key':cache_key}
    if kind == 'pdf':
        result = pdf_text(original, settings.pdf_max_pages)
        if settings.pdf_ocr_enabled:
            cache = settings.root / 'data/work' / check_id(source['id']) / ('pdf-ocr-' + cache_key)
            if force and cache.exists():
                shutil.rmtree(cache)
            try:
                pdf_ocr(original, output, result, settings, ledger, cache, cache_key)
            except Exception:
                kararecall.write_json(artifact, {**result, **metadata, 'status':'partial'})
                raise
    elif settings.image_ocr_enabled:
        result = image_text(original, output / ('document-' + cache_key + '.jpg'), settings, ledger)
    else:
        result = {'status': 'original_only'}
    kararecall.write_json(artifact, {**result, **metadata})
    return result['status']
