import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kararecall import core as kararecall
from fixtures import corpus
from kararecall.publication import active_root,file_hash,generation,migrate
from kararecall.web_server import Corpus,context_for,source_summary


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        corpus(self.root)
        self.publish_migration()

    def tearDown(self):self.temp.cleanup()

    def publish_migration(self):
        with generation(self.root) as (draft,commit):
            sources,entities=migrate(kararecall.read_json(draft/'data/sources.json'),kararecall.read_json(draft/'data/entities.json'),draft)
            kararecall.write_json(draft/'data/sources.json',sources)
            kararecall.write_json(draft/'data/entities.json',entities)
            commit()

    def test_retranscription_preserves_exact_old_citation_and_reader_snapshot(self):
        reader=Corpus(self.root)
        old,oldroot,assets=reader.view()
        entity=old['entities'][0]
        old_ref=entity['claims'][0]['evidence'][0]
        old_text=next(e['text'] for e in old['sources'][0]['evidence'] if old_ref.endswith('#'+e['id']))
        with generation(self.root) as (draft,commit):
            path=draft/'data/extracted/demo-model/transcript.json'
            transcript=kararecall.read_json(path);transcript['segments'][0]['text']='Nouvelle transcription contradictoire.'
            transcript['model']='different-model';kararecall.write_json(path,transcript)
            commit()
        current,newroot,_=reader.view()
        self.assertNotEqual(oldroot,newroot)
        source=current['sources'][0]
        retained=next(e for e in source['evidence'] if old_ref.endswith('#'+e['id']))
        self.assertTrue(retained['archived']);self.assertEqual(retained['text'],old_text)
        self.assertEqual(source_summary(source)['transcript_count'],1)
        packet=context_for(entity,{s['id']:s for s in current['sources']})
        self.assertIn(old_text,packet);self.assertIn('version antérieure',packet)
        self.assertNotIn('Nouvelle transcription contradictoire.',packet)
        self.assertEqual(kararecall.read_json(oldroot/'data/catalog.json'),old)

    def test_invalid_publication_keeps_complete_previous_generation(self):
        before=(self.root/'data/current.json').read_bytes();oldroot=active_root(self.root)
        with self.assertRaises(ValueError):
            with generation(self.root) as (draft,commit):
                entities=kararecall.read_json(draft/'data/entities.json')
                entities[0]['claims'][0]['evidence']=['demo-model#missing-proof']
                kararecall.write_json(draft/'data/entities.json',entities)
                commit()
        self.assertEqual((self.root/'data/current.json').read_bytes(),before)
        self.assertEqual(active_root(self.root),oldroot)
        self.assertTrue((oldroot/'vault/outils/heretic.md').exists())
        self.assertEqual(len(list((self.root/'data/generations').iterdir())),1)

    def test_failure_at_pointer_switch_preserves_previous_export_and_media(self):
        oldroot=active_root(self.root);old=(oldroot/'vault/outils/heretic.md').read_bytes()
        write=kararecall.write_json
        def fail_pointer(path,value):
            if path==self.root/'data/current.json':raise OSError('simulated pointer failure')
            return write(path,value)
        with self.assertRaises(OSError):
            with generation(self.root) as (draft,commit):
                with patch('kararecall.core.write_json',side_effect=fail_pointer):commit()
        self.assertEqual(active_root(self.root),oldroot)
        self.assertEqual((oldroot/'vault/outils/heretic.md').read_bytes(),old)

    def test_screenshot_bytes_are_immutable_across_generations(self):
        oldroot=active_root(self.root)
        old=kararecall.read_json(oldroot/'data/catalog.json')
        frame=next(e for e in old['sources'][0]['evidence'] if e['kind']=='ocr')
        image=(oldroot/frame['image']).read_bytes()
        with generation(self.root) as (draft,commit):
            (draft/'data/extracted/demo-model/frame.jpg').write_bytes(b'different screenshot')
            commit()
        self.assertEqual((oldroot/frame['image']).read_bytes(),image)
        self.assertEqual((active_root(self.root)/frame['image']).read_bytes(),image)

    def test_pointer_cannot_escape_storage(self):
        kararecall.write_json(self.root/'data/current.json',{'generation':'../../outside'})
        with self.assertRaises(ValueError):active_root(self.root)

    def test_media_hash_is_reused_across_generations_and_detects_modified_bytes(self):
        media=active_root(self.root)/'data/media/demo-model.mp4'
        digest=file_hash(media)
        with generation(self.root) as (draft,_):
            linked=draft/'data/media/demo-model.mp4'
            with patch('kararecall.publication._hash_stream',side_effect=AssertionError('Unexpected rehash')):
                self.assertEqual(file_hash(linked),digest)
            previous=linked.stat()
            linked.write_bytes(b'X'*previous.st_size)
            os.utime(linked,ns=(previous.st_atime_ns,previous.st_mtime_ns))
            self.assertNotEqual(file_hash(linked),digest)
            with self.assertRaisesRegex(ValueError,'Extraction périmée'):
                kararecall.build(draft)

    def test_exception_after_pointer_switch_never_deletes_selected_generation(self):
        oldroot=active_root(self.root);write=kararecall.write_json
        def switch_then_fail(path,value):
            write(path,value)
            if path==self.root/'data/current.json':raise OSError('error after atomic rename')
        with self.assertRaises(OSError):
            with generation(self.root) as (draft,commit):
                with patch('kararecall.core.write_json',side_effect=switch_then_fail):commit()
        self.assertNotEqual(active_root(self.root),oldroot)
        self.assertEqual(len(Corpus(self.root).load()['entities']),2)
