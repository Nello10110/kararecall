"""Observed content coverage, distinct from import, inference and source truth."""
from collections import Counter
from urllib.parse import urlsplit

STATES={'metadata':'Métadonnées seules','content':'Contenu disponible','partial':'Analyse partielle',
        'analyzed':'Analyse configurée terminée','unsupported':'Format non pris en charge'}
KINDS={'article':'Sites et articles','video':'Vidéos jointes','remote_video':'Vidéos sans fichier joint',
       'note':'Notes personnelles','pdf':'PDF','image':'Images','unknown':'Formats inconnus'}
ASSET_TYPES=('linkHtmlContent','screenshot','pdf','assetScreenshot','bannerImage','fullPageArchive',
             'video','bookmarkAsset','precrawledArchive','userUploaded','avatar','unknown','image')


def content_kind(source):
    if source.get('processing',{}).get('media_downloaded') or any(a.get('type')=='video' for a in source.get('assets',[])):return 'video'
    if source.get('document_asset_id') and not (source.get('bookmark_type')=='link' and source.get('page_text')):return source.get('asset_type') if source.get('asset_type') in ('pdf','image') else 'unknown'
    kind=source.get('bookmark_type','link')
    if kind=='text':return 'note'
    if kind!='link':return 'unknown'
    url=urlsplit(source.get('url',''));host=url.hostname or ''
    if host in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be') and (host=='youtu.be' or url.path.startswith(('/watch','/shorts/','/embed/','/live/'))):return 'remote_video'
    if host in ('instagram.com','www.instagram.com') and url.path.startswith(('/reel/','/reels/')):return 'remote_video'
    return 'article'


def coverage(source):
    if source.get('coverage_state'):return source['coverage_state']
    kind=content_kind(source);processing=source.get('processing',{});attachment=processing.get('attachment') or {}
    evidence=[row for row in source.get('evidence',[]) if not row.get('archived')]
    has_text=bool(source.get('page_text') or any(row.get('text','').strip() for row in evidence if row.get('kind') not in ('caption','note','passage')))
    summary=bool(source.get('reading') or source.get('has_reading'));stages=source.get('stages',{})
    limits=[];state='content' if has_text else 'metadata'
    if kind=='unknown':
        state='unsupported';limits.append('Le favori est conservé ; aucun extracteur n’est associé à son type.')
    elif kind=='remote_video':
        state='partial' if has_text or summary else 'metadata'
        limits.append('Aucune vidéo jointe fournie par Karakeep : les paroles et les images ne sont pas analysées.')
    elif kind=='video':
        audio=processing.get('audio_transcribed') or processing.get('subtitles_available') or stages.get('asr')=='not_applicable'
        screen=processing.get('ocr_sampled')
        state='analyzed' if audio and screen and summary else 'partial' if has_text or summary or audio or screen else 'metadata'
        limits.append('Lecture d’écran par échantillonnage ; les images non sélectionnées ne sont pas analysées.')
        if not audio:limits.append('Paroles indisponibles ou transcription non terminée.')
        if not screen:limits.append('Lecture d’écran indisponible ou non terminée.')
    elif summary:
        state='analyzed' if has_text else 'partial'
    if attachment.get('truncated') or any(row.get('text_truncated') for row in source.get('reading',{}).get('coverage',{}).values()):
        state='partial'
        limits.append('Une partie du document n’a pas été représentée dans l’analyse.')
    if attachment.get('frames_total',1)>1:
        limits.append(f"Animation : première image lue sur {attachment['frames_total']} ; le mouvement n’est pas analysé.")
    if not has_text and kind not in ('video','remote_video','unknown'):
        limits.append('Le contenu principal n’est pas disponible ; un résumé éventuel se limite aux métadonnées.')
    if source.get('crawl_status') in ('pending','failure'):
        limits.append('La collecte Karakeep est '+('en attente.' if source['crawl_status']=='pending' else 'en échec.'))
    unhandled=[a for a in source.get('assets',[]) if a.get('type') in ('fullPageArchive','precrawledArchive','userUploaded','unknown') or a.get('type') not in ASSET_TYPES]
    if unhandled:
        limits.append('Certaines pièces jointes sont inventoriées mais n’ont pas d’extracteur ; leur contenu n’a pas été analysé.')
        if state=='analyzed':state='partial'
    if any(value in ('failed','paused','waiting_content','waiting') for value in stages.values()) and state=='analyzed':state='partial'
    return {'kind':kind,'state':state,'label':STATES[state],'has_text':has_text,'has_summary':summary,'limitations':limits}


def inventory(sources):
    """A shareable projection: counts only, no titles, domains or source IDs."""
    rows={kind:{'kind':kind,'label':label,'total':0,'states':{state:0 for state in STATES}} for kind,label in KINDS.items()}
    totals=Counter();assets=Counter();crawl=Counter()
    for source in sources:
        item=coverage(source);row=rows[item['kind']];row['total']+=1;row['states'][item['state']]+=1;totals[item['state']]+=1
        for asset in source.get('assets',[]):assets[asset.get('type') if asset.get('type') in ASSET_TYPES else 'unknown']+=1
        if source.get('crawl_status') in ('pending','failure','success'):crawl[source['crawl_status']]+=1
    return {'total':len(sources),'states':{key:totals[key] for key in STATES},'labels':STATES,
            'kinds':list(rows.values()),'attachments':dict(assets),'karakeep_crawl':dict(crawl),
            'qualification':'local_observation_not_provider_validation'}
