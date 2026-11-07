"""Worker scheduling and explicitly configured delivery of reviewed editions."""
from datetime import datetime, time, timedelta
from email.message import EmailMessage
from email.utils import format_datetime, getaddresses
import hashlib
import json
import os
import smtplib
import ssl
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from controls import locked
import digests
import kararecall
from publication import active_root
from settings import boolean, integer


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def targets():
    channels = [value.strip() for value in os.getenv('DIGEST_CHANNELS', '').split(',') if value.strip()]
    if any(channel not in ('email', 'webhook') for channel in channels):
        raise ValueError('Canal de bulletin inconnu.')
    result = []
    if 'email' in channels:
        recipients = getaddresses([os.getenv('DIGEST_EMAIL_TO', '')])
        sender = os.getenv('DIGEST_EMAIL_FROM', '')
        tls = os.getenv('DIGEST_SMTP_TLS', 'starttls')
        if tls not in ('starttls', 'ssl'):
            raise ValueError('DIGEST_SMTP_TLS attend starttls ou ssl.')
        if not os.getenv('DIGEST_SMTP_HOST') or not valid_email(sender) or not recipients:
            raise ValueError('Configurer le serveur SMTP, l’expéditeur et les destinataires du bulletin.')
        for _, address in recipients:
            if not valid_email(address):
                raise ValueError('Adresse de diffusion invalide.')
            result.append(('email', address))
        if len(result)>20:
            raise ValueError('Le bulletin est limité à vingt destinataires.')
    if 'webhook' in channels:
        endpoint = os.getenv('DIGEST_WEBHOOK_URL', '')
        parts = urlsplit(endpoint)
        local = parts.hostname in ('127.0.0.1', 'localhost', '::1')
        if not parts.hostname or parts.username or parts.password or parts.fragment or not (parts.scheme=='https' or parts.scheme=='http' and local):
            raise ValueError('Configurer une URL webhook HTTPS sans identifiants intégrés.')
        result.append(('webhook', endpoint))
    return list(dict.fromkeys(result))


def valid_email(value):
    return isinstance(value, str) and '\n' not in value and '\r' not in value and value.count('@')==1 and all(value.split('@')) and not any(c in value for c in '<> ,;')


def mail_message(root, edition, address):
    message = EmailMessage()
    message['From'] = os.environ['DIGEST_EMAIL_FROM']
    message['To'] = address
    message['Subject'] = edition['title']+' · '+edition['start']
    message['Date'] = format_datetime(datetime.now().astimezone())
    tag = hashlib.sha256((edition['id']+address).encode()).hexdigest()
    message['Message-ID'] = '<'+tag+'@'+os.environ['DIGEST_EMAIL_FROM'].split('@')[1]+'>'
    message.set_content(digests.markdown(edition))
    message.add_alternative(digests.article_html(root, edition, email_images=True), subtype='html')
    attached = set()
    for item in edition['items']:
        image = item['image']
        if not item['included'] or not item['include_image'] or not image or image['file'] in attached:
            continue
        raw, mime = digests.image_bytes(root, image)
        message.get_payload()[-1].add_related(raw, maintype='image', subtype=mime.split('/')[1],
                                             cid='<'+image['file']+'>', disposition='inline')
        attached.add(image['file'])
    return message


def send_mail(root, edition, address):
    # Build all content before contacting the relay.
    message = mail_message(root, edition, address)
    mode = os.getenv('DIGEST_SMTP_TLS', 'starttls')
    host = os.environ['DIGEST_SMTP_HOST']
    port = integer('DIGEST_SMTP_PORT', 465 if mode=='ssl' else 587, 1, 65535)
    context = ssl.create_default_context()
    if mode=='ssl':
        connection = smtplib.SMTP_SSL(host, port, timeout=15, context=context)
    else:
        connection = smtplib.SMTP(host, port, timeout=15)
    with connection as server:
        if mode=='starttls':
            server.starttls(context=context)
        username = os.getenv('DIGEST_SMTP_USERNAME', '')
        if username:
            server.login(username, os.getenv('DIGEST_SMTP_PASSWORD', ''))
        rejected = server.send_message(message, from_addr=os.environ['DIGEST_EMAIL_FROM'], to_addrs=[address])
        if rejected:
            raise RuntimeError('Destinataire refusé.')


