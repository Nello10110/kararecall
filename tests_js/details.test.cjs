const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.join(__dirname,'..');
function context(){
 const ctx=vm.createContext({URL,Intl});
 const app=fs.readFileSync(path.join(root,'web/app.js'),'utf8');
 vm.runInContext(app.slice(0,app.indexOf('function nav(')),ctx);
 vm.runInContext(fs.readFileSync(path.join(root,'web/details.js'),'utf8'),ctx);
 return ctx;
}
function entry(overrides={}){return {id:'fixture',name:'Notes de test',description:'Un outil de notes locales.',aliases:[],source_ids:['source'],claims:[],details:{},links:[],...overrides};}

test('primary link excludes original posts, social links, failed reads and credential URLs',()=>{
 const ctx=context();
 const e=entry({links:[
  {url:'https://original.example/article',status:'page_read'},
  {url:'https://instagram.com/reel/example',status:'page_read'},
  {url:'https://example.org/missing',status:'not_found_at_check'},
  {url:'https://user:secret@example.org',status:'page_read'},
  {url:'javascript:alert(1)',status:'page_read'},
  {url:'https://github.com/example/notes',status:'repository_exists'}]});
 const selected=ctx.toolDestination(e,[{url:'https://original.example/article'}]);
 assert.equal(selected.url,'https://github.com/example/notes');
 assert.equal(selected.label,'Voir le dépôt');
});
test('a read homepage is preferred, without claiming official identity',()=>{
 const ctx=context();
 const selected=ctx.toolDestination(entry({links:[{url:'https://docs.example.org/start',status:'page_read'},
  {url:'https://example.org/',status:'page_read'}]}));
 assert.equal(selected.domain,'example.org');assert.equal(selected.label,'Ouvrir le site');
 assert.equal(selected.note,'Page consultée');
});
test('an unchecked address stays unchecked and an absent address is never invented',()=>{
 const ctx=context();
 const selected=ctx.toolDestination(entry({links:[{url:'https://example.org',status:'caption_mention_unchecked',label:'Site officiel'}]}));
 assert.equal(selected.label,'Ouvrir le lien');assert.equal(selected.read,false);
 assert.equal(selected.note,'Accès non vérifié');
 assert.equal(ctx.toolDestination(entry({name:'An invented domain should not be generated'})),null);
});
test('boilerplate about a video gives way to a useful sourced description',()=>{
 const ctx=context();
 assert.equal(ctx.toolLead(entry({description:'Cet outil est cité dans une vidéo.',details:{usefulness:[{text:'Organiser ses notes locales.'}]}})),'Organiser ses notes locales.');
 assert.equal(ctx.toolLead(entry()),'Un outil de notes locales.');
 assert.doesNotMatch(ctx.toolLead(entry({description:'Outil mentionné dans une vidéo.'})),/vidéo/);
});
test('references are collapsed and deduplicated while retaining their destinations',()=>{
 const ctx=context();ctx.reference=(ref,index)=>`<a href="${ref}">Passage ${index}</a>`;
 const html=ctx.proofDetails({evidence:['one#asr-a','one#asr-a','one#ocr-b']});
 assert.match(html,/2 références/);assert.doesNotMatch(html,/<details[^>]*\sopen[\s>]/);
 assert.match(html,/one#asr-a/);assert.match(html,/one#ocr-b/);
});
test('tool reading precedes the collapsed editor and rendering makes no mutation',async()=>{
 const ctx=context(),content={innerHTML:''},calls=[];
 ctx.document={querySelector:()=>content,querySelectorAll:()=>[]};
 ctx.editorForm=()=>'<form id="editorial-form">Editor</form>';
 ctx.researchPanel=()=>'';ctx.bindEditor=()=>{};ctx.bindActions=()=>{};ctx.bindReadingView=()=>{};
 ctx.api=async route=>{calls.push(route);return {entity:entry({details:{usefulness:[{text:'Useful facts',status:'source_claim',evidence:[]}]},links:[{url:'https://example.org',status:'page_read'}]}),sources:[],revision:'fixture-revision'};};
 vm.runInContext('state.epoch=1',ctx);
 await ctx.toolPage('fixture',1);
 assert.deepEqual(calls,['/api/tools/fixture']);
 assert.ok(content.innerHTML.indexOf('Useful facts')<content.innerHTML.indexOf('id="tool-management"'));
 assert.match(content.innerHTML,/Ouvrir le site/);assert.doesNotMatch(content.innerHTML,/OUTIL[^<]*SOURCE/);
 assert.match(content.innerHTML,/<details[^>]*id="tool-management"/);
 assert.doesNotMatch(content.innerHTML,/<details[^>]*id="tool-management"[^>]*\sopen[\s>]/);
});

test('bulletin links distinguish tool routes from sources with either hash form',()=>{
 const ctx=context();
 assert.equal(ctx.recordRouteLabel('/#/tools/fixture'),'Ouvrir l’outil');
 assert.equal(ctx.recordRouteLabel('#/tools/fixture'),'Ouvrir l’outil');
 assert.equal(ctx.recordRouteLabel('/#/sources/fixture'),'Ouvrir la source');
});

test('a bookmarked homepage remains eligible when explicitly saved as a read tool link',()=>{
 const ctx=context();
 const selected=ctx.toolDestination(entry({links:[{url:'https://example.org/',status:'page_read'}]}),[{url:'https://example.org/'}]);
 assert.equal(selected.url,'https://example.org/');
 assert.equal(selected.label,'Ouvrir le site');
});

test('document status names existing Karakeep text without irrelevant audio steps',()=>{
 const ctx=context(),app=fs.readFileSync(path.join(root,'web/app.js'),'utf8');
 vm.runInContext(app.slice(app.indexOf('function sourceStatusPanel('),app.indexOf('function evidenceText(')),ctx);
 vm.runInContext('state.catalog={worker:{}}',ctx);
 const html=ctx.sourceStatusPanel({id:'document-fixture',document_asset_id:'pdf-one',assets:[],processing:{},stages:{document:'source_text',llm:'disabled'}});
 assert.match(html,/Texte fourni par Karakeep/);
 assert.doesNotMatch(html,/<strong>Paroles<|<strong>Texte à l’écran</);
});

test('coverage is visible without claiming that metadata is a full analysis',()=>{
 const ctx=context();
 const html=ctx.coveragePanel({coverage_state:{label:'Métadonnées seules',limitations:['Le texte principal est absent.']}});
 assert.match(html,/Métadonnées seules/);assert.match(html,/texte principal est absent/);
 assert.equal(ctx.coveragePanel({}),'');
});

test('administration coverage links to source filters and escapes unknown attachment names',()=>{
 const ctx=context();vm.runInContext(fs.readFileSync(path.join(root,'web/workspace.js'),'utf8'),ctx);
 const html=ctx.coverageAdministration({labels:{metadata:'Métadonnées seules',unsupported:'Format non pris en charge'},
  states:{metadata:2,unsupported:1},kinds:[{label:'Fichiers',total:3,states:{metadata:2,unsupported:1}}],attachments:{'<script>evil</script>':1}});
 assert.match(html,/#\/sources\?support=metadata/);assert.match(html,/Format non pris en charge/);
 assert.doesNotMatch(html,/<script>/);assert.match(html,/Type inconnu/);
});
