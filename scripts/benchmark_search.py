#!/usr/bin/env python3
"""Reproducible lexical baseline on 20 fictional documents, without LLMs."""
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kararecall import core as kararecall
from kararecall.integrations import normalize_bookmark
from scripts.pilot import benchmark


def reference():
    rows=json.loads((Path(__file__).resolve().parents[1]/'benchmarks/search_memories.json').read_text())
    with tempfile.TemporaryDirectory() as name:
        root=Path(name);sources=[];questions=[]
        for row in rows:
            raw={'id':row['id'],'title':row['title'],'createdAt':'2026-11-08T12:00:00Z',
                 'content':{'type':'link','url':'https://example.org/'+row['id'],'text':row['text']},'assets':[]}
            source=normalize_bookmark(raw);sources.append(source);kararecall.write_json(root/source['raw_file'],raw)
            questions.append({'query':row['question'],'source_id':row['id']})
        kararecall.write_json(root/'data/sources.json',sources);kararecall.write_json(root/'data/entities.json',[])
        kararecall.build(root)
        result=benchmark(kararecall.read_json(root/'data/catalog.json'),questions)
    return {'dataset':'20 fictional documents, no generated tool cards','search_mode':'lexical',
            'target_top_3':16,'nas_validation':False,**result}


if __name__=='__main__':print(json.dumps(reference(),ensure_ascii=False,indent=2))
