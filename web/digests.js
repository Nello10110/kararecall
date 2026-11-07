'use strict';

async function digestMutation(path,payload){
 const control=await api('/api/control');
 return api(path,{method:'POST',headers:{'Content-Type':'application/json','X-KaraRecall-CSRF':control.csrf_token},body:JSON.stringify(payload)});
}
function digestState(edition){
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
 $('#content').innerHTML=intro('VOTRE VEILLE','Les découvertes prennent la parole.','Un rendez-vous pour retrouver les idées de la semaine et les thèmes du mois.')
  +`<section class="detail-panel"><form id="digest-generate" class="digest-generate"><label>Période<select name="kind"><option value="weekly">Semaine précédente</option><option value="monthly">Mois précédent</option></select></label><label>Date de référence<input type="date" name="anchor" required value="${new Intl.DateTimeFormat('sv-SE',{timeZone:cfg.timezone}).format(new Date())}"></label><button class="btn btn-primary" type="submit">${icon('spark')}Préparer le bulletin</button></form><p class="text-muted">Le bulletin couvre la semaine ou le mois complet précédant cette date. Les textes reprennent les fiches et les preuves disponibles.</p><p id="digest-generation-status" role="status"></p></section>`
  +`<div class="notice">${icon('clock')}<p>${cfg.enabled?`Préparation programmée à ${esc(cfg.time.slice(0,5))} (${esc(cfg.timezone)}). ${cfg.weekly?'Chaque semaine. ':''}${cfg.monthly?'Chaque mois. ':''}`:'La préparation programmée s’active avec DIGEST_ENABLED dans le .env du NAS.'} Périmètre choisi, ${esc({added:'favoris ajoutés',analyzed:'sources traitées',viewed:'sources consultées dans l’interface'}[cfg.scope])}. ${data.worker.delivery_enabled?'Diffusion configurée après validation.':'Le mail et le webhook se configurent dans le .env du worker.'}</p></div>`
  +(data.worker.state==='error'?`<div class="notice warning"><p>${esc(data.worker.message)}</p></div>`:'')
  +`<div class="section-top"><h2>Vos éditions</h2><a class="btn" href="/api/digests/feed.xml" target="_blank" rel="noopener">${icon('source')}RSS privé</a></div><div class="cards">${data.editions.map(row=>`<a class="tool-card" href="#/digests/${esc(row.id)}"><div class="card-top">${icon('book')}${badge(digestState(row),'neutral')}</div><h3>${esc(row.title)}</h3><p>À partir du ${date(row.start+'T12:00:00Z')}</p><div class="card-footer">${row.items} découverte${row.items===1?'':'s'} · ${row.kind==='weekly'?'Semaine':'Mois'}</div></a>`).join('')}</div>`
  +(data.editions.length?'':'<div class="empty-state"><h2>Votre premier rendez-vous de veille</h2><p>Préparez un bulletin, sélectionnez les découvertes et relisez les présentations avant de les partager.</p></div>');
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
function digestImage(item){
 if(!item.image||!item.include_image)return '';
 return `<figure class="digest-image"><img src="/api/digests/assets/${esc(item.image.file)}" alt="${esc(item.image.alt)}" loading="lazy"><figcaption>${esc(item.image.caption)}</figcaption></figure>`;
}
function digestProofs(item){
 return `<details class="digest-proofs"><summary>Sources et preuves</summary>${item.evidence.map(proof=>`<p>${reference(proof.ref)}<small>${esc(proof.ref)}</small><br>${esc(proof.text)}</p>`).join('')}${item.documentation.map(doc=>`<p><a href="${safeUrl(doc.url)}" target="_blank" rel="noopener noreferrer">Documentation consultée</a></p>`).join('')}${item.sources.filter(source=>source.url).map(source=>`<p><a href="${safeUrl(source.url)}" target="_blank" rel="noopener noreferrer">Source originale ${icon('external')}</a></p>`).join('')}</details>`;
}
async function digestPage(id,epoch){
 const edition=await api('/api/digests/'+encodeURIComponent(id));
 if(epoch!==state.epoch)return;
 const frozen=Object.values(edition.delivery).some(row=>['sent','sending','uncertain'].includes(row.state));
 const visible=edition.items.filter(row=>row.included);
 $('#content').innerHTML=`<div class="detail-top"><a class="btn btn-quiet" href="#/digests">${icon('back')}Tous les bulletins</a><div class="detail-actions"><a class="btn" href="/api/digests/${esc(id)}/article.html" target="_blank" rel="noopener">${icon('download')}HTML / imprimer en PDF</a><a class="btn" href="/api/digests/${esc(id)}/article.md">Markdown</a></div></div>`
  +`<div class="detail-heading"><div><div class="eyebrow">VEILLE ${edition.kind==='weekly'?'HEBDOMADAIRE':'MENSUELLE'} · ${esc(digestState(edition))}</div><h1>${esc(edition.title)}</h1></div></div><p class="detail-summary">${esc(edition.intro)}</p>`
  +(edition.total_candidates>edition.items.length?`<div class="notice"><p>${edition.items.length} découvertes retenues sur ${edition.total_candidates}, selon la limite configurée.</p></div>`:'')
  +`<div class="detail-actions digest-actions">${!edition.approved&&!frozen?'<button class="btn" id="digest-refresh">Repréparer depuis les sources</button>':''}<button class="btn" id="digest-approve" ${frozen||!visible.length?'disabled':''}>${icon('check')}Valider pour diffusion</button><button class="btn btn-primary" id="digest-send" ${edition.approved&&!frozen?'':'disabled'}>${icon('arrow')}Demander l’envoi</button></div><p id="digest-action-status" role="status"></p>`
  +(Object.values(edition.delivery).length?`<section class="detail-panel"><h2>Suivi des diffusions</h2>${Object.values(edition.delivery).map(row=>`<p>${esc(row.channel==='email'?'Mail':'Webhook')} · ${esc({sending:'En cours',sent:'Accepté par le service',uncertain:'À vérifier'}[row.state]||row.state)}<br><small>${esc(row.message||'')}</small></p>`).join('')}</section>`:'')
  +(!edition.items.length?'<div class="empty-state"><h2>Aucune découverte sur cette période</h2><p>Vérifiez la date et le périmètre configuré pour les bulletins.</p></div>':'')
  +(!frozen&&edition.items.length?`<details class="detail-panel"><summary>Relire et composer le bulletin</summary><form id="digest-editor"><label>Titre<input name="title" maxlength="180" required value="${esc(edition.title)}"></label><label>Introduction<textarea name="intro" maxlength="2000" required>${esc(edition.intro)}</textarea></label>${edition.items.map(item=>`<fieldset data-digest-item="${esc(item.id)}"><legend>${esc(item.title)}</legend><label class="editorial-review"><input type="checkbox" name="included" ${item.included?'checked':''}> Inclure cette découverte</label><label>Rubrique<input name="theme" maxlength="100" value="${esc(item.theme)}"></label><label>Titre<input name="title" maxlength="180" value="${esc(item.title)}"></label><label>Présentation<textarea name="summary" maxlength="1500">${esc(item.summary)}</textarea></label><label>Utilité<textarea name="usefulness" maxlength="1000">${esc(item.usefulness)}</textarea></label><label>Fonctionnement<textarea name="operation" maxlength="1000">${esc(item.operation)}</textarea></label><label class="editorial-review"><input type="checkbox" name="include_image" ${item.include_image?'checked':''} ${item.image?'':'disabled'}> Inclure l’image disponible</label></fieldset>`).join('')}<button class="btn btn-primary" type="submit">Enregistrer le brouillon</button><p id="digest-editor-status" role="status"></p></form></details>`:'')
  +`<section class="digest-article" aria-label="Aperçu du bulletin">${visible.map(item=>`<article class="detail-panel"><div class="eyebrow">${esc(item.theme)} · ${esc(item.novelty)}</div><h2>${esc(item.title)}</h2>${digestImage(item)}<small class="text-muted">${esc(digestAttribution(item,'description'))}</small><p>${esc(item.summary)}</p>${item.usefulness?`<p><strong>À quoi ça sert</strong><br><small class="text-muted">${esc(digestAttribution(item,'usefulness'))}</small><br>${esc(item.usefulness)}</p>`:''}${item.operation?`<p><strong>Comment ça fonctionne</strong><br><small class="text-muted">${esc(digestAttribution(item,'operation'))}</small><br>${esc(item.operation)}</p>`:''}<a class="btn btn-quiet" href="${esc(item.route)}">Ouvrir la fiche ${icon('arrow')}</a>${digestProofs(item)}</article>`).join('')}</section>`
  +'<div class="notice"><p>La version HTML conserve les images pour le partage. Le navigateur permet de l’enregistrer en PDF depuis son menu d’impression. Les textes restent attribués aux sources.</p></div>';
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
 $('#digest-approve').onclick=()=>action('approve');
 $('#digest-send').onclick=()=>action('send');
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
