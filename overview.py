"""Read-only operational views. Never reads environment secrets or original responses."""
from datetime import datetime, timedelta, timezone
import shutil
from zoneinfo import ZoneInfo

import kararecall
from controls import action_status, history_status, library_paused
from version import __version__
from settings import integer


def source_type(source):
    if source.get('has_video') or source.get('processing',{}).get('media_downloaded') or any(row.get('type')=='video' for row in source.get('assets',[])):return 'video'
    kind=source.get('bookmark_type','link')
    return 'note' if kind=='text' else 'file' if kind=='asset' else 'article'


def stage_matches(source,stage):
    states=source.get('stages',{}).values()
    complete=source.get('processing',{}).get('audio_transcribed') and source.get('processing',{}).get('ocr_sampled')
    reading=source.get('has_reading',bool(source.get('reading')))
    return {'all':True,'complete':bool(complete),'partial':not complete,'failed':'failed' in states,
            'paused':'paused' in states,'summarized':reading,'pending':not reading}.get(stage,False)


def worker_view(root):
    worker=kararecall.read_json(root/'data/service-status.json',{})
    usage=kararecall.read_json(root/'data/usage-summary.json',worker.get('usage',{}))
    if usage:worker['usage']=usage
    if worker.get('heartbeat_at'):
        try:
            moments=[worker.get('heartbeat_at'),usage.get('updated_at')]
            latest=max(datetime.fromisoformat(value).timestamp() for value in moments if value)
            threshold=max(300,worker.get('sync_interval_seconds',900)*2) if worker.get('state')=='running' else 300
            worker['stale']=datetime.now(timezone.utc).timestamp()-latest>threshold
        except (ValueError,TypeError):worker['stale']=True
    return worker


def public_configuration(settings):
    from urllib.parse import urlsplit
    def role(url,model,key,enabled):
        host=urlsplit(url).hostname or ''
        provider={'api.deepseek.com':'DeepSeek','api.openai.com':'OpenAI','api.groq.com':'Groq'}.get(host,'Service compatible' if host else 'Non renseigné')
        return {'enabled':bool(enabled),'configured':bool(url and model and (key or host not in ('api.deepseek.com','api.openai.com','api.groq.com'))),
                'provider':provider,'model':model[:120]}
    return {'karakeep':{'configured':bool(settings.karakeep_url and settings.karakeep_key)},
            'llm':role(settings.llm_url,settings.llm_model,settings.llm_key,settings.llm_enabled),
            'asr':role(settings.asr_url,settings.asr_model,settings.asr_key,bool(settings.asr_model)),
            'vision':role(settings.vision_url,settings.vision_model,settings.vision_key,bool(settings.vision_model)),
            'web_research':{'enabled':settings.web_research_enabled,'configured':bool(settings.web_research_key)},
            'catalogue_filtered':bool(settings.url_filter or settings.tag_filter),'batch_size':settings.batch_size,'sync_interval_seconds':settings.sync_interval,
            'download_media':settings.download_media,'media_max_mb':settings.media_max_mb,
            'media_max_seconds':settings.media_max_seconds,'vision_max_frames':settings.vision_max_frames,
            'vision_interval':settings.vision_interval,'vision_sample_mode':settings.vision_sample_mode,'pdf_max_pages':settings.pdf_max_pages,
            'pdf_ocr_enabled':settings.pdf_ocr_enabled,'pdf_ocr_max_pages':settings.pdf_ocr_max_pages,
            'image_ocr_enabled':settings.image_ocr_enabled}


