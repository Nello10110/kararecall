"""Digest snapshots, scheduling and delivery use synthetic local data only."""
import base64
import copy
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import digests
import digest_delivery
from fixtures import corpus
import kararecall
from web_server import Corpus, make_handler


class DigestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        corpus(self.root)
        self.png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jk1sAAAAASUVORK5CYII=')
        (self.root/'data/extracted/demo-model/frame.jpg').write_bytes(self.png)
        self.data = kararecall.build(self.root)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def edition(self):
        return digests.generate(self.root, 'weekly', '2026-11-02')

    def approve(self, edition):
        return digests.revise(self.root, edition['id'], {'revision':edition['revision']}, 'approve')

    def test_edition_is_idempotent_and_images_and_citations_survive_source_changes(self):
        edition = self.edition()
        self.assertEqual(edition['start'], '2026-10-26')
        self.assertEqual(len(edition['items']), 2)
        self.assertEqual(digests.generate(self.root,'weekly','2026-11-05'),edition)
        proof = edition['items'][0]['evidence'][0]
        self.assertEqual(proof['ref'],'demo-model#asr-000')
        (self.root/'data/extracted/demo-model/frame.jpg').write_bytes(b'changed')
        rendered = digests.article_html(self.root,edition)
        self.assertIn('data:image/png;base64,',rendered)
        self.assertIn('demo-model#asr-000',rendered)
        self.assertNotIn('changed',rendered)
        self.assertIn(self.png, [digests.image_bytes(self.root,item['image'])[0] for item in edition['items'] if item['image']])
        html = digests.article_html(self.root,dict(edition,title='<script>bad()</script>'))
        self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<script>',html)

    def test_review_revision_selection_and_private_rss(self):
        edition=self.edition()
        payload={key:copy.deepcopy(edition[key]) for key in ('revision','title','intro','items')}
        payload['items'][0]['included']=False
        payload['items'][1]['summary']='Présentation relue.'
        edited=digests.revise(self.root,edition['id'],payload)
        self.assertFalse(edited['approved'])
        with self.assertRaises(digests.DigestConflict):
            digests.revise(self.root,edition['id'],payload)
        approved=self.approve(edited)
        self.assertIn(b'Pr\xc3\xa9sentation relue.',digests.rss(self.root))
        self.assertNotIn('Un modèle',digests.article_html(self.root,approved))
        self.assertTrue((self.root/'data/digests/revisions'/edition['id']/'1.json').is_file())

    def test_week_month_and_schedule_boundaries_are_local_and_restart_safe(self):
        self.assertEqual([day.isoformat() for day in digests.period('monthly','2024-03-01')],['2024-02-01','2024-03-01'])
        os.environ.update(DIGEST_ENABLED='true',DIGEST_TIME='08:00',DIGEST_TIMEZONE='Europe/Paris',DIGEST_MONTHDAY='2')
        before=datetime(2026,11,2,6,59,tzinfo=timezone.utc)
        digest_delivery.process(self.root,before)
        self.assertEqual(digests.list_editions(self.root),[])
        after=datetime(2026,11,2,7,0,tzinfo=timezone.utc)
        digest_delivery.process(self.root,after)
        first=digests.list_editions(self.root)
        digest_delivery.process(self.root,after)
        self.assertEqual(digests.list_editions(self.root),first)
        self.assertEqual({row['kind'] for row in first},{'weekly','monthly'})
        self.assertTrue(all(not row['approved'] for row in first))

    def test_duplicate_tool_favorites_are_grouped_and_empty_period_is_saved(self):
        entities=kararecall.read_json(self.root/'data/entities.json')
        duplicate=copy.deepcopy(entities[0]);duplicate['id']='another-heretic'
        entities.append(duplicate)
        kararecall.write_json(self.root/'data/entities.json',entities)
        kararecall.build(self.root)
        self.assertEqual(len(self.edition()['items']),2)
        empty=digests.generate(self.root,'monthly','2020-01-01')
        self.assertTrue(empty['empty'])
        self.assertEqual(empty['items'],[])
        with self.assertRaises(ValueError):self.approve(empty)

    def test_fully_automatic_delivery_requires_explicit_options_and_keeps_its_label(self):
        os.environ.update(DIGEST_ENABLED='true',DIGEST_WEEKLY='true',DIGEST_MONTHLY='false',
                          DIGEST_AUTO_APPROVE='true',DIGEST_AUTO_SEND='true',DIGEST_SEND_ENABLED='true',
                          DIGEST_CHANNELS='email',DIGEST_SMTP_HOST='relay.invalid',
                          DIGEST_EMAIL_FROM='sender@example.test',DIGEST_EMAIL_TO='reader@example.test')
        with patch('digest_delivery.send_mail') as send:
            digest_delivery.process(self.root,datetime(2026,11,2,9,tzinfo=timezone.utc))
            digest_delivery.process(self.root,datetime(2026,11,2,9,tzinfo=timezone.utc))
            send.assert_called_once()
        edition=digests.list_editions(self.root)[0]
        self.assertEqual(edition['approval_mode'],'automatic')
        self.assertIn('Rédaction automatique à relire',digests.article_html(self.root,edition))

    def test_invalid_digest_settings_report_an_error_without_interrupting_imports(self):
        os.environ['DIGEST_TIMEZONE']='Invalid/Fixture'
        self.assertEqual(digest_delivery.process(self.root)['state'],'error')

    def test_manual_refresh_archives_draft_and_preserves_approved_edition(self):
        edition=self.edition()
        rebuilt=digests.generate(self.root,'weekly','2026-11-02',refresh=True)
        self.assertEqual(rebuilt['revision'],2)
        self.assertEqual(kararecall.read_json(self.root/'data/digests/revisions'/edition['id']/'1.json'),edition)
        self.approve(rebuilt)
        with self.assertRaises(digests.DigestConflict):
            digests.generate(self.root,'weekly','2026-11-02',refresh=True)

    def test_views_require_opt_in_and_keep_period_history(self):
        self.assertFalse(digests.record_view(self.root,'demo-tv')['recorded'])
        os.environ.update(DIGEST_TRACK_VIEWS='true',DIGEST_SCOPE='viewed')
        with patch('digests.utcnow',return_value='2026-10-31T09:00:00+00:00'):
            digests.record_view(self.root,'demo-tv')
        with patch('digests.utcnow',return_value='2026-11-03T09:00:00+00:00'):
            digests.record_view(self.root,'demo-tv')
        self.assertEqual([item['id'] for item in self.edition()['items']],['tool-tv-detox'])
        self.assertEqual(len(kararecall.read_json(self.root/'data/digests/views.json')),2)

    def test_mail_is_reviewed_and_deduplicated_including_ambiguous_failures(self):
        os.environ.update(DIGEST_SEND_ENABLED='true',DIGEST_CHANNELS='email',DIGEST_SMTP_HOST='relay.invalid',
                          DIGEST_EMAIL_FROM='sender@example.test',DIGEST_EMAIL_TO='reader@example.test')
        edition=self.edition()
        with patch('digest_delivery.send_mail') as send:
            self.assertEqual(digest_delivery.deliver(self.root,edition['id'])['state'],'waiting_review')
            send.assert_not_called()
        edition=self.approve(edition)
        edition=digests.revise(self.root,edition['id'],{'revision':edition['revision']},'send')
        with patch('digest_delivery.send_mail',side_effect=TimeoutError('password-must-not-be-logged')) as send:
            digest_delivery.process(self.root)
            digest_delivery.process(self.root)
            self.assertEqual(send.call_count,1)
        saved=digests.load(self.root,edition['id'])
        self.assertEqual(next(iter(saved['delivery'].values()))['state'],'uncertain')
        self.assertNotIn('password-must-not-be-logged',json.dumps(saved))
        with self.assertRaises(digests.DigestConflict):self.approve(saved)

    def test_successful_mail_contains_inline_image_and_persistent_receipt(self):
        os.environ.update(DIGEST_SEND_ENABLED='true',DIGEST_CHANNELS='email',DIGEST_SMTP_HOST='relay.invalid',
                          DIGEST_EMAIL_FROM='sender@example.test',DIGEST_EMAIL_TO='reader@example.test')
        edition=self.approve(self.edition())
        edition=digests.revise(self.root,edition['id'],{'revision':edition['revision']},'send')
        message=digest_delivery.mail_message(self.root,edition,'reader@example.test')
        self.assertTrue(any(part.get_content_type()=='image/png' for part in message.walk()))
        with patch('digest_delivery.send_mail') as send:
            digest_delivery.deliver(self.root,edition['id'])
            digest_delivery.deliver(self.root,edition['id'])
            send.assert_called_once()
        self.assertEqual(next(iter(digests.load(self.root,edition['id'])['delivery'].values()))['state'],'sent')

    def test_transports_use_tls_and_webhook_idempotency_without_redirects(self):
        os.environ.update(DIGEST_SMTP_HOST='relay.invalid',DIGEST_SMTP_USERNAME='fixture-user',
                          DIGEST_SMTP_PASSWORD='fixture-secret',DIGEST_EMAIL_FROM='sender@example.test')
        edition=self.approve(self.edition())
        with patch('digest_delivery.smtplib.SMTP') as smtp:
            relay=smtp.return_value.__enter__.return_value
            relay.send_message.return_value={}
            digest_delivery.send_mail(self.root,edition,'reader@example.test')
            relay.starttls.assert_called_once()
            relay.login.assert_called_once_with('fixture-user','fixture-secret')
            self.assertEqual(relay.send_message.call_args.kwargs['to_addrs'],['reader@example.test'])
        with patch('digest_delivery.build_opener') as opener:
            response=opener.return_value.open.return_value.__enter__.return_value
            response.status=204
            digest_delivery.send_webhook(self.root,edition,'https://example.invalid/hook')
            request=opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header('Idempotency-key'),edition['id'])
            self.assertIn('markdown',json.loads(request.data))
        self.assertIsNone(digest_delivery.NoRedirect().redirect_request(None,None,302,'',{},'https://elsewhere.invalid'))

    def test_http_protects_generation_export_images_and_edits(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Corpus(self.root),'fixture','fixture-password'))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        auth='Basic '+base64.b64encode(b'fixture:fixture-password').decode()
        def request(path,method='GET',payload=None,token=None,authenticated=True):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
            headers={'Content-Type':'application/json'}
            if authenticated:headers['Authorization']=auth
            if token:headers['X-KaraRecall-CSRF']=token
            connection.request(method,path,json.dumps(payload) if payload is not None else None,headers)
            response=connection.getresponse();body=response.read();status=response.status
            connection.close()
            return status,body
        try:
            self.assertEqual(request('/api/digests',authenticated=False)[0],401)
            self.assertEqual(request('/api/digests/generate','POST',{})[0],403)
            csrf=json.loads(request('/api/control')[1])['csrf_token']
            status,body=request('/api/digests/generate','POST',{'kind':'weekly','anchor':'2026-11-02'},csrf)
            self.assertEqual(status,201)
            edition=json.loads(body)
            image=next(item['image'] for item in edition['items'] if item['image'])
            for path in ['/api/digests/feed.xml','/api/digests/'+edition['id'],
                         '/api/digests/'+edition['id']+'/article.html','/api/digests/assets/'+image['file']]:
                self.assertEqual(request(path,authenticated=False)[0],401)
                self.assertEqual(request(path)[0],200)
            self.assertEqual(request('/api/digests/../../.env')[0],404)
            self.assertEqual(request('/api/digests/'+edition['id']+'/approve','POST',{'revision':0},csrf)[0],409)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':
    unittest.main()
