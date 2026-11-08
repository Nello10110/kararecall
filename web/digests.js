'use strict';

async function digestMutation(path,payload){
 const control=await api('/api/control');
 return api(path,{method:'POST',headers:{'Content-Type':'application/json','X-KaraRecall-CSRF':control.csrf_token},body:JSON.stringify(payload)});
}
function digestState(edition){
 const writing=edition.writing?.state;
 if(['pending','retry','paused','waiting_configuration'].includes(writing)&&!edition.approved)return {pending:'Rédaction en cours',retry:'Rédaction à reprendre',paused:'Budget en attente',waiting_configuration:'Modèle à raccorder'}[writing];
 const values=Object.values(edition.delivery||{});
 if(values.some(row=>['uncertain','sending'].includes(row.state)))return 'Envoi à vérifier';
 if(values.length&&values.every(row=>row.state==='sent'))return 'Diffusé';
 if(edition.send_requested)return 'Envoi demandé';
 return edition.approved?'Prêt à diffuser':edition.empty?'Aucune nouveauté':'Brouillon';
}
async function digestsPage(epoch){
 const data=await api('/api/digests');
 if(epoch!==state.epoch)return;
 state.digestConfig=data.config;
 const cfg=data.config;
 $('#content').innerHTML=pageHeading('Vos rendez-vous de lecture','Les découvertes prennent la parole.','Des articles sourcés pour retrouver les idées de la semaine et les thèmes du mois.')+digestScheduleCard(data)
  +`<details class="glass-panel digest-advanced"><summary>Préparer un bulletin ponctuel</summary><form id="digest-generate" class="digest-generate"><label>Période<select name="kind"><option value="weekly">Semaine précédente</option><option value="monthly">Mois précédent</option></select></label><label>Date de référence<input type="date" name="anchor" required value="${new Intl.DateTimeFormat('sv-SE',{timeZone:cfg.timezone}).format(new Date())}"></label><button class="btn btn-primary" type="submit">${icon('spark')}Préparer le bulletin</button></form><p class="text-muted">Le bulletin couvre la semaine ou le mois complet précédant cette date. Les textes reprennent les fiches et les preuves disponibles.</p><p id="digest-generation-status" role="status"></p></details>`
  +(data.worker.state==='error'?`<div class="notice warning"><p>${esc(data.worker.message)}</p></div>`:'')
  +`<div class="section-top"><h2>Vos éditions</h2><a class="btn" href="/api/digests/feed.xml" target="_blank" rel="noopener">${icon('source')}RSS privé</a></div><div class="cards">${data.editions.map(row=>`<a class="tool-card" href="#/digests/${esc(row.id)}"><div class="card-top">${icon('book')}${badge(digestState(row),'neutral')}</div><h3>${esc(row.title)}</h3><p>À partir du ${date(row.start+'T12:00:00Z')}</p><div class="card-footer">${row.items} découverte${row.items===1?'':'s'} · ${row.kind==='weekly'?'Semaine':row.kind==='monthly'?'Mois':'Historique'}</div></a>`).join('')}</div>`
  +(data.editions.length?'':'<div class="empty-state"><h2>Votre premier rendez-vous de veille</h2><p>Les éditions apparaîtront selon le rythme configuré, lorsque les contenus et le modèle seront disponibles. Consultez l’automatisation pour vérifier la configuration.</p></div>');
 $('#digest-generate').onsubmit=async event=>{
  event.preventDefault();
  const form=event.currentTarget,button=$('button',form),output=$('#digest-generation-status');
  button.disabled=true;output.textContent='Préparation du bulletin…';
  try{
   const fields=new FormData(form);
   const edition=await digestMutation('/api/digests/generate',{kind:fields.get('kind'),anchor:fields.get('anchor')});
   setRoute('/digests/'+edition.id);
  }catch(error){output.textContent=error.message;button.disabled=false;}
 };
}
function digestAttribution(item,section){
 if(item.editorial_status==='user-edited')return 'Texte édité · sources associées';
 return [...new Set((item.claims[section]||[]).map(row=>labels[row.status]||row.status))].join(' · ');
}
function digestBody(item){
 if(item.paragraphs?.length)return '<small class="text-muted">D’après les contenus enregistrés</small>'+item.paragraphs.map(p=>'<p>'+esc(p.text)+'</p>').join('');
 return '<p>'+esc(item.summary)+'</p>'+(item.usefulness?'<p><strong>À quoi ça sert</strong><br>'+esc(item.usefulness)+'</p>':'')+(item.operation?'<p><strong>Comment ça fonctionne</strong><br>'+esc(item.operation)+'</p>':'');
}
function digestImage(item){
 if(!item.image||!item.include_image)return '';
 return `<figure class="digest-image"><img src="/api/digests/assets/${esc(item.image.file)}" alt="${esc(item.image.alt)}" loading="lazy"><figcaption>${esc(item.image.caption)}</figcaption></figure>`;
}
function digestProofs(item){
 return `<details class="digest-proofs"><summary>Sources et preuves</summary>${item.evidence.map(proof=>`<p>${reference(proof.ref)}<small>${esc(proof.ref)}</small><br>${esc(proof.text.slice(0,600))}</p>`).join('')}${item.documentation.map(doc=>`<p><a href="${safeUrl(doc.url)}" target="_blank" rel="noopener noreferrer">Documentation consultée</a></p>`).join('')}${item.sources.filter(source=>source.url).map(source=>`<p><a href="${safeUrl(source.url)}" target="_blank" rel="noopener noreferrer">Source originale ${icon('external')}</a></p>`).join('')}</details>`;
}
async function digestPage(id,epoch){
 const edition=await api('/api/digests/'+encodeURIComponent(id));
 if(epoch!==state.epoch)return;
 const frozen=Object.values(edition.delivery).some(row=>['sent','sending','uncertain'].includes(row.state));
 const visible=edition.items.filter(row=>row.included);
 const automatic=edition.approval_mode==='automatic';
 const editor=(!frozen&&edition.items.length?`<section class="digest-editor-section"><h3>Modifier le bulletin</h3><form id="digest-editor"><label>Titre<input name="title" maxlength="180" required value="${esc(edition.title)}"></label><label>Introduction<textarea name="intro" maxlength="2000" required>${esc(edition.intro)}</textarea></label>${edition.items.map(item=>`<fieldset data-digest-item="${esc(item.id)}"><legend>${esc(item.title)}</legend><label class="editorial-review"><input type="checkbox" name="included" ${item.included?'checked':''}> Inclure cette découverte</label><label>Rubrique<input name="theme" maxlength="100" value="${esc(item.theme)}"></label><label>Titre<input name="title" maxlength="180" value="${esc(item.title)}"></label><label>Présentation<textarea name="summary" maxlength="1500">${esc(item.summary)}</textarea></label><label>Utilité<textarea name="usefulness" maxlength="1000">${esc(item.usefulness)}</textarea></label><label>Fonctionnement<textarea name="operation" maxlength="1000">${esc(item.operation)}</textarea></label><label class="editorial-review"><input type="checkbox" name="include_image" ${item.include_image?'checked':''} ${item.image?'':'disabled'}> Inclure l’image disponible</label></fieldset>`).join('')}<button class="btn btn-primary" type="submit">Enregistrer le brouillon</button><p id="digest-editor-status" role="status"></p></form></section>`:'');
 const controls=(automatic?'<p>La rédaction et la diffusion suivent les paramètres du worker.</p>':`<div class="detail-actions digest-actions">${!edition.approved&&!frozen?'<button class="btn" id="digest-refresh">Repréparer depuis les sources</button>':''}<button class="btn" id="digest-approve" ${frozen||!visible.length?'disabled':''}>${icon('check')}Valider pour diffusion</button><button class="btn btn-primary" id="digest-send" ${edition.approved&&!frozen?'':'disabled'}>${icon('arrow')}Demander l’envoi</button></div>`)
  +'<p id="digest-action-status" role="status"></p>'
  +(Object.values(edition.delivery).length?`<section class="digest-delivery"><h3>Suivi des diffusions</h3>${Object.values(edition.delivery).map(row=>`<p>${esc(row.channel==='email'?'Mail':'Webhook')} · ${esc({sending:'En cours',sent:'Accepté par le service',uncertain:'À vérifier'}[row.state]||row.state)}<br><small>${esc(row.message||'')}</small></p>`).join('')}</section>`:'')
  +editor;
 $('#content').innerHTML=`<div class="detail-top"><a class="btn btn-quiet" href="#/digests">${icon('back')}Tous les bulletins</a><div class="detail-actions"><a class="btn btn-primary" href="/api/digests/${esc(id)}/article.html" target="_blank" rel="noopener">Lire l’article / PDF ${icon('external')}</a>${exportMenu(`<a href="/api/digests/${esc(id)}/article.md">Bulletin Markdown</a>`)}</div></div>`
  +`<header class="digest-reading-head"><div class="eyebrow">VEILLE ${edition.kind==='weekly'?'HEBDOMADAIRE':edition.kind==='monthly'?'MENSUELLE':'DÉCOUVERTES'}</div><h1>${esc(edition.title)}</h1><p class="detail-summary">${esc(edition.intro)}</p><div class="digest-reading-state">${badge(digestState(edition),'neutral')} · ${visible.length} découverte${visible.length>1?'s':''} · À partir du ${date(edition.start+'T12:00:00Z')}</div></header>`
  +(edition.total_candidates>edition.items.length?`<p class="reading-footnote">${edition.items.length} découvertes retenues sur ${edition.total_candidates}, selon la limite configurée.</p>`:'')
  +(!edition.items.length?'<div class="empty-state"><h2>Aucune découverte sur cette période</h2><p>Vérifiez la date et le périmètre configuré pour les bulletins.</p></div>':'')
  +`<section class="digest-article" aria-label="Aperçu du bulletin">${visible.map(item=>`<article class="detail-panel"><div class="eyebrow">${esc(item.theme)} · ${esc(item.novelty)}</div><h2>${esc(item.title)}</h2>${digestImage(item)}${digestBody(item)}<a class="btn btn-quiet" href="${esc(item.route)}">${recordRouteLabel(item.route)} ${icon('arrow')}</a>${digestProofs(item)}</article>`).join('')}</section>`
  +disclosure('Diffusion et édition','Relire, modifier et suivre les envois',controls,'id="digest-management"','record-management digest-management')
  +'<p class="reading-footnote">L’article HTML conserve les images et peut être enregistré en PDF depuis le menu d’impression du navigateur. Les textes restent attribués aux sources.</p>';
 bindReadingView();
 const action=async name=>{
  const output=$('#digest-action-status');
  try{
   await digestMutation('/api/digests/'+id+'/'+name,{revision:edition.revision});
   await renderRoute();
   toast(name==='approve'?'Bulletin validé.':'Envoi demandé au worker.');
  }catch(error){output.textContent=error.message;}
 };
 const refresh=$('#digest-refresh');
 if(refresh)refresh.onclick=async()=>{
  refresh.disabled=true;
  try{
   await digestMutation('/api/digests/generate',{kind:edition.kind,anchor:edition.end,refresh:true});
   await renderRoute();toast('Bulletin repréparé. La version précédente est conservée.');
  }catch(error){$('#digest-action-status').textContent=error.message;refresh.disabled=false;}
 };
 if($('#digest-approve'))$('#digest-approve').onclick=()=>action('approve');
 if($('#digest-send'))$('#digest-send').onclick=()=>action('send');
 const form=$('#digest-editor');
 if(form)form.onsubmit=async event=>{
  event.preventDefault();
  const output=$('#digest-editor-status'),button=$('button[type="submit"]',form);
  button.disabled=true;
  const items=[...form.querySelectorAll('[data-digest-item]')].map(field=>{
   const value={id:field.dataset.digestItem};
   for(const name of ['title','theme','summary','usefulness','operation'])value[name]=field.querySelector(`[name="${name}"]`).value;
   for(const name of ['included','include_image'])value[name]=field.querySelector(`[name="${name}"]`).checked;
   return value;
  });
  try{
   await digestMutation('/api/digests/'+id+'/edit',{revision:edition.revision,title:form.querySelector('input[name=title]').value,intro:form.querySelector('textarea[name=intro]').value,items});
   await renderRoute();toast('Brouillon enregistré.');
  }catch(error){output.textContent=error.message;button.disabled=false;}
 };
}
