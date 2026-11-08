#!/usr/bin/env python3
"""Check bilingual public documentation locally, without fetching external URLs."""
import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT=Path(__file__).resolve().parents[1]


def anchors(path):
    result=set();counts={};fenced=False
    for line in path.read_text().splitlines():
        if line.startswith('```'):fenced=not fenced;continue
        if fenced:continue
        match=re.match(r'^#{1,6}\s+(.+)',line)
        if match:
            title=re.sub(r'\[([^]]+)\]\([^)]*\)',r'\1',match[1])
            slug=re.sub(r'[^\w\- ]','',html.unescape(title).lower()).replace(' ','-')
            count=counts.get(slug,0);counts[slug]=count+1
            result.add(slug+(('-'+str(count)) if count else ''))
        result.update(re.findall(r'\bid=["\']([^"\']+)',line))
    return result


def check(root=ROOT):
    manifest=json.loads((root/'docs/languages.json').read_text());errors=[];pages=[]
    for pair in manifest['pages']:
        for language in ('fr','en'):
            path=root/pair[language];pages.append(path)
            if not path.is_file():errors.append('Missing translated page: '+pair[language]);continue
            text=path.read_text()
            if '🇫🇷' not in text or '🇬🇧' not in text:errors.append('Missing language navigation: '+pair[language])
    for path in pages:
        if not path.is_file():continue
        text=re.sub(r'```.*?```','',path.read_text(),flags=re.S)
        links=re.findall(r'\[[^\]]*\]\(([^)]+)\)',text)
        links+=re.findall(r'(?:href|src)=["\']([^"\']+)',text)
        for link in links:
            link=html.unescape(link.strip().strip('<>'))
            parts=urlsplit(link)
            if parts.scheme or parts.netloc:continue
            target=(path.parent/unquote(parts.path)).resolve() if parts.path else path.resolve()
            if not target.is_relative_to(root.resolve()) or not target.exists():
                errors.append(str(path.relative_to(root))+': missing target '+link);continue
            if parts.fragment and target.suffix=='.md' and unquote(parts.fragment) not in anchors(target):
                errors.append(str(path.relative_to(root))+': missing anchor '+link)
    fr=(root/'docs/BACKLOG.md').read_text();en=(root/'docs/en/backlog.md').read_text()
    if len(re.findall(r'^- \[ \]',fr,re.M))!=len(re.findall(r'^- \[ \]',en,re.M)):
        errors.append('French and English remaining backlog counts differ')
    return {'pages':len(pages),'errors':errors}


if __name__=='__main__':
    report=check();print(json.dumps(report,ensure_ascii=False,indent=2))
    sys.exit(bool(report['errors']))