def overview(root,data,view_root):
    now=datetime.now(timezone.utc)
    worker=worker_view(root);usage=worker.get('usage',{})
    sources=data['sources'];entities=data['entities'];actions=action_status(root)
    summary={'sources':len(sources),'tools':len(entities),'summarized':sum(bool(row.get('reading')) for row in sources),
             'failed':sum(stage_matches(row,'failed') for row in sources),
             'paused':sum(stage_matches(row,'paused') for row in sources),
             'review':sum(row.get('curation') in ('machine-generated','user-edited') for row in entities),
             'videos_complete':sum(bool(row['processing']['audio_transcribed'] and row['processing']['ocr_sampled']) for row in sources),
             'metadata_only':sum(row.get('content_status')=='metadata_only' and not row.get('reading') for row in sources)}
    summary['pending']=summary['sources']-summary['summarized']
    summary['attention']=sum(stage_matches(row,'failed') or stage_matches(row,'paused') for row in sources)
    days={ (now.astimezone(ZoneInfo('Europe/Paris')).date()-timedelta(days=i)).isoformat():0 for i in reversed(range(7))}
    kinds={key:0 for key in ('article','video','note','file')}
    for row in sources:
        kinds[source_type(row)]+=1
        try:
            instant=datetime.fromisoformat(row['created_at'].replace('Z','+00:00'))
            day=instant.astimezone(ZoneInfo('Europe/Paris')).date().isoformat()
            if day in days:days[day]+=1
        except (ValueError,TypeError):pass
    alerts=[]
    def alert(key,title,message,route,level='warning'):
        alerts.append({'id':key,'title':title,'message':message,'route':route,'level':level})
    if not sources:alert('empty','Votre bibliothèque attend ses premières sources','Importez vos favoris Karakeep pour commencer.','#/processing','info')
    if library_paused(root):alert('suspended','Automatisation suspendue','Les commandes manuelles restent disponibles. Reprenez quand vous le souhaitez.','#/administration','info')
    if not worker.get('heartbeat_at'):alert('worker_unknown','Le worker n’a pas encore donné de nouvelles','Vérifiez son démarrage et sa configuration.','#/administration')
    elif worker.get('stale'):alert('worker_stale','Le worker ne donne plus d’état récent','Les contenus déjà conservés restent consultables.','#/administration')
    if worker.get('application_version') and worker['application_version']!=__version__:alert('version_mismatch','Le web et le worker ont des versions différentes','Reconstruisez les deux images depuis la même version du projet.','#/administration')
    if worker.get('state')=='error':alert('worker_error','Le dernier passage a échoué',worker.get('message') or 'Vérifiez les connexions du worker.','#/administration')
    if summary['pending'] and worker.get('llm_enabled') is False:alert('llm_disabled','Les résumés IA sont désactivés','Les textes sont consultables ; activez le service de rédaction pour produire des résumés.','#/administration','info')
    if usage.get('blocked_by'):alert('quota','Les traitements attendent un quota disponible','Consultez les limites et la consommation avant de relancer.','#/administration?tab=usage')
    if summary['failed']:alert('failed',f"{summary['failed']} source(s) à vérifier",'Ouvrez les étapes en échec et leur dernière erreur.','#/processing?stage=failed')
    if summary['paused'] and not usage.get('blocked_by'):alert('paused',f"{summary['paused']} source(s) en pause",'Le dernier traitement a été suspendu ; consultez sa progression.','#/processing?stage=paused')
    disk=shutil.disk_usage(root)
    minimum=worker.get('storage_min_free_mb',integer('STORAGE_MIN_FREE_MB',256,0,1048576))
    if disk.free<int(minimum)*1024*1024:alert('disk','Espace libre faible','Les nouveaux téléchargements peuvent être suspendus.','#/administration?tab=storage')
    connection=kararecall.read_json(root/'data/connection-check.json',{})
    if connection.get('state')=='error':alert('connections','Le dernier contrôle des connexions a échoué','Consultez le diagnostic et les paramètres du worker.','#/administration')
    pointer=kararecall.read_json(root/'data/current.json',{})
    return {'version':__version__,'generated_at':now.isoformat(),'summary':summary,'source_types':kinds,
            'additions':[{'date':day,'count':count} for day,count in days.items()],
            'alerts':alerts,'worker':worker,'usage':usage,'configuration':worker.get('configuration'),
            'actions':actions,'history_import':history_status(root),'connection_check':connection,
            'storage':{'free_mb':disk.free//1048576,'total_mb':disk.total//1048576,'used_mb':disk.used//1048576,
                       'minimum_free_mb':minimum,'low_space':disk.free<int(minimum)*1048576,
                       'versioned':bool(pointer),'generation':view_root.name if pointer else None,
                       'published_at':datetime.fromtimestamp((view_root/'data/catalog.json').stat().st_mtime,timezone.utc).isoformat(),
                       'backup_status':'not_observed'}}


def diagnostic(report):
    """Shareable operational metadata: no sources, jobs, models, URLs or free-form errors."""
    worker=report['worker'];usage=report['usage']
    return {'application':'KaraRecall','version':report['version'],'generated_at':report['generated_at'],
            'summary':report['summary'],'storage':report['storage'],
            'worker':{key:worker.get(key) for key in ('application_version','state','heartbeat_at','stale','sync_enabled','llm_enabled','asr_enabled','vision_enabled')},
            'usage':{key:usage.get(key) for key in ('month','calls','daily_calls','daily_call_limit','monthly_call_limit','accounted_usd','limit_usd','blocked_by')},
            'automation_suspended':report['actions']['library_paused'],
            'alerts':[row['id'] for row in report['alerts']]}
