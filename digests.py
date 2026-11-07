"""Portable discovery editions, snapshots and previews. No provider calls."""
import base64
import copy
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import kararecall
from controls import locked
from publication import active_root, file_hash
from settings import boolean, integer


MAX_ITEMS = 40
MAX_IMAGE = 512 * 1024
EDITION_ID = r'(?:weekly|monthly)-[0-9]{4}-[0-9]{2}-[0-9]{2}'


class DigestConflict(ValueError):
    pass


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def config():
    import os

    zone = os.getenv('DIGEST_TIMEZONE', 'Europe/Paris')
    try:
        ZoneInfo(zone)
        send_time = time.fromisoformat(os.getenv('DIGEST_TIME', '08:00'))
    except (ValueError, KeyError):
        raise ValueError('Fuseau ou heure du bulletin invalide.') from None
    if send_time.tzinfo is not None:
        raise ValueError('DIGEST_TIME attend une heure locale sans fuseau.')
    scope = os.getenv('DIGEST_SCOPE', 'added')
    if scope not in ('added', 'analyzed', 'viewed'):
        raise ValueError('DIGEST_SCOPE attend added, analyzed ou viewed.')
    return {'enabled':boolean('DIGEST_ENABLED'), 'weekly':boolean('DIGEST_WEEKLY', True),
            'monthly':boolean('DIGEST_MONTHLY', True), 'timezone':zone, 'time':send_time.isoformat(),
            'weekday':integer('DIGEST_WEEKDAY', 0, 0, 6), 'monthday':integer('DIGEST_MONTHDAY', 1, 1, 28),
            'scope':scope, 'track_views':boolean('DIGEST_TRACK_VIEWS'),
            'auto_send':boolean('DIGEST_AUTO_SEND'),
            'auto_approve':boolean('DIGEST_AUTO_APPROVE'),
            'weekly_limit':integer('DIGEST_WEEKLY_MAX_ITEMS', 12, 1, MAX_ITEMS),
            'monthly_limit':integer('DIGEST_MONTHLY_MAX_ITEMS', 24, 1, MAX_ITEMS),
            'base_url':web_url(os.getenv('KARARECALL_PUBLIC_URL', '').rstrip('/'))}


def web_url(value):
    parts = urlsplit(value)
    if parts.scheme in ('http', 'https') and parts.netloc and not (parts.username or parts.password):
        return value
    return ''


def period(kind, anchor=None, zone='Europe/Paris'):
    if kind not in ('weekly', 'monthly'):
        raise ValueError('Période inconnue.')
    day = date.fromisoformat(anchor) if anchor else datetime.now(ZoneInfo(zone)).date()
    if kind == 'weekly':
        end = day - timedelta(days=day.weekday())
        start = end - timedelta(days=7)
    else:
        end = day.replace(day=1)
        start = (end - timedelta(days=1)).replace(day=1)
    return start, end


def load(root, identifier):
    if not re.fullmatch(EDITION_ID, identifier):
        raise ValueError('Identifiant de bulletin invalide.')
    value = kararecall.read_json(root / 'data/digests/editions' / (identifier + '.json'))
    if value is None:
        raise FileNotFoundError('Bulletin absent.')
    return value


def save(root, edition):
    kararecall.write_json(root / 'data/digests/editions' / (edition['id'] + '.json'), edition)


def list_editions(root):
    values = [kararecall.read_json(path) for path in (root / 'data/digests/editions').glob('*.json')]
    return sorted(values, key=lambda row: (row['end'], row['kind']), reverse=True)


def overview(root):
    fields = ('id', 'title', 'kind', 'start', 'end', 'revision', 'approved', 'created_at', 'empty', 'scope')
    editions = [{**{key:row[key] for key in fields},
                 'items':sum(item['included'] for item in row['items']),
                 'delivery':row.get('delivery', {})} for row in list_editions(root)]
    return {'editions':editions, 'config':config(),
            'worker':kararecall.read_json(root/'data/digests/status.json', {})}


def in_period(timestamp, start, end, zone):
    try:
        instant = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if instant.tzinfo is None:
            return False
        day = instant.astimezone(ZoneInfo(zone)).date()
        return start <= day < end
    except (AttributeError, TypeError, ValueError):
        return False


