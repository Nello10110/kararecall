"""Synthetic audiovisual integration tests. Requires the optional worker image."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

import cerveau
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

    def test_audio_and_frames_are_extracted_sent_and_cached(self):
        from worker_media import transcribe,recognize_frames
        transcribe(self.media,self.output,self.config)
        recognize_frames(self.media,self.output,self.config)
        transcript=cerveau.read_json(self.output/'transcript.json')
        ocr=cerveau.read_json(self.output/'ocr.json')
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
        self.assertEqual(len(cerveau.read_json(self.output/'ocr.json')['frames']),2)

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
        self.assertEqual(cerveau.read_json(self.output/'transcript.json')['status'],'not_applicable')


if __name__=='__main__':unittest.main()
