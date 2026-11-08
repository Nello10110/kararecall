"""Optional software decoding plus configured remote ASR/vision; sequential processing."""
import hashlib
import json
from pathlib import Path
import tempfile
import wave
import uuid
from kararecall.publication import file_hash

from kararecall import core as kararecall
from kararecall.integrations import recognize_image, OCR_CONTRACT, json_object_mode, request, ServiceError


TEXT_SUBTITLES={'mov_text','subrip','srt','ass','ssa','webvtt','text'}
PLAIN_TEXT_SUBTITLES={'subrip','srt','text'}


def extract_subtitles(media,output,settings):
    import av

    digest=file_hash(media)
    target=output/'subtitles.json'
    previous=kararecall.read_json(target,{})
    if (previous.get('media_sha256')==digest and previous.get('engine')=='pyav-text-track-v2'
            and previous.get('max_seconds')==settings.media_max_seconds):
        return previous['status']
    result={'engine':'pyav-text-track-v2','media_sha256':digest,'max_seconds':settings.media_max_seconds,
            'status':'not_applicable','segments':[]}
    with av.open(str(media)) as container:
        tracks=[stream for stream in container.streams.subtitles
                if stream.codec_context.name in TEXT_SUBTITLES and not (stream.disposition & stream.disposition.forced)]
        if tracks:
            tracks.sort(key=lambda stream:(stream.metadata.get('language') not in ('fra','fre','fr'),stream.index))
            track=tracks[0]
            result.update(track=track.index,language=track.metadata.get('language') or 'unknown')
            origin=float((container.start_time or 0)/av.time_base)
            duration=float(container.duration/av.time_base) if container.duration else None
            result['duration']=duration
            if duration and duration>settings.media_max_seconds:
                result['status']='partial'
            else:
                for index,packet in enumerate(container.demux(track)):
                    if index>=3000 or len(result['segments'])>=1000:
                        result['status']='partial'
                        break
                    if not packet.size:
                        continue
                    if packet.pts is None or packet.time_base is None:
                        result['status']='partial'
                        continue
                    base=float(packet.pts*packet.time_base)-origin
                    packet_end=base+float(packet.duration*packet.time_base) if packet.duration else base
                    if track.codec_context.name in PLAIN_TEXT_SUBTITLES and packet.duration:
                        start,end=max(0,base),packet_end
                        text=bytes(packet).decode('utf-8','replace').strip()
                    else:
                        subset=track.decode2(packet)
                        if subset is None:
                            continue
                        start=max(0,base+subset.start_display_time/1000)
                        end=packet_end if packet.duration else base+subset.end_display_time/1000
                        text='\n'.join((getattr(row,'dialogue',b'') or getattr(row,'text',b'')).decode('utf-8','replace')
                                       for row in subset).strip()
                    if not text:
                        continue
                    if end>settings.media_max_seconds:
                        result['status']='partial'
                        break
                    if not 0<=start<end:
                        result['status']='partial'
                        continue
                    if len(text)>4000:
                        result['status']='partial'
                        break
                    result['segments'].append({'start':start,'end':end,'text':text})
                if result['status']!='partial' and result['segments']:
                    result['status']='complete'
    kararecall.write_json(target,result)
    return result['status']


def transcribe(media,output,settings,ledger=None):
    import av
    digest=file_hash(media)
    cache_key=hashlib.sha256(json.dumps(['asr-v2',settings.asr_url,settings.asr_model,settings.asr_timestamps]).encode()).hexdigest()
    old=kararecall.read_json(output/'transcript.json',{})
    if old.get('media_sha256')==digest and old.get('cache_key')==cache_key and old.get('status') in ('complete','not_applicable'):
        return
    with tempfile.TemporaryDirectory() as temporary:
        wav=Path(temporary)/'audio.wav'
        samples=0
        with av.open(str(media)) as container:
            if not container.streams.audio:
                kararecall.write_json(output/'transcript.json',{'engine':'configured-asr-api','model':settings.asr_model,'media_sha256':digest,'cache_key':cache_key,'status':'not_applicable','segments':[]})
                return 'not_applicable'
            resampler=av.AudioResampler(format='s16',layout='mono',rate=16000)
            with wave.open(str(wav),'wb') as target:
                target.setnchannels(1);target.setsampwidth(2);target.setframerate(16000)
                for frame in container.decode(audio=0):
                    for audio in resampler.resample(frame):
                        samples+=audio.samples
                        if samples/16000>settings.media_max_seconds:
                            raise ServiceError('Durée supérieure à MEDIA_MAX_SECONDS ; audio non envoyé.')
                        target.writeframes(audio.to_ndarray().tobytes())
                for audio in resampler.resample(None):
                    samples+=audio.samples
                    if samples/16000>settings.media_max_seconds:
                        raise ServiceError('Durée supérieure à MEDIA_MAX_SECONDS ; audio non envoyé.')
                    target.writeframes(audio.to_ndarray().tobytes())
        duration=samples/16000
        raw=wav.read_bytes()
        if len(raw)>24*1024*1024:
            raise ServiceError('Audio WAV supérieur à 24 Mio ; réduire MEDIA_MAX_SECONDS.')
        boundary=uuid.uuid4().hex
        body=b''
        fields=[('model',settings.asr_model),('response_format','verbose_json')]
        if settings.asr_timestamps:fields.append(('timestamp_granularities[]','segment'))
        for key,value in fields:
            body+=f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        body+=f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode()+raw+f'\r\n--{boundary}--\r\n'.encode()
        def operation():
            with request(settings.asr_url+'/audio/transcriptions',settings.asr_key,body,settings.timeout,'multipart/form-data; boundary='+boundary) as response:
                return json.loads(response.read(8*1024*1024))
        result=ledger.call('asr',settings.asr_url,settings.asr_model,operation,duration) if ledger else operation()
        segments=[]
        for row in result.get('segments',[]):
            start,end=float(row['start']),float(row['end'])
            if not 0<=start<end<=duration+2:
                raise ServiceError('Horodatages ASR non valides ; transcription non publiée.')
            segments.append({'start':start,'end':end,'text':str(row['text']).strip()})
        precision='segments'
        if not segments:
            if not isinstance(result.get('text'),str):
                raise ServiceError('Le service ASR ne renvoie aucun texte.')
            if not result['text'].strip():
                kararecall.write_json(output/'transcript.json',{'engine':'configured-asr-api','model':settings.asr_model,'media_sha256':digest,'cache_key':cache_key,'status':'complete','duration':duration,'segments':[]})
                return
            segments=[{'start':0,'end':duration,'text':str(result['text'])}]
            precision='whole_media'
        kararecall.write_json(output/'transcript.json',{'engine':'configured-asr-api','model':settings.asr_model,
            'cache_key':cache_key,'media_sha256':digest,'duration':duration,'language':result.get('language','unknown'),
            'timestamp_precision':precision,'status':'complete','segments':segments})


