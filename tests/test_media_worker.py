"""Synthetic audiovisual integration tests. Requires the optional worker image."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

import kararecall
from settings import Settings
from integrations import ServiceError


@unittest.skipUnless(importlib.util.find_spec('av') and importlib.util.find_spec('numpy'),'Dépendances du travailleur optionnel absentes')
class MediaTests(unittest.TestCase):
    def setUp(self):
        import av
        import numpy as np
        self.temporary=tempfile.TemporaryDirectory()
        root=Path(self.temporary.name)
        self.media=root/'sample.mp4';self.output=root/'extracted';self.output.mkdir()
        with av.open(str(self.media),'w') as container:
            video=container.add_stream('mpeg4',rate=5)
            video.width=64;video.height=64;video.pix_fmt='yuv420p'
            audio=container.add_stream('aac',rate=16000)
            audio.layout='mono'
            for i in range(10):
                frame=av.VideoFrame.from_ndarray(np.full((64,64,3),i*10,dtype=np.uint8),format='rgb24')
                for packet in video.encode(frame):container.mux(packet)
            for packet in video.encode():container.mux(packet)
            sound=av.AudioFrame.from_ndarray(np.zeros((1,16000),dtype=np.float32),format='fltp',layout='mono')
            sound.sample_rate=16000
            for packet in audio.encode(sound):container.mux(packet)
            for packet in audio.encode():container.mux(packet)
        self.calls=[]
        self.fail_second_vision=False
        owner=self
        class Mock(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=self.rfile.read(int(self.headers['Content-Length']))
                owner.calls.append((self.path,body))
                if owner.fail_second_vision and len(owner.calls)==2:
                    self.send_response(503);self.send_header('Content-Length','0');self.end_headers();return
                if self.path=='/v1/audio/transcriptions':
                    data={'language':'fr','segments':[{'start':0,'end':0.7,'text':'Audio de test synthétique.'}]}
                else:
                    data={'choices':[{'message':{'content':json.dumps({'text':'Écran de test synthétique'})}}]}
                encoded=json.dumps(data).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(encoded)));self.end_headers();self.wfile.write(encoded)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Mock)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        base='http://127.0.0.1:'+str(self.server.server_port)+'/v1'
        self.config=Settings(root=root,asr_url=base,asr_model='test-asr',vision_url=base,vision_model='test-vision',vision_max_frames=2,vision_interval=1)

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5);self.temporary.cleanup()

    def test_embedded_text_subtitles_avoid_asr_and_keep_provenance(self):
        import av
        import numpy as np
        import shutil
        from publication import active_root
        from worker import run_cycle

        root=self.config.root
        srt=root/'embedded.srt'
        srt.write_text('1\n00:00:01,000 --> 00:00:03,500\nSous-titre français de test\n\n',encoding='utf-8')
        video_path=root/'embedded.mkv'
        with av.open(str(srt)) as source,av.open(str(video_path),'w') as output:
            stream=output.add_stream('mpeg4',rate=1)
            stream.width=64;stream.height=64;stream.pix_fmt='yuv420p'
            subtitles=output.add_stream_from_template(source.streams.subtitles[0])
            subtitles.metadata['language']='fra'
            for _ in range(5):
                frame=av.VideoFrame.from_ndarray(np.zeros((64,64,3),dtype=np.uint8),format='rgb24')
                for packet in stream.encode(frame):output.mux(packet)
            for packet in stream.encode():output.mux(packet)
            for packet in source.demux(source.streams.subtitles[0]):
                if packet.dts is not None:
                    packet.stream=subtitles
                    output.mux(packet)
        self.config.sync_enabled=True
        self.config.karakeep_url=self.config.asr_url
        self.config.karakeep_key='fixture-only'
        self.config.vision_model=''
        self.config.reuse_subtitles=True
        bookmark={'id':'with-subtitles','createdAt':'2026-11-05T12:00:00Z',
                  'content':{'type':'link','url':'https://example.com/video','videoAssetId':'video-file'}}
        def download(_,destination):
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(video_path,destination)
        with patch('worker.Karakeep.bookmarks',return_value=iter([bookmark])),patch('worker.Karakeep.download',side_effect=download):
            self.assertEqual(run_cycle(self.config)['processed'],1)
        self.assertEqual(self.calls,[])
        source=kararecall.read_json(active_root(root)/'data/catalog.json')['sources'][0]
        self.assertEqual(source['stages']['asr'],'subtitles_reused')
        self.assertFalse(source['processing']['audio_transcribed'])
        proof=next(row for row in source['evidence'] if row['kind']=='subtitle')
        self.assertEqual((proof['start'],proof['end']),(1.0,3.5))
        self.assertEqual(proof['recognition']['language'],'fra')

    def test_audio_and_frames_are_extracted_sent_and_cached(self):
        from worker_media import transcribe,recognize_frames
        transcribe(self.media,self.output,self.config)
        recognize_frames(self.media,self.output,self.config)
        transcript=kararecall.read_json(self.output/'transcript.json')
        ocr=kararecall.read_json(self.output/'ocr.json')
        self.assertEqual(transcript['segments'][0]['text'],'Audio de test synthétique.')
        self.assertEqual(transcript['timestamp_precision'],'segments')
        self.assertEqual(len(ocr['frames']),2)
        self.assertIsNone(ocr['frames'][0]['lines'][0]['confidence'])
        self.assertTrue((self.output/ocr['frames'][0]['image']).is_file())
        self.assertEqual(len(self.calls),3)
        self.assertIn(b'RIFF',self.calls[0][1])
        vision=json.loads(self.calls[1][1])
        self.assertTrue(vision['messages'][0]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,'))
        transcribe(self.media,self.output,self.config)
        recognize_frames(self.media,self.output,self.config)
        self.assertEqual(len(self.calls),3)

    def test_duration_limit_prevents_audio_upload(self):
        from worker_media import transcribe
        self.config.media_max_seconds=0.1
        with self.assertRaisesRegex(ServiceError,'MEDIA_MAX_SECONDS'):
            transcribe(self.media,self.output,self.config)
        self.assertEqual(self.calls,[])

    def test_provider_change_invalidates_audio_cache(self):
        from worker_media import transcribe
        transcribe(self.media,self.output,self.config)
        self.config.asr_url=self.config.asr_url.replace('127.0.0.1','localhost')
        transcribe(self.media,self.output,self.config)
        self.assertEqual(len(self.calls),2)

    def test_completed_vision_frames_resume_after_failure(self):
        from worker_media import recognize_frames
        self.fail_second_vision=True
        with self.assertRaises(ServiceError):recognize_frames(self.media,self.output,self.config)
        self.fail_second_vision=False
        recognize_frames(self.media,self.output,self.config)
        self.assertEqual(len(self.calls),3)
        self.assertEqual(len(kararecall.read_json(self.output/'ocr.json')['frames']),2)

    def test_change_sampling_keeps_frame_budget_and_prioritizes_transitions(self):
        import av
        import numpy as np
        from worker_media import recognize_frames

        video=self.media.parent/'changes.mp4'
        with av.open(str(video),'w') as container:
            stream=container.add_stream('mpeg4',rate=10)
            stream.width=64;stream.height=64;stream.pix_fmt='yuv420p'
            for index in range(20):
                level=240 if 5<=index<15 else 10
                frame=av.VideoFrame.from_ndarray(np.full((64,64,3),level,dtype=np.uint8),format='rgb24')
                for packet in stream.encode(frame):container.mux(packet)
            for packet in stream.encode():container.mux(packet)
        self.config.vision_sample_mode='changes'
        recognize_frames(video,self.output,self.config)
        ocr=kararecall.read_json(self.output/'ocr.json')
        self.assertEqual(ocr['sampling'],'bounded_changes')
        self.assertEqual([row['time'] for row in ocr['frames']],[0.5,1.5])
        self.assertEqual(len(self.calls),2)

    def test_video_without_audio_never_calls_audio_service(self):
        import av
        import numpy as np
        from worker_media import transcribe
        video=self.media.parent/'silent.mp4'
        with av.open(str(video),'w') as container:
            stream=container.add_stream('mpeg4',rate=5);stream.width=64;stream.height=64;stream.pix_fmt='yuv420p'
            frame=av.VideoFrame.from_ndarray(np.zeros((64,64,3),dtype=np.uint8),format='rgb24')
            for packet in stream.encode(frame):container.mux(packet)
            for packet in stream.encode():container.mux(packet)
        self.assertEqual(transcribe(video,self.output,self.config),'not_applicable')
        self.assertEqual(self.calls,[])
        self.assertEqual(kararecall.read_json(self.output/'transcript.json')['status'],'not_applicable')


if __name__=='__main__':unittest.main()
