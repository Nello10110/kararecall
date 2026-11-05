#!/usr/bin/env python3
"""Portable knowledge vault: read-only imports, evidence, Markdown and local search.

The core only uses Python's standard library. ASR/OCR are optional workers.
"""
import argparse
from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

from settings import load_env
load_env()
ROOT = Path(os.getenv('MEMOIRE_ROOT',str(Path(__file__).resolve().parent))).resolve()
STOP = set("a au aux avec ce ces cet cette dans de des du elle en est et il je la le les leur lui ma mais me mes moi mon ne nos notre on ou par pas plus pour qu que quel quelle qui sa se ses si son sur ta te tes toi ton tu un une vos votre vous y outil outils video videos retrouve cherche recherche utilise utiliser permet faire comme comment c etait avait dont celui celle".split())
DETAIL_SECTIONS = [('description', 'Description'), ('usefulness', 'À quoi ça sert'),
                   ('operation', 'Comment ça fonctionne'), ('limitations', 'Limites et points à confirmer')]
STATUS_LABELS = {'source_claim': 'Selon la source', 'hypothesis': 'Hypothèse à confirmer',
                 'verified': 'Vérification externe', 'documented': 'Selon la documentation éditeur'}
LINK_LABELS = {'repository_exists': 'Dépôt trouvé', 'page_read': 'Page consultée',
               'source_link_unchecked': 'Relevé dans la source, accès non vérifié',
               'source_publication': 'Publication d’origine conservée dans Karakeep',
               'linked_from_official_page': 'Lien fourni par l’éditeur, page cible non relue',
               'not_found_at_check': 'Adresse en 404 lors de la vérification',
               'visible_in_video_unchecked': 'Vu dans la vidéo, accès non vérifié',
               'caption_mention_unchecked': 'Mentionné dans la légende, accès non vérifié'}


def entity_claims(entity):
    return entity['claims'] + [entry for key, _ in DETAIL_SECTIONS for entry in entity.get('details', {}).get(key, [])]


def coverage_notice(entity):
    if any(row.get('text_truncated') or row.get('included',0)<row.get('available',0) for row in entity.get('coverage',{}).values()):
        return 'Cette fiche repose sur une sélection d’extraits. Certains éléments des sources n’ont pas été pris en compte dans la synthèse.'
    return ''


def validate_reference(ref, lookup):
    sid, eid = ref.split('#', 1)
    if sid not in lookup or eid not in {e['id'] for e in lookup[sid]['evidence']}:
        raise ValueError(f'Preuve manquante: {ref}')


def validate_reading(source,lookup):
    reading=source.get('reading')
    if reading is None:return
    if not isinstance(reading,dict) or reading.get('status')!='source_claim' or not isinstance(reading.get('text'),str) or not reading['text'].strip() or not reading.get('evidence'):
        raise ValueError('Résumé de lecture sans attribution ou références')
    for ref in reading['evidence']:
        if not isinstance(ref,str) or not ref.startswith(source['id']+'#'):raise ValueError('Résumé lié à une autre source')
        validate_reference(ref,lookup)


def validate_entity(entity, lookup, root):
    for claim in entity_claims(entity):
        if claim['status'] not in STATUS_LABELS:
            raise ValueError('Unknown claim status')
        if claim['status'] in ('verified', 'documented'):
            url = claim.get('verification_url', '')
            if urlsplit(url).scheme not in ('https', 'http') or not urlsplit(url).netloc:
                raise ValueError('Une affirmation externe exige une URL source')
            trace = claim.get('verification_file', 'MISSING')
            if not (root / trace).is_file():
                raise ValueError('Une vérification exige une trace locale')
        elif not claim.get('evidence'):
            raise ValueError('Une affirmation exige une preuve')
        for ref in claim.get('evidence', []):
            validate_reference(ref, lookup)
    for link in entity.get('links', []):
        if urlsplit(link['url']).scheme not in ('http', 'https') or not urlsplit(link['url']).netloc:
            raise ValueError('Lien non HTTP(S) ou sans domaine')
        if link['status'] not in LINK_LABELS:
            raise ValueError('Statut de lien inconnu')
        if link.get('evidence'):
            validate_reference(link['evidence'], lookup)
        if link.get('reference_file'):
            if not (root / link['reference_file']).is_file():
                raise ValueError('Trace de lien manquante')
        elif not link.get('evidence'):
            raise ValueError('Un lien exige une provenance')


