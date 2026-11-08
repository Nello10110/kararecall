'use strict';

// Shared reading views. Link selection never invents a URL or an official identity.
function navigableUrl(value){try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password?url:null;}catch{return null;}}
function recordRouteLabel(route){return /#\/tools\//.test(route)?'Ouvrir l’outil':'Ouvrir la source';}
function destinationKind(url){
 if(['github.com','gitlab.com','codeberg.org','bitbucket.org'].includes(url.hostname)&&url.pathname.split('/').filter(Boolean).length>=2)return 'repository';
 if(url.hostname.startsWith('docs.')||/^\/(docs?|documentation)(\/|$)/i.test(url.pathname))return 'documentation';
 return 'site';
}
function toolDestination(entity,sources=[]){
 const originals=new Set(sources.map(row=>navigableUrl(row.url)?.href).filter(Boolean));
 const scores={page_read:100,repository_exists:85,linked_from_official_page:70,user_link_unchecked:45,visible_in_video_unchecked:35,caption_mention_unchecked:30,source_link_unchecked:30};
 return (entity.links||[]).map((link,index)=>{
  const url=navigableUrl(link.url),score=scores[link.status],kind=url?destinationKind(url):null;
  if(!url||!score||(originals.has(url.href)&&kind==='site'&&url.pathname!=='/')||/(^|\.)(instagram\.com|tiktok\.com|youtube\.com|youtu\.be|facebook\.com|linkedin\.com|x\.com|twitter\.com)$/.test(url.hostname))return null;
  const read=['page_read','repository_exists'].includes(link.status);
  return {url:url.href,domain:url.hostname.replace(/^www\./,''),kind,status:link.status,read,
   label:read||link.status==='linked_from_official_page'?{site:'Ouvrir le site',repository:'Voir le dépôt',documentation:'Lire la documentation'}[kind]:'Ouvrir le lien',
   note:linkLabels[link.status]||'Accès non vérifié',score:score+(kind==='site'&&url.pathname==='/'?5:0),index};
 }).filter(Boolean).sort((a,b)=>b.score-a.score||a.index-b.index)[0]||null;
}
function toolLead(entity){
 const candidates=[entity.description,...(entity.details?.usefulness||[]).map(row=>row.text),...(entity.details?.description||[]).map(row=>row.text)];
 const text=candidates.find(value=>typeof value==='string'&&value.trim()&&!(/\b(cite|mentionne|presente|repere)(?:e|s)?\b.{0,65}\b(video|reel|publication|source|instagram)\b/i.test(value.normalize('NFD').replace(/\p{M}/gu,''))&&value.length<220));
 return text?.trim()||'Les usages, le fonctionnement et les liens disponibles sont réunis dans cette fiche.';
}
function proofDetails(entry){
 const refs=[...new Set(entry.evidence||[])];
 const documentary=navigableUrl(entry.verification_url);
 if(!refs.length&&!documentary)return '';
 return `<details class="claim-references"><summary>${refs.length+(documentary?1:0)} référence${refs.length+(documentary?1:0)>1?'s':''}</summary><div class="evidence-links">${refs.map((ref,index)=>reference(ref,index+1)).join('')}${documentary?`<a class="evidence-link" href="${safeUrl(documentary.href)}" target="_blank" rel="noopener noreferrer">${icon('external')}Documentation consultée</a>`:''}</div></details>`;
}
function claim(entry){return `<div class="claim"><p>${esc(entry.text)}</p><div class="claim-meta"><span class="claim-attribution ${entry.status==='hypothesis'?'uncertain':''}">${esc(labels[entry.status]||entry.status||'Selon la source')}</span>${proofDetails(entry)}</div></div>`;}
function linkCard(link){
 const url=navigableUrl(link.url);if(!url)return '';
 const warning=link.status==='not_found_at_check'||String(link.status).includes('unchecked');
 return `<a class="resource-link" href="${safeUrl(url.href)}" target="_blank" rel="noopener noreferrer"><span class="resource-icon">${icon(destinationKind(url)==='repository'?'book':'external')}</span><span><strong>${esc(link.label||url.hostname)}</strong><small>${esc(url.hostname.replace(/^www\./,''))}</small>${link.purpose?`<p>${esc(link.purpose)}</p>`:''}<span class="resource-status ${warning?'uncertain':''}">${esc(linkLabels[link.status]||'Accès non vérifié')}</span></span>${icon('external')}</a>`;
}
function toolCard(entity){
 const sources=(entity.source_ids||[]).map(id=>state.sources.get(id)).filter(Boolean),destination=toolDestination(entity,sources);
 const review=['machine-generated','user-edited'].includes(entity.curation);
 return `<article class="tool-card reading-tool-card"><a class="tool-card-main" href="${slugRoute('tools',entity.id)}"><div class="card-top">${logo(entity)}<span class="card-arrow">${icon('arrow')}</span></div><h3>${esc(toolName(entity))}</h3><p class="desc">${esc(toolLead(entity))}</p><div class="tags">${(entity.aliases||[]).slice(0,3).map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div></a><div class="card-footer">${destination?`<a class="tool-card-site" href="${safeUrl(destination.url)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(destination.label+' pour '+toolName(entity))}" title="${esc(destination.note)}">${esc(destination.domain)} ${icon('external')}</a>`:'<span>Lien à renseigner</span>'}${review?badge('À relire','neutral'):''}</div></article>`;
}
function disclosure(title,description,content,extra='',className=''){
 return `<details class="detail-panel record-disclosure ${className}" ${extra}><summary><span><strong>${title}</strong>${description?`<small>${description}</small>`:''}</span>${icon('arrow')}</summary><div class="disclosure-content">${content}</div></details>`;
}
function exportMenu(links){return `<details class="record-menu"><summary class="btn">${icon('download')}Exporter</summary><div>${links}</div></details>`;}
function revealSection(id){
 const section=document.getElementById(id);if(!section)return;
 section.open=true;
 section.querySelectorAll('details.source-status').forEach(row=>row.open=true);
 section.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
 section.querySelector('summary,button,input')?.focus({preventScroll:true});
}
function bindReadingView(){
 document.querySelectorAll('[data-reveal]').forEach(button=>button.onclick=()=>revealSection(button.dataset.reveal));
 if(state.readingMenuListeners)return;
 state.readingMenuListeners=true;
 document.addEventListener('click',event=>document.querySelectorAll('.record-menu[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;}));
 document.addEventListener('keydown',event=>{if(event.key==='Escape')document.querySelectorAll('.record-menu[open]').forEach(menu=>{menu.open=false;menu.querySelector('summary')?.focus();});});
}
function sourceAttention(source){
 const states=Object.values(source.stages||{}),failed=states.includes('failed'),paused=states.includes('paused');
 if(!failed&&!paused)return '';
 return `<div class="record-attention" role="status">${icon('info')}<span>${failed?'Une étape d’analyse a échoué.':'Une étape d’analyse est en pause.'} Les contenus déjà disponibles restent consultables.</span><button type="button" class="text-link" data-reveal="source-management">Voir le détail</button></div>`;
}
async function toolPage(id,epoch){
 const {entity:e,sources,revision}=await api('/api/tools/'+encodeURIComponent(id));if(state.epoch!==epoch)return;
 const destination=toolDestination(e,sources),related=[...state.entities.values()].filter(other=>other.id!==e.id&&other.source_ids.some(s=>e.source_ids.includes(s)));
 const review=e.curation==='user-reviewed'?'Fiche relue':['machine-generated','user-edited'].includes(e.curation)?'À relire':'';
 const resourceLinks=(e.links||[]).filter(link=>link.status!=='source_publication');
 const mainSections=[['usefulness','À quoi ça sert','spark'],['operation','Comment ça fonctionne','activity'],['limitations','Ce qu’il faut savoir','info']].map(([key,label,i])=>`<section class="detail-panel reading-section"><h2>${icon(i)}${label}</h2>${(e.details?.[key]||[]).map(claim).join('')||'<p class="text-muted">Cette information n’est pas encore documentée.</p>'}</section>`).join('');
 const presentation=(e.details?.description||[]).map(claim).join('')+`<p class="text-muted">${esc(e.description)}</p>${e.aliases?.length?`<div class="tags record-tags">${e.aliases.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>`:''}`;
 const supplementary=e.web_research?.summary?`<section class="detail-panel reading-section"><h2>${icon('book')}Complément documentaire</h2><p>${esc(e.web_research.summary.text)}</p><small class="text-muted">Selon les pages consultées</small><div class="documentary-links">${(e.web_research.summary.urls||[]).map(url=>`<a class="text-link" href="${safeUrl(url)}" target="_blank" rel="noopener noreferrer">${esc(navigableUrl(url)?.hostname||'Page consultée')} ${icon('external')}</a>`).join('')}</div></section>`:'';
 $('#content').innerHTML=`<div class="detail-top"><a class="btn btn-quiet" href="#/library">${icon('back')}Mes outils</a>${exportMenu(`<a href="/download/tool/${encodeURIComponent(e.id)}.md">Fiche Markdown</a>`)}</div>
 <section class="record-hero"><div class="record-identity">${logo(e)}<div><div class="eyebrow">OUTIL${review?' · '+esc(review):''}</div><h1>${esc(toolName(e))}</h1>${destination?`<span class="record-domain">${esc(destination.domain)}</span>`:''}</div></div><p class="record-lead">${esc(toolLead(e))}</p><div class="record-primary-actions">${destination?`<a class="btn btn-primary" href="${safeUrl(destination.url)}" target="_blank" rel="noopener noreferrer">${esc(destination.label)} ${icon('external')}</a>`:'<button class="btn" type="button" data-reveal="tool-management">Ajouter un lien</button>'}<button class="btn" type="button" data-context="${esc(e.id)}">${icon('copy')}Copier pour un assistant</button></div>${destination?`<p class="record-link-note">${esc(destination.note)}</p>`:'<p class="record-link-note">Aucun site n’est renseigné dans cette fiche.</p>'}</section>
 <div class="record-layout"><div>${mainSections}${supplementary}${disclosure('Présentation détaillée','Description complète conservée dans la fiche',presentation)}${e.claims?.length?disclosure('Identification et références',`${e.claims.length} élément(s) conservé(s)`,e.claims.map(claim).join('')):''}${Object.values(e.coverage||{}).some(c=>c.text_truncated||c.included<c.available)?'<div class="notice">Cette fiche repose sur une sélection d’extraits ; sa couverture est partielle.</div>':''}</div><aside class="record-aside"><section class="aside-panel reading-resources"><h2>Liens utiles</h2>${resourceLinks.map(linkCard).join('')||'<p class="text-muted">Aucun lien disponible pour le moment.</p>'}</section>${disclosure('Sources de cette fiche',`${sources.length} source${sources.length>1?'s':''} à consulter`,sources.map(s=>`<a class="source-reference-row" href="${sourceLink(s)}"><strong>${esc(s.title)}</strong><small>${esc(s.author)} · ${date(s.created_at)}</small>${icon('arrow')}</a>`).join(''))}${e.follow_up?`<section class="aside-panel assistant-next"><h2>Poursuivre avec un assistant</h2><p>${esc(e.follow_up)}</p><small>Le bouton de copie prépare le contexte et les références.</small></section>`:''}</aside></div>
 ${related.length?`<section class="detail-panel related-reading"><h2>À découvrir aussi</h2><div class="related-links">${related.map(other=>`<a class="btn" href="${slugRoute('tools',other.id)}">${esc(toolName(other))} ${icon('arrow')}</a>`).join('')}</div></section>`:''}
 ${disclosure('Gérer cette fiche','Modifier, regrouper ou compléter les informations',editorForm(e)+`<section class="record-maintenance"><h3>Compléter depuis le web</h3><p>Cette commande utilise les services configurés et le budget IA.</p><button class="btn" type="button" data-action="research" data-tool-id="${esc(e.id)}">${icon('search')}Enrichir la description sur le web</button></section>`+researchPanel(e),'id="tool-management"','record-management')}`;
 document.querySelectorAll('[data-context]').forEach(b=>b.onclick=()=>copyContext(e.id));bindEditor(e,revision);bindActions();bindReadingView();
}
