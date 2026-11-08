"""Observed read-only Karakeep catalogue comparison; never infer sync from AI jobs."""
from datetime import datetime, timezone
import fcntl

from kararecall import core
from kararecall.integrations import Karakeep, ServiceError, normalize_bookmark
from kararecall.publication import active_root
from kararecall.settings import initialize


def now():return datetime.now(timezone.utc).isoformat()


def revision(view_root):
    stat=(view_root/'data/catalog.json').stat()
    return f'{view_root.name}:{stat.st_mtime_ns}:{stat.st_size}'


def begin(root,mode):
    previous=core.read_json(root/'data/sync-status.json',{})
    core.write_json(root/'data/sync-status.json',{**previous,'state':'running','mode':mode,
        'started_at':now(),'updated_at':now(),'collected':0,'error':''})


def progress(root,count):
    previous=core.read_json(root/'data/sync-status.json',{})
    core.write_json(root/'data/sync-status.json',{**previous,'collected':count,'updated_at':now()})


def failed(root,error):
    previous=core.read_json(root/'data/sync-status.json',{})
    core.write_json(root/'data/sync-status.json',{**previous,'state':'error','failed_at':now(),'error':error[:400]})


def eligible(source,settings):
    wanted={tag.strip().casefold() for tag in settings.tag_filter.split(',') if tag.strip()}
    return (not settings.url_filter or settings.url_filter in source['url']) and (not wanted or bool(wanted.intersection(tag.casefold() for tag in source['tags'])))


def content_changed(remote,local):
    # Raw snapshot names may change because of expiring image URLs or JSON order.
    fields=('url','modified_at','title','description','note','bookmark_type','asset_type','document_asset_id','page_asset_id','crawl_status')
    if any(remote.get(key)!=local.get(key) for key in fields):return True
    if sorted(remote.get('tags',[]))!=sorted(local.get('tags',[])):return True
    if sorted((a['id'],a['type']) for a in remote.get('assets',[]))!=sorted((a['id'],a['type']) for a in local.get('assets',[])):return True
    if remote.get('preview_asset_ids',[])!=local.get('preview_asset_ids',[]):return True
    hydrated=local.get('page_origin') and not remote.get('page_text') and remote.get('page_asset_id')==local.get('page_asset_id')
    return not hydrated and remote.get('page_text','')!=local.get('page_text','')


def complete(settings,remote,mode):
    root=settings.root;selected=active_root(root)
    local={s['id']:s for s in core.read_json(selected/'data/sources.json',[])}
    remote_ids=set(remote);local_ids=set(local);common=remote_ids&local_ids
    scope={sid for sid,source in remote.items() if eligible(source,settings)}
    changed={sid for sid in common if content_changed(remote[sid],local[sid])}
    snapshot={'observed_at':now(),'karakeep_total':len(remote),'local_total':len(local),
        'present':len(common),'missing':len(remote_ids-local_ids),'local_only':len(local_ids-remote_ids),
        'updates':len(changed),'in_scope':len(scope),'excluded':len(remote_ids-scope),
        'missing_in_scope':len(scope-local_ids),'updates_in_scope':len(changed&scope),
        'filtered':bool(settings.url_filter or settings.tag_filter),'local_revision':revision(selected),'mode':mode}
    previous=core.read_json(root/'data/sync-status.json',{})
    value={**previous,'state':'completed','mode':mode,'collected':len(remote),'error':'','last_success':snapshot}
    if mode in ('history','periodic'):value['last_import_at']=snapshot['observed_at']
    core.write_json(root/'data/sync-status.json',value)
    return snapshot


def check(settings):
    if not settings.karakeep_url or not settings.karakeep_key:
        message='Renseigner KARAKEEP_BASE_URL et KARAKEEP_API_KEY dans le .env du worker.'
        failed(settings.root,message)
        raise ServiceError(message)
    initialize(settings.root)
    with (settings.root/'data/worker.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ServiceError('Un traitement utilise le volume ; relancer le contrôle après sa fin.') from None
        begin(settings.root,'check')
        try:
            remote={}
            for raw in Karakeep(settings).bookmarks():
                source=normalize_bookmark(raw);remote[source['id']]=source
                if len(remote)%100==0:progress(settings.root,len(remote))
            return complete(settings,remote,'check')
        except Exception as exc:
            from kararecall.worker import safe_error
            failed(settings.root,safe_error(exc,settings));raise
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def view(root,view_root,local_total,interval=900,worker_alive=False):
    stored=core.read_json(root/'data/sync-status.json',{})
    snapshot=stored.get('last_success')
    public={key:stored.get(key) for key in ('state','mode','started_at','collected','error','failed_at','last_import_at')}
    public['state']=public['state'] or 'not_observed';public['local_total']=local_total
    public['last_success']={key:value for key,value in snapshot.items() if key!='local_revision'} if snapshot else None
    public['comparison_current']=bool(snapshot and snapshot.get('local_revision')==revision(view_root))
    public['stale']=False
    if public['state']=='running' and not worker_alive:
        try:
            if (datetime.now(timezone.utc)-datetime.fromisoformat(stored.get('updated_at') or stored['started_at'])).total_seconds()>300:
                public.update(state='interrupted',error='Le dernier contrôle semble interrompu ; une nouvelle vérification peut être demandée.')
        except (ValueError,TypeError,KeyError):public.update(state='interrupted')
    if snapshot:
        try:public['stale']=(datetime.now(timezone.utc)-datetime.fromisoformat(snapshot['observed_at'])).total_seconds()>max(1800,interval*2)
        except (ValueError,TypeError):public['stale']=True
    return public