def record_view(root, source_id):
    if not config()['track_views']:
        return {'recorded':False}
    selected = active_root(root)
    if not any(row['id']==source_id for row in kararecall.read_json(selected/'data/sources.json', [])):
        raise ValueError('Source absente.')
    with locked(root, 'digests.lock'):
        path = root/'data/digests/views.json'
        rows = kararecall.read_json(path, {})
        stamp = utcnow()
        rows[source_id + '/' + stamp[:10]] = {'source_id':source_id, 'viewed_at':stamp}
        kararecall.write_json(path, rows)
    return {'recorded':True}


def snapshot_image(root, selected, sources):
    for source in sources:
        for proof in source['evidence']:
            if proof.get('archived') or not proof.get('image'):
                continue
            path = (selected / proof['image']).resolve()
            allowed = [selected / 'data' / folder / source['id'] for folder in ('evidence', 'extracted')]
            if not any(path.is_relative_to(folder.resolve()) for folder in allowed) or not path.is_file():
                continue
            if path.stat().st_size > MAX_IMAGE:
                continue
            raw = path.read_bytes()
            extension = '.jpg' if raw.startswith(b'\xff\xd8\xff') else '.png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else None
            if not extension:
                continue
            name = hashlib.sha256(raw).hexdigest() + extension
            target = root/'data/digests/assets'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copyfile(path, target)
            return {'file':name, 'caption':'Image de la source', 'alt':source['title'][:180],
                    'ref':source['id']+'#'+proof['id']}
    return None


def claim_excerpt(entries):
    return [{'text':row['text'][:500], 'status':row['status'],
             'evidence':row.get('evidence', []),
             **{key:row[key] for key in ('verification_url', 'verification_file') if key in row}}
            for row in entries[:2]]


def make_item(root, selected, identifier, title, sources, entity=None):
    if entity:
        details = {key:claim_excerpt(entity.get('details', {}).get(key, [])) for key in ('description', 'usefulness', 'operation')}
        if not details['description']:
            details['description'] = claim_excerpt(entity.get('claims', []))
        summary = ' '.join(row['text'] for row in details['description']) or entity['description'][:500]
    else:
        reading = sources[0].get('reading')
        proof = next((p for p in sources[0]['evidence'] if p['kind'] in ('page', 'text', 'document', 'caption') and not p.get('archived')), None)
        entry = reading or ({'text':proof['text'], 'status':'source_claim', 'evidence':[sources[0]['id']+'#'+proof['id']]} if proof else None)
        details = {'description':claim_excerpt([entry]) if entry else [], 'usefulness':[], 'operation':[]}
        summary = ' '.join(row['text'] for row in details['description']) or 'Informations disponibles dans la source.'
    refs = list(dict.fromkeys(ref for entries in details.values() for entry in entries for ref in entry['evidence']))
    lookup = {source['id']+'#'+proof['id']:(source, proof) for source in sources for proof in source['evidence']}
    evidence = []
    for ref in refs:
        source, proof = lookup[ref]
        evidence.append({'ref':ref, 'text':proof['text'][:600], 'url':web_url(source['url']),
                         **{key:proof[key] for key in ('start', 'end', 'page') if key in proof}})
    documentation = []
    for entries in details.values():
        for entry in entries:
            url = web_url(entry.get('verification_url',''))
            if url and entry['status'] in ('documented','verified'):
                documentation.append({'url':url, 'file':entry['verification_file'], 'status':entry['status']})
    tags = list(dict.fromkeys(tag for source in sources for tag in source.get('tags', [])))
    item_id=('tool-' if entity else 'source-')+identifier
    return {'id':item_id, 'title':title[:180], 'summary':summary, 'theme':tags[0] if tags else 'Découvertes',
            'usefulness':' '.join(entry['text'] for entry in details['usefulness']),
            'operation':' '.join(entry['text'] for entry in details['operation']), 'claims':details,
            'source_ids':[source['id'] for source in sources],
            'sources':[{'id':source['id'], 'url':web_url(source['url']), 'title':source['title'][:180]} for source in sources],
            'evidence':evidence, 'documentation':documentation,
            'image':snapshot_image(root, selected, sources), 'include_image':True,
            'included':True, 'route':('/#/tools/' if entity else '/#/sources/')+identifier,
            'editorial_status':'draft'}


