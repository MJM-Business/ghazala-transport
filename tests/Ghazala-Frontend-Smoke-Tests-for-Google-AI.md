# Ghazala Transport Frontend Smoke Tests

Read-only copies of the original `.cjs` test files, combined for Google AI Studio upload. Do not replace or rename the originals in the project.


## Original file: `frontend_baseline_smoke.cjs`

```javascript
'use strict';
/* Offline fixtures only: no HTTP requests, server starts, or database writes. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const ops=fs.readFileSync(path.join(root,'static','ops.js'),'utf8');
const app=fs.readFileSync(path.join(root,'static','app.js'),'utf8');
const section=(source,start,end)=>source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)));
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function field(value=''){
  const classes=new Set();
  return {value,dataset:{},disabled:false,isConnected:true,innerHTML:'',textContent:'',
    classList:{add:value=>classes.add(value),remove:value=>classes.delete(value),contains:value=>classes.has(value)},
    click(){},dispatchEvent(){},getBoundingClientRect(){return {width:320,height:160,top:0,left:0}}};
}
function makeForm(){
  const names=['proofAwb','receiverName','receiverId','otp','podNote','podPhoto','podPhotoButton','podPhotoLabel','podPhotoButtonLabel','podSmsState','podLocationLabel','sendOtp','podGps','submitPod','clearSignature'];
  const fields=Object.fromEntries(names.map(name=>['#'+name,field()]));
  fields['#proofAwb'].value='GHZ-A';
  const photo=fields['#podPhoto'];photo.files=[];
  let photoValue='';
  Object.defineProperty(photo,'value',{get:()=>photoValue,set:value=>{photoValue=value;if(value==='')photo.files=[]}});
  const draws=[];
  const ctx={scale(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},clearRect(){draws.push('clear')},drawImage(){draws.push('image')}};
  const canvas=field();canvas.getContext=()=>ctx;canvas.setPointerCapture=()=>{};canvas.toDataURL=()=>'data:image/png;base64,signature';
  fields['#signatureCanvas']=canvas;fields['.ops-recipient-card']=field();
  const controls=['receiverName','receiverId','otp','podNote','podPhoto','podPhotoButton','sendOtp','podGps','submitPod','clearSignature'].map(id=>fields['#'+id]);
  const form={dataset:{},isConnected:true,querySelector:selector=>fields[selector]||null,querySelectorAll:()=>controls};
  return {form,fields,canvas,draws};
}
const shipments=[
  {awb:'GHZ-A',recipient:'Recipient A',origin:'جدة',destination:'جازان',eta:'ETA A',status:'قيد التوصيل',driver_latitude:21,driver_longitude:39},
  {awb:'GHZ-B',recipient:'Recipient B',origin:'جازان',destination:'جدة',eta:'ETA B',status:'قيد التوصيل',driver_latitude:16,driver_longitude:42}
];
async function podTests(){
  const fixture=makeForm(),{form,fields,canvas}=fixture,requests=[],messages=[],images=[];
  let apiHandler=async()=>{throw Object.assign(new Error('No saved proof'),{status:404})};
  let photoHandler=async()=>'',gpsCallback;
  const context={shipments,hasPermission:()=>true,requirePermission:()=>true,window:{devicePixelRatio:1},Image:class{set src(value){this.value=value;images.push(this)}},
    $:(selector,scope)=>scope.querySelector(selector),$$:(selector,scope)=>[...scope.querySelectorAll(selector)],
    tr:value=>value,safe:value=>String(value||'').replace(/</g,'&lt;'),fmt:value=>String(value),localizeNow(){},
    gps:callback=>{gpsCallback=callback},toast:message=>messages.push(message),load:async()=>{},
    compressPhoto:file=>photoHandler(file),
    api:async(url,opts)=>{requests.push({url,opts});return apiHandler(url,opts)}};
  vm.createContext(context);
  vm.runInContext(section(ops,'  function bindPodForm(','  function bindOps('),context);
  context.bindPodForm(form);await tick();
  assert.equal(fields['#submitPod'].disabled,false);
  assert.equal(requests[0].url,'/api/shipments/GHZ-A/pod');
  fields['#otp'].value='111111';fields['#receiverId'].value='4321';fields['#podNote'].value='A note';
  fields['#podPhoto'].files=[{name:'A.jpg',size:100}];fields['#podPhoto'].value='A.jpg';fields['#podPhoto'].onchange();
  canvas.onpointerdown({pointerId:1,clientX:5,clientY:5});canvas.onpointermove({clientX:20,clientY:20});canvas.onpointerup();
  fields['#podGps'].onclick();gpsCallback('21.5','39.1');
  context.bindPodForm(form);
  assert.equal(form.podDraft.hasInk,true,'Rebinding the same form retains signature validity');
  assert.equal(fields['#otp'].value,'111111');
  fields['#proofAwb'].value='GHZ-B';fields['#proofAwb'].onchange();await tick();
  assert.equal(fields['#receiverName'].value,'Recipient B');
  assert.match(fields['.ops-recipient-card'].innerHTML,/Recipient B.*ETA B/);
  for(const selector of ['#otp','#receiverId','#podNote','#podPhoto'])assert.equal(fields[selector].value,'');
  assert.equal(fields['#podPhoto'].files.length,0);
  assert.equal(form.podDraft.hasInk,false);assert.equal(form.podDraft.location,null);
  assert.equal(fields['#podSmsState'].textContent,'');
  const count=requests.length;await form.onsubmit({preventDefault(){}});
  assert.equal(requests.length,count,'Unsigned proof does not send a request');

  fields['#proofAwb'].value='GHZ-A';fields['#proofAwb'].onchange();await tick();
  let resolveOtp;
  apiHandler=async(url,opts)=>{
    if(opts?.method==='POST'&&url.endsWith('/otp'))return new Promise(resolve=>{resolveOtp=resolve});
    throw Object.assign(new Error('No saved proof'),{status:404});
  };
  const otpPending=fields['#sendOtp'].onclick();fields['#podGps'].onclick();
  const staleGps=gpsCallback;
  fields['#proofAwb'].value='GHZ-B';fields['#proofAwb'].onchange();
  resolveOtp({delivery:'demo',demo_code:'999999'});staleGps('55','44');await otpPending;await tick();
  assert.equal(fields['#podSmsState'].textContent,'');
  assert.equal(form.podDraft.location,null,'Delayed GPS for A cannot attach to B');

  let resolveProof;
  apiHandler=async(url)=>url.includes('GHZ-A')?new Promise(resolve=>{resolveProof=resolve}):Promise.reject(Object.assign(new Error('No saved proof'),{status:404}));
  fields['#proofAwb'].value='GHZ-A';fields['#proofAwb'].onchange();
  fields['#proofAwb'].value='GHZ-B';fields['#proofAwb'].onchange();await tick();
  resolveProof({recipient_name:'Old A',signature_data:'data:A',note:'Stale A'});await tick();
  assert.equal(fields['#receiverName'].value,'Recipient B');
  assert.equal(fields['#podNote'].value,'');
  const saved={recipient_name:'Verified B',recipient_id_suffix:'1234',signature_data:'data:B',photo_data:'photo:B',note:'B only',latitude:16.8,longitude:42.5};
  apiHandler=async()=>saved;
  fields['#proofAwb'].onchange();await tick();
  assert.equal(fields['#receiverName'].value,'Verified B');assert.equal(fields['#podNote'].value,'B only');
  assert.equal(fields['#submitPod'].disabled,true);assert.equal(fields['#podPhotoButton'].disabled,true);
  assert.equal(fields['#proofAwb'].disabled,false);
  images.at(-1).onload();assert.equal(form.podDraft.hasInk,true);
  const beforeSavedSubmit=requests.length;await form.onsubmit({preventDefault(){}});
  assert.equal(requests.length,beforeSavedSubmit,'Saved proof stays read only');

  apiHandler=async()=>{throw Object.assign(new Error('No saved proof'),{status:404})};
  fields['#proofAwb'].value='GHZ-A';fields['#proofAwb'].onchange();await tick();
  assert.equal(fields['#receiverName'].value,'Recipient A');assert.equal(fields['#podNote'].value,'');
  assert.equal(fields['#submitPod'].disabled,false);assert.equal(form.podDraft.location,null);
  images.at(-1).onload();assert.equal(form.podDraft.hasInk,false,'A delayed saved signature cannot attach to a new AWB');
  canvas.onpointerdown({pointerId:2,clientX:5,clientY:5});canvas.onpointermove({clientX:30,clientY:20});canvas.onpointerup();
  fields['#otp'].value='222222';fields['#podPhoto'].files=[{name:'New A.jpg',size:100}];
  let resolvePhoto;photoHandler=()=>new Promise(resolve=>{resolvePhoto=resolve});
  apiHandler=async()=>({ok:true});
  const pendingSubmit=form.onsubmit({preventDefault(){}});
  assert.equal(fields['#proofAwb'].disabled,true);
  fields['#proofAwb'].value='GHZ-B';fields['#proofAwb'].onchange();
  assert.equal(fields['#proofAwb'].value,'GHZ-A','An in-flight submission remains pinned to A');
  await form.onsubmit({preventDefault(){}});
  resolvePhoto('photo:New A');await pendingSubmit;
  const writes=requests.filter(request=>request.opts?.method==='POST'&&request.url.endsWith('/pod'));
  assert.equal(writes.length,1,'Double submit causes one POD request');
  assert.equal(writes[0].url,'/api/shipments/GHZ-A/pod');
  const payload=JSON.parse(writes[0].opts.body);
  assert.equal(payload.photo_data,'photo:New A');assert.equal(payload.recipient_name,'Recipient A');
  assert.equal(payload.latitude,null);assert.equal(payload.longitude,null,'No driver-location fallback');
  context.hasPermission=()=>false;context.requirePermission=()=>false;
  apiHandler=async()=>{throw Object.assign(new Error('No saved proof'),{status:404})};
  fields['#proofAwb'].onchange();await tick();
  assert.equal(fields['#submitPod'].disabled,true,'Read-only POD permission cannot enable completion');
  assert.equal(fields['#sendOtp'].disabled,true);assert.equal(fields['#podPhotoButton'].disabled,true);
  assert.equal(fields['#proofAwb'].disabled,false,'Read-only users retain shipment selection');
  const readonlyCount=requests.length;await form.onsubmit({preventDefault(){}});
  assert.equal(requests.length,readonlyCount,'Read-only proof cannot submit a write request');
  return {requests:requests.length,podWrites:writes.length};
}
async function pdfTests(){
  const saves=[],slices=[],messages=[];
  const sheet={dataset:{documentKind:'manifest',documentId:'TRK-TEST'},getBoundingClientRect:()=>({height:1750,top:10}),
    querySelectorAll:selector=>selector==='img'?[{complete:true}]:Array.from({length:22},(_,index)=>({getBoundingClientRect:()=>({top:10+index*75})}))};
  const frame={dataset:{},isConnected:true,contentDocument:{fonts:{ready:Promise.resolve()},querySelector:()=>sheet}};
  const button=field();
  const context={document:{querySelector:()=>frame,createElement:()=>{const canvas={width:0,height:0,getContext:()=>({drawImage:(source,sx,sy,sw,sh)=>slices.push({sy,sh})}),toDataURL:()=> 'data:image/jpeg;base64,fixture'};return canvas}},
    requirePermission:()=>true,window:{html2canvas:async()=>({width:800,height:3500}),jsPDF:class{
      constructor(){this.pages=1;this.images=[]}
      addPage(){this.pages++}
      addImage(...args){this.images.push(args)}
      save(name){saves.push({name,pages:this.pages,images:this.images})}
    }},$:()=>button,tr:value=>value,toast:message=>messages.push(message),console:{warn(){}}};
  vm.createContext(context);
  vm.runInContext(section(ops,'  async function triggerWaybillPdfDownload(','  function triggerWaybillParentPrint('),context);
  await context.triggerWaybillPdfDownload('TRK-TEST');
  assert.equal(saves[0].name,'Manifest-TRK-TEST.pdf');assert.ok(saves[0].pages>1);
  assert.equal(slices.reduce((total,slice)=>total+slice.sh,0),3500,'All source pixels are retained');
  assert.equal(slices[0].sy,0);
  slices.slice(1).forEach((slice,index)=>assert.equal(slice.sy,slices[index].sy+slices[index].sh));
  saves[0].images.forEach(args=>assert.ok(args[5]<=281,'Each page fits its printable area'));
  assert.equal(button.disabled,false);
  context.window.html2canvas=null;
  await context.triggerWaybillPdfDownload('TRK-TEST');
  assert.equal(saves.length,1,'Failure does not download HTML disguised as PDF');
  assert.match(messages.at(-1),/PDF/);
  const preview={},route={id:1,code:'TRK-REAL',origin:'جدة',destination:'جازان',driver_name:'Driver',vehicle_plate:'PLATE',shipments:[{awb:'GHZ-A',recipient:'A',weight:1}]};
  context.state={routes:[route]};context.safe=value=>String(value||'');context.fmt=String;
  context.tr=value=>value;context.document.documentElement={lang:'en',dir:'ltr'};
  context.location={origin:'http://localhost'};
  context.documentPreview=(title,record)=>{assert.equal(record.code,'TRK-REAL');return preview};
  context.fetchCodeSvg=async()=>'data:image/svg+xml,barcode';
  context.previewDocument=(target,html)=>{target.html=html};
  context.documentError=()=>assert.fail('Manifest fixture generation failed');
  vm.runInContext(section(ops,'  async function printManifest(','  function bindPodForm('),context);
  await context.printManifest(1);
  assert.match(preview.html,/class="sheet" data-document-kind="manifest" data-document-id="TRK-REAL"/);
  assert.match(preview.html,/GHZ-A/);
  return {pages:saves[0].pages,sourceHeight:3500};
}
async function statusTests(){
  const fields={'#modalRoot':field(),'#newStatus':field('تم الاستلام'),'#saveStatus':field()};
  const opened=[],context={shipments,document:{querySelector:id=>fields[id],querySelectorAll:()=>[]},
    requirePermission:()=>true,window:{openDeliveryProof:awb=>opened.push(awb)},localize(){},phrase:value=>value,esc:String,
    closeModal(){fields['#modalRoot'].innerHTML=''},api:async()=>assert.fail('Delivered status must open POD'),toast(){},load:async()=>{}};
  vm.createContext(context);
  vm.runInContext(app.split('\n').find(line=>line.startsWith('function statusModal(')),context);
  context.statusModal('GHZ-B');await fields['#saveStatus'].onclick();
  assert.deepEqual(opened,['GHZ-B']);
}
(async()=>{
  const localeContext={window:{}};vm.createContext(localeContext);
  for(const name of ['locales.js','ops-locales.js','landing-locales.js','workflow-locales.js'])vm.runInContext(fs.readFileSync(path.join(root,'static',name),'utf8'),localeContext);
  for(const key of ['مبالغ التحصيل المطلوبة','قيمة رسوم الشحن المسجلة (شاملة الضريبة)','إثبات التسليم محفوظ (للقراءة فقط)','Complete delivery through the POD screen with a valid OTP and signature.'])for(const language of ['ar','en','ur','hi'])assert.ok(localeContext.window.LOCALES[language].phrases[key]);
  const pod=await podTests(),pdf=await pdfTests();await statusTests();
  console.log(JSON.stringify({ok:true,offline:true,pod,pdf,status:'delivered opens correct POD',locales:4},null,2));
})().catch(error=>{console.error(error);process.exitCode=1});

```


