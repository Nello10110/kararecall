"""Immutable publication generations; a single atomic pointer selects the visible corpus."""
from contextlib import contextmanager
from collections import OrderedDict
import copy
import fcntl
import hashlib
import os
import re
import shutil
from threading import Lock
from time import monotonic
import uuid


def active_root(root):
    from kararecall import core as kararecall
    pointer=kararecall.read_json(root/'data/current.json',{})
    if not pointer:
        return root
    relative=pointer.get('generation','')
    if not re.fullmatch(r'data/generations/[a-f0-9]{32}',relative):
        raise ValueError('Pointeur de publication non valide')
    target=root/relative
    if not (target/'data/catalog.json').is_file():
        raise ValueError('Publication absente ou incomplète')
    return target


HASH_CACHE_SIZE = 16384
_hash_cache = OrderedDict()
_hash_lock = Lock()


def _file_identity(stat):
    return stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns


def _cached_hash(identity):
    with _hash_lock:
        value=_hash_cache.get(identity)
        if value is not None:
            _hash_cache.move_to_end(identity)
        return value


def _remember_hash(identity, digest):
    with _hash_lock:
        _hash_cache[identity]=digest
        _hash_cache.move_to_end(identity)
        if len(_hash_cache)>HASH_CACHE_SIZE:
            _hash_cache.popitem(last=False)


def _hash_stream(stream):
    digest=hashlib.sha256()
    for block in iter(lambda:stream.read(1024*1024),b''):
        digest.update(block)
    return digest.hexdigest()


def file_hash(path):
    with path.open('rb') as stream:
        identity=_file_identity(os.fstat(stream.fileno()))
        digest=_cached_hash(identity)
        if digest is None:
            digest=_hash_stream(stream)
            if _file_identity(os.fstat(stream.fileno()))!=identity:
                raise ValueError('Fichier modifié pendant la vérification de son empreinte.')
            _remember_hash(identity,digest)
    return digest


def share_immutable(src,dst):
    try:
        before=os.stat(src)
        identity=_file_identity(before)
        os.link(src,dst)
    except OSError:
        return shutil.copy2(src,dst)
    # Creating a hard link updates ctime even when bytes are unchanged.
    after=os.stat(dst)
    linked=_file_identity(after)
    known=_cached_hash(identity)
    if known is not None and linked[:-1]==identity[:-1] and after.st_nlink==before.st_nlink+1:
        _remember_hash(linked,known)
    return dst


@contextmanager
def generation(root, empty=False):
    """Copy mutable files, share immutable media, discard only our unpublished draft."""
    (root/'data').mkdir(parents=True,exist_ok=True)
    lease=(root/'data/publication.lock').open('a')
    fcntl.flock(lease,fcntl.LOCK_EX)
    origin=active_root(root)
    draft=root/'data/generations'/uuid.uuid4().hex
    (draft/'data').mkdir(parents=True)
    published=False
    try:
        copied_at=monotonic()
        for name in (() if empty else ('sources.json','entities.json','last-process.json')):
            source=origin/'data'/name
            if source.is_file():shutil.copy2(source,draft/'data'/name)
        for name in (() if empty else ('raw','media','documents','previews','evidence','verification','editorial','extracted')):
            source=origin/'data'/name
            if source.is_dir():
                # Extraction scripts can overwrite JPEGs in place; never hardlink those.
                copier=shutil.copy2 if name=='extracted' else share_immutable
                shutil.copytree(source,draft/'data'/name,copy_function=copier)
        copy_seconds=round(monotonic()-copied_at,3)
        def commit():
            nonlocal published
            from kararecall import core as kararecall
            started=monotonic()
            sources=kararecall.read_json(draft/'data/sources.json',[])
            prepared={}
            for source in sources:
                if source.get('evidence_schema')==2:
                    evidence,status=kararecall.load_evidence(source,draft)
                    source['evidence_archive']=[{k:v for k,v in row.items() if k!='archived'} for row in evidence]
                    prepared[source['id']]=(evidence,status)
            kararecall.write_json(draft/'data/sources.json',sources)
            kararecall.build(draft, prepared=prepared, previous_root=origin)
            relative=str(draft.relative_to(root))
            try:
                kararecall.write_json(root/'data/current.json',{'schema_version':2,'generation':relative})
            finally:
                # Even an exception just after rename must not delete a selected generation.
                try:published=kararecall.read_json(root/'data/current.json',{}).get('generation')==relative
                except (OSError,ValueError):published=True
            return {'copy_seconds':copy_seconds,'publish_seconds':round(monotonic()-started,3)}
        yield draft,commit
    finally:
        if not published:
            shutil.rmtree(draft,ignore_errors=True)
        fcntl.flock(lease,fcntl.LOCK_UN)
        lease.close()


def freeze(source,evidence,root):
    """Content-address each proof, preserve its origin and immutable screenshot."""
    from kararecall import core as kararecall
    result=[]
    for original in evidence:
        row=copy.deepcopy(original)
        row.pop('archived',None)
        legacy=row.pop('id')
        row.pop('legacy_id',None)
        row.setdefault('source_url',source['url'])
        row.setdefault('source_title',source['title'])
        row.setdefault('raw_file',source.get('raw_file',''))
        if row.get('image'):
            path=root/row['image']
            digest=file_hash(path)
            target=root/'data/evidence'/source['id']/(digest+path.suffix.lower())
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():shutil.copy2(path,target)
            row['image']=str(target.relative_to(root))
        identity=hashlib.sha256(__import__('json').dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        row['id']=row['kind']+'-'+identity
        row['legacy_id']=legacy
        result.append(row)
    return result


def migrate(sources,entities,root):
    """Bind legacy citations to their first frozen proof before any source is changed."""
    from kararecall import core as kararecall
    references={}
    for source in sources:
        if source.get('evidence_schema')==2:continue
        evidence,_=kararecall.load_evidence(source,root)
        frozen=freeze(source,evidence,root)
        for old,new in zip(evidence,frozen):
            references[source['id']+'#'+old['id']]=source['id']+'#'+new['id']
        source['evidence_schema']=2
        source['evidence_archive']=frozen
        if source.get('reading'):
            source['reading']['evidence']=[references.get(ref,ref) for ref in source['reading'].get('evidence',[])]
    for entity in entities:
        for claim in kararecall.entity_claims(entity):
            claim['evidence']=[references.get(ref,ref) for ref in claim.get('evidence',[])]
        for link in entity.get('links',[]):
            if link.get('evidence'):link['evidence']=references.get(link['evidence'],link['evidence'])
    return sources,entities