def generate(root, kind='weekly', anchor=None, refresh=False):
    cfg = config()
    start, end = period(kind, anchor, cfg['timezone'])
    identifier = kind + '-' + start.isoformat()
    with locked(root, 'digests.lock'):
        previous = None
        try:
            previous = load(root, identifier)
            if not refresh:
                return previous
            if previous['approved'] or previous['delivery']:
                raise DigestConflict('Seul un brouillon sans diffusion peut être repréparé.')
        except FileNotFoundError:
            pass
        selected = active_root(root)
        catalog = kararecall.read_json(selected/'data/catalog.json', {'sources':[], 'entities':[]})
        lookup = {source['id']:source for source in catalog['sources']}
        stamps = {}
        for source in catalog['sources']:
            stamp = source['created_at']
            if cfg['scope']=='analyzed':
                stamp = source.get('processed_at') or source.get('reading', {}).get('generated_at')
            stamps[source['id']] = stamp
        if cfg['scope']=='viewed':
            stamps = {row['source_id']:row['viewed_at'] for row in kararecall.read_json(root/'data/digests/views.json', {}).values()
                      if in_period(row['viewed_at'], start, end, cfg['timezone'])}
        eligible = {sid for sid, stamp in stamps.items() if in_period(stamp, start, end, cfg['timezone']) and sid in lookup}
        items = []
        covered = set()
        seen = set()
        prior = [edition for edition in list_editions(root) if edition['kind']==kind and edition['end']<=start.isoformat()]
        for edition in prior:
            seen.update(item['id'] for item in edition['items'] if item['included'])
        from web_research import identity
        grouped = {}
        for original in catalog['entities']:
            spec = identity(original)
            key = spec[0] if spec else original['id']
            if key not in grouped:
                grouped[key] = copy.deepcopy(original)
                continue
            entity = grouped[key]
            entity['source_ids'] = list(dict.fromkeys(entity['source_ids']+original['source_ids']))
            for section in ('description', 'usefulness', 'operation'):
                entity.setdefault('details', {}).setdefault(section, []).extend(original.get('details', {}).get(section, []))
        candidates = []
        for entity in grouped.values():
            if not eligible.intersection(entity['source_ids']):
                continue
            candidates.append((entity['id'], entity['name'], [lookup[sid] for sid in entity['source_ids']], entity))
            covered.update(entity['source_ids'])
        for sid in sorted(eligible-covered, key=lambda sid:(stamps[sid], sid), reverse=True):
            source = lookup[sid]
            candidates.append((sid, source['title'], [source], None))
        total = len(candidates)
        candidates.sort(key=lambda item:max((stamps[source['id']] for source in item[2]
                                           if source['id'] in eligible), default=''), reverse=True)
        for sid, title, sources, entity in candidates[:cfg[kind+'_limit']]:
            item = make_item(root, selected, sid, title, sources, entity)
            item['novelty'] = 'Complément' if item['id'] in seen else 'Découverte'
            items.append(item)
        label = 'La semaine en découvertes' if kind=='weekly' else 'Le mois en découvertes'
        themes = list(dict.fromkeys(item['theme'] for item in items))
        intro = f"{len(items)} découvertes du {start:%d/%m/%Y} au {end-timedelta(days=1):%d/%m/%Y}."
        if themes:
            intro += ' Au programme, ' + ', '.join(themes[:5]) + '.'
        edition = {'id':identifier, 'kind':kind, 'start':start.isoformat(), 'end':end.isoformat(),
                   'scope':cfg['scope'], 'timezone':cfg['timezone'], 'title':label, 'intro':intro,
                   'created_at':utcnow(), 'generation':str(selected.relative_to(root)) or '.',
                   'revision':previous['revision']+1 if previous else 1,
                   'approved':False, 'empty':not items, 'total_candidates':total, 'items':items,
                   'base_url':cfg['base_url'], 'delivery':{}, 'send_requested':False}
        if previous:
            kararecall.write_json(root/'data/digests/revisions'/identifier/(str(previous['revision'])+'.json'),previous)
        save(root, edition)
        return edition


