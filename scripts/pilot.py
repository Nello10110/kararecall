#!/usr/bin/env python3
"""Shareable local pilot diagnostics. Optional Karakeep probes use GET only."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import kararecall
from integrations import Karakeep, ServiceError, normalize_bookmark
from publication import active_root
from settings import Settings


def counts(sources):
    return {'total':len(sources),'types':dict(Counter(row.get('bookmark_type','link') for row in sources)),
            'sans_texte_de_page':sum(not row.get('page_text') for row in sources),
            'videos_jointes':sum(any(asset.get('type')=='video' for asset in row.get('assets',[])) for row in sources),
            'documents_joints':sum(bool(row.get('document_asset_id')) for row in sources)}


def probe(settings, with_media):
    if not settings.karakeep_url or not settings.karakeep_key:
        raise ServiceError('Renseigner les accès Karakeep dans .env.')
    client=Karakeep(settings)
    started=time.monotonic()
    unique={}
    for bookmark in client.bookmarks():
        row=normalize_bookmark(bookmark)
        unique[row['id']]=row
    report={**counts(list(unique.values())),'lecture_secondes':round(time.monotonic()-started,2)}
    if with_media:
        candidates=[]
        for row in unique.values():
            for asset in row.get('assets',[]):
                if asset['type']=='video':candidates.append((asset['id'],'video'))
            if row.get('document_asset_id'):candidates.append((row['document_asset_id'],row['asset_type']))
            if len(candidates)>=3:break
        report['media']={'state':'absent' if not candidates else 'failed'}
        work=settings.root/'data/work';work.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work,prefix='pilot-') as name:
            for identifier,kind in candidates[:3]:
                target=Path(name)/'asset'
                started=time.monotonic()
                try:
                    client.download(identifier,target,max_mb=20)
                except ServiceError:
                    continue
                report['media']={'state':'downloaded','kind':kind,'bytes':target.stat().st_size,
                                 'secondes':round(time.monotonic()-started,2)}
                break
    return report


def benchmark(catalog, questions):
    if not isinstance(questions,list) or not 1<=len(questions)<=200:
        raise ValueError('Fichier de questions invalide.')
    known={row['id'] for row in catalog['sources']}
    ranks=[]
    for case in questions:
        if not isinstance(case,dict):raise ValueError('Cas de recherche invalide.')
        query=case.get('query')
        expected=case.get('source_id')
        if not isinstance(query,str) or not 1<=len(query.strip())<=1000 or not isinstance(expected,str) or expected not in known:
            raise ValueError('Chaque cas exige une requête et une source présente dans le catalogue.')
        results=kararecall.search(query,catalog,3)
        ranks.append(next((rank for rank,row in enumerate(results,1) if expected in row['source_ids']),None))
    return {'questions':len(ranks),'top_1':ranks.count(1),'top_3':sum(rank is not None for rank in ranks),'ranks':ranks}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe-karakeep',action='store_true',help='Lire le catalogue réel en GET')
    parser.add_argument('--probe-media',action='store_true',help='Télécharger temporairement un original de 20 Mio maximum')
    parser.add_argument('--questions',type=Path,help='Fichier local de questions pour mesurer la recherche')
    args=parser.parse_args()
    settings=Settings.from_env()
    root=active_root(settings.root)
    catalog=kararecall.read_json(root/'data/catalog.json',{'sources':[],'entities':[]})
    disk=shutil.disk_usage(settings.root)
    report={'catalogue':counts(catalog['sources']),'fiches':len(catalog['entities']),
            'volume_mio_libres':disk.free//(1024*1024),
            'usage':kararecall.read_json(settings.root/'data/usage-summary.json',{})}
    if args.probe_karakeep or args.probe_media:report['karakeep']=probe(settings,args.probe_media)
    if args.questions:report['recherche']=benchmark(catalog,kararecall.read_json(args.questions))
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:
        main()
    except (OSError,ServiceError,ValueError) as exc:
        message=str(exc) if isinstance(exc,ServiceError) else 'Impossible de lire les données ou la configuration du pilote.'
        print(json.dumps({'state':'error','message':message},ensure_ascii=False))
        raise SystemExit(1)
