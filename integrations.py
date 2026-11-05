"""Read-only Karakeep and OpenAI-compatible inference clients.

No credentials, signed URLs or upstream response bodies are written to logs.
"""
import json
import hashlib
from pathlib import Path
import re
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class ServiceError(RuntimeError):
    pass


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        result=super().redirect_request(req,fp,code,msg,headers,newurl)
        if result and (urlsplit(req.full_url).scheme,urlsplit(req.full_url).netloc)!=(urlsplit(newurl).scheme,urlsplit(newurl).netloc):
            result.remove_header('Authorization')
        return result


def request(url,key='',payload=None,timeout=120,content_type='application/json'):
    headers={'Accept':'application/json'}
    if key:
        headers['Authorization']='Bearer '+key
    if payload is not None:
        headers['Content-Type']=content_type
    try:
        return build_opener(SafeRedirect()).open(Request(url,data=payload,headers=headers),timeout=timeout)
    except HTTPError as exc:
        raise ServiceError(f'Le service répond HTTP {exc.code}. Vérifier sa configuration et les droits de la clé.') from None
    except (URLError,TimeoutError,OSError):
        raise ServiceError('Service inaccessible ou délai dépassé. Vérifier son adresse et sa disponibilité.') from None


def request_json(url,key='',payload=None,timeout=120):
    body=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
    with request(url,key,body,timeout) as response:
        raw=response.read(16*1024*1024+1)
        if len(raw)>16*1024*1024:
            raise ServiceError('Réponse JSON trop volumineuse.')
    try:
        return json.loads(raw)
    except (ValueError,UnicodeError):
        raise ServiceError('Le service ne renvoie pas un JSON valide.') from None


def check_id(value):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,120}',value):
        raise ServiceError('Identifiant de source ou de média non valide.')
    return value


class Karakeep:
    def __init__(self,settings):
        self.settings=settings
        base=settings.karakeep_url
        if not base:
            raise ServiceError('KARAKEEP_BASE_URL est manquant.')
        self.base=base if base.endswith('/api/v1') else base+'/api/v1'

    def bookmarks(self):
        cursor=None
        seen=set()
        for _ in range(1000):
            params={'limit':100,'includeContent':'true','sortOrder':'desc'}
            if cursor:
                params['cursor']=cursor
            page=request_json(self.base+'/bookmarks?'+urlencode(params),self.settings.karakeep_key,timeout=self.settings.timeout)
            if not isinstance(page.get('bookmarks'),list):
                raise ServiceError('Format de réponse Karakeep inattendu.')
            yield from page['bookmarks']
            cursor=page.get('nextCursor')
            if not cursor:
                return
            if cursor in seen:
                raise ServiceError('Karakeep répète un curseur de pagination.')
            seen.add(cursor)
        raise ServiceError('Pagination Karakeep trop longue ; aucun import partiel appliqué.')

    def download(self,asset_id,destination):
        check_id(asset_id)
        maximum=self.settings.media_max_mb*1024*1024
        temporary=Path(str(destination)+'.part')
        destination.parent.mkdir(parents=True,exist_ok=True)
        try:
            with request(self.base+'/assets/'+quote(asset_id),self.settings.karakeep_key,timeout=self.settings.timeout) as response:
                declared=response.headers.get('Content-Length')
                if declared and int(declared)>maximum:
                    raise ServiceError('Pièce jointe trop volumineuse pour MEDIA_MAX_MB.')
                count=0
                with temporary.open('wb') as output:
                    while True:
                        block=response.read(128*1024)
                        if not block:
                            break
                        count+=len(block)
                        if count>maximum:
                            raise ServiceError('Pièce jointe trop volumineuse pour MEDIA_MAX_MB.')
                        output.write(block)
                if count==0:
                    raise ServiceError('Pièce jointe vide.')
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)


