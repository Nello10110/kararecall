"""Durable local import requests. No credentials and no writes to Karakeep."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import uuid

import cerveau


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
    return cerveau.read_json(root/'data/control/history.json',{'state':'none'})


def request_history(root):
    with locked(root,'state.lock'):
        current=history_status(root)
        if current['state'] in ('queued','running'):return current
        current={'id':uuid.uuid4().hex,'state':'queued','requested_at':now(),
                 'message':'En attente du worker. Import du catalogue sans appel IA.'}
        cerveau.write_json(root/'data/control/history.json',current)
        return current


def update_history(root,**fields):
    with locked(root,'state.lock'):
        current=history_status(root);current.update(fields,updated_at=now())
        cerveau.write_json(root/'data/control/history.json',current)
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
                    message='Catalogue importé. Les analyses configurées suivront par lots si la synchronisation est activée.')
            except Exception as exc:
                from worker import safe_error
                update_history(settings.root,state='error',completed_at=now(),message=safe_error(exc,settings))
            return True
    except BlockingIOError:return False