def sample_frames(frames, step, prefer_changes):
    if not prefer_changes:
        next_time=0
        for frame in frames:
            if frame.time is not None and frame.time+0.001>=next_time:
                yield frame
                next_time+=step
        return

    import numpy as np

    window, next_probe = 0, 0
    earliest, best_score = 0, -1
    best = previous = None
    for frame in frames:
        timestamp=frame.time
        if timestamp is None or timestamp+0.001<next_probe:
            continue
        next_probe=timestamp+0.5
        current=frame.reformat(width=96,height=54,format='gray').to_ndarray().astype(np.int16)
        score=0 if previous is None else np.abs(current-previous).mean()
        previous=current
        current_window=int(timestamp/step)
        if current_window!=window:
            if best is not None:
                earliest=best.time+step
                yield best
            window,best,best_score=current_window,None,-1
        if timestamp+0.001>=earliest and score>best_score:
            best,best_score=frame,score
    if best is not None:
        yield best


def recognize_frames(media,output,settings,ledger=None):
    import av
    digest=file_hash(media)
    config=['vision-v2',settings.vision_url,settings.vision_model,settings.vision_interval,settings.vision_max_frames,
            settings.vision_max_tokens,settings.vision_reasoning,settings.token_limit_param,settings.vision_thinking,
            OCR_CONTRACT,json_object_mode(settings.vision_url)]
    prefer_changes=settings.vision_sample_mode=='changes'
    if prefer_changes:
        config.append('changes-v1')
    cache_key=hashlib.sha256(json.dumps(config).encode()).hexdigest()
    old=kararecall.read_json(output/'ocr.json',{})
    if old.get('media_sha256')==digest and old.get('cache_key')==cache_key and old.get('status')=='complete':
        return
    rows=[]
    progress_path=output/('vision-progress-'+cache_key+'.json')
    progress=kararecall.read_json(progress_path,{})
    if progress.get('media_sha256')!=digest:progress={'media_sha256':digest,'frames':{}}
    with av.open(str(media)) as container:
        stream=container.streams.video[0]
        duration=float(stream.duration*stream.time_base) if stream.duration else float(container.duration or 0)/1000000
        if not 0<duration<=settings.media_max_seconds:
            raise ServiceError('Durée vidéo absente ou supérieure à MEDIA_MAX_SECONDS ; images non envoyées.')
        step=max(settings.vision_interval,duration/settings.vision_max_frames)
        for frame in sample_frames(container.decode(stream),step,prefer_changes):
            filename=f'frame-{frame.time:08.3f}.jpg'
            path=output/filename
            image=frame.to_image()
            image.thumbnail((1280,1280))
            image.save(path,quality=85)
            cache_id=str(round(frame.time,6))
            if cache_id in progress['frames']:
                row=progress['frames'][cache_id]
            else:
                text=recognize_image(settings.vision_url,settings.vision_key,settings.vision_model,path.read_bytes(),settings.timeout,
                    max_tokens=settings.vision_max_tokens,reasoning=settings.vision_reasoning,thinking=settings.vision_thinking,token_limit_param=settings.token_limit_param,ledger=ledger)
                row={'time':frame.time,'image':filename,'lines':[{'text':line,'confidence':None,'box':None} for line in text.splitlines() if line.strip()]}
                progress['frames'][cache_id]=row
                kararecall.write_json(progress_path,progress)
            rows.append(row)
            if len(rows)>=settings.vision_max_frames:
                break
    kararecall.write_json(output/'ocr.json',{'engine':'configured-vision-api','model':settings.vision_model,
        'cache_key':cache_key,'media_sha256':digest,'duration':duration,'interval':step,'requested_interval':settings.vision_interval,
        'max_frames':settings.vision_max_frames,'sampling':'bounded_changes' if prefer_changes else 'bounded_regular',
        'status':'complete','frames':rows})
