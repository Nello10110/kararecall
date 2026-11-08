'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icons = {
 search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
 grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
 source:'<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 12h7M9 16h5"/>',
 activity:'<path d="M3 12h4l3-7 4 14 3-7h4"/>',
 arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',
 external:'<path d="M14 3h7v7M21 3l-11 11M10 4H4v16h16v-6"/>',
 back:'<path d="M19 12H5m7-7-7 7 7 7"/>',
 download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
 copy:'<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
 play:'<path d="m9 5 11 7-11 7z"/>',
 check:'<path d="m5 12 4 4 10-10"/>',
 info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
 link:'<path d="m10 14 4-4m-7 6-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m4 1 1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0"/>',
 spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
 book:'<path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1zm0 0v15"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 screen:'<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/>',
 refresh:'<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>',
 close:'<path d="m6 6 12 12M6 18 18 6"/>'
};
Object.assign(icons,{home:'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/><path d="M9 21v-8h6v8"/>',settings:'<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/><path d="m9 3-1 3-3 1-2 3 2 2-1 4 3 2 3-1 2 4 3-2 1-3 4-1 1-4-3-2-1-4-4 1Z"/>'});

const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.source}</svg>`;
const labels = {source_claim:'Selon la source',documented:'Documentation éditeur',verified:'Vérification externe',hypothesis:'À confirmer'};
const linkLabels = {user_link_unchecked:'Ajouté lors de la revue · accès non vérifié',repository_exists:'Dépôt trouvé',page_read:'Page consultée',linked_from_official_page:'Lien de l’éditeur · page non relue',not_found_at_check:'Adresse en 404',visible_in_video_unchecked:'Accès non vérifié',caption_mention_unchecked:'Accès non vérifié',source_publication:'Publication d’origine',source_link_unchecked:'Accès non vérifié'};
const state = {catalog:null,sources:new Map(),entities:new Map(),scope:'all',sort:'name',sourceFilter:'all',sourceText:'',sourceOffset:0,processingFilter:'all',processingOffset:0,epoch:0,sourceView:null};
const toolsOrder = ['heretic','higgsfield','instagram-obsidian','tv-detox','claude-code'];
const toolName = e => e.name.replace(/ \(.*\)$/, '');
const date = text => new Intl.DateTimeFormat('fr-FR',{day:'numeric',month:'short',year:'numeric',timeZone:'Europe/Paris'}).format(new Date(text));
const shortDate = text => new Intl.DateTimeFormat('fr-FR',{day:'numeric',month:'short',timeZone:'Europe/Paris'}).format(new Date(text));
const time = seconds => `${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;
const safeUrl = url => {try{const u=new URL(url);return ['http:','https:'].includes(u.protocol)?esc(u.href):'#';}catch{return '#';}};
const asset = path => '/assets/' + path.split('/').map(encodeURIComponent).join('/');
const complete = s => s.processing.audio_transcribed && s.processing.ocr_sampled;
function processingLabel(source){
 if(source.stages?.page==='failed')return 'Texte de page en échec';
 if(source.stages?.llm==='waiting_content')return 'En attente du texte';
 const documentStage=source.stages?.document;
 const attachment=source.processing.attachment;
 if(documentStage==='failed')return 'Extraction en échec';
 if(documentStage==='paused')return 'Extraction en pause';
 if(attachment?.status==='complete')return attachment.truncated?'PDF extrait en partie':'Texte extrait';
 if(attachment?.status==='no_text')return 'Aucun texte extrait';
 if(attachment)return 'Original conservé';
 if(complete(source))return 'Audio et écran analysés';
 if(source.processing.audio_transcribed)return 'Audio transcrit';
 if(source.processing.subtitles_available)return 'Sous-titres récupérés';
 if(source.processing.ocr_sampled)return 'Écran analysé';
 if(source.content_status==='metadata_only')return 'Métadonnées seulement';
 return source.has_reading?'Synthèse disponible':'Texte disponible';
}
const stageLabel = (s,kind,count) => {if(s.has_video===false)return 'Non applicable';const value=s.stages?.[kind];if(value==='failed')return count?'Échec · résultat antérieur disponible':'Échec';if(value==='paused')return 'Quota ou budget atteint';if(value==='disabled')return 'Désactivé';if(value==='subtitles_reused')return 'Sous-titres réutilisés';if(value==='not_applicable')return 'Non applicable';return count?`${count} ${kind==='asr'?'passages':'images'}`:value==='complete'?'Terminé · aucun texte':'—';};
const initials = text => text.split(/\s+/).filter(Boolean).slice(0,2).map(w=>w[0]).join('').toUpperCase();
const slugRoute = (kind,id) => '#/' + kind + '/' + encodeURIComponent(id);
const logo = e => `<span class="tool-logo ${esc(e.id)}">${({heretic:'h',higgsfield:'h', 'tv-detox':icon('screen'),'instagram-obsidian':'◇','claude-code':'✳'})[e.id] || esc(toolName(e)[0])}</span>`;
const badge = (text, style='') => `<span class="badge ${style}">${esc(text)}</span>`;
function toast(text){const t=$('#toast');t.textContent=text;t.classList.add('visible');clearTimeout(toast.timer);toast.timer=setTimeout(()=>t.classList.remove('visible'),3000);}
async function api(path,options={}){const r=await fetch(path,{credentials:'same-origin',...options});if(!r.ok){let message;try{message=(await r.json()).error;}catch{}throw new Error(message || `Le service répond ${r.status}.`);}return r.json();}
function setRoute(route){if(location.hash==='#'+route)renderRoute();else location.hash=route;}
function route(){const text=location.hash.slice(1)||'/dashboard';const [path,query='']=text.split('?');return {parts:path.split('/').filter(Boolean),params:new URLSearchParams(query)};}
function navigateSearch(query){setRoute('/search'+(query?'?q='+encodeURIComponent(query):''));}
function sourceLink(s){return slugRoute('sources',s.id);}
function sourceCard(source){return sourceTile(source);}

function nav(current){shellNavigation(current);}
function intro(eyebrow,title,description,action=''){return `<section class="intro"><div class="page-description"><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div>${action}</section>`;}
function searchForm(q){return `<form class="search-box" id="search-form" role="search">${icon('search')}<input type="search" id="search-input" aria-label="Décrire un outil ou un souvenir" autocomplete="off" placeholder="Décrivez un outil, un besoin, un souvenir…" value="${esc(q)}" maxlength="1000"><button class="btn btn-primary" type="submit">Retrouver</button></form>`;}
function bindSearch(){const form=$('#search-form');form?.addEventListener('submit',e=>{e.preventDefault();navigateSearch($('#search-input').value.trim());});}
function proofRoute(sid,eid,kind,query=''){
 const tab=['asr','subtitle'].includes(kind)?'transcript':kind==='ocr'?'ocr':'raw';
 return slugRoute('sources',sid)+'?'+new URLSearchParams({e:eid,tab,...(query&&tab==='transcript'?{q:query}:{})});
}
const fold = text => text.normalize('NFD').replace(/\p{M}/gu,'').toLocaleLowerCase('fr');
const wordsFor = text => fold(text).match(/[\p{L}\p{N}]+/gu)||[];
function highlighted(text,words){
 return text.split(/([\p{L}\p{N}\p{M}]+)/u).map(part=>words.some(word=>fold(part).includes(word))?`<mark>${esc(part)}</mark>`:esc(part)).join('');
}
function resultCard(r,query){
 const entity=state.entities.get(r.id), source=r.source_summary;
 const snippet=r.snippets?.[0];
 const destination=entity?toolDestination(entity,[source]):null;
 const proof=snippet?proofRoute(snippet.source_id,snippet.evidence_id,snippet.kind,query):null;
 const href=entity?slugRoute('tools',r.id):proof||sourceLink(source);
 const location=snippet?.page?`Page ${snippet.page}`:snippet?.start!=null?time(snippet.start):'';
 const excerpt=snippet?`<div class="snippet">${snippet.archived?'Preuve antérieure · ':''}${location?location+' · ':''}${snippet.display_state==='translation_pending'?'Extrait conservé · traduction française en attente.':highlighted((snippet.display_text??snippet.text).replace(/\n/g,' · '),r.matched)}</div>`:'';
 return `<div class="result-entry"><a class="result-card" href="${esc(href)}">${entity?logo(entity):`<span class="tool-logo">${icon('source')}</span>`}<div class="result-card-body"><div class="result-type">${entity?'Outil':'Source'}${r.matched.length?' · '+r.matched.length+' '+(r.matched.length>1?'repères retrouvés':'repère retrouvé'):''}</div><h3>${esc(entity?toolName(entity):source.title)}</h3><p>${esc(entity?toolLead(entity):source.summary||source.author)}</p>${excerpt}<div class="card-footer"><span>${entity?esc(destination?.domain||'Fiche d’outil'):esc(source.author)+' · '+shortDate(source.created_at)}</span><span>${entity?'Voir la fiche':proof?'Ouvrir le passage':'Voir la source'} →</span></div></div></a>${entity?`<div class="result-reading-actions">${destination?`<a class="text-link" href="${safeUrl(destination.url)}" target="_blank" rel="noopener noreferrer" title="${esc(destination.note)}">${esc(destination.label)} ${icon('external')}</a>`:''}${proof?`<a class="text-link" href="${esc(proof)}">Ouvrir le passage${location?' · '+location:''} ${icon('arrow')}</a>`:''}</div>`:''}</div>`;
}
async function searchPage(query,epoch){
 const main=$('#content');
 main.innerHTML=pageHeading('Retrouver une découverte','Quelques mots suffisent.','Cherchez dans vos sources, vos outils, les résumés et les preuves conservées.')+searchForm(query)+'<p class="search-method">Recherche par mots et variantes orthographiques · aucun appel IA</p><section id="search-content"></section>';
 bindSearch();
 if(!query){
  const suggestions=[...state.entities.values()].slice(0,6);
  $('#search-content').innerHTML=`<section class="glass-panel search-start"><h2>Un nom, un usage, un souvenir.</h2><p>Vous pouvez rechercher le nom d’un outil, un sujet ou des mots présents dans une transcription.</p>${suggestions.length?`<div class="search-suggestions">${suggestions.map(row=>`<button class="btn" type="button" data-suggestion="${esc(row.name)}">${icon('search')}${esc(row.name)}</button>`).join('')}</div>`:'<a class="btn" href="#/processing">Importer mes favoris</a>'}<a class="text-link" href="#/sources">Ou parcourir toutes les sources →</a></section>`;
  document.querySelectorAll('[data-suggestion]').forEach(button=>button.onclick=()=>navigateSearch(button.dataset.suggestion));return;
 }
 const target=$('#search-content');target.innerHTML='<div class="loading" role="status">Recherche dans vos découvertes…</div>';
 const response=await api('/api/search?q='+encodeURIComponent(query));if(state.epoch!==epoch)return;
 const all=response.results;const selected=all.filter(r=>state.scope==='all'||(state.scope==='tools')===(r.kind==='outil'));
 target.innerHTML=`<div class="toolbar"><div class="tabs" role="group" aria-label="Type de résultat">${[['all','Tout',all.length],['tools','Outils',all.filter(r=>r.kind==='outil').length],['sources','Sources',all.filter(r=>r.kind==='source').length]].map(([id,label,n])=>`<button class="${state.scope===id?'active':''}" type="button" data-scope="${id}" aria-pressed="${state.scope===id}">${label}<small>${n}</small></button>`).join('')}</div><span class="text-muted"><small>Recherche par mots et variantes</small></span></div><div class="section-top"><h2>${selected.length} résultat${selected.length>1?'s':''}</h2><button type="button" class="btn btn-quiet" id="clear-search">Effacer ${icon('close')}</button></div>${selected.length?selected.map(result=>resultCard(result,query)).join(''):`<div class="empty-state">${icon('search')}<h2>Ce souvenir n’est pas encore retrouvé</h2><p>Essayez un usage plus court, le nom d’un créateur ou un mot que vous avez retenu.</p><a class="btn" href="#/library">Parcourir mes outils</a></div>`}`;
 target.querySelectorAll('[data-scope]').forEach(b=>b.addEventListener('click',()=>{state.scope=b.dataset.scope;renderRoute();}));$('#clear-search').onclick=()=>navigateSearch('');}
function reference(ref,position){
 const [sid,eid]=ref.split('#');
 const kind=eid.startsWith('pdf-page')?'pdf-page':eid.startsWith('image-text')?'image-text':eid.split('-')[0];
 const labels={'caption':'Titre / description','page':'Texte de page','note':'Note personnelle','text':'Note enregistrée','document':'Texte du fichier','pdf-page':'Page du PDF','image-text':'Texte de l’image','passage':'Passage du document','asr':'Paroles','subtitle':'Sous-titres embarqués','ocr':'Texte à l’écran'};
 return `<a class="evidence-link" href="${esc(proofRoute(sid,eid,kind))}">${icon(kind==='asr'?'play':'source')}${labels[kind]||'Preuve'}${position?' · '+position:''}</a>`;
}
async function copyContext(id){const buttons=document.querySelectorAll('[data-context]');buttons.forEach(b=>b.disabled=true);try{const data=await api('/api/context/'+encodeURIComponent(id));if(navigator.clipboard&&window.isSecureContext){await navigator.clipboard.writeText(data.markdown);toast('Contexte et sources copiés. Prêts pour votre assistant.');}else{showCopyFallback(data.markdown);}}catch(e){toast('Copie impossible : '+e.message);}finally{buttons.forEach(b=>b.disabled=false);}}
function showCopyFallback(text){const section=document.createElement('section');section.className='detail-panel';const h=document.createElement('h2');h.textContent='Contexte à copier';const p=document.createElement('p');p.textContent='Sélectionnez le texte et copiez-le dans votre assistant.';const textarea=document.createElement('textarea');textarea.className='context-fallback';textarea.value=text;textarea.readOnly=true;textarea.setAttribute('aria-label','Contexte et sources à copier');const button=document.createElement('button');button.className='btn';button.textContent='Fermer';button.onclick=()=>section.remove();section.append(h,p,textarea,button);$('#content').prepend(section);textarea.focus();textarea.select();}
function researchPanel(entity){
 const research=entity.web_research;
 if(!research)return '';
 const pages=new Map(research.pages.map(page=>[page.url,page]));
 const rows=research.results.map(result=>{
  const page=pages.get(result.url);
  const state=page?.status==='read'?'Page consultée':page?'Lecture indisponible':'Lien relevé';
  return `<div class="link-item"><a href="${safeUrl(result.url)}" target="_blank" rel="noopener noreferrer"><strong>Page de référence ${icon('external')}</strong></a><p>${esc(result.url)}</p>${badge(state,'neutral')}${page?.excerpt?`<details><summary>Extrait original</summary><p>${esc(page.excerpt)}</p></details>`:''}</div>`;
 }).join('');
 const message=research.error||(!research.results.length?'Aucun lien retenu.':research.identity==='ambiguous'?'Correspondance incertaine. Les liens restent à vérifier.':'Les pages lues sont des pistes à vérifier avant d’attribuer leurs propos à l’éditeur.');
 return `<section class="aside-panel"><h2>Pistes de recherche web</h2><p class="text-muted">${esc(message)}</p>${research.searched_at?`<p><small>${esc(research.provider)} · ${date(research.searched_at)}</small></p>`:''}${rows}<a class="btn" href="/api/research/${encodeURIComponent(entity.id)}">${icon('download')}Trace de recherche</a></section>`;
}
const editableSections=[['description','Description'],['usefulness','À quoi ça sert'],['operation','Comment ça fonctionne'],['limitations','Limites et points à confirmer']];
function editorForm(entity){
 const tools=[...state.entities.values()].filter(item=>item.id!==entity.id);
 const pages=(entity.web_research?.pages||[]).filter(page=>page.status==='read'&&page.excerpt);
 const sections=editableSections.map(([key,label])=>{
  const rows=entity.details?.[key]||[];
  return rows.length?`<fieldset><legend>${label}</legend>${rows.map((row,index)=>`<label>Entrée ${index+1}<textarea data-detail="${key}" maxlength="8000" rows="3" required>${esc(row.text)}</textarea></label><div class="evidence-links">${(row.evidence||[]).map(ref=>reference(ref)).join('')}</div>`).join('')}</fieldset>`:'';
 }).join('');
 return `<section class="editorial"><h3>Modifier la fiche</h3><form id="editorial-form">
  <label>Nom<input name="name" value="${esc(entity.name)}" maxlength="200" required></label>
  <label>Résumé<textarea name="description" rows="3" maxlength="8000" required>${esc(entity.description)}</textarea></label>
  <label>Repères de recherche, un par ligne<textarea name="aliases" rows="3">${esc(entity.aliases.join('\n'))}</textarea></label>
  ${sections}
  <label>Liens, un par ligne au format Libellé | URL<textarea name="links" rows="4">${esc(entity.links.map(link=>`${link.label||link.url} | ${link.url}`).join('\n'))}</textarea></label>
  ${tools.length?`<label>Regrouper une autre fiche du même outil<select name="merge"><option value="">Garder cette fiche seule</option>${tools.map(item=>`<option value="${esc(item.id)}">${esc(item.name)} (${item.source_ids.length} source(s))</option>`).join('')}</select></label>`:''}
  ${pages.length?`<fieldset><legend>Ajouter des notes documentaires</legend><label>Page de l’éditeur vérifiée par toi<select name="documentation-url"><option value="">Choisir une page consultée</option>${pages.map(page=>`<option value="${esc(page.url)}">${esc(page.title||page.url)}</option>`).join('')}</select></label><p class="text-muted">Confirme l’identité de l’éditeur et relis la page avant d’y attribuer un texte.</p>${editableSections.map(([key,label])=>`<label>${label}<textarea name="doc-${key}" maxlength="1600" rows="2"></textarea></label>`).join('')}</fieldset>`:''}
  <p class="text-muted">Les preuves et versions précédentes sont conservées. Regroupe uniquement les fiches qui parlent du même outil.</p>
  <label class="editorial-review"><input type="checkbox" name="reviewed" ${entity.curation==='user-reviewed'?'checked':''}> Fiche relue</label>
  <div class="detail-actions"><button type="submit" class="btn btn-primary">Enregistrer la fiche</button>${entity.editorial_history?.length?`<a class="btn" href="/api/editorial/${encodeURIComponent(entity.id)}">Dernière revue</a>`:''}</div>
  <p id="editorial-status" role="status"></p></form></section>`;
}
function bindEditor(entity,revision){
 const form=$('#editorial-form');
 form.onsubmit=async event=>{
  event.preventDefault();
  const button=$('button[type="submit"]',form), output=$('#editorial-status',form);
  button.disabled=true;output.textContent='Enregistrement…';
  try{
   const fields=new FormData(form);
   const lines=name=>fields.get(name).split('\n').map(line=>line.trim()).filter(Boolean);
   const links=lines('links').map(line=>{
    const separator=line.lastIndexOf('|');
    if(separator<1)throw new Error('Utilise une ligne par lien au format Libellé | URL.');
    return {label:line.slice(0,separator).trim(),url:line.slice(separator+1).trim()};
   });
   const details=Object.fromEntries(editableSections.map(([key])=>[key,[...form.querySelectorAll(`[data-detail="${key}"]`)].map(field=>field.value)]));
   const payload={revision,name:fields.get('name'),description:fields.get('description'),aliases:lines('aliases'),details,links,reviewed:fields.has('reviewed')};
   const doc=Object.fromEntries(editableSections.map(([key])=>[key,fields.get('doc-'+key)?.trim()]).filter(([,value])=>value));
   if(Object.keys(doc).length)payload.documentation={url:fields.get('documentation-url'),details:doc};
   const merge=fields.get('merge');
   if(merge){
    const current=await api('/api/tools/'+encodeURIComponent(merge));
    if(current.entity.id!==merge||current.entity.name!==state.entities.get(merge)?.name)throw new Error('La fiche à regrouper a changé. Actualise la page.');
    payload.merge_id=merge;payload.merge_revision=current.revision;
   }
   const control=await api('/api/control');
   await api(`/api/tools/${encodeURIComponent(entity.id)}/edit`,{method:'POST',headers:{'Content-Type':'application/json','X-KaraRecall-CSRF':control.csrf_token},body:JSON.stringify(payload)});
   await bootstrap();toast('Fiche enregistrée.');
  }catch(error){output.textContent=error.message;button.disabled=false;}
 };
}
function pagination(page){
 if(page.total<=page.limit)return '';
 const end=Math.min(page.offset+page.limit,page.total);
 return `<nav class="toolbar" aria-label="Pagination"><button class="btn" type="button" data-offset="${Math.max(0,page.offset-page.limit)}" ${page.offset?'':'disabled'}>Précédent</button><span class="text-muted">${page.offset+1}–${end} sur ${page.total}</span><button class="btn" type="button" data-offset="${page.offset+page.limit}" ${end<page.total?'':'disabled'}>Suivant</button></nav>`;
}
function bindPagination(key){
 $('#content').querySelectorAll('[data-offset]').forEach(button=>button.onclick=()=>{
  state[key]=Number(button.dataset.offset);
  renderRoute();
 });
}
function sourceActions(id){return `<div class="source-actions"><button class="btn" type="button" data-action="llm" data-source-id="${esc(id)}">Résumer / traduire</button><button class="btn" type="button" data-action="refresh" data-source-id="${esc(id)}">Relancer l’analyse complète</button></div>`;}
function bindActions(){
 document.querySelectorAll('[data-action]').forEach(button=>button.onclick=async()=>{
  const kind=button.dataset.action;
  const payload={kind,...(button.dataset.sourceId?{source_id:button.dataset.sourceId}:{}),...(button.dataset.toolId?{tool_id:button.dataset.toolId}:{}),...(button.dataset.stage?{stage:button.dataset.stage}:{})};
  if(kind==='clear'){
   if(window.prompt('Vider les sources et fiches locales et suspendre la synchronisation ? Les favoris Karakeep, les anciennes versions et les bulletins restent conservés. Tapez VIDER pour confirmer.')!=='VIDER')return;
   payload.confirmation='VIDER';
  }
  button.disabled=true;
  try{const session=await api('/api/control');await api('/api/actions',{method:'POST',headers:{'Content-Type':'application/json','X-KaraRecall-CSRF':session.csrf_token},body:JSON.stringify(payload)});toast('Commande enregistrée. Suivez sa progression dans Activité.');await bootstrap();}
  catch(error){toast(error.message);button.disabled=false;}
 });

}
function sourceStatusPanel(source){
 const stages=source.stages||{}, usage=state.catalog.worker?.usage;
 const labels={complete:'Terminé',failed:'En échec',paused:'En pause · quota ou budget',disabled:'Désactivé',waiting:'En attente',pending:'En attente',not_applicable:'Non applicable',subtitles_reused:'Sous-titres réutilisés',source_text:'Texte fourni par Karakeep',original_only:'Original conservé',no_text:'Aucun texte extrait',partial:'Extraction partielle',metadata_only:'Métadonnées seules',waiting_content:'En attente du contenu Karakeep'};
 const video=Boolean(source.processing.media_downloaded||source.assets?.some(row=>row.type==='video'));
 const steps=[...(source.bookmark_type==='link'?[['page','Texte de la page',Boolean(source.page_text)]]:[]),...(video?[['asr','Paroles',source.processing.audio_transcribed||source.processing.subtitles_available],['vision','Texte à l’écran',source.processing.ocr_sampled]]:source.document_asset_id?[['document','Texte du fichier',source.processing.attachment?.status==='complete']]:[]),['llm','Résumé IA',Boolean(source.reading)]];
 const status=steps.map(([key,label,done])=>`<span><strong>${label}</strong> : ${labels[stages[key]]||(done?'Terminé':'Non démarré')}${done&&['paused','failed','disabled'].includes(stages[key])?' · résultat antérieur conservé':''}</span>`).join('');
 const reasons={daily_calls:'Quota journalier d’appels atteint ; renouvellement à minuit UTC.',monthly_calls:'Quota mensuel d’appels atteint.',monthly_budget:'Budget mensuel insuffisant pour réserver un nouvel appel.'};
 const quota=(usage?.blocked_by||[]).map(key=>reasons[key]).filter(Boolean).join(' ');
 const paused=Object.values(stages).includes('paused');
 return `<details class="detail-panel source-status" ${Object.values(stages).some(value=>['failed','paused'].includes(value))?'open':''}><summary>État de cette source <span class="text-muted">${video?'Paroles · écran · résumé':'Texte · résumé'}</span></summary><div class="source-status-content"><div class="source-stage-list">${status}</div>${paused?`<p>${esc(quota||'Le dernier passage a été suspendu par un quota ou le budget IA. Les étapes restantes reprendront selon les limites disponibles.')} Les résultats déjà disponibles restent consultables.</p>`:''}${usage?.daily_call_limit?`<p class="text-muted">Appels IA : ${usage.daily_calls}/${usage.daily_call_limit} aujourd’hui (UTC) · ${usage.calls}/${usage.monthly_call_limit} ce mois. Budget : ${Number(usage.accounted_usd).toFixed(3)} / ${Number(usage.limit_usd).toFixed(2)} USD.</p>`:''}${source.processing_error?`<details><summary>Détail du dernier traitement</summary><p>${esc(source.processing_error)}</p></details>`:''}${!source.reading?'<p class="text-muted">Résumé IA en attente. Le titre est un extrait abrégé de la publication lorsqu’il est disponible en français.</p>':''}${['paused','failed'].includes(stages.vision)?`<button class="btn" type="button" data-action="refresh" data-stage="vision" data-source-id="${esc(source.id)}">Réessayer l’analyse de l’écran</button>`:''}</div></details>`;
}
function evidenceText(source,row){
 if(state.sourceView?.original)return row.text;
 if(row.presentation)return row.presentation.text;
 const translation=source.translations?.[row.id];
 if(translation)return translation.text;
 if(source.reading?.source_language==='fr')return row.display_text??row.text;
 return '';
}
function evidenceEmptyText(row){if(row.presentation?.state==='translation_pending')return 'Texte conservé ; traduction française en attente. Les preuves originales restent accessibles.';if(row.text?.trim())return 'Aucun extrait utile dans la présentation nettoyée. L’original reste accessible.';return 'Aucun texte reconnu.';}
function historyPanel(){
 const task=state.catalog.history_import||{state:'none'};
 const busy=['queued','running'].includes(task.state);
 const statusText={none:'Importez tous les favoris : sites, articles, notes, fichiers et vidéos. La lecture du catalogue ne déclenche aucun appel IA.',queued:'En attente du service de collecte. Il doit être démarré et connecté à Karakeep.',running:`Lecture de tout l’historique en cours${task.collected?' · '+task.collected+' favoris lus':''}…`,completed:`${task.synced||0} favoris pris en compte. ${state.catalog.actions?.library_paused?'L’automatisation reste suspendue.':'Les analyses suivront par lots, selon les services activés et le budget.'}`,error:task.message};
 return `<section class="detail-panel history-import" aria-live="polite"><div><h2>Tout votre historique</h2><p>${esc(statusText[task.state]||task.message||'')}</p>${task.failed?'<p>Certains médias remplacés demandent une intervention ; leur version précédente a été conservée.</p>':''}<small>Les sources déjà présentes sont mises à jour sans doublon. L’import inclut les favoris archivés et ignore les filtres de collecte.</small></div><button class="btn btn-primary" type="button" id="import-history" ${busy?'disabled':''}>${busy?'Import en attente ou en cours':'Importer tout l’historique'}</button></section>`;
}
function bindHistory(){
 const button=$('#import-history');
 button.onclick=async()=>{button.disabled=true;try{const session=await api('/api/control');await api('/api/import-history',{method:'POST',headers:{'Content-Type':'application/json','X-KaraRecall-CSRF':session.csrf_token},body:'{}'});await bootstrap();toast('Import demandé. Aucun appel IA pour lire le catalogue.');}catch(error){toast(error.message);button.disabled=false;}};
 clearTimeout(state.historyTimer);

}
function seek(second,play=true){const video=$('#source-video');if(!video)return;if(video.readyState){video.currentTime=second;}else{video.addEventListener('loadedmetadata',()=>{video.currentTime=second;},{once:true});}if(play)video.play().catch(()=>{});}
function renderTranscript(panel,view,transcript){
 if(!transcript.length){panel.innerHTML='<div class="source-empty"><h3>Aucune parole disponible</h3><p>Consultez l’état des traitements et le texte conservé dans l’onglet Texte source.</p></div>';return;}
 const pending=view.original?0:transcript.filter(row=>row.presentation?.state==='translation_pending'||(!row.presentation&&!row.text.trim())).length;
 panel.innerHTML=(pending?`<div class="notice">${icon('info')}<p>${pending} passage(s) conservé(s) attendent une traduction française. Les preuves originales restent accessibles avec la case ci-dessus.</p></div>`:'')+`<div class="transcript-find"><label for="transcript-query">Rechercher dans les paroles</label><input type="search" id="transcript-query" value="${esc(view.query)}" maxlength="150" placeholder="Un mot ou un passage…"><small id="transcript-count" role="status"></small></div><div class="transcript"></div>`;
 const input=$('#transcript-query',panel), list=$('.transcript',panel);
 const render=()=>{
  view.query=input.value;
  const words=wordsFor(view.query);
  const rows=transcript.filter(row=>row.text.trim()&&(row.id===view.selected||words.every(word=>fold(row.text).includes(word))));
  $('#transcript-count',panel).textContent=words.length?`${rows.filter(row=>words.every(word=>fold(row.text).includes(word))).length} passage(s) trouvé(s)`:'';
  list.innerHTML=rows.length?rows.map(row=>`<button class="transcript-entry ${view.selected===row.id?'selected':''}" type="button" data-seek="${row.start}" data-eid="${esc(row.id)}"><span class="time">${time(row.start)}</span><p>${highlighted(row.text,words)}${row.kind==='subtitle'?'<small> Piste embarquée</small>':''}</p></button>`).join(''):'<div class="source-empty">Aucun passage trouvé.</div>';
  list.querySelectorAll('[data-seek]').forEach(button=>button.onclick=()=>{
   view.selected=button.dataset.eid;
   list.querySelectorAll('[data-seek]').forEach(item=>item.classList.toggle('selected',item===button));
   seek(Number(button.dataset.seek));
  });
 };
 input.oninput=()=>{view.selected='';render();};
 render();
 list.querySelector('.selected')?.scrollIntoView({block:'nearest'});
}
function attachmentLink(sid,attachment,label='Télécharger l’original'){
 const name=attachment.file.split('/').pop().replace(/\.bin$/,'');
 return `<a class="btn" href="/download/document/${encodeURIComponent(sid)}/${encodeURIComponent(name)}">${icon('download')}${esc(label)}</a>`;
}
function renderEvidencePanel(){
 const view=state.sourceView, source=view.source;
 const transcript=source.evidence.filter(e=>['asr','subtitle'].includes(e.kind)).map(e=>({...e,text:evidenceText(source,e)})).sort((a,b)=>a.start-b.start), frames=source.evidence.filter(e=>e.kind==='ocr');
 const tabs=[['transcript',transcript.some(row=>row.kind==='subtitle')?'Paroles et sous-titres':'Paroles',transcript.length],['ocr','À l’écran',frames.length],['raw','Texte source',null]].filter(([id])=>id==='raw'||source.processing.media_downloaded||transcript.length||frames.length);
 const target=$('#evidence-panel');
 target.innerHTML=`<div class="tabs" role="group" aria-label="Type de preuve">${tabs.map(([id,label,count])=>`<button type="button" data-evidence-tab="${id}" class="${view.tab===id?'active':''}" aria-pressed="${view.tab===id}">${label}${count!==null?`<small>${count}</small>`:''}</button>`).join('')}</div><label class="original-switch"><input type="checkbox" id="show-original" ${view.original?'checked':''}> Voir le texte original</label><div id="evidence-content"></div>`;
 $('#show-original',target).onchange=event=>{view.original=event.target.checked;renderEvidencePanel();};
 target.querySelectorAll('[data-evidence-tab]').forEach(button=>button.onclick=()=>{view.tab=button.dataset.evidenceTab;renderEvidencePanel();});
 const panel=$('#evidence-content');
 if(view.tab==='transcript')return renderTranscript(panel,view,transcript);
 if(view.tab==='ocr'){
  if(!frames.length){const paused=source.stages?.vision==='paused';const failed=source.stages?.vision==='failed';panel.innerHTML=`<div class="source-empty"><h3>${paused?'Analyse de l’écran en pause':failed?'Analyse de l’écran en échec':'Écran non analysé'}</h3><p>${paused?'Le dernier passage a été suspendu par un quota ou le budget IA avant de terminer la lecture des images. Les paroles déjà transcrites restent accessibles.':failed?'Le dernier essai a échoué. Les traitements et les commandes de reprise sont disponibles en bas de cette page.':'Aucune image OCR n’est disponible pour cette source.'}</p></div>`;return;}
  const frame=frames.find(f=>f.id===view.selected)||frames[0];
  panel.innerHTML=`<div class="frame-select" aria-label="Choisir une image">${frames.map(f=>`<button type="button" data-frame="${esc(f.id)}" class="${frame.id===f.id?'selected':''}">${time(f.start)}</button>`).join('')}</div><div class="frame-view"><img src="${asset(frame.image)}" alt="Image extraite de la vidéo à ${time(frame.start)}"><div class="frame-text">${esc(evidenceText(source,frame))||esc(evidenceEmptyText(frame))}</div></div><div class="notice">${icon('info')}<p>Texte extrait automatiquement sur des images échantillonnées. Des mots peuvent être mal reconnus ou manqués.</p></div>`;
  panel.querySelectorAll('[data-frame]').forEach(button=>button.onclick=()=>{view.selected=button.dataset.frame;seek(frames.find(f=>f.id===view.selected).start,false);renderEvidencePanel();});
  panel.querySelector('.frame-select .selected')?.scrollIntoView({block:'nearest',inline:'nearest'});
  return;
 }
 const titles={passage:'Passage cité',caption:'Titre et description conservés',page:'Texte conservé par Karakeep',text:'Note enregistrée',document:'Texte du fichier fourni par Karakeep',note:'Note personnelle','image-text':'Texte de l’image'};
 panel.innerHTML=source.evidence.filter(e=>e.kind in titles||e.kind==='pdf-page').map(e=>`<section class="detail-panel ${e.id===view.selected?'selected-proof':''}"><h3>${e.kind==='pdf-page'?`PDF · page ${e.page}${e.image?' · OCR':''}`:e.kind==='passage'?`Passage ${e.section}${e.page?` · page ${e.page}`:''}`:titles[e.kind]}</h3>${e.image?`<div class="frame-view"><img src="${asset(e.image)}" alt="Aperçu analysé"></div>`:''}<div class="frame-text">${esc(evidenceText(source,e))||esc(evidenceEmptyText(e))}</div>${e.attachment?attachmentLink(source.id,e.attachment):''}</section>`).join('');
 panel.querySelector('.selected-proof')?.scrollIntoView({block:'nearest'});
}
function readingCoverage(reading){
 const metrics=reading.coverage?.long_document;
 if(metrics)return `<p class="text-muted">${metrics.included.toLocaleString('fr')} caractères sur ${metrics.available.toLocaleString('fr')} représentés par ${metrics.sections} résumés de passages.</p>`;
 return Object.values(reading.coverage||{}).some(c=>c.text_truncated||c.included<c.available)
  ?'<p class="text-muted">Synthèse fondée sur une sélection d’extraits. Certains passages ont été omis.</p>':'';
}
function documentPanel(source){
 const attachment=source.processing.attachment;
 const stage=source.stages?.document;
 let message=source.content_status==='metadata_only'
  ?'Les métadonnées de ce favori sont conservées.'
  :'Le texte fourni par Karakeep est consultable dans les preuves.';
 if(source.stages?.page==='failed')message=source.processing_error||'Le texte de la page n’a pas pu être récupéré depuis Karakeep.';
 else if(source.stages?.llm==='waiting_content')message='Karakeep ne fournit pas encore le texte de cette page. Aucun résumé du document complet n’a été généré. La collecte reprendra lorsque le contenu sera disponible.';
 else if(source.content_status==='metadata_only'&&source.bookmark_type==='link')message='Karakeep ne fournit que les métadonnées de ce lien. Un éventuel résumé se limite à ces informations.';
 else if(stage==='failed')message=source.processing_error||'L’extraction a échoué.';
 else if(stage==='paused')message='Extraction en pause, budget ou quota atteint.';
 else if(attachment?.status==='no_text')message=attachment.kind==='pdf'
  ?`Aucun texte extrait sur ${attachment.pages_scanned} page(s). Un PDF numérisé nécessite un OCR.`
  :'Aucun texte visible reconnu.';
 else if(attachment?.truncated)message=`Couverture partielle du PDF (${attachment.pages_scanned} pages parcourues).`;
 else if(attachment?.status==='original_only')message='Image conservée. La reconnaissance de texte est désactivée.';
 else if(attachment?.status==='complete')message='Le texte extrait est consultable dans les preuves.';
 return `<section class="detail-panel"><h2>${attachment?'Pièce jointe conservée':'Contenu disponible'}</h2><p>${esc(message)}</p>${attachment?attachmentLink(source.id,attachment):''}</section>`;
}
async function sourcePage(id,params,epoch){const response=await api('/api/sources/'+encodeURIComponent(id));if(state.epoch!==epoch)return;const {source,summary:s,entities,media_url}=response;const selected=params.get('e')||'';const evidence=source.evidence.find(e=>e.id===selected);const historical=Boolean(evidence?.archived);source.evidence=historical?source.evidence.filter(e=>e.id===selected):source.evidence.filter(e=>!e.archived);state.sourceView={source,selected,query:(params.get('q')||'').slice(0,150),tab:params.get('tab')||(media_url?'transcript':'raw')};if(!['transcript','ocr','raw'].includes(state.sourceView.tab))state.sourceView.tab='raw';$('#content').innerHTML=`<div class="detail-top"><a class="btn btn-quiet" href="#/sources">${icon('back')}Toutes les sources</a><div class="detail-actions">${exportMenu(`<a href="/download/source/${encodeURIComponent(id)}.md">Source Markdown</a>`)}${source.url?`<a class="btn btn-primary" href="${safeUrl(source.url)}" target="_blank" rel="noopener noreferrer">Source originale ${icon('external')}</a>`:''}</div></div>${historical?'<div class="notice">'+icon('info')+'<p>Preuve conservée d’une version antérieure. <a href="'+sourceLink(s)+'">Voir l’analyse actuelle</a></p></div>':''}<div class="source-detail-head"><div class="eyebrow">SOURCE · ${esc(s.author)}</div><h1>${esc(s.title)}</h1><div class="source-meta"><span>Enregistrée le ${date(source.created_at)}</span>${badge(processingLabel(s),complete(s)?'':'neutral')}${s.processing.duration_seconds?`<span>${time(s.processing.duration_seconds)} de vidéo</span>`:''}</div></div>${sourceAttention(source)}<div class="video-layout"><div>${media_url?`<div class="video-box"><video id="source-video" controls playsinline preload="metadata" ${s.thumbnail?`poster="${esc(s.thumbnail)}"`:''}><source src="${esc(media_url)}" type="video/mp4">Votre navigateur ne peut pas lire cette vidéo.</video><div class="video-caption"><span>${icon('play')} Pièce jointe conservée localement</span><span>${time(s.processing.duration_seconds||0)}</span></div></div>`:`<figure class="source-preview"><img src="${esc(s.thumbnail)}" alt="Aperçu du favori" loading="lazy"></figure>`+documentPanel(source)}${source.reading?`<section class="detail-panel"><h2>En quelques mots</h2>${claim({...source.reading,text:s.summary})}${readingCoverage(source.reading)}</section>`:''}${entities.length?`<section class="detail-panel sources-strip"><h2>Outils repérés dans cette source</h2><div class="related-links">${entities.map(e=>`<a class="btn" href="${slugRoute('tools',e.id)}">${esc(toolName(e))} ${icon('arrow')}</a>`).join('')}</div></section>`:''}</div><section class="evidence-panel" id="evidence-panel" aria-label="Preuves de la source"></section></div>${disclosure('Gérer cette source','Traitements, reprise et état détaillé',sourceStatusPanel(source)+'<div class="record-maintenance"><h3>Mettre à jour les contenus</h3><p>Ces commandes utilisent les étapes configurées et le budget IA.</p>'+sourceActions(id)+'</div>','id="source-management"','record-management')}<p class="reading-footnote">Les synthèses restituent les propos des sources et restent à relire.</p>`;renderEvidencePanel();bindActions();bindReadingView();if(state.catalog.digest_track_views)digestMutation('/api/digests/view',{source_id:id}).catch(()=>{});if(evidence?.start!==undefined)seek(evidence.start,false);const video=$('#source-video');if(video){video.addEventListener('error',()=>toast('Lecture vidéo indisponible dans ce navigateur. La transcription et les images restent accessibles.'));video.addEventListener('timeupdate',()=>{if(state.sourceView?.tab!=='transcript')return;const current=source.evidence.find(e=>['asr','subtitle'].includes(e.kind)&&e.start<=video.currentTime&&e.end>video.currentTime);if(current)document.querySelectorAll('[data-eid]').forEach(b=>b.classList.toggle('selected',b.dataset.eid===current.id));});}}
async function renderRoute(){if(!state.catalog)return;const epoch=++state.epoch;clearTimeout(state.workspaceTimer);clearTimeout(state.actionTimer);const {parts,params}=route();const current=parts[0]||'dashboard';nav(current==='tools'?'library':current);window.scrollTo({top:0});try{if(current==='dashboard')await dashboardPage(epoch);else if(current==='administration')await administrationPage(epoch,params);else if(current==='search')await searchPage(params.get('q')||'',epoch);else if(current==='library')toolsPage();else if(current==='sources'&&parts[1]){ $('#content').innerHTML='<div class="loading">Ouverture de la source…</div>';await sourcePage(decodeURIComponent(parts[1]),params,epoch);}else if(current==='sources')await browseSourcesPage(epoch,params);else if(current==='processing')await activityPage(epoch,params);else if(current==='digests'&&parts[1])await digestPage(decodeURIComponent(parts[1]),epoch);else if(current==='digests')await digestsPage(epoch);else if(current==='tools'&&parts[1]){ $('#content').innerHTML='<div class="loading">Ouverture de la fiche…</div>';await toolPage(decodeURIComponent(parts[1]),epoch);}else throw new Error('Cette page n’existe pas.');}catch(error){if(state.epoch!==epoch)return;$('#content').innerHTML=`<div class="error-box"><h2>Cette page ne peut pas être affichée</h2><p>${esc(error.message)}</p><a class="btn" href="#/search">Revenir à la recherche</a></div>`;}}
async function bootstrap(){try{const catalog=await api('/api/catalog?compact=1');state.catalog=catalog;$('#application-version').textContent='KaraRecall '+(catalog.version||'');state.entities=new Map(catalog.entities.map(e=>[e.id,e]));state.sources=new Map(catalog.sources.map(s=>[s.id,s]));await renderRoute();}catch(e){$('#content').innerHTML=`<div class="error-box"><h2>La bibliothèque est momentanément indisponible</h2><p>${esc(e.message)}</p><button class="btn" id="retry-load">Réessayer</button></div>`;$('#retry-load').onclick=bootstrap;}}
window.addEventListener('hashchange',()=>{if(document.body.classList.contains('nav-open'))toggleNavigation(false);renderRoute();});
window.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();if($('#search-input'))$('#search-input').focus();else{navigateSearch('');setTimeout(()=>$('#search-input')?.focus(),50);}}});
initializeWorkspace();
bootstrap();

$('.skip-link').addEventListener('click',event=>{event.preventDefault();$('#content').focus();$('#content').scrollIntoView({block:'start'});});