def revise(root, identifier, payload, action='edit'):
    if not isinstance(payload, dict):
        raise ValueError('Objet JSON attendu.')
    with locked(root, 'digests.lock'):
        edition = load(root, identifier)
        if payload.get('revision') != edition['revision']:
            raise DigestConflict('Le bulletin a changé. Actualise la page avant de le modifier.')
        if any(state['state'] in ('sending', 'sent', 'uncertain') for state in edition['delivery'].values()):
            raise DigestConflict('Cette édition possède un envoi terminé ou à vérifier. Son contenu est conservé.')
        previous = copy.deepcopy(edition)
        if action=='edit':
            for key, maximum in (('title', 180), ('intro', 2000)):
                value = payload.get(key)
                if not isinstance(value, str) or len(value)>maximum or not value.strip():
                    raise ValueError('Titre ou introduction invalide.')
                if key=='title' and ('\r' in value or '\n' in value):
                    raise ValueError('Le titre doit tenir sur une seule ligne.')
                edition[key] = value.strip()
            changes = payload.get('items')
            if not isinstance(changes, list) or len(changes)!=len(edition['items']):
                raise ValueError('Liste des découvertes invalide.')
            supplied = {row.get('id'):row for row in changes if isinstance(row, dict)}
            if set(supplied)!={row['id'] for row in edition['items']}:
                raise ValueError('Découverte inconnue ou dupliquée.')
            for item in edition['items']:
                row = supplied[item['id']]
                for key in ('included', 'include_image'):
                    if type(row.get(key)) is not bool:
                        raise ValueError('Sélection invalide.')
                    item[key] = row[key]
                for key, maximum in (('title',180), ('theme',100), ('summary',1500), ('usefulness',1000), ('operation',1000)):
                    value = row.get(key)
                    if not isinstance(value,str) or len(value)>maximum:
                        raise ValueError('Texte du bulletin invalide.')
                    item[key] = value.strip()
                item['editorial_status'] = 'user-edited'
            edition['approved'] = False
            edition['send_requested'] = False
        elif action in ('approve','auto-approve'):
            if not any(row['included'] for row in edition['items']):
                raise ValueError('Sélectionne au moins une découverte.')
            if action=='auto-approve' and (not config()['auto_approve'] or edition['revision']!=1):
                raise DigestConflict('Cette édition demande une relecture.')
            edition['approved'] = True
            edition['approval_mode'] = 'automatic' if action=='auto-approve' else 'human'
            edition['approved_at'] = utcnow()
            edition['send_requested'] = config()['auto_send']
        elif action=='send':
            if not edition['approved']:
                raise ValueError('Valide le bulletin avant de demander sa diffusion.')
            edition['send_requested'] = True
        else:
            raise ValueError('Action inconnue.')
        edition['revision'] += 1
        revision_file = root/'data/digests/revisions'/identifier/(str(previous['revision'])+'.json')
        kararecall.write_json(revision_file, previous)
        save(root, edition)
        return edition


def image_bytes(root, image):
    name = image['file']
    if not re.fullmatch(r'[a-f0-9]{64}\.(?:jpg|png)', name):
        raise ValueError('Image de bulletin invalide.')
    path = root/'data/digests/assets'/name
    if path.stat().st_size>MAX_IMAGE or file_hash(path)!=Path(name).stem:
        raise ValueError('Image de bulletin incohérente.')
    return path.read_bytes(), 'image/jpeg' if name.endswith('.jpg') else 'image/png'


def markdown(edition):
    def text(value):
        return re.sub(r'([\\`*_{}\[\]<>#!|])', r'\\\1', value)
    lines = ['# '+text(edition['title']), '', text(edition['intro']), '']
    for item in edition['items']:
        if not item['included']:
            continue
        lines += ['## '+text(item['theme'])+' · '+text(item['title']), '', attribution(item,'description'), '', text(item['summary']), '']
        for key, label in (('usefulness','Utilité'),('operation','Fonctionnement')):
            if item[key]:
                lines += [label+' — '+attribution(item,key), text(item[key]), '']
        reviewed = edition['approved'] and edition.get('approval_mode')=='human'
        lines += ['Édition relue' if reviewed else 'Rédaction automatique à relire', '']
        for source in item['sources']:
            if source['url']:
                lines += ['Source originale — '+source['url']]
        if edition['base_url']:
            lines += ['Fiche — '+edition['base_url']+item['route']]
        for proof in item['evidence']:
            lines += ['Preuve '+text(proof['ref'])+' — '+text(proof['text'])]
        lines += ['Documentation consultée — '+doc['url'] for doc in item['documentation']]
        lines.append('')
    return '\n'.join(lines)


ARTICLE_CSS = '''body{margin:0;background:#f4f6f8;color:#20303d;font:16px/1.65 system-ui,sans-serif}main{max-width:720px;margin:auto;padding:42px 24px}header{border-bottom:3px solid #427c68;padding-bottom:24px;margin-bottom:28px}small{color:#547064}h1{font-size:34px;line-height:1.2}h2{font-size:23px;line-height:1.3}h3{font-size:15px;text-transform:uppercase;letter-spacing:.08em;color:#427c68;margin-top:36px}article{background:white;border:1px solid #dce4df;border-radius:16px;padding:24px;margin:18px 0;break-inside:avoid}img{display:block;max-width:100%;max-height:240px;margin:auto;border-radius:10px;object-fit:contain}figure{margin:12px 0}figcaption{font-size:12px;color:#62716c;margin-top:6px}a{color:#27614c;overflow-wrap:anywhere}footer,details{font-size:12px;color:#62716c}summary{cursor:pointer}p{white-space:pre-line}@media(max-width:500px){main{padding:24px 14px}article{padding:18px}h1{font-size:27px}}@media print{body{background:white}main{padding:0}article{border-color:#ddd}details{display:block}a{color:inherit}}'''