def render_claim(claim, lookup):
    lines = [f"**{STATUS_LABELS[claim['status']]}** — {claim['text']}", '']
    for ref in claim.get('evidence', []):
        sid, eid = ref.split('#')
        lines += [f"[Preuve {ref}](../sources/{sid}.md#{eid})"+(f" · [Source originale]({lookup[sid]['url']})" if lookup[sid]['url'] else '')+"  "]
    if claim.get('verification_url'):
        lines += [f"[Source externe]({claim['verification_url']}) · [Trace de lecture](../../{claim['verification_file']})  "]
    return lines + ['']


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix='.'+path.name+'-',suffix='.tmp',delete=False) as handle:
        tmp=Path(handle.name)
        try:
            handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def normalize(text):
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", normalize(text)) if len(t) > 1 and t not in STOP]


def parse_export(text):
    """Parse the connector's plain-text read response; preserve original alongside it."""
    for block in re.split(r"(?m)(?=^Bookmark ID: )", text):
        if not block.startswith("Bookmark ID: "):
            continue
        def field(name):
            m = re.search(r"(?m)^\s*" + re.escape(name) + r": (.*)$", block)
            return m.group(1).strip() if m else ""
        source_id = field("Bookmark ID")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", source_id):
            raise ValueError("Invalid bookmark ID")
        title = re.search(r"(?ms)^  Title: (.*?)\n  Archived:", block)
        content = re.search(r"(?ms)^  Content: (.*?)\n  Tags:", block)
        assets = [{"id": m[0], "type": m[1].split(",")[0]}
                  for m in re.findall(r"([a-f0-9-]{36}) \(([^)]+)\)", field("Assets"))]
        yield {"id": source_id, "url": field("Bookmarked URL"),
               "created_at": field("Created at"), "modified_at": field("Modified at"),
               "title": title.group(1) if title else field("Title"),
               "description": field("description"), "note": field("Note"),
               "tags": field("Tags").split(", ") if field("Tags") else [],
               "page_text": content.group(1) if content else "",
               "karakeep_summary_unverified": field("Summary"), "assets": assets}


def ingest(root=ROOT):
    sources = {}
    for path in sorted((root / "data/raw").glob("*.txt")):
        for source in parse_export(path.read_text()):
            # A modified record supersedes an earlier snapshot. Repeated ingestion is stable.
            previous = sources.get(source["id"])
            if previous and previous["modified_at"] > source["modified_at"]:
                continue
            source["raw_file"] = str(path.relative_to(root))
            sources[source["id"]] = source
    write_json(root / "data/sources.json", sorted(sources.values(), key=lambda s: s["id"]))
    return len(sources)


