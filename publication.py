"""Immutable publication generations; a single atomic pointer selects the visible corpus."""
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import re
import shutil
import uuid


def active_root(root):
    import kararecall
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


def file_hash(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


@contextmanager
def generation(root):
    """Copy mutable files, share immutable media, discard only our unpublished draft."""
    (root/'data').mkdir(parents=True,exist_ok=True)
    lease=(root/'data/publication.lock').open('a')
    fcntl.flock(lease,fcntl.LOCK_EX)
    origin=active_root(root)
    draft=root/'data/generations'/uuid.uuid4().hex
    (draft/'data').mkdir(parents=True)
    published=False
    try:
        for name in ('sources.json','entities.json','last-process.json'):
            source=origin/'data'/name
            if source.is_file():shutil.copy2(source,draft/'data'/name)
        for name in ('raw','media','evidence','verification','extracted'):
            source=origin/'data'/name
            if source.is_dir():
                # Extraction scripts can overwrite JPEGs in place; never hardlink those.
                if name=='extracted':
                    copier=shutil.copy2
                else:
                    def copier(src,dst):
                        import os
                        try:os.link(src,dst)
                        except OSError:shutil.copy2(src,dst)
                shutil.copytree(source,draft/'data'/name,copy_function=copier)
        def commit():
            nonlocal published
            import kararecall
            sources=kararecall.read_json(draft/'data/sources.json',[])
            for source in sources:
                if source.get('evidence_schema')==2:
                    evidence,_=kararecall.load_evidence(source,draft)
                    source['evidence_archive']=[{k:v for k,v in row.items() if k!='archived'} for row in evidence]
            kararecall.write_json(draft/'data/sources.json',sources)
            kararecall.build(draft)  # Validate all references before making any new file visible.
            relative=str(draft.relative_to(root))
            try:
                kararecall.write_json(root/'data/current.json',{'schema_version':2,'generation':relative})
            finally:
                # Even an exception just after rename must not delete a selected generation.
                try:published=kararecall.read_json(root/'data/current.json',{}).get('generation')==relative
                except (OSError,ValueError):published=True
        yield draft,commit
    finally:
        if not published:
            shutil.rmtree(draft,ignore_errors=True)
        fcntl.flock(lease,fcntl.LOCK_UN)
        lease.close()


def freeze(source,evidence,root):
    """Content-address each proof, preserve its origin and immutable screenshot."""
    import kararecall
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
    import kararecall
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
