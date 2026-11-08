#!/usr/bin/env python3
"""Read-only verification of a live or restored corpus; no network or inference."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import kararecall
import digests
from publication import active_root,file_hash
from worker_documents import attachment_target


def verify(root):
    selected=active_root(root)
    catalog=kararecall.read_json(selected/'data/catalog.json')
    if not isinstance(catalog,dict):raise ValueError('Catalogue absent')
    lookup={source['id']:source for source in catalog['sources']}
    for source in catalog['sources']:kararecall.validate_reading(source,lookup)
    for entity in catalog['entities']:kararecall.validate_entity(entity,lookup,selected)
    proofs=0
    checked_attachments={}
    for source in catalog['sources']:
        sid=source['id']
        raw=(selected/source['raw_file']).resolve()
        raw.relative_to((selected/'data/raw').resolve())
        if not raw.is_file():raise ValueError('Réponse source manquante')
        if source.get('preview'):
            from source_enrichment import preview_target
            if not preview_target(selected,source):raise ValueError('Aperçu manquant ou incohérent')
        if source.get('page_origin'):
            page=source['page_origin'];target=(selected/page['file']).resolve()
            target.relative_to((selected/'data/raw/api').resolve())
            if not target.is_file() or file_hash(target)!=page['sha256']:raise ValueError('HTML source manquant ou incohérent')
        media=selected/'data/media'/(sid+'.mp4')
        expected=source['processing'].get('media_sha256')
        if expected and (not media.is_file() or file_hash(media)!=expected):raise ValueError('Empreinte média incohérente')
        attachments=[source['processing'].get('attachment'),*(e.get('attachment') for e in source['evidence'])]
        for attachment in filter(None, attachments):
            target=attachment_target(selected,sid,attachment)
            if target not in checked_attachments:checked_attachments[target]=file_hash(target)
            if checked_attachments[target]!=attachment['sha256']:raise ValueError('Empreinte de pièce jointe incohérente')
        for evidence in source['evidence']:
            proofs+=1
            if source.get('evidence_schema')==2:
                identity={k:v for k,v in evidence.items() if k not in ('id','legacy_id','archived')}
                digest=hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                if evidence['id']!=evidence['kind']+'-'+digest:raise ValueError('Preuve versionnée modifiée')
            if evidence.get('image'):
                image=(selected/evidence['image']).resolve()
                if not any(image.is_relative_to((selected/'data'/kind/sid).resolve()) for kind in ('extracted','evidence')):raise ValueError('Chemin image non autorisé')
                if not image.is_file():raise ValueError('Image de preuve manquante')
                if '/evidence/' in evidence['image'] and image.stem!=file_hash(image):raise ValueError('Image versionnée modifiée')
    for name in ('worker.sqlite','usage.sqlite'):
        path=root/'data'/name
        if path.exists():
            connection=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
            try:
                if connection.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('État SQLite incohérent')
            finally:connection.close()
    editions=digests.list_editions(root)
    for edition in editions:
        for item in edition['items']:
            if item['image']:digests.image_bytes(root,item['image'])
    return {'status':'ok','versioned':selected!=root,'sources':len(lookup),'tools':len(catalog['entities']),
            'proofs':proofs,'digests':len(editions)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=kararecall.ROOT)
    args=parser.parse_args()
    try:print(json.dumps(verify(args.root.resolve()),ensure_ascii=False))
    except (ValueError,OSError,KeyError,sqlite3.Error):
        print(json.dumps({'status':'error','message':'Corpus incomplet ou incohérent ; conserver la sauvegarde et vérifier les fichiers.'},ensure_ascii=False))
        raise SystemExit(1)


if __name__=='__main__':main()