def attribution(item, section):
    if item['editorial_status']=='user-edited':
        return 'Texte édité · sources associées'
    labels = list(dict.fromkeys(kararecall.STATUS_LABELS[row['status']] for row in item['claims'].get(section, [])))
    return ' · '.join(labels) or 'Information à compléter'


def article_html(root, edition, email_images=False):
    escape = html.escape
    pieces = ['<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
              '<title>'+escape(edition['title'])+'</title><style>'+ARTICLE_CSS+'</style></head><body><main><header>',
              '<small>KARARECALL · VEILLE '+('MENSUELLE' if edition['kind']=='monthly' else 'HEBDOMADAIRE')+'</small>',
              '<h1>'+escape(edition['title'])+'</h1><p>'+escape(edition['intro'])+'</p></header>']
    theme = None
    for item in sorted((item for item in edition['items'] if item['included']), key=lambda item:item['theme'].casefold()):
        if item['theme'] != theme:
            theme = item['theme']
            pieces += ['<h3>'+escape(theme)+'</h3>']
        pieces += ['<article><small>'+escape(item['novelty'])+'</small><h2>'+escape(item['title'])+'</h2>']
        if item['image'] and item['include_image']:
            image = item['image']
            raw, mime = image_bytes(root, image)
            url = 'cid:'+image['file'] if email_images else 'data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii')
            pieces += ['<figure><img src="'+url+'" alt="'+escape(image['alt'],quote=True)+'"><figcaption>'+escape(image['caption'])+'</figcaption></figure>']
        pieces += ['<small>'+escape(attribution(item,'description'))+'</small><p>'+escape(item['summary'])+'</p>']
        for key, label in (('usefulness','À quoi ça sert'),('operation','Comment ça fonctionne')):
            if item[key]:
                pieces += ['<p><strong>'+label+'</strong><br><small>'+escape(attribution(item,key))+'</small><br>'+escape(item[key])+'</p>']
        links = []
        if edition['base_url']:
            links += ['<a href="'+escape(edition['base_url']+item['route'],quote=True)+'">Ouvrir la fiche</a>']
        links += ['<a href="'+escape(source['url'],quote=True)+'">Source originale</a>' for source in item['sources'] if source['url']]
        links += ['<a href="'+escape(doc['url'],quote=True)+'">Documentation consultée</a>' for doc in item['documentation']]
        pieces += ['<p>'+' · '.join(links)+'</p><details><summary>Sources et preuves</summary>']
        for proof in item['evidence']:
            pieces += ['<p><strong>'+escape(proof['ref'])+'</strong><br>'+escape(proof['text'])+'</p>']
        pieces += ['</details></article>']
    reviewed = edition['approved'] and edition.get('approval_mode')=='human'
    pieces += ['<footer><p>'+('Édition relue. Les descriptions restent attribuées aux sources.' if reviewed else 'Rédaction automatique à relire. Les descriptions restent attribuées aux sources.')+'</p></footer></main></body></html>']
    return ''.join(pieces)


def rss(root):
    cfg = config()
    feed = ET.Element('rss', version='2.0')
    channel = ET.SubElement(feed, 'channel')
    ET.SubElement(channel, 'title').text = 'La veille KaraRecall'
    ET.SubElement(channel, 'description').text = 'Bulletins sélectionnés pour diffusion de la bibliothèque personnelle.'
    ET.SubElement(channel, 'link').text = cfg['base_url'] or 'http://localhost/'
    approved = [edition for edition in list_editions(root) if edition['approved']]
    for edition in approved[:50]:
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'guid', isPermaLink='false').text = 'kararecall:'+edition['id']
        ET.SubElement(item, 'title').text = edition['title']+' · '+edition['start']
        ET.SubElement(item, 'description').text = markdown(edition)
        if cfg['base_url']:
            ET.SubElement(item, 'link').text = cfg['base_url']+'/#/digests/'+edition['id']
    return ET.tostring(feed, encoding='utf-8', xml_declaration=True)
