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
