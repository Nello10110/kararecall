"""Synthetic corpus for distributable tests. No real bookmarks or user media."""
import hashlib
from pathlib import Path
import cerveau


def corpus(root):
    sources=[]
    for sid,title in [('demo-model','Un modèle qui ne répond plus non'),('demo-tv','Nettoyer les pubs et applis inutiles de ma télé')]:
        media=root/'data/media'/f'{sid}.mp4'
        media.parent.mkdir(parents=True,exist_ok=True)
        media.write_bytes(bytes(range(256))*64)  # Byte-range fixture, deliberately not a real video.
        digest=hashlib.sha256(media.read_bytes()).hexdigest()
        extracted=root/'data/extracted'/sid
        extracted.mkdir(parents=True,exist_ok=True)
        (extracted/'frame.jpg').write_bytes(b'synthetic-image')
        cerveau.write_json(extracted/'transcript.json',{'status':'complete','duration':30,'media_sha256':digest,
            'segments':[{'start':18,'end':20,'text':'Le nom de cet outil est présent dans cette source synthétique.'}]})
        cerveau.write_json(extracted/'ocr.json',{'status':'complete','duration':30,'interval':1,'media_sha256':digest,
            'frames':[{'time':21,'image':'frame.jpg','lines':[{'text':'theo-buildz / tv-detox' if sid=='demo-tv' else 'Un nom de modèle', 'confidence':None}]}]})
        raw='data/raw/'+sid+'.txt'
        (root/'data/raw').mkdir(exist_ok=True)
        (root/raw).write_text(title)
        sources.append(dict(id=sid,url='https://example.com/'+sid,created_at='2026-10-31T08:00:00Z',modified_at='2026-10-31T08:00:00Z',
            title='Auteur de démonstration on Instagram: '+title,description=title,note='',tags=['Démonstration'],page_text='',
            karakeep_summary_unverified='',assets=[],raw_file=raw))
    entities=[]
    for sid,name,eid in [('demo-model','Heretic de démonstration','heretic'),('demo-tv','TV Detox de démonstration','tv-detox')]:
        text='Un outil pour enlever les pubs et les applis inutiles de sa télé.' if sid=='demo-tv' else 'Un modèle de démonstration qui ne répond plus non.'
        entry=dict(text=text,status='source_claim',evidence=[sid+'#asr-000'])
        entities.append(dict(id=eid,name=name,description=text,aliases=['démonstration'],source_ids=[sid],claims=[entry],
            details={key:[entry] for key,_ in cerveau.DETAIL_SECTIONS},links=[dict(url='https://example.com/'+sid,label='Source de démonstration',status='source_publication',evidence=sid+'#caption')],follow_up='Comparer les preuves synthétiques.'))
    cerveau.write_json(root/'data/sources.json',sources)
    cerveau.write_json(root/'data/entities.json',entities)
    return cerveau.build(root)