def load_evidence(source, root=ROOT):
    sid = source["id"]
    evidence = [{"id": "caption", "kind": "caption", "text": source["title"] + "\n" + source["description"]}]
    if source["page_text"]:
        kind={'text':'text','asset':'document'}.get(source.get('bookmark_type'),'page')
        evidence.append({"id":kind,"kind":kind,"text":source['page_text']})
    if source.get('note'):
        evidence.append({'id':'note','kind':'note','text':source['note']})
    directory = root / "data/extracted" / sid
    transcript = read_json(directory / "transcript.json", {})
    ocr = read_json(directory / "ocr.json", {})
    media = root / "data/media" / (sid + ".mp4")
    from publication import file_hash
    digest = file_hash(media) if media.exists() else None
    for artifact in (transcript, ocr):
        if artifact and (not digest or artifact.get("media_sha256") != digest):
            raise ValueError(f"Extraction périmée ou média absent: {sid}")
    for i, segment in enumerate(transcript.get("segments", [])):
        evidence.append({"id": f"asr-{i:03}", "kind": "asr", "text": segment["text"],
                         "start": segment["start"], "end": segment["end"],
                         "recognition":{key:transcript.get(key) for key in ('engine','model','cache_key')},"media_sha256":digest})
    for i, frame in enumerate(ocr.get("frames", [])):
        evidence.append({"id": f"ocr-{i:03}", "kind": "ocr", "start": frame["time"],
                         "text": "\n".join(line["text"] for line in frame["lines"]),
                         "image": str((directory / frame["image"]).relative_to(root)),
                         "recognition":{key:ocr.get(key) for key in ('engine','model','cache_key')},"media_sha256":digest})
    if source.get('evidence_schema')==2:
        from publication import freeze
        evidence=freeze(source,evidence,root)
        current={row['id'] for row in evidence}
        evidence += [dict(row,archived=True) for row in source.get('evidence_archive',[]) if row['id'] not in current]
    return evidence, {"media_downloaded": media.exists(), "media_sha256": digest,
                      "audio_transcribed": transcript.get("status") == "complete",
                      "ocr_sampled": ocr.get("status") == "complete",
                      "ocr_interval_seconds": ocr.get("interval"),
                      "duration_seconds": transcript.get("duration") or ocr.get("duration")}


def stamp(second):
    return f"{int(second)//60:02}:{second%60:04.1f}"


