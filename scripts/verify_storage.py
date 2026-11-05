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
from publication import active_root,file_hash


def verify(root):
    selected=active_root(root)
    catalog=kararecall.read_json(selected/'data/catalog.json')
    if not isinstance(catalog,dict):raise ValueError('Catalogue absent')
    lookup={source['id']:source for source in catalog['sources']}
    for source in catalog['sources']:kararecall.validate_reading(source,lookup)
    for entity in catalog['entities']:kararecall.validate_entity(entity,lookup,selected)
    proofs=0
    for source in catalog['sources']:
        sid=source['id']
        raw=(selected/source['raw_file']).resolve()
        raw.relative_to((selected/'data/raw').resolve())
        if not raw.is_file():raise ValueError('Réponse source manquante')
        media=selected/'data/media'/(sid+'.mp4')
        expected=source['processing'].get('media_sha256')
        if expected and (not media.is_file() or file_hash(media)!=expected):raise ValueError('Empreinte média incohérente')
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
    return {'status':'ok','versioned':selected!=root,'sources':len(lookup),'tools':len(catalog['entities']),'proofs':proofs}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=kararecall.ROOT)
    args=parser.parse_args()
    try:print(json.dumps(verify(args.root.resolve()),ensure_ascii=False))
    except (ValueError,OSError,KeyError,sqlite3.Error):
        print(json.dumps({'status':'error','message':'Corpus incomplet ou incohérent ; conserver la sauvegarde et vérifier les fichiers.'},ensure_ascii=False))
        raise SystemExit(1)


if __name__=='__main__':main()
