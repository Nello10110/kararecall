"""Read-only page acquisition and local previews. No inference, no public crawl."""
import hashlib
import json
from html import escape
from io import BytesIO
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
import warnings

from kararecall.integrations import ServiceError, readable_html
from kararecall.publication import file_hash


def acquire_page(source, client, draft):
    """Retrieve Karakeep's separate HTML asset with bounded, versioned provenance."""
    if source.get('page_text'):
        return 'source_text'
    asset=source.get('page_asset_id')
    if not asset:
        if source.get('crawl_status')!='success':return 'metadata_only'
        parts=client.page_content(source['id'])
        text='\n'.join(part['content'] for part in parts)
        raw=json.dumps(parts,ensure_ascii=False,sort_keys=True).encode()
        kind='karakeep_readable_content';suffix='json'
        versions={part.get('contentVersion') for part in parts if part.get('contentVersion')}
        if len(versions)>1:raise ServiceError('Le contenu Karakeep a changé pendant sa lecture ; reprise nécessaire.')
    else:
        with tempfile.TemporaryDirectory(dir=draft/'data') as name:
            path=Path(name)/'page.html'
            client.download(asset,path,max_mb=8)
            raw=path.read_bytes()
        text=readable_html(raw.decode('utf-8',errors='replace'))
        kind='karakeep_html_asset';suffix='html'
    if not text.strip():
        raise ServiceError('Le contenu fourni par Karakeep ne contient aucun texte lisible.')
    digest=hashlib.sha256(raw).hexdigest()
    relative=f'data/raw/api/{source["id"]}-page-{digest}.{suffix}'
    target=draft/relative
    if not target.exists():target.write_bytes(raw)
    source.update(page_text=text,content_status='text_available',
                  page_origin={'kind':kind,'asset_id':asset,'file':relative,'sha256':digest})
    return 'complete'


def preview_key(source):
    # Preview availability must not invalidate paid inference caches.
    return hashlib.sha256(str([source.get('preview_asset_ids',[]),
        [(a['id'],a['type']) for a in source.get('assets',[]) if a['type']=='video']]).encode()).hexdigest()


def save_preview(raw, draft, sid, kind):
    from PIL import Image, ImageOps
    with warnings.catch_warnings():
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        with Image.open(BytesIO(raw)) as image:
            if image.format not in ('JPEG','PNG','WEBP','GIF','AVIF'):
                raise ValueError('Format d’aperçu non pris en charge')
            if image.width*image.height>20_000_000:raise ValueError('Aperçu trop volumineux')
            image=ImageOps.exif_transpose(image)
            image.thumbnail((960,640))
            image=image.convert('RGB')
            buffer=BytesIO();image.save(buffer,'JPEG',quality=82)
    content=buffer.getvalue();digest=hashlib.sha256(content).hexdigest()
    relative=f'data/previews/{sid}/{digest}.jpg';target=draft/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():target.write_bytes(content)
    return {'file':relative,'sha256':digest,'kind':kind}


def make_preview(source,client,draft):
    """A failed preview never blocks analysis and never invokes an AI service."""
    for asset in source.get('preview_asset_ids',[])[:3]:
        try:
            original=draft/'data/documents'/source['id']/(asset+'.bin')
            if asset==source.get('document_asset_id') and original.is_file():
                if original.stat().st_size>8*1024*1024:continue
                raw=original.read_bytes()
            else:
                with tempfile.TemporaryDirectory(dir=draft/'data') as name:
                    path=Path(name)/'preview'
                    client.download(asset,path,max_mb=8)
                    raw=path.read_bytes()
            result=save_preview(raw,draft,source['id'],'karakeep')
            return dict(result,asset_id=asset)
        except (OSError,ValueError,ServiceError,ImportError):
            continue
    media=draft/'data/media'/(source['id']+'.mp4')
    if media.is_file():
        try:
            import av
            with av.open(str(media)) as container:
                if container.streams.video:
                    # Seek near the start; decode at most 24 frames, no full-video pass.
                    stream=container.streams.video[0]
                    if stream.codec_context.width*stream.codec_context.height>20_000_000:return None
                    frame=None
                    for index,frame in enumerate(container.decode(video=0)):
                        if index>=23 or (frame.time is not None and frame.time>=1):
                            break
                    if frame is not None:
                        buffer=BytesIO();frame.to_image().save(buffer,'JPEG')
                        return save_preview(buffer.getvalue(),draft,source['id'],'video_frame')
        except (OSError,ValueError,ImportError):
            pass
    return None


def preview_target(root,source):
    item=source.get('preview') or {}
    digest=item.get('sha256','')
    relative=f'data/previews/{source["id"]}/{digest}.jpg'
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest) or item.get('file')!=relative:
        return None
    target=(root/relative).resolve()
    if not target.is_relative_to((root/'data/previews'/source['id']).resolve()):return None
    if target.is_file() and file_hash(target)==digest:return target
    return None


def thumbnail_bytes(source,root):
    target=preview_target(root,source)
    if target:return target.read_bytes(),'image/jpeg'
    images=[row for row in source.get('evidence',[]) if row.get('image') and not row.get('archived')]
    images.sort(key=lambda row:abs(row.get('start',14)-14))
    for row in images:
        target=(root/row['image']).resolve()
        if not any(target.is_relative_to((root/'data'/kind/source['id']).resolve()) for kind in ('extracted','evidence')):continue
        if target.is_file():
            raw=target.read_bytes()
            if raw.startswith(b'\xff\xd8\xff'):return raw,'image/jpeg'
            if raw.startswith(b'\x89PNG\r\n\x1a\n'):return raw,'image/png'
    # A private, deterministic cover, explicitly not a screenshot or evidence.
    from kararecall.overview import source_type
    kind=source_type(source)
    label={'video':'Vidéo','article':'Site ou article','note':'Note personnelle','file':'Fichier'}[kind]
    domain=urlsplit(source.get('url','')).hostname or label
    color={'video':'#8c83c7','article':'#54958e','note':'#b79860','file':'#688fbd'}[kind]
    glyph='<path d="M292 110l70 40-70 40z"/>' if kind=='video' else '<path d="M287 107h66v86h-66z"/><path d="M300 130h40m-40 14h40m-40 14h28" stroke="#162831" stroke-width="5"/>'
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
    <defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#162831"/><stop offset="1" stop-color="{color}"/></linearGradient></defs>
    <rect width="640" height="360" fill="url(#bg)"/><circle cx="520" cy="10" r="190" fill="#fff" opacity=".06"/>
    <circle cx="320" cy="150" r="72" fill="#fff" opacity=".10"/><g fill="#fff" opacity=".9">{glyph}</g>
    <g fill="#fff" font-family="system-ui,sans-serif" text-anchor="middle"><text x="320" y="260" font-size="24">{escape(domain[:42])}</text>
    <text x="320" y="294" font-size="17" opacity=".8">{label} · Aperçu générique</text></g></svg>'''
    return svg.encode(),'image/svg+xml; charset=utf-8'
