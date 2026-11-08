import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

import kararecall
from fixtures import corpus
from publication import generation, active_root, migrate
from recovery import inspect
from scripts.pilot import http_benchmark, usage_since
from web_server import Corpus, make_handler


class PilotToolsTests(unittest.TestCase):
    def test_recovery_inventory_and_integrity_check_never_change_publication_or_usage(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);corpus(root)
            for _ in range(2):
                with generation(root) as (draft,publish):
                    sources,entities=migrate(kararecall.read_json(draft/'data/sources.json'),kararecall.read_json(draft/'data/entities.json'),draft)
                    kararecall.write_json(draft/'data/sources.json',sources);kararecall.write_json(draft/'data/entities.json',entities);publish()
            pointer=(root/'data/current.json').read_bytes();selected=active_root(root)
            report=inspect(root);self.assertEqual(len(report['generations']),2)
            older=next(row['generation'] for row in report['generations'] if not row['selected'])
            self.assertEqual(inspect(root,older)['integrity']['status'],'ok')
            self.assertEqual(report['external_backup'],'not_observed')
            self.assertEqual((root/'data/current.json').read_bytes(),pointer);self.assertEqual(active_root(root),selected)
            with self.assertRaises(ValueError):inspect(root,'../../.env')

    def test_usage_batch_is_read_only_and_uncertain_reserves_remain_visible(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'data').mkdir()
            self.assertFalse(usage_since(root,'2026-11-08T00:00:00Z')['observed'])
            self.assertFalse((root/'data/usage.sqlite').exists())
            path=root/'data/usage.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE calls (started TEXT,stage TEXT,state TEXT,accounted_usd REAL,measured_usd REAL)')
                db.executemany('INSERT INTO calls VALUES (?,?,?,?,?)',[
                    ('2026-11-07T12:00:00+00:00','llm','complete',1,1),
                    ('2026-11-08T01:00:00+00:00','llm','complete',.01,.01),
                    ('2026-11-08T02:00:00+00:00','vision','uncertain',.05,None)])
            before=path.read_bytes();report=usage_since(root,'2026-11-08T00:00:00Z')
            self.assertEqual(report['calls'],2);self.assertEqual(report['accounted_usd'],.06)
            self.assertEqual(report['stages']['vision']['uncertain'],1)
            self.assertEqual(path.read_bytes(),before)
            with self.assertRaises(ValueError):usage_since(root,'2026-11-08T00:00:00')

    def test_authenticated_http_measurements_return_only_sizes_and_durations(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);corpus(root)
            server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Corpus(root),'pilot','private-fixture'))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with patch.dict('os.environ',{'KARARECALL_USERNAME':'pilot','KARARECALL_PASSWORD':'private-fixture'}):
                    report=http_benchmark('http://127.0.0.1:'+str(server.server_port))
                self.assertEqual(len(report),3);self.assertTrue(all(row['bytes_max']>0 for row in report))
                for value in ('private-fixture','demo-model','example.com'):self.assertNotIn(value,json.dumps(report))
                with self.assertRaises(ValueError):http_benchmark('https://user:secret@example.org')
            finally:server.shutdown();server.server_close();thread.join(5)