## Original file: `frontend_ops_cache_smoke.cjs`

```javascript
'use strict';
/* Offline fixtures only: no HTTP requests, browsers, server starts, or database writes. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'static', 'ops.js'), 'utf8');
const appSource = fs.readFileSync(path.join(__dirname, '..', 'static', 'app.js'), 'utf8');
const permissionHelpers = appSource.slice(appSource.indexOf('const accessRoleLabels='), appSource.indexOf('function applyLanguage('));
const stateDeclaration = source.match(/^\s*const state=\{[^\r\n]+\};/m)?.[0];
assert.ok(stateDeclaration, 'Extract the real operations state declaration');

function section(start, end) {
  const first = source.indexOf(start);
  const last = source.indexOf(end, first);
  assert.ok(first >= 0 && last > first, `Extract real source between ${start} and ${end}`);
  return source.slice(first, last);
}

const cacheFunctions = section('  function opsOwnerKey(', '  function baseFeeQuote(');
const renderWrapper = section('  window.render=function()', "  window.addEventListener('hashchange'");
assert.match(renderWrapper, /^\s*window\.render=function\(\)\{\s*syncOpsOwner\(\);/,
  'The real render wrapper synchronizes ownership before rendering');
assert.ok(renderWrapper.indexOf('syncOpsOwner()') < renderWrapper.indexOf('baseRender()'));

const arrayKeys = ['routes', 'branches', 'branchDirectory', 'vehicles', 'clients', 'campaigns', 'users', 'notifications'];
const commonPaths = ['/api/routes', '/api/branches', '/api/vehicles', '/api/pricing', '/api/notifications'];
const adminPaths = [...commonPaths, '/api/clients', '/api/campaigns', '/api/users', '/api/branch-directory'];

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function responseFor(url, owner) {
  return url === '/api/pricing' ? { owner, base_fee: 77 } : [{ id: `${owner}:${url}`, owner }];
}

function settle(requests, owner, error = null) {
  requests.forEach((request, index) => {
    if (error && index === 0) request.reject(error);
    else request.resolve(responseFor(request.url, owner));
  });
}

function fixture(initialUser = { id: 1, role: 'admin' }) {
  const calls = [], modal = { innerHTML: '' };
  let now = 1000000, renders = 0, binds = 0, renderObserver = () => {};
  const context = {
    user: initialUser, page: 'home', tracking: '', window: {}, app: { dataset: {} },
    Date: { now: () => now },
    $: selector => selector === '#modalRoot' ? modal : null,
    trackingFragment: () => null,
    location: { pathname: '/', search: '' }, history: { replaceState() {} },
    baseRender() { renders++; renderObserver(); },
    bindOps() { binds++; },
    api(url) {
      const pending = deferred();
      calls.push({ url, ...pending });
      return pending.promise;
    }
  };
  vm.createContext(context);
  vm.runInContext(`${permissionHelpers}\n${stateDeclaration}\n${cacheFunctions}\n${renderWrapper}\n` +
    'globalThis.cache={state,opsOwnerKey,syncOpsOwner,refreshOps};', context,
    { filename: 'ops-cache-extracted.js' });
  return {
    context, cache: context.cache, calls, modal,
    get renders() { return renders; }, get binds() { return binds; },
    get now() { return now; }, setTime(value) { now = value; },
    setUser(value) { context.user = value; },
    observeRender(callback) { renderObserver = callback; },
    start(force = false) {
      const first = calls.length;
      const promise = context.cache.refreshOps(force);
      return { promise, requests: calls.slice(first), pending: context.cache.state.pending };
    }
  };
}

function assertEmpty(state, label, checkRequest = true) {
  for (const key of arrayKeys) assert.equal(state[key].length, 0, `${label}: ${key} cleared`);
  assert.equal(Object.keys(state.pricing).length, 0, `${label}: pricing cleared`);
  assert.equal(state.last, 0, `${label}: cache timestamp cleared`);
  assert.equal(state.lastError, null, `${label}: error cleared`);
  assert.equal(state.location, null, `${label}: location cleared`);
  assert.equal(state.documentPreview, null, `${label}: preview cleared`);
  if (checkRequest) {
    assert.equal(state.busy, false, `${label}: busy cleared`);
    assert.equal(state.pending, null, `${label}: pending cleared`);
  }
}

function assertOwned(state, owner, role) {
  for (const key of arrayKeys) {
    const privileged = ['clients', 'campaigns', 'users'].includes(key);
    const accessible = key==='branchDirectory'?role!=='employee':!privileged || role === 'admin' || (role === 'manager' && key !== 'users');
    assert.equal(state[key].length, accessible ? 1 : 0, `${owner}: ${key} access`);
    if (accessible) assert.equal(state[key][0].owner, owner, `${owner}: ${key} belongs to current owner`);
  }
  assert.equal(state.pricing.owner, owner);
  assert.equal(state.busy, false);
  assert.equal(state.pending, null);
  assert.equal(state.lastError, null);
}

async function logoutClearsBeforeRender() {
  const f = fixture(), request = f.start();
  assert.deepEqual(request.requests.map(item => item.url), adminPaths);
  settle(request.requests, 'admin'); await request.promise;
  assertOwned(f.cache.state, 'admin', 'admin');
  f.cache.state.location = { latitude: 21, longitude: 39 };
  f.cache.state.documentPreview = { kind: 'waybill', id: 'ADMIN-ONLY' };
  f.cache.state.lastError = new Error('Previous owner error');
  f.modal.innerHTML = '<iframe>Authenticated document</iframe>';
  const revision = f.cache.state.ownerRevision, count = f.calls.length;
  let observed = false;
  f.observeRender(() => {
    observed = true;
    assert.equal(f.cache.state.ownerKey, null);
    assertEmpty(f.cache.state, 'Logout before baseRender');
    assert.equal(f.modal.innerHTML, '', 'Authenticated modal clears before baseRender');
  });
  f.setUser(null); f.context.window.render();
  assert.equal(observed, true);
  assert.equal(f.cache.opsOwnerKey(), null);
  assert.equal(f.cache.state.ownerRevision, revision + 1);
  assert.equal(f.calls.length, count, 'Logged-out render makes no cache request');
  await f.cache.refreshOps(true);
  assert.equal(f.calls.length, count, 'Logged-out refresh makes no request');
  assert.equal(f.cache.state.ownerRevision, revision + 1, 'Repeated logout does not increment revision');
}

async function pendingLogoutDiscardsResponse() {
  const f = fixture(), old = f.start(), revision = f.cache.state.ownerRevision;
  f.cache.state.location = { latitude: 1, longitude: 2 };
  f.cache.state.documentPreview = { kind: 'manifest', id: 1 };
  f.modal.innerHTML = '<section>Private account modal</section>';
  f.setUser(null); f.context.window.render();
  assertEmpty(f.cache.state, 'Logout while refreshing');
  assert.equal(f.modal.innerHTML, '');
  const renders = f.renders, binds = f.binds;
  settle(old.requests, 'stale-admin'); await old.promise;
  assertEmpty(f.cache.state, 'Delayed admin response after logout');
  assert.equal(f.cache.state.ownerRevision, revision + 1);
  assert.equal(f.renders, renders, 'Delayed response cannot render after logout');
  assert.equal(f.binds, binds, 'Delayed response cannot bind after logout');
}

async function ownerSwitchDiscardsSuccess(nextUser) {
  const f = fixture(), old = f.start();
  const oldRevision = f.cache.state.ownerRevision;
  f.setUser(nextUser);
  const current = f.start();
  assert.equal(f.cache.state.ownerKey, `${nextUser.id}:${nextUser.role}`);
  assert.equal(f.cache.state.ownerRevision, oldRevision + 1);
  assert.equal(current.requests.length, nextUser.role === 'admin' ? 9 : 5,
    'The new owner starts a request without waiting for the old owner');
  assert.notEqual(current.pending, old.pending);
  assertEmpty(f.cache.state, 'Switch before results', false);
  settle(old.requests, 'stale-admin'); await old.promise;
  assertEmpty(f.cache.state, 'Stale success cannot fill new cache', false);
  assert.equal(f.cache.state.busy, true, 'Old success/finally cannot release the new request');
  assert.equal(f.cache.state.pending, current.pending);
  assert.equal(f.renders, 0, 'Stale success does not render');
  settle(current.requests, 'current-owner'); await current.promise;
  assertOwned(f.cache.state, 'current-owner', nextUser.role);
  assert.equal(f.renders, 1);
  assert.equal(f.binds, 1);
}

async function staleFailureCannotReleaseNewRequest() {
  const f = fixture(), old = f.start();
  f.setUser({ id: 2, role: 'employee' });
  const current = f.start();
  settle(old.requests, 'old', new Error('Old administrator request failed'));
  await old.promise;
  assertEmpty(f.cache.state, 'Stale failure ignored', false);
  assert.equal(f.cache.state.busy, true, 'Old failure/finally cannot release the new request');
  assert.equal(f.cache.state.pending, current.pending);
  const failure = new Error('Current employee request failed');
  settle(current.requests, 'current', failure); await current.promise;
  assert.equal(f.cache.state.lastError, failure, 'Current owner receives its own failure');
  assert.equal(f.cache.state.busy, false);
  assert.equal(f.cache.state.pending, null);
  const retry = f.start(true);
  settle(retry.requests, 'recovered-employee'); await retry.promise;
  assertOwned(f.cache.state, 'recovered-employee', 'employee');
}

async function liveOwnerGuard() {
  for (const failed of [false, true]) {
    const f = fixture(), old = f.start();
    f.setUser({ id: 7, role: 'employee' });
    // No render or refresh has synchronized the new owner yet: the live user check is essential.
    settle(old.requests, 'stale-live-user', failed ? new Error('Stale live-user failure') : null);
    await old.promise;
    for (const key of arrayKeys) assert.equal(f.cache.state[key].length, 0);
    assert.equal(f.cache.state.last, 0);
    assert.equal(f.cache.state.lastError, null);
    assert.equal(f.renders, 0);
    f.cache.syncOpsOwner();
    assertEmpty(f.cache.state, 'Synchronizing a live user change releases old busy state');
  }
}

async function sameAccountReturnUsesRevision() {
  const f = fixture(), old = f.start(), oldKey = f.cache.state.ownerKey;
  const revision = f.cache.state.ownerRevision;
  f.setUser(null); f.cache.syncOpsOwner();
  f.setUser({ id: 1, role: 'admin' });
  const current = f.start();
  assert.equal(f.cache.state.ownerKey, oldKey, 'Account returns to the same owner key');
  assert.equal(f.cache.state.ownerRevision, revision + 2);
  settle(old.requests, 'before-logout'); await old.promise;
  assertEmpty(f.cache.state, 'Same-key stale session cannot fill cache', false);
  assert.equal(f.cache.state.busy, true);
  assert.equal(f.cache.state.pending, current.pending, 'Revision prevents old session finally from releasing the new request');
  settle(current.requests, 'after-login'); await current.promise;
  assertOwned(f.cache.state, 'after-login', 'admin');
}

async function roleChangeForSameIdResetsCache() {
  const f = fixture(), admin = f.start();
  settle(admin.requests, 'admin'); await admin.promise;
  const revision = f.cache.state.ownerRevision;
  f.cache.state.location = { latitude: 4, longitude: 5 };
  f.cache.state.documentPreview = { kind: 'waybill', id: 'PRIVATE' };
  f.modal.innerHTML = 'Administrator document';
  f.setUser({ id: 1, role: 'employee' });
  const employee = f.start();
  assert.equal(f.cache.opsOwnerKey(), '1:employee');
  assert.equal(f.cache.state.ownerRevision, revision + 1);
  assert.deepEqual(employee.requests.map(item => item.url), commonPaths,
    'Fresh role bypasses the previous role cache and requests only authorized resources');
  assertEmpty(f.cache.state, 'Role change clears previous owner state', false);
  assert.equal(f.modal.innerHTML, '');
  settle(employee.requests, 'employee'); await employee.promise;
  assertOwned(f.cache.state, 'employee', 'employee');
}

async function sameOwnerCacheAndDedup() {
  const f = fixture(), first = f.start(), revision = f.cache.state.ownerRevision;
  const duplicate = f.start(), forcedDuplicate = f.start(true);
  assert.equal(f.calls.length, 9, 'Repeated refreshes deduplicate an in-flight request');
  assert.equal(duplicate.pending, first.pending);
  assert.equal(forcedDuplicate.pending, first.pending, 'Forced refresh also deduplicates while busy');
  f.cache.syncOpsOwner();
  assert.equal(f.cache.state.ownerRevision, revision);
  assert.equal(f.cache.state.pending, first.pending, 'Same-owner sync retains the active request');
  settle(first.requests, 'same-owner');
  await Promise.all([first.promise, duplicate.promise, forcedDuplicate.promise]);
  assertOwned(f.cache.state, 'same-owner', 'admin');
  assert.equal(f.cache.state.last, f.now);
  const cachedAt = f.now;
  f.setUser({ id: 1, role: 'admin', name: 'Updated display name' });
  f.setTime(cachedAt + 14999); await f.cache.refreshOps();
  assert.equal(f.calls.length, 9, 'Same owner retains cache for 15 seconds');
  assert.equal(f.cache.state.ownerRevision, revision);
  f.setTime(cachedAt + 15000);
  const expired = f.start();
  assert.equal(expired.requests.length, 9, 'Cache expires at 15 seconds');
  settle(expired.requests, 'expired-refresh'); await expired.promise;
  const forced = f.start(true);
  assert.equal(forced.requests.length, 9, 'Forced refresh bypasses a completed fresh cache');
  settle(forced.requests, 'forced-refresh'); await forced.promise;
  assertOwned(f.cache.state, 'forced-refresh', 'admin');
  assert.equal(f.cache.state.ownerRevision, revision);
}

async function permissionAndBranchChangesResetCache() {
  const initial={id:5,role:'employee',access_role:'office_employee',permissions:['shipments.read','shipments.create','branches.read','pricing.read'],branches:[{id:10},{id:20}],primary_branch_id:10};
  const changes=[
    {...initial,access_role:'accountant'},
    {...initial,permissions:['shipments.read','branches.read','pricing.read']},
    {...initial,branches:[{id:30}],primary_branch_id:30},
    {...initial,primary_branch_id:20}
  ];
  for(const next of changes){
    const f=fixture(initial),old=f.start(),revision=f.cache.state.ownerRevision,oldKey=f.cache.state.ownerKey;
    assert.deepEqual(old.requests.map(request=>request.url),['/api/branches','/api/pricing','/api/branch-directory'],'Request only permitted resources');
    f.setUser({...initial,permissions:[...initial.permissions].reverse(),branches:[...initial.branches].reverse()});
    assert.equal(f.cache.opsOwnerKey(),oldKey,'Order changes preserve the same access scope');
    f.setUser(next);const current=f.start();
    assert.equal(f.cache.state.ownerRevision,revision+1,'Canonical role, permission or office change invalidates cache');
    assert.notEqual(f.cache.state.ownerKey,oldKey);
    assert.notEqual(current.pending,old.pending);
    settle(old.requests,'old-scope');await old.promise;
    assertEmpty(f.cache.state,'Old scope is discarded',false);
    assert.equal(f.cache.state.busy,true);assert.equal(f.cache.state.pending,current.pending);
    settle(current.requests,'new-scope');await current.promise;
    assert.equal(f.cache.state.branches[0].owner,'new-scope');
    assert.equal(f.cache.state.pricing.owner,'new-scope');
    assert.equal(f.cache.state.users.length,0);assert.equal(f.cache.state.clients.length,0);
    assert.equal(f.cache.state.busy,false);assert.equal(f.cache.state.pending,null);
  }
}

(async () => {
  await logoutClearsBeforeRender();
  await pendingLogoutDiscardsResponse();
  await ownerSwitchDiscardsSuccess({ id: 2, role: 'employee' });
  await ownerSwitchDiscardsSuccess({ id: 9, role: 'admin' });
  await staleFailureCannotReleaseNewRequest();
  await liveOwnerGuard();
  await sameAccountReturnUsesRevision();
  await roleChangeForSameIdResetsCache();
  await sameOwnerCacheAndDedup();
  await permissionAndBranchChangesResetCache();
  console.log(JSON.stringify({ ok: true, offline: true, scenarios: 14,
    coverage: ['render clears before baseRender', 'logout clears populated and pending caches',
      'account and role switches discard stale success and failure', 'stale finally preserves new request',
      'live user and session revision guards', 'same-owner cache expiry, forced refresh and dedup',
      'permission, canonical role, office membership and primary-office invalidation'] }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });

```


