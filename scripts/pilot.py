#!/usr/bin/env python3
"""Shareable local pilot diagnostics. Optional Karakeep probes use GET only."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import shutil
import sqlite3
from statistics import median
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import base64
import os

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kararecall import core as kararecall
from kararecall.integrations import Karakeep, ServiceError, normalize_bookmark
from kararecall.publication import active_root
from kararecall.settings import Settings
from kararecall.content_support import inventory


def usage_since(root, instant):
    moment=datetime.fromisoformat(instant.replace('Z','+00:00'))
    if moment.tzinfo is None:raise ValueError('Le début du lot exige un fuseau horaire.')
    path=root/'data/usage.sqlite'
    result={'since':moment.astimezone(timezone.utc).isoformat(),'observed':path.is_file(),'calls':0,'accounted_usd':0,'measured_usd':None,'stages':{}}
    if not path.is_file():return result
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        rows=db.execute('SELECT stage,state,accounted_usd,measured_usd FROM calls WHERE julianday(started)>=julianday(?)',(result['since'],)).fetchall()
    measured=[]
    for stage,state,accounted,cost in rows:
        safe=stage if stage in ('asr','vision','llm','translation','digest','research','research.search','research.fetch') else 'other'
        row=result['stages'].setdefault(safe,{'calls':0,'accounted_usd':0,'uncertain':0})
        row['calls']+=1;row['accounted_usd']+=accounted or 0;row['uncertain']+=state in ('uncertain','reserved')
        result['calls']+=1;result['accounted_usd']+=accounted or 0
        if cost is not None:measured.append(cost)
    if measured:result['measured_usd']=sum(measured)
    result['accounted_usd']=round(result['accounted_usd'],6)
    for row in result['stages'].values():row['accounted_usd']=round(row['accounted_usd'],6)
    return result


def http_benchmark(base):
    parsed=urlsplit(base)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Adresse HTTP du pilote invalide.')
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    headers={}
    username,password=os.getenv('KARARECALL_USERNAME',''),os.getenv('KARARECALL_PASSWORD','')
    if username and password:headers['Authorization']='Basic '+base64.b64encode((username+':'+password).encode()).decode()
    report=[]
    for route in ('/api/catalog?compact=1','/api/sources?limit=24','/api/overview'):
        times=[];sizes=[]
        for _ in range(3):
            started=time.monotonic()
            with build_opener(NoRedirect()).open(Request(base.rstrip('/')+route,headers=headers),timeout=15) as response:
                raw=response.read(20*1024*1024+1)
                if len(raw)>20*1024*1024:raise ValueError('Réponse HTTP du pilote trop volumineuse.')
                json.loads(raw)
            times.append((time.monotonic()-started)*1000);sizes.append(len(raw))
        report.append({'route':route,'bytes_max':max(sizes),'median_ms':round(median(times),1),'max_ms':round(max(times),1)})
    return report


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
    timings=[]
    for case in questions:
        if not isinstance(case,dict):raise ValueError('Cas de recherche invalide.')
        query=case.get('query')
        expected=case.get('source_id')
        if not isinstance(query,str) or not 1<=len(query.strip())<=1000 or not isinstance(expected,str) or expected not in known:
            raise ValueError('Chaque cas exige une requête et une source présente dans le catalogue.')
        started=time.monotonic()
        results=kararecall.search(query,catalog,3)
        timings.append((time.monotonic()-started)*1000)
        ranks.append(next((rank for rank,row in enumerate(results,1) if expected in row['source_ids']),None))
    return {'questions':len(ranks),'top_1':ranks.count(1),'top_3':sum(rank is not None for rank in ranks),'ranks':ranks,
            'latence_mediane_ms':round(median(timings),1),'latence_max_ms':round(max(timings),1)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe-karakeep',action='store_true',help='Lire le catalogue réel en GET')
    parser.add_argument('--probe-media',action='store_true',help='Télécharger temporairement un original de 20 Mio maximum')
    parser.add_argument('--questions',type=Path,help='Fichier local de questions pour mesurer la recherche')
    parser.add_argument('--usage-since',help='Coût du lot depuis une date ISO avec fuseau, sans appel IA')
    parser.add_argument('--http-url',help='Mesurer trois routes HTTP, sans en conserver les contenus')
    args=parser.parse_args()
    settings=Settings.from_env()
    root=active_root(settings.root)
    catalog=kararecall.read_json(root/'data/catalog.json',{'sources':[],'entities':[]})
    disk=shutil.disk_usage(settings.root)
    report={'catalogue':counts(catalog['sources']),'fiches':len(catalog['entities']),
            'couverture':inventory(catalog['sources']),
            'volume_mio_libres':disk.free//(1024*1024),
            'usage':kararecall.read_json(settings.root/'data/usage-summary.json',{})}
    if args.probe_karakeep or args.probe_media:report['karakeep']=probe(settings,args.probe_media)
    if args.usage_since:report['lot_ia']=usage_since(settings.root,args.usage_since)
    if args.http_url:report['http']=http_benchmark(args.http_url)
    if args.questions:
        report['recherche']=benchmark(catalog,kararecall.read_json(args.questions))
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report['recherche']['memoire_processus_max_mio']=round(peak/(1024**2 if sys.platform=='darwin' else 1024),1)
    timing=kararecall.read_json(settings.root/'data/service-status.json',{}).get('publication_timing')
    if timing:report['derniere_publication']=timing
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:
        main()
    except (OSError,ServiceError,ValueError,sqlite3.Error) as exc:
        message=str(exc) if isinstance(exc,ServiceError) else 'Impossible de lire les données ou la configuration du pilote.'
        print(json.dumps({'state':'error','message':message},ensure_ascii=False))
        raise SystemExit(1)