def memory_context(source):
    months = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
    date = datetime.fromisoformat(source['created_at'].replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Paris'))
    author = source['title'].split(' on Instagram:')[0]
    return f"{author} {date.day} {months[date.month-1]} {date.year} {source['created_at'][:10]}"


def candidates(catalog):
    found = {}
    for source in catalog['sources']:
        for ev in source['evidence']:
            if ev['kind'] == 'page':
                continue  # page text contains many unrelated CDN/profile links
            matches = re.findall(r"(?:https?://)?(?:[a-zA-Z0-9-]+\.)+(?:com|org|io|ai|fr|net|app|dev|ovh)(?:/[a-zA-Z0-9_./?=&%+-]*)?", ev['text'])
            # OCR often renders a GitHub breadcrumb without the full URL.
            for line in ev['text'].splitlines():
                breadcrumb = re.fullmatch(r'([a-zA-Z0-9_-]+)\s+/\s+([a-zA-Z0-9_-]+)(?: Public)?', line.strip().lstrip('() '))
                if breadcrumb:
                    matches.append('https://github.com/' + breadcrumb[1] + '/' + breadcrumb[2])
            for match in matches:
                value = match.rstrip('.,/')
                key = (value.lower(), source['id'])
                record = found.setdefault(key, {'value': value, 'source_id': source['id'], 'evidence': [], 'status': 'candidate_unverified'})
                if ev['id'] not in record['evidence']:
                    record['evidence'].append(ev['id'])
    return list(found.values())


def build(root=ROOT):
    sources = read_json(root / "data/sources.json", [])
    entities = read_json(root / "data/entities.json", [])
    catalog = {"schema_version": 1, "sources": [], "entities": entities}
    vault = root / "vault"
    (vault / "sources").mkdir(parents=True, exist_ok=True)
    (vault / "outils").mkdir(exist_ok=True)
    for source in sources:
        evidence, status = load_evidence(source, root)
        source = dict(source, evidence=evidence, processing=status)
        catalog["sources"].append(source)
    lookup = {s["id"]: s for s in catalog["sources"]}
    for source in catalog['sources']:validate_reading(source,lookup)
    # Fail closed: a synthesis may not cite a missing or stale piece of evidence.
    for entity in entities:
        if not re.fullmatch(r"[a-z0-9-]+", entity["id"]):
            raise ValueError("Invalid entity ID")
        validate_entity(entity, lookup, root)
    for source in catalog["sources"]:
        sid, status = source["id"], source["processing"]
        lines = ["---", f"id: {sid}", "type: source", f"saved_at: {source['created_at']}",
                 f"audio_transcribed: {str(status['audio_transcribed']).lower()}",
                 f"ocr_sampled: {str(status['ocr_sampled']).lower()}", "---", "",
                 "# " + source["title"].replace("\n", " ")[:180], "",
                 (f"[Source originale]({source['url']}) · " if source['url'] else '')+f"[Réponse Karakeep brute](../../{source['raw_file']})", "",
                 f"Enregistré : {source['created_at']} (UTC). Cette date n’est pas la date de publication.", "",
                 "## État de traitement", "",
                 f"Audio transcrit : {status['audio_transcribed']}. OCR échantillonné : {status['ocr_sampled']}."]
        if status["ocr_sampled"]:
            lines += [f"Une image toutes les {status['ocr_interval_seconds']} s ; du texte bref peut être manqué."]
        if source.get('content_status')=='metadata_only':
            lines += ['', 'Texte intégral indisponible dans Karakeep : seules les métadonnées sont conservées. Une pièce jointe non vidéo n’est pas analysée par ce worker.']
        if source.get('reading'):
            lines += ['', '## Résumé de lecture · à relire', '']+render_claim(source['reading'],lookup)
            if coverage_notice(source['reading']):lines += [coverage_notice(source['reading']),'']
        lines += ["", "Les transcriptions et l’OCR sont des extractions automatiques, à relire. Les propos de l’auteur ne sont pas des faits vérifiés.", "", "## Fiches liées", ""]
        related = [e for e in entities if sid in e["source_ids"]]
        lines += [f"- [{e['name']}](../outils/{e['id']}.md)" for e in related] or ["Aucune synthèse relue pour cette source."]
        lines += ["", "## Preuves", ""]
        for evidence in source["evidence"]:
            eid, kind = evidence["id"], evidence["kind"]
            if evidence.get('archived'):kind+=' · version antérieure conservée'
            lines += [f'<a id="{eid}"></a>', "", f"### {eid} · {kind}", ""]
            if "start" in evidence:
                lines += [f"[{stamp(evidence['start'])} · vidéo locale](../../data/media/{sid}.mp4#t={evidence['start']:.2f})", ""]
            if evidence.get("image"):
                lines += [f"[Image source](../../{evidence['image']})", ""]
            lines += ["> " + evidence["text"].replace("\n", "\n> "), ""]
        (vault / "sources" / (sid + ".md")).write_text("\n".join(lines))
    for entity in entities:
        lines = ["---", f"id: {entity['id']}", "type: tool", f"curation: {entity.get('curation','assistant-reviewed')}", "---", "",
                 "# " + entity["name"], "", entity["description"], "",
                 "Repères de recherche : " + ", ".join(entity.get("aliases", [])), "",
                 "Les informations sont attribuées à la vidéo ou à la documentation de l’éditeur. Une lecture documentaire ne constitue pas un essai du produit.", ""]
        if coverage_notice(entity):lines += [coverage_notice(entity),'']
        for key, title in DETAIL_SECTIONS:
            lines += [f'## {title}', '']
            for entry in entity.get('details', {}).get(key, []):
                lines += render_claim(entry, lookup)
            if not entity.get('details', {}).get(key):
                lines += ['Information à compléter à partir d’une source identifiable.', '']
        lines += ['## Identification et vérifications', '']
        for claim in entity["claims"]:
            lines += render_claim(claim, lookup)
        lines += ['', '## Liens pour approfondir', '']
        for link in entity.get('links', []):
            lines += [f"- [{link.get('label', link['url'])}]({link['url']}) — {link.get('purpose', '')}",
                      f"  {LINK_LABELS[link['status']]}. Date : {link.get('checked_on', 'non relevée')}.  "]
            if link.get('evidence'):
                sid, eid = link['evidence'].split('#')
                lines += [f"  [Origine dans la vidéo](../sources/{sid}.md#{eid})  "]
            if link.get('reference_file'):
                lines += [f"  [Trace de lecture](../../{link['reference_file']})  "]
        lines += ['', '## Pour aller plus loin avec un assistant', '', entity.get('follow_up', 'Partir des liens ci-dessus et préciser le besoin concret à approfondir.'), '']
        lines += ["", "## Autres fiches liées", ""]
        lines += [f"- [{other['name']}]({other['id']}.md)" for other in entities if other["id"] != entity["id"] and set(other["source_ids"]) & set(entity["source_ids"])] or ["Pas encore de lien thématique relu."]
        (vault / "outils" / (entity["id"] + ".md")).write_text("\n".join(lines) + "\n")
    write_json(root / "data/catalog.json", catalog)
    write_json(root / 'data/candidates.json', candidates(catalog))
    db = sqlite3.connect(root / "data/index.sqlite")
    with db:
        db.execute("CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, kind TEXT, body TEXT)")
        db.execute("DELETE FROM documents")
        db.executemany("INSERT INTO documents VALUES (?, ?, ?)",
                       [(s["id"], "source", json.dumps(s, ensure_ascii=False)) for s in catalog["sources"]] +
                       [(e["id"], "entity", json.dumps(e, ensure_ascii=False)) for e in entities])
    db.close()
    index = ["# Second cerveau", "", "## Outils et usages", ""]
    index += [f"- [{e['name']}](outils/{e['id']}.md) — {e['description']}" for e in entities]
    index += ["", f"## {len(sources)} sources importées", ""]
    index += [f"- [{s['title'][:100]}](sources/{s['id']}.md) · audio={s['processing']['audio_transcribed']}, OCR={s['processing']['ocr_sampled']}" for s in catalog["sources"]]
    (vault / "INDEX.md").write_text("\n".join(index) + "\n")
    return catalog


def search(query, catalog, limit=5):
    """Rank words + approximate spelling; no hidden LLM or embeddings call."""
    lookup = {s["id"]: s for s in catalog["sources"]}
    documents = []
    for e in catalog["entities"]:
        # Restrict the source context to cited evidence, avoiding unrelated video topics.
        claims = entity_claims(e)
        refs = list(dict.fromkeys(r for c in claims for r in c.get('evidence', [])))
        cited = []
        for ref in refs:
            sid, eid = ref.split("#")
            cited += [x["text"] for x in lookup[sid]["evidence"] if x["id"] == eid]
        context = " ".join(memory_context(lookup[sid]) for sid in e["source_ids"])
        body = " ".join([e["description"], " ".join(e.get("aliases", [])), context] + [c["text"] for c in claims] + cited)
        documents.append({"id": e["id"], "kind": "outil", "title": e["name"], "body": body,
                          "path": f"vault/outils/{e['id']}.md", "source_ids": e["source_ids"], "refs": refs,
                          "description": e['description'], 'details': e.get('details', {}),
                          'links': e.get('links', []), 'follow_up': e.get('follow_up', '')})
    for s in catalog["sources"]:
        reading=s.get('reading',{})
        body = " ".join([s["title"], memory_context(s), ' '.join(s.get('tags',[])), reading.get('text',''), ' '.join(reading.get('keywords',[]))] + [e["text"] for e in s["evidence"] if not e.get('archived')])
        documents.append({"id": s["id"], "kind": "source", "title": s["title"][:160], "body": body,
                          "path": f"vault/sources/{s['id']}.md", "source_ids": [s["id"]], "refs": []})
    q = set(tokens(query))
    if not q:
        return []
    bags = [set(tokens(d["title"] + " " + d["body"])) for d in documents]
    df = Counter(t for b in bags for t in b)
    results = []
    for doc, bag in zip(documents, bags):
        matched, score = [], 0.0
        for term in q:
            exact = term in bag
            fuzzy = not exact and len(term) >= 5 and any(len(t) >= 5 and abs(len(t)-len(term)) <= 2 and SequenceMatcher(None, term, t).ratio() >= 0.84 for t in bag)
            if exact or fuzzy:
                matched.append(term)
                score += (1 if exact else 0.65) * (1 + math.log(1 + len(documents) / (1 + df.get(term, 0))))
        coverage = len(matched) / len(q)
        if not matched or (len(q) >= 3 and len(matched) < 2):
            continue
        score *= coverage * (1.25 if doc["kind"] == "outil" else 1)
        if set(tokens(doc["title"])) & q:
            score *= 1.2
        item = {k: v for k, v in doc.items() if k != "body"}
        item.update(score=round(score, 3), matched=sorted(matched),
                    sources=[{"id": sid, "url": lookup[sid]["url"], "saved_at": lookup[sid]["created_at"],
                              "processing": lookup[sid]["processing"]} for sid in doc["source_ids"]])
        snippets = []
        for sid in doc['source_ids']:
            for evidence in lookup[sid]['evidence']:
                if doc['refs'] and sid + '#' + evidence['id'] not in doc['refs']:
                    continue
                overlap = len(q & set(tokens(evidence['text'])))
                if overlap:
                    snippets.append({'source_id': sid, 'evidence_id': evidence['id'],
                                     'kind': evidence['kind'], 'archived':evidence.get('archived',False), 'start': evidence.get('start'),
                                     'image': evidence.get('image'), 'text': evidence['text'][:700], 'overlap': overlap})
        item['snippets'] = sorted(snippets, key=lambda x: -x['overlap'])[:2]
        results.append(item)
    return sorted(results, key=lambda d: (-d["score"], d["id"]))[:limit]


def main():
    p = argparse.ArgumentParser(description="Second cerveau local, sans appel IA pour la recherche")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest", help="Importer les réponses texte du connecteur Karakeep")
    sub.add_parser("build", help="Générer le catalogue, SQLite et le coffre Markdown")
    q = sub.add_parser("search", help="Retrouver un outil ou une source depuis un souvenir")
    q.add_argument("query")
    q.add_argument("--json", action="store_true")
    q.add_argument("--limit", type=int, default=5)
    args = p.parse_args()
    from publication import active_root, generation
    active=active_root(ROOT)
    if args.command == 'build' and active!=ROOT:
        with generation(ROOT) as (draft,publish):
            publish()
        print('Nouvelle génération publiée ; anciennes preuves conservées.')
        return
    if args.command == 'ingest' and active!=ROOT:
        p.error('Une bibliothèque publiée utilise le worker REST ; importer un corpus avant sa première publication.')
    if args.command == "ingest":
        print(f"{ingest()} sources importées (Karakeep inchangé).")
    elif args.command == "build":
        catalog = build()
        print(f"{len(catalog['sources'])} sources, {len(catalog['entities'])} fiches d’outils.")
    else:
        catalog = read_json(active / "data/catalog.json", {"sources": [], "entities": []})
        results = search(args.query, catalog, args.limit)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        elif not results:
            print("Aucune correspondance suffisamment étayée dans ce corpus.")
        for r in [] if args.json else results:
            print(f"\n{r['title']} [{r['kind']}] — score {r['score']} (pertinence, pas fiabilité)")
            print("  Fiche :", active / r["path"])
            if r.get('description'):
                print('  Description :', r['description'])
            for key, label in [('usefulness', 'Utilité'), ('operation', 'Fonctionnement')]:
                for entry in r.get('details', {}).get(key, []):
                    print(f"  {label} ({STATUS_LABELS[entry['status']]}) :", entry['text'])
            for link in r.get('links', []):
                print(f"  {link.get('label', 'Lien')} : {link['url']} — {LINK_LABELS[link['status']]}")
            print("  Mots retrouvés :", ", ".join(r["matched"]))
            for source in r["sources"]:
                print("  Source :", source["url"], "· enregistré", source["saved_at"])
            if r["refs"]:
                print("  Preuves :", ", ".join(r["refs"]))
            for snippet in r.get('snippets', [])[:1]:
                at = f" à {stamp(snippet['start'])}" if snippet['start'] is not None else ''
                print(f"  Extrait {snippet['kind']}{at} :", snippet['text'].replace('\n', ' | ')[:240])


if __name__ == "__main__":
    main()
