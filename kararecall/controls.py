"""Durable local import requests. No credentials and no writes to Karakeep."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import uuid
import time

from kararecall import core as kararecall


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def locked(root,name,blocking=True):
    directory=root/'data/control';directory.mkdir(parents=True,exist_ok=True)
    with (directory/name).open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)


def history_status(root):
    return kararecall.read_json(root/'data/control/history.json',{'state':'none'})


def request_history(root):
    with locked(root,'state.lock'):
        if any(row['kind']=='clear' and row['state'] in ('queued','running') for row in action_status(root)['jobs']):
            raise ValueError('Attendre la fin du vidage avant de réimporter.')
        suspension=kararecall.read_json(root/'data/control/library.json',{})
        if suspension.get('reason')!='manual':
            kararecall.write_json(root/'data/control/library.json',{'paused':False})
        current=history_status(root)
        if current['state'] in ('queued','running'):return current
        current={'id':uuid.uuid4().hex,'state':'queued','requested_at':now(),
                 'message':'En attente du worker. Import du catalogue sans appel IA.'}
        kararecall.write_json(root/'data/control/history.json',current)
        return current


def update_history(root,**fields):
    with locked(root,'state.lock'):
        current=history_status(root);current.update(fields,updated_at=now())
        kararecall.write_json(root/'data/control/history.json',current)
        return current


def process_history(settings,import_catalog):
    """A surviving running request resumes after restart; catalogue import is idempotent."""
    if history_status(settings.root)['state'] not in ('queued','running'):return False
    try:
        with locked(settings.root,'runner.lock',blocking=False):
            if history_status(settings.root)['state'] not in ('queued','running'):return False
            update_history(settings.root,state='running',started_at=now(),collected=0,
                           message='Lecture de tout l’historique Karakeep, sans appel IA.')
            try:
                result=import_catalog(settings,catalog_only=True)
                update_history(settings.root,state='completed',completed_at=now(),**result,
                    message=('Catalogue importé. L’automatisation reste suspendue ; les traitements manuels sont disponibles.' if library_paused(settings.root) else 'Catalogue importé. Les analyses configurées suivront par lots si la synchronisation est activée.'))
            except Exception as exc:
                from kararecall.worker import safe_error
                update_history(settings.root,state='error',completed_at=now(),message=safe_error(exc,settings))
            return True
    except BlockingIOError:return False


def library_paused(root):
    return kararecall.read_json(root/'data/control/library.json',{}).get('paused',False)


def action_status(root):
    value=kararecall.read_json(root/'data/control/actions.json',{'jobs':[]})
    return {**value,'library_paused':library_paused(root)}


def request_action(root,kind,source_id=None,tool_id=None,confirmation=None,stage='all'):
    from kararecall.publication import active_root
    if kind not in ('llm','refresh','research','clear','check','sync_check'):raise ValueError('Commande inconnue.')
    if kind in ('check','sync_check') and (source_id or tool_id):raise ValueError('Le contrôle porte sur le catalogue ou les connexions configurées.')
    if stage not in ('all','asr','vision','document','llm') or (kind!='refresh' and stage!='all'):raise ValueError('Étape de reprise invalide.')
    if source_id is not None and (not isinstance(source_id,str) or len(source_id)>150):raise ValueError('Source invalide.')
    if tool_id is not None and (kind!='research' or not isinstance(tool_id,str)):raise ValueError('Outil invalide.')
    if kind=='clear' and (confirmation!='VIDER' or source_id or tool_id):raise ValueError('Confirmation VIDER requise.')
    with locked(root,'state.lock'):
        data=action_status(root);jobs=data['jobs']
        if kind!='clear' and any(row['kind']=='clear' and row['state'] in ('queued','running') for row in jobs):
            raise ValueError('Le vidage de la bibliothèque est en cours.')
        current=next((row for row in jobs if row['kind']==kind and row.get('source_id')==source_id and row.get('tool_id')==tool_id and row.get('stage','all')==stage and row['state'] in ('queued','running','paused')),None)
        if current:return current
        if kind!='clear' and sum(row['state'] in ('queued','running','paused') for row in jobs)>=10:raise ValueError('La file contient déjà dix commandes actives.')
        catalogue=kararecall.read_json(active_root(root)/'data/catalog.json',{'sources':[],'entities':[]})
        if source_id and not any(row['id']==source_id for row in catalogue['sources']):raise ValueError('Source absente de la bibliothèque.')
        if kind=='refresh' and not source_id:raise ValueError('Une source est requise pour actualiser.')
        if kind in ('check','sync_check'):ids=['connections' if kind=='check' else 'catalogue']
        elif kind=='research':
            ids=[row['id'] for row in catalogue['entities'] if not tool_id or row['id']==tool_id]
        else:ids=[row['id'] for row in catalogue['sources'] if not source_id or row['id']==source_id]
        if kind!='clear' and not ids:raise ValueError('Aucun élément à traiter ; importer les sources d’abord.')
        if kind=='clear':
            for row in jobs:
                if row['state'] in ('queued','running','paused'):row.update(state='cancelled',message='Annulée par le vidage.')
            history=history_status(root)
            if history['state'] in ('queued','running'):
                history.update(state='cancelled',message='Import annulé par le vidage.')
                kararecall.write_json(root/'data/control/history.json',history)
            kararecall.write_json(root/'data/control/library.json',{'paused':True,'reason':'cleared'})
            ids=['library']
        job={'id':uuid.uuid4().hex,'kind':kind,'source_id':source_id,'tool_id':tool_id,'stage':stage,'ids':ids,
             'state':'queued','cursor':0,'total':len(ids),'failed':0,'requested_at':now(),
             'message':'Commande enregistrée ; en attente du worker.'}
        active=[row for row in jobs if row['state'] in ('queued','running','paused')]
        history=[row for row in jobs if row['state'] not in ('queued','running','paused')][-20:]
        kararecall.write_json(root/'data/control/actions.json',{'jobs':history+active+[job]})
        return job


def _update_action(root,identifier,**changes):
    with locked(root,'state.lock'):
        data=action_status(root)
        for row in data['jobs']:
            if row['id']==identifier and row['state']!='cancelled':row.update(changes,updated_at=now())
        kararecall.write_json(root/'data/control/actions.json',{'jobs':data['jobs']})


def process_actions(settings):
    """One resumable item per pass; explicit commands work without periodic sync."""
    from kararecall.worker import safe_error, run_cycle, run_local_llm, clear_library, check_connections
    from kararecall.web_research import run_research
    from kararecall.usage import BudgetExceeded
    from dataclasses import replace
    try:
        with locked(settings.root,'actions-runner.lock',blocking=False):
            jobs=action_status(settings.root)['jobs']
            job=next((row for row in jobs if row['state'] in ('queued','running','paused') and row.get('retry_at',0)<=time.time()),None)
            if not job:return False
            identifier=job['id'];index=job['cursor'];target=job['ids'][index]
            errors=job.get('errors',[])
            _update_action(settings.root,identifier,state='running',message=f'Traitement {index+1} sur {job["total"]}.')
            try:
                if job['kind']=='clear':clear_library(settings)
                elif job['kind']=='sync_check':
                    from kararecall.synchronization import check
                    check(settings)
                elif job['kind']=='check':
                    try:
                        checked=check_connections(settings)
                        kararecall.write_json(settings.root/'data/connection-check.json',{'state':'completed','checked_at':now(),'results':checked})
                    except Exception as exc:
                        kararecall.write_json(settings.root/'data/connection-check.json',{'state':'error','checked_at':now(),'message':safe_error(exc,settings)})
                        raise
                elif job['kind']=='llm':run_local_llm(settings,target,identifier)
                elif job['kind']=='refresh':
                    result=run_cycle(replace(settings,sync_enabled=True),force_id=target,force_stage='resume' if job.get('resuming') else job.get('stage','all'))
                    if result['failed']:
                        from kararecall.publication import active_root
                        sources=kararecall.read_json(active_root(settings.root)/'data/sources.json',[])
                        source=next((row for row in sources if row['id']==target),{})
                        stages=source.get('stages',{}).values()
                        if 'paused' in stages and 'failed' not in stages:raise BudgetExceeded('Quota IA atteint.')
                        raise ValueError('Actualisation partielle ; consulter les étapes de cette source.')
                else:
                    result=run_research(replace(settings,web_research_enabled=True),target)
                    if result['state']=='paused':raise BudgetExceeded('Quota IA atteint.')
                    if result['state'] in ('error','disabled','busy','retry'):raise ValueError('Recherche non terminée ; consulter son état et la configuration.')
                failed=job['failed'];message='Traitement terminé.'
            except BudgetExceeded:
                _update_action(settings.root,identifier,state='paused',resuming=True,retry_at=time.time()+60,message='Quota IA atteint ; reprise automatique après renouvellement.')
                return True
            except Exception as exc:
                failed=job['failed']+1;message=safe_error(exc,settings)
                errors=(errors+[{'id':target,'message':message}])[-20:]
            # A concurrent clear request can cancel this action while a call is in flight.
            _update_action(settings.root,identifier,cursor=index+1,failed=failed,errors=errors,resuming=False,retry_at=0,
                           state=('error' if failed else 'completed') if index+1==job['total'] else 'queued',message=message)
            return True
    except BlockingIOError:return False


def cancel_action(root,identifier):
    with locked(root,'state.lock'):
        data=action_status(root)
        job=next((row for row in data['jobs'] if row['id']==identifier),None)
        if not job:raise ValueError('Commande introuvable.')
        if job['kind']=='clear':raise ValueError('Un vidage confirmé ne peut pas être annulé dans cette file.')
        if job['state'] in ('queued','running','paused'):
            job.update(state='cancelled',updated_at=now(),message='Suite de la commande annulée. Une opération déjà engagée peut se terminer.')
            kararecall.write_json(root/'data/control/actions.json',{'jobs':data['jobs']})
        return job


def pause_automation(root,paused):
    if type(paused) is not bool:raise ValueError('État de suspension invalide.')
    with locked(root,'state.lock'):
        if not paused and any(row['kind']=='clear' and row['state'] in ('queued','running') for row in action_status(root)['jobs']):
            raise ValueError('Attendre la fin du vidage avant de reprendre.')
        kararecall.write_json(root/'data/control/library.json',{'paused':paused,'reason':'manual' if paused else None,'updated_at':now()})
    return {'paused':paused}