class ReadableHTML(HTMLParser):
    """Keep page text and link targets; never execute embedded page content."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript','template'):self.hidden+=1
        if self.hidden:return
        if tag in ('p','div','br','li','h1','h2','h3','section','article'):self.parts.append('\n')
        if tag=='a':
            href=dict(attrs).get('href','')
            if href.startswith(('http://','https://')):self.parts.append(' '+href+' ')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript','template'):self.hidden=max(0,self.hidden-1)
        elif not self.hidden and tag in ('p','div','li','section','article'):self.parts.append('\n')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


def readable_html(text):
    parser=ReadableHTML();parser.feed(text)
    return '\n'.join(re.sub(r'\s+',' ',line).strip() for line in ''.join(parser.parts).splitlines() if line.strip())


def normalize_bookmark(bookmark):
    sid=check_id(bookmark['id'])
    content=bookmark.get('content') or {}
    kind=content.get('type','unknown')
    title=bookmark.get('title') or content.get('title') or content.get('fileName') or content.get('url') or str(content.get('text') or '')[:120] or 'Sans titre'
    text=content.get('text') or content.get('content') or ''
    if not text and content.get('htmlContent'):text=readable_html(content['htmlContent'])
    created=bookmark.get('createdAt')
    if not isinstance(created,str) or not created:
        raise ServiceError('Date d’enregistrement absente du favori.')
    assets=[{'id':check_id(a['id']),'type':a.get('assetType','unknown')} for a in bookmark.get('assets',[])]
    if content.get('assetId') and not any(a['id']==content['assetId'] for a in assets):
        assets.append({'id':check_id(content['assetId']),'type':content.get('assetType','unknown')})
    video_id=content.get('videoAssetId') or next((a['id'] for a in assets if a['type']=='video'),None)
    if video_id:
        check_id(video_id)
        if not any(a['id']==video_id for a in assets):
            assets.append({'id':video_id,'type':'video'})
    return {'id':sid,'url':content.get('url') or content.get('sourceUrl') or '',
        'bookmark_type':kind,'asset_type':content.get('assetType'),
        'content_status':'text_available' if text else 'metadata_only',
        'archived':bool(bookmark.get('archived')),'favourited':bool(bookmark.get('favourited')),
        'created_at':created,'modified_at':bookmark.get('modifiedAt') or created,'title':str(title),
        'description':content.get('description') or '', 'note':bookmark.get('note') or '',
        'tags':[t['name'] for t in bookmark.get('tags',[]) if t.get('name')],
        'page_text':text,
        'karakeep_summary_unverified':bookmark.get('summary') or '', 'assets':assets,
        'raw_file':'data/raw/api/'+sid+'-'+hashlib.sha256(json.dumps(bookmark,sort_keys=True).encode()).hexdigest()[:12]+'.json'}


def chat(base,key,model,messages,timeout=120,*,max_tokens=2000,reasoning='',thinking='',token_limit_param='max_completion_tokens',ledger=None,stage='llm'):
    if not (base and model):
        raise ServiceError('Adresse et modèle IA non configurés.')
    payload={'model':model,'messages':messages,'stream':False,token_limit_param:max_tokens}
    if reasoning:payload['reasoning_effort']=reasoning
    if thinking:payload['thinking']={'type':thinking}
    operation=lambda:request_json(base.rstrip('/')+'/chat/completions',key,payload,timeout)
    data=ledger.call(stage,base,model,operation) if ledger else operation()
    try:
        if data['choices'][0].get('finish_reason')=='length':
            raise ServiceError('Sortie du modèle tronquée par la limite ; résultat non publié.')
        text=data['choices'][0]['message']['content']
        if not isinstance(text,str):
            raise KeyError()
        return text
    except (KeyError,IndexError,TypeError):
        raise ServiceError('Réponse du modèle incompatible avec chat/completions.') from None


def json_result(text):
    text=text.strip()
    if text.startswith('```'):
        text=re.sub(r'^```(?:json)?\s*','',text)
        text=re.sub(r'\s*```$','',text)
    try:
        value=json.loads(text)
        if not isinstance(value,dict):
            raise ValueError()
        return value
    except ValueError:
        raise ServiceError('Le modèle n’a pas renvoyé l’objet JSON attendu ; résultat non publié.') from None