def send_webhook(root, edition, endpoint):
    body = json.dumps({'id':edition['id'], 'title':edition['title'], 'start':edition['start'], 'end':edition['end'],
                       'markdown':digests.markdown(edition), 'html':digests.article_html(root, edition)}, ensure_ascii=False).encode()
    headers = {'Content-Type':'application/json', 'Idempotency-Key':edition['id']}
    token = os.getenv('DIGEST_WEBHOOK_TOKEN', '')
    if token:
        headers['Authorization'] = 'Bearer '+token
    with build_opener(NoRedirect()).open(Request(endpoint, data=body, headers=headers), timeout=15) as response:
        if not 200<=response.status<300:
            raise RuntimeError('Diffusion refusée.')
        response.read(1024)


def deliver(root, identifier):
    if not boolean('DIGEST_SEND_ENABLED'):
        return {'state':'disabled'}
    destinations = targets()
    if not destinations:
        raise ValueError('Choisir au moins un canal pour le bulletin.')
    for channel, destination in destinations:
        key = hashlib.sha256((channel+'\n'+destination).encode()).hexdigest()
        with locked(root, 'digests.lock'):
            edition = digests.load(root, identifier)
            if not edition['approved'] or not edition['send_requested']:
                return {'state':'waiting_review'}
            prior = edition['delivery'].get(key)
            if prior:
                # A crash or ambiguous network response cannot be retried safely.
                if prior['state']=='sending':
                    prior.update(state='uncertain', message='Résultat d’envoi à vérifier auprès de la destination.')
                    digests.save(root, edition)
                continue
            edition['delivery'][key] = {'state':'sending', 'channel':channel, 'started_at':digests.utcnow()}
            edition['revision'] += 1
            digests.save(root, edition)
        try:
            (send_mail if channel=='email' else send_webhook)(root, edition, destination)
            state, message = 'sent', 'Accepté par le service de diffusion.'
        except Exception:
            # Remote exception messages can contain relay credentials or webhook tokens.
            state, message = 'uncertain', 'Envoi à vérifier. Aucun nouvel essai automatique pour cette destination.'
        with locked(root, 'digests.lock'):
            current = digests.load(root, identifier)
            current['delivery'][key].update(state=state, message=message, completed_at=digests.utcnow())
            current['revision'] += 1
            digests.save(root, current)
    return {'state':'processed'}


def process(root, now=None):
    try:
        cfg = digests.config()
        with locked(root, 'digest-runner.lock', blocking=False):
            current = (now or datetime.now(ZoneInfo(cfg['timezone']))).astimezone(ZoneInfo(cfg['timezone']))
            if cfg['enabled']:
                selected=active_root(root)
                sources=kararecall.read_json(selected/'data/catalog.json',{}).get('sources',[])
                if cfg['initial_history'] and sources and not any(e['kind']=='initial' for e in digests.list_editions(root)):
                    digests.generate(root,'initial',current.date().isoformat())
                local_time = time.fromisoformat(cfg['time'])
                week_start = current.date()-timedelta(days=current.weekday())
                due_week = datetime.combine(week_start+timedelta(days=cfg['weekday']), local_time, ZoneInfo(cfg['timezone']))
                due_month = datetime.combine(current.date().replace(day=cfg['monthday']), local_time, ZoneInfo(cfg['timezone']))
                for kind, due in (('weekly',due_week), ('monthly',due_month)):
                    if cfg[kind] and current>=due:
                        digests.generate(root, kind, current.date().isoformat())
                for edition in digests.list_editions(root):
                    if edition['approved'] or edition['empty'] or any(i['editorial_status']=='user-edited' for i in edition['items']):
                        continue
                    ready=True
                    if cfg['write_articles']:
                        from digest_writer import write_edition
                        ready=write_edition(root,edition['id'])=='ready'
                    edition=digests.load(root,edition['id'])
                    if ready and cfg['auto_approve']:
                        digests.revise(root,edition['id'],{'revision':edition['revision']},'auto-approve')
            if boolean('DIGEST_SEND_ENABLED'):
                for edition in digests.list_editions(root):
                    if edition['approved'] and edition['send_requested']:
                        deliver(root, edition['id'])
            result = {'state':'ready', 'updated_at':digests.utcnow(), 'delivery_enabled':boolean('DIGEST_SEND_ENABLED'),
                      'channels':[c.strip() for c in os.getenv('DIGEST_CHANNELS','').split(',') if c.strip()]}
            kararecall.write_json(root/'data/digests/status.json', result)
            return result
    except BlockingIOError:
        return {'state':'busy'}
    except Exception:
        result = {'state':'error', 'updated_at':digests.utcnow(),
                  'message':'Vérifier les paramètres du bulletin et les accès de diffusion dans .env.'}
        kararecall.write_json(root/'data/digests/status.json', result)
        return result