## Original file: `frontend_permissions_smoke.cjs`

```javascript
'use strict';
/* Offline UI fixtures: no HTTP requests, browser, server or database writes. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const app=fs.readFileSync(path.join(root,'static/app.js'),'utf8'),ops=fs.readFileSync(path.join(root,'static/ops.js'),'utf8');
const section=(text,start,end)=>{const a=text.indexOf(start),b=text.indexOf(end,a);assert.ok(a>=0&&b>a);return text.slice(a,b)};
const helpers=section(app,'const accessRoleLabels=','function applyLanguage(');
const legacy={system_admin:'admin',branch_manager:'manager',office_employee:'employee',courier:'employee',accountant:'employee',customer:'employee'};
const permissions={
  system_admin:['shipments.read','shipments.create','shipments.status','shipments.assign','shipments.payment','drivers.read','drivers.manage','drivers.location','routes.read','routes.manage','branches.read','branches.manage','vehicles.read','vehicles.manage','clients.read','clients.manage','pricing.read','pricing.manage','campaigns.read','campaigns.manage','reports.read','users.manage','pod.read','pod.create','stats.read','demo.reset'],
  branch_manager:['shipments.read','shipments.create','shipments.status','shipments.assign','shipments.payment','drivers.read','drivers.manage','drivers.location','routes.read','routes.manage','branches.read','branches.manage','vehicles.read','clients.read','clients.manage','pricing.read','campaigns.read','reports.read','pod.read','pod.create','stats.read'],
  office_employee:['shipments.read','shipments.create','shipments.status','shipments.assign','drivers.read','routes.read','branches.read','vehicles.read','clients.read','pricing.read','campaigns.read','pod.read','pod.create','stats.read'],
  courier:['shipments.read','shipments.status','drivers.read','drivers.location','routes.read','branches.read','vehicles.read','pod.read','pod.create','stats.read'],
  accountant:['shipments.read','shipments.payment','branches.read','clients.read','pricing.read','reports.read','stats.read'],
  customer:[]
};
const account=role=>({id:1,role:legacy[role],access_role:role,permissions:permissions[role],branches:[{id:10,code:'JED',name:'Jeddah office',city:'جدة'}],primary_branch_id:10,display_name:'Staff'});
const modal={innerHTML:''},toasts=[],writes=[];let saved=0,form;
const context={user:account('system_admin'),document:{querySelector:selector=>selector==='#modalRoot'?modal:selector==='#userForm'?form:null},drivers:[{id:4,name:'Driver',national_id:'ID'}],phrase:value=>value,esc:value=>String(value??'').replace(/</g,'&lt;'),toast:value=>toasts.push(value),wireModal(){},closeModal(){modal.innerHTML=''},load:async()=>{saved++},api:async(url,options)=>{writes.push({url,options});return {ok:true}},FormData:class{
  constructor(value){this.rows=value.rows}
  [Symbol.iterator](){return this.rows[Symbol.iterator]()}
  getAll(name){return this.rows.filter(row=>row[0]===name).map(row=>row[1])}
}};
vm.createContext(context);vm.runInContext(helpers,context);
vm.runInContext('globalThis.access={accessRoleLabels,accessRole,hasPermission,canPage,canAction,applyPermissionControls,sessionContext};',context);
vm.runInContext(section(app,'function accountPayload(','function assignShipmentModal('),context);
Object.assign(context,{badge:status=>'<span>'+status+'</span>',money:value=>String(value),tr:value=>value,safe:value=>String(value??''),fmt:value=>String(value),head:()=>'',kpi:(label,value)=>'<div>'+label+': '+value+'</div>',shipments:[],state:{routes:[{status:'في الطريق'}],notifications:[{branch_name:'Office',route_code:'ROUTE-1'}]}});
vm.runInContext(section(app,'function shipmentCard(','function filtered('),context);
vm.runInContext(section(ops,'  function liveHome(','  function publicTrackBlock('),context);
vm.runInContext(section(ops,'  function clientCard(','  function clientsLivePage('),context);
function makeForm(rows,active=true,revoke=false){
  const primary={value:'',innerHTML:''},button={disabled:false,isConnected:true};
  const branches=[10,20].map(id=>({value:String(id),checked:rows.some(row=>row[0]==='branch_ids'&&row[1]===String(id))}));
  return {rows,elements:{namedItem:name=>name==='primary_branch_id'?primary:name==='is_active'?{checked:active}:name==='revoke_sessions'?{checked:revoke}:null},querySelector:()=>button,querySelectorAll:selector=>selector.endsWith(':checked')?branches.filter(field=>field.checked):branches,primary,button};
}
function node(dataset){return {dataset,removed:false,remove(){this.removed=true}}}
function controls(nodes){return {querySelectorAll:selector=>{const match=selector.match(/^\[([^\]]+)\]$/);return match?nodes.filter(node=>Object.hasOwn(node.dataset,match[1].replace(/^data-/,'').replace(/-([a-z])/g,(_,letter)=>letter.toUpperCase()))):[]}}}
async function customerHeaderRegression(){
  const classes=new Set(),calls=[],staffLink=node({page:'business'});
  const selectors=['.sidebar','#mobileNav','#globalSearch','#logoutBtn','.notice','#passwordBtn','#sessionLabel','#sideNav','#sideLogoutBtn','#menuToggle','#sidebar','#topbarGuestNav','.topbar'];
  const nodes=Object.fromEntries(selectors.map(selector=>[selector,{hidden:false,textContent:'',innerHTML:''}]));
  const customerContext={user:account('customer'),page:'home',app:controls([staffLink]),window:{},nav:[['home','Home'],['shipments','Shipments'],['staff','Staff'],['business','Staff Sign In']],navItem:()=>'<button>navigation</button>',phrase:value=>value,applyLanguage(){},localize(){},bindLandingInteractions(){},document:{body:{classList:{toggle(name,enabled){enabled?classes.add(name):classes.delete(name)}}},querySelector:selector=>nodes[selector]||null,querySelectorAll:()=>[]},api:async(url,options)=>{calls.push({url,options});return {ok:true}}};
  for(const name of ['landingPage','home','shipmentsPage','trackingPage','dispatchPage','driversPage','clientsPage','pricingPage','campaignsPage','analyticsPage','staffPage','proofPage','businessPage'])customerContext[name]=()=>'<section>landing</section>';
  customerContext.load=async()=>customerContext.render();
  vm.createContext(customerContext);vm.runInContext(helpers,customerContext);
  vm.runInContext(section(app,'function layoutNav(','function head('),customerContext);
  vm.runInContext(section(app,'function render(){','function bindLandingInteractions('),customerContext);
  vm.runInContext(section(app,'async function doLogout(){','function passwordModal('),customerContext);
  customerContext.render();
  assert.equal(customerContext.page,'landing');assert.ok(classes.has('guest'));assert.ok(classes.has('authenticated-customer'));
  assert.equal(nodes['#logoutBtn'].hidden,false);assert.equal(nodes['#passwordBtn'].hidden,false);assert.equal(nodes['#logoutBtn'].textContent,'⇥');
  for(const selector of ['.sidebar','#mobileNav','#globalSearch','.notice'])assert.equal(nodes[selector].hidden,true,'Customer restriction '+selector);
  assert.equal(nodes['#sideNav'].innerHTML,'');assert.equal(nodes['#mobileNav'].innerHTML,'');assert.ok(staffLink.removed,'Customer staff sign-in link is removed');
  const css=fs.readFileSync(path.join(root,'static/style.css'),'utf8');
  for(const selector of ['#logoutBtn','#passwordBtn','#sessionLabel']){
    assert.ok(css.includes('body.guest:not(.authenticated-customer) '+selector),'Guest CSS excludes authenticated customer '+selector);
    assert.ok(!css.includes('body.guest '+selector),'No unconditional guest rule can hide '+selector);
  }
  await nodes['#logoutBtn'].onclick();
  assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/logout');assert.equal(calls[0].options.method,'POST');
  assert.equal(customerContext.user,null);assert.ok(!classes.has('authenticated-customer'),'Logout clears the CSS exemption');
  assert.equal(nodes['#logoutBtn'].hidden,true);assert.equal(nodes['#passwordBtn'].hidden,true);
}
(async()=>{
  await customerHeaderRegression();
  for(const role of Object.keys(permissions)){
    context.user=account(role);
    assert.equal(context.access.accessRole(),role);
    assert.equal(context.access.canPage('staff'),role==='system_admin',role+' HR access');
    assert.equal(context.access.canPage('business'),role!=='customer','Reserved customers cannot open staff portal');
    assert.equal(context.access.canAction('staff'),role==='system_admin',role+' account administration');
    assert.equal(context.access.canAction('create'),['system_admin','branch_manager','office_employee'].includes(role));
    assert.equal(context.access.canPage('analytics'),['system_admin','branch_manager','accountant'].includes(role));
    assert.equal(context.access.canPage('proof'),['system_admin','branch_manager','office_employee','courier'].includes(role));
    assert.equal(context.access.canAction('branch'),role==='system_admin','Only system admin creates branches');
    assert.match(context.access.sessionContext(),/Jeddah office/);
  }
  context.user={id:1,role:'admin',access_role:'system_admin',permissions:[]};
  assert.equal(context.access.hasPermission('users.manage'),false,'Explicit empty permissions never fall back to legacy admin');
  context.user=account('accountant');
  const redacted={awb:'GHZ-ACCOUNTANT',recipient:'Recipient',sender_name:'Sender',origin:'جدة',destination:'جازان',status:'قيد النقل',stage:'قيد النقل',eta:'2026-10-07 15:00',cod:10,payment_status:'غير مدفوع'};
  context.shipments=[redacted];
  const card=context.shipmentCard(redacted);
  for(const withheld of ['السائق:','الموقع الحالي:','هوية','غير معيّن','غير محدد','—'])assert.ok(!card.includes(withheld),'Redacted shipment omits '+withheld);
  assert.ok(card.includes(redacted.eta));assert.ok(card.includes('Sender'));assert.ok(card.includes('Recipient'));
  const home=context.liveHome();
  for(const withheld of ['الرحلات النشطة','رحلات نشطة','المناديب','تنبيهات الرحلات','لا توجد تنبيهات مجدولة','ROUTE-1'])assert.ok(!home.includes(withheld),'Accountant dashboard omits withheld '+withheld);
  assert.ok(home.includes('إجمالي الشحنات'));
  const client=context.clientCard({id:1,name:'Client',code:'CL-1',city:'جدة',status:'نشط',credit_limit:10,payment_terms:'شهري'});
  assert.ok(!client.includes('رقم السجل'));assert.ok(!client.includes('tel:'));assert.ok(!client.includes('—'),'Redacted client data does not imply missing identity');
  context.user=account('system_admin');
  const fullCard=context.shipmentCard({...redacted,recipient_id:'REC-ID',phone:'REC-PHONE',sender_id:'SEND-ID',sender_phone:'SEND-PHONE',driver_name:'Driver',driver_national_id:'DRIVER-ID',driver_mobile:'DRIVER-PHONE',driver_location:'Driver location',driver_latitude:0,driver_longitude:42});
  for(const text of ['REC-ID','REC-PHONE','SEND-ID','SEND-PHONE','DRIVER-ID','DRIVER-PHONE','Driver location','0, 42'])assert.ok(fullCard.includes(text),'Authorized detail remains '+text);
  assert.ok(context.liveHome().includes('ROUTE-1'),'Authorized route alerts remain visible');
  assert.ok(context.liveHome().includes('المناديب'),'Authorized driver metric remains visible');
  context.user=account('courier');
  const courierCard=context.shipmentCard({...redacted,phone:'REC-PHONE',driver_name:'Driver',driver_mobile:'DRIVER-PHONE'});
  assert.ok(courierCard.includes('REC-PHONE'));assert.ok(!courierCard.includes('هوية'),'Courier identity redaction is not replaced with a dash');
  context.user=account('office_employee');
  const buttons=[node({action:'create'}),node({action:'staff'}),node({page:'analytics'}),node({page:'shipments'}),node({paymentAwb:'GHZ-A'}),node({status:'GHZ-A'}),node({clientEdit:1})];
  context.access.applyPermissionControls(controls(buttons));
  assert.deepEqual(buttons.map(button=>button.removed),[false,true,true,false,true,false,true]);
  form=makeForm([]);const before=writes.length;
  context.userModal();assert.equal(modal.innerHTML,'','Office cannot open the account form');assert.equal(writes.length,before);
  context.user=account('system_admin');
  const rows=[['display_name','New staff'],['username','new@example.test'],['password','StrongPass123'],['role','courier'],['branch_ids','10'],['branch_ids','20'],['primary_branch_id','20'],['driver_id','4']];
  form=makeForm(rows);
  context.userModal(null,null,[{id:10,code:'JED',name:'Jeddah office',city:'جدة'},{id:20,code:'JAZ',name:'Jaazan office',city:'جازان'}]);
  for(const role of Object.keys(permissions))assert.ok(modal.innerHTML.includes('value="'+role+'"'),'Canonical role option '+role);
  const payload=context.accountPayload(form,false);
  assert.deepEqual(JSON.parse(JSON.stringify(payload.branch_ids)),[10,20]);assert.equal(payload.primary_branch_id,20);assert.equal(payload.driver_id,4);
  await form.onsubmit({preventDefault(){}});
  assert.equal(writes.at(-1).url,'/api/users');assert.equal(writes.at(-1).options.method,'POST');assert.equal(saved,1);
  const editRows=rows.map(row=>row[0]==='role'?['role','office_employee']:row[0]==='password'?['password','']:row);
  form=makeForm(editRows,false,true);
  context.userModal(2,{id:2,username:'existing@example.test',display_name:'Existing',access_role:'office_employee',branches:[{id:20}],primary_branch_id:20,is_active:0},[{id:10,name:'Jeddah office',city:'جدة'},{id:20,name:'Jaazan office',city:'جازان'}]);
  assert.ok(modal.innerHTML.includes('readonly'));
  assert.match(modal.innerHTML,/<input name="password" type="password"\s+minlength="10" maxlength="256" autocomplete="new-password">/,'Edit password is optional and never prefilled');
  assert.ok(modal.innerHTML.includes('اترك كلمة المرور الجديدة فارغة للإبقاء على الحالية. إعادة تعيينها تنهي جلسات الحساب.'));
  const edit=context.accountPayload(form,true);
  assert.equal(edit.username,undefined);assert.equal(edit.password,undefined);assert.equal(edit.driver_id,null,'Office accounts cannot carry courier links');
  assert.equal(edit.is_active,false);assert.equal(edit.revoke_sessions,true);
  await form.onsubmit({preventDefault(){}});
  assert.equal(writes.at(-1).url,'/api/users/2');assert.equal(writes.at(-1).options.method,'PATCH');
  assert.equal(JSON.parse(writes.at(-1).options.body).password,undefined,'Blank edit password preserves the existing password');
  const resetRows=editRows.map(row=>row[0]==='password'?['password','ReplacementPass123']:row);
  form=makeForm(resetRows,true,false);
  context.userModal(2,{id:2,username:'existing@example.test',access_role:'office_employee',branch_ids:[10,20],primary_branch_id:20,is_active:1},[{id:10,name:'Office',city:'جدة'},{id:20,name:'Office',city:'جازان'}]);
  await form.onsubmit({preventDefault(){}});
  assert.equal(JSON.parse(writes.at(-1).options.body).password,'ReplacementPass123','Entered reset password is sent to the backend');
  assert.equal(JSON.parse(writes.at(-1).options.body).revoke_sessions,false,'Backend always revokes password-reset sessions independently of the checkbox');
  const resetCount=writes.length;
  form.rows=resetRows.map(row=>row[0]==='password'?['password','weak']:row);
  await form.onsubmit({preventDefault(){}});
  assert.equal(writes.length,resetCount,'Weak reset password is rejected before a request');
  assert.equal(toasts.at(-1),'Use 10–256 characters including an uppercase letter, a lowercase letter and a number.');
  form.rows=resetRows.map(row=>row[0]==='password'?['password','   ']:row);
  assert.equal(context.accountPayload(form,true).password,undefined,'Whitespace-only reset input is omitted');
  form=makeForm(editRows,false);
  context.userModal(1,{id:1,username:'self@example.test',access_role:'system_admin',is_active:1},[{id:10,name:'Office',city:'جدة'}]);
  const count=writes.length;await form.onsubmit({preventDefault(){}});
  assert.equal(writes.length,count,'Self deactivation is rejected before a request');
  assert.equal(toasts.at(-1),'لا يمكنك تعطيل حسابك الحالي');
  for(const language of ['ar','en','ur','hi']){
    const localeContext={window:{}};vm.createContext(localeContext);
    vm.runInContext(fs.readFileSync(path.join(root,'static/workflow-locales.js'),'utf8'),localeContext);
    const catalog=localeContext.window.LOCALES[language].phrases;
    for(const text of ['مدير الفرع','موظف المكتب','المحاسب','العميل (محجوز)','الفروع المسموح بها','تعديل الحساب','كلمة مرور جديدة (اختياري)','تم استلام الشحنة','في مكتب الإرسال','تم الترحيل للنقل','تم الاستلام في المكتب'])assert.ok(catalog[text]);
    for(const file of ['accounts.py','security.py','request_policy.py']){
      const errors=[...fs.readFileSync(path.join(root,file),'utf8').matchAll(/(?:ValueError|AccessDenied)\((['"])(.*?)\1\)/g)].map(match=>match[2]);
      for(const message of errors)assert.ok(catalog[message],language+' error coverage: '+message);
    }
  }
  console.log(JSON.stringify({ok:true,offline:true,roles:6,scope:'permissions are authoritative',customerHeader:'logout and password visible, operational navigation hidden, logout clears exemption',redactedData:'withheld identity, contact, driver and dashboard fragments omitted',accounts:'canonical role, branch, active, revocation and optional password-reset payloads',selfDeactivation:'blocked',locales:4},null,2));
})().catch(error=>{console.error(error);process.exitCode=1});

```
