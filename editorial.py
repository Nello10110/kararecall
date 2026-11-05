"""Versioned manual edits and explicit merges of local tool cards."""
from datetime import datetime, timezone
import copy
import fcntl
import hashlib
import json
import re
import uuid
from urllib.parse import urlsplit

import kararecall
from publication import active_root, generation


class EditConflict(ValueError):
    pass


def revision(entity):
    return hashlib.sha256(json.dumps(entity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def distinct(items):
    return list({json.dumps(item,sort_keys=True,ensure_ascii=False):item for item in items}.values())


def text(value, maximum, label):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum:
        raise ValueError(f'{label} manquant ou trop long.')
    return value.strip()


def edit_links(entity, requested, trace):
    if not isinstance(requested,list) or len(requested)>30:
        raise ValueError('Liste de liens invalide.')
    originals={}
    for link in entity.get('links',[]):
        originals.setdefault(link['url'],[]).append(link)
    result=[]
    for item in requested:
        if not isinstance(item,dict) or set(item)!={'label','url'}:
            raise ValueError('Lien incomplet.')
        url=text(item['url'],1000,'URL')
        label=text(item['label'],200,'Libellé')
        parsed=urlsplit(url)
        if (parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password
                or re.search(r'[\x00-\x20<>\\]',url)):
            raise ValueError('Les liens doivent être des URL HTTP(S) sans identifiants.')
        choices=originals.get(url,[])
        index=next((i for i,link in enumerate(choices) if link.get('label')==label),0)
        link=choices.pop(index) if choices else {'url':url,'status':'user_link_unchecked','reference_file':trace}
        result.append({**link,'label':label})
    return distinct(result)


def merge_cards(primary, other):
    primary['source_ids']=list(dict.fromkeys(primary['source_ids']+other['source_ids']))
    primary['claims']=distinct(primary['claims']+other['claims'])
    primary['links']=distinct(primary['links']+other['links'])
    primary['aliases']=list(dict.fromkeys(primary.get('aliases',[])+[other['name']]+other.get('aliases',[])))
    primary['merged_ids']=list(dict.fromkeys(primary.get('merged_ids',[])+[other['id']]+other.get('merged_ids',[])))
    for section,_ in kararecall.DETAIL_SECTIONS:
        left=primary.get('details',{}).get(section,[])
        right=other.get('details',{}).get(section,[])
        primary.setdefault('details',{})[section]=distinct(left+right)


def add_documentation(edited, original, documentation, reviewed):
    if documentation is None:
        return
    if not reviewed or not isinstance(documentation,dict) or set(documentation)!={'url','details'}:
        raise ValueError('Confirme la revue de la page avant d’ajouter des notes documentaires.')
    research=original.get('web_research',{})
    url=documentation['url']
    page=next((row for row in research.get('pages',[]) if row['url']==url and row['status']=='read' and row.get('excerpt')),None)
    if page is None:
        raise ValueError('La page choisie doit correspondre à une trace de lecture conservée.')
    notes=documentation['details']
    if not isinstance(notes,dict) or not notes or set(notes)-{key for key,_ in kararecall.DETAIL_SECTIONS}:
        raise ValueError('Notes documentaires invalides.')
    for section,value in notes.items():
        entry={'text':text(value,1600,'Note documentaire'),'status':'documented',
               'verification_url':url,'verification_file':research['trace_file']}
        rows=edited.setdefault('details',{}).setdefault(section,[])
        if entry not in rows:rows.append(entry)


def edit_tool(root, tool_id, payload):
    fields={'revision','name','description','aliases','details','links','reviewed','merge_id','merge_revision','documentation'}
    if not isinstance(payload,dict) or set(payload)-fields or type(payload.get('reviewed')) is not bool:
        raise ValueError('Modifications non valides.')
    (root/'data').mkdir(parents=True,exist_ok=True)
    with (root/'data/worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise EditConflict('Un traitement est en cours. Réessaie dans un instant.') from None
        selected=active_root(root)
        entities=kararecall.read_json(selected/'data/entities.json',[])
        lookup={entity['id']:entity for entity in entities}
        original=lookup.get(tool_id)
        if original is None:
            raise EditConflict('La fiche a changé ou a été regroupée. Recharge la page.')
        if revision(original)!=payload.get('revision'):
            raise EditConflict('La fiche a changé depuis son ouverture. Recharge-la avant d’enregistrer.')
        merge_id=payload.get('merge_id') or ''
        if not isinstance(merge_id,str) or merge_id==tool_id:
            raise ValueError('Fiche à regrouper invalide.')
        other=lookup.get(merge_id) if merge_id else None
        if merge_id and (other is None or revision(other)!=payload.get('merge_revision')):
            raise EditConflict('La fiche à regrouper a changé. Recharge la page.')
        edited=copy.deepcopy(original)
        stamp=datetime.now(timezone.utc).isoformat()
        trace=f'data/editorial/{uuid.uuid4().hex}.json'
        edited.update(name=text(payload.get('name'),200,'Nom'),description=text(payload.get('description'),8000,'Description'),
                      curation='user-reviewed' if payload['reviewed'] else 'user-edited',edited_at=stamp)
        aliases=payload.get('aliases')
        if not isinstance(aliases,list) or len(aliases)>100:
            raise ValueError('Repères de recherche invalides.')
        edited['aliases']=list(dict.fromkeys(text(item,200,'Repère') for item in aliases))
        details=payload.get('details')
        if not isinstance(details,dict) or set(details)!={key for key,_ in kararecall.DETAIL_SECTIONS}:
            raise ValueError('Rubriques de fiche invalides.')
        for section,label in kararecall.DETAIL_SECTIONS:
            rows=edited.get('details',{}).get(section,[])
            values=details[section]
            if not isinstance(values,list) or len(values)!=len(rows):
                raise ValueError('Le nombre de preuves par rubrique doit rester identique.')
            for row,value in zip(rows,values):
                row['text']=text(value,8000,label)
        edited['links']=edit_links(original,payload.get('links'),trace)
        add_documentation(edited,original,payload.get('documentation'),payload['reviewed'])
        if other:
            merge_cards(edited,other)
        history=list(original.get('editorial_history',[]))
        if other:history.extend(other.get('editorial_history',[]))
        edited['editorial_history']=list(dict.fromkeys(history+[trace]))
        # A changed identity will be researched again with its own cache key.
        from web_research import identity
        if identity(edited)!=identity(original):
            edited.pop('web_research',None)
        event={'edited_at':stamp,'before':original,'merged':other,'after':edited}
        with generation(root) as (draft,publish):
            kararecall.write_json(draft/trace,event)
            kararecall.write_json(draft/'data/entities.json',[
                edited if row['id']==tool_id else row for row in entities if row['id']!=merge_id])
            publish()
        return {'id':tool_id,'revision':revision(edited),'reviewed':payload['reviewed']}
