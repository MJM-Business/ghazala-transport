(()=>{
const $=s=>document.querySelector(s);
const app=$('#app'),toastEl=$('#toast');
let me=null,shipments=[],branches=[];
let lang=localStorage.getItem('ghz-pos-lang')==='ar'?'ar':'en';
const deviceId=localStorage.getItem('ghz-pos-device-id')||('POS-'+Math.random().toString(36).slice(2,8).toUpperCase());
localStorage.setItem('ghz-pos-device-id',deviceId);
const api=async(path,options={})=>{
  const res=await fetch(path,{credentials:'same-origin',headers:{'Content-Type':'application/json',...(options.headers||{})},...options});
  let data={};try{data=await res.json()}catch(_){}
  if(!res.ok)throw new Error(data.error||('Request failed ('+res.status+')'));
  return data;
};
const TXT={
 en:{
  dedicated:'Dedicated shipment terminal',username:'Username',password:'Password',login:'Login to POS',
  denied:'This account cannot use the POS portal.',logout:'Logout',create:'Create Shipment',
  sub:'Fill details and print receipt',newShipment:'Create New Shipment',senderName:'Sender Name',
  senderMobile:'Sender Mobile',senderId:'Sender ID / Iqama (Optional)',recipientId:'Recipient ID / Iqama (Optional)',
  pickup:'Pickup Address',recipientName:'Recipient Name',recipientMobile:'Recipient Mobile',
  fromCity:'From City',toCity:'To City',destinationBranch:'Destination Branch',
  chooseBranch:'Choose Destination Branch',shipmentValue:'Shipment Value',cod:'Cash on Delivery',
  senderPays:'Sender Pays',collection:'Collection Amount',pieces:'Pieces',createPrint:'Create Shipment & Print',
  creating:'Creating Shipment...',created:'Shipment created',createdTitle:'Shipment Created',
  printSent:'Receipt print command has been sent.',newAgain:'Create New Shipment',printAgain:'Print Again',
  sentPrinter:'Sent to POS printer',qrError:'Could not generate',language:'Language'
 },
 ar:{
  dedicated:'جهاز مخصص لإنشاء الشحنات',username:'اسم المستخدم',password:'كلمة المرور',login:'تسجيل الدخول',
  denied:'هذا الحساب غير مخول لاستخدام بوابة نقاط البيع.',logout:'تسجيل الخروج',create:'إنشاء شحنة',
  sub:'أدخل البيانات واطبع الإيصال',newShipment:'إنشاء شحنة جديدة',senderName:'اسم المرسل',
  senderMobile:'جوال المرسل',senderId:'هوية / إقامة المرسل (اختياري)',recipientId:'هوية / إقامة المستلم (اختياري)',
  pickup:'عنوان الاستلام',recipientName:'اسم المستلم',recipientMobile:'جوال المستلم',
  fromCity:'من مدينة',toCity:'إلى مدينة',destinationBranch:'فرع الوجهة',
  chooseBranch:'اختر فرع الوجهة',shipmentValue:'قيمة الشحنة',cod:'الدفع عند الاستلام',
  senderPays:'يدفع المرسل',collection:'مبلغ التحصيل',pieces:'عدد القطع',createPrint:'إنشاء الشحنة والطباعة',
  creating:'جارٍ إنشاء الشحنة...',created:'تم إنشاء الشحنة',createdTitle:'تم إنشاء الشحنة',
  printSent:'تم إرسال أمر الطباعة.',newAgain:'إنشاء شحنة جديدة',printAgain:'طباعة مرة أخرى',
  sentPrinter:'تم الإرسال إلى طابعة الجهاز',qrError:'تعذر إنشاء',language:'اللغة'
 }
};
const t=k=>TXT[lang]?.[k]||TXT.en[k]||k;
function applyLanguage(){
 document.documentElement.lang=lang;
 document.documentElement.dir=lang==='ar'?'rtl':'ltr';
 document.body.dir=document.documentElement.dir;
}
function languageSelect(id='posLanguage'){
 return '<select id="'+id+'" class="pos-language" aria-label="'+esc(t('language'))+'"><option value="en" '+(lang==='en'?'selected':'')+'>English</option><option value="ar" '+(lang==='ar'?'selected':'')+'>العربية</option></select>';
}
function bindLanguage(id='posLanguage'){
 const el=$('#'+id);if(!el)return;
 el.onchange=()=>{lang=el.value==='ar'?'ar':'en';localStorage.setItem('ghz-pos-lang',lang);applyLanguage();render()};
}
function toast(msg){toastEl.textContent=msg;toastEl.hidden=false;clearTimeout(toast._t);toast._t=setTimeout(()=>toastEl.hidden=true,2600)}
function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function userRole(u){return u?.role||u?.access_role||''}
function canUsePos(u){return !!u&&userRole(u)!=='customer'}
function userBranch(u){return u?.branch_name||u?.branch_code||u?.branch||'Ghazala Branch'}
function defaultCity(){return me?.branch_city||me?.city||branches[0]?.city||'Jeddah'}
function cityOptions(selected=''){const cities=[...new Set(branches.filter(b=>b.is_active!==0).map(b=>b.city).filter(Boolean))];return cities.map(c=>'<option '+(c===selected?'selected':'')+'>'+esc(c)+'</option>').join('')}
function branchOptions(city,selected=''){return '<option value="">'+esc(t('chooseBranch'))+'</option>'+branches.filter(b=>b.city===city&&b.is_active!==0).map(b=>'<option value="'+esc(b.code)+'" '+(b.code===selected?'selected':'')+'>'+esc(b.name||b.code)+'</option>').join('')}
function loginView(){
 applyLanguage();
 app.innerHTML='<section class="screen login"><div class="login-card"><div class="login-language">'+languageSelect('loginLanguage')+'</div><img class="logo" src="/ghazala-logo.png?v=2" alt="Ghazala Transport"><h1>Ghazala POS</h1><p>'+esc(t('dedicated'))+' · '+esc(deviceId)+'</p><form id="loginForm"><label class="field"><span>'+esc(t('username'))+'</span><input name="username" autocomplete="username" required></label><label class="field"><span>'+esc(t('password'))+'</span><input name="password" type="password" autocomplete="current-password" required></label><button class="btn primary">'+esc(t('login'))+'</button><div id="loginStatus" class="status"></div></form></div></section>';
 bindLanguage('loginLanguage');
 $('#loginForm').onsubmit=async e=>{e.preventDefault();const f=e.currentTarget,s=$('#loginStatus');s.textContent='';const b=f.querySelector('button');b.disabled=true;try{const r=await api('/api/login',{method:'POST',body:JSON.stringify({username:f.username.value,password:f.password.value})});if(!canUsePos(r.user))throw new Error(t('denied'));me=r.user;await refresh();render()}catch(err){s.textContent=err.message}finally{b.disabled=false}};
}
async function refresh(){const [auth,br]=await Promise.all([api('/api/me'),api('/api/public/branch-directory')]);me=auth.user;branches=Array.isArray(br)?br:(br.branches||[]);if(me&&canUsePos(me)){try{shipments=await api('/api/shipments')}catch(_){shipments=[]}}}
function shell(){
 applyLanguage();
 app.innerHTML='<header class="top"><img src="/ghazala-logo.png?v=2"><div class="identity"><b>Ghazala POS</b><small>'+esc(userBranch(me))+' · '+esc(deviceId)+'</small></div><div class="top-controls">'+languageSelect()+'<button id="logout" class="btn light logout">'+esc(t('logout'))+'</button></div></header><div class="content"><div class="head"><div><h1>'+esc(t('create'))+'</h1><small>'+esc(t('sub'))+'</small></div></div><section id="panel" class="panel"></section></div>';
 bindLanguage();
 $('#logout').onclick=async()=>{try{await api('/api/logout',{method:'POST',body:'{}'})}catch(_){}me=null;shipments=[];loginView()};
 createPanel();
}
function etaDefault(){const d=new Date(Date.now()+24*3600*1000);return d.toISOString().slice(0,16)}
function createPanel(){
 const origin=defaultCity(),dest=branches.find(b=>b.city&&b.city!==origin)?.city||origin;
 $('#panel').innerHTML='<div class="section-title">'+esc(t('newShipment'))+'</div><form id="shipmentForm"><div class="split"><label class="field"><span>'+esc(t('senderName'))+'</span><input name="sender_name" required></label><label class="field"><span>'+esc(t('senderMobile'))+'</span><input name="sender_phone" type="tel" required></label></div><div class="split"><label class="field"><span>'+esc(t('senderId'))+'</span><input name="sender_id"></label><label class="field"><span>'+esc(t('recipientId'))+'</span><input name="recipient_id"></label></div><label class="field"><span>'+esc(t('pickup'))+'</span><textarea name="sender_address" required></textarea></label><div class="split"><label class="field"><span>'+esc(t('recipientName'))+'</span><input name="recipient" required></label><label class="field"><span>'+esc(t('recipientMobile'))+'</span><input name="phone" type="tel" required></label></div><div class="split"><label class="field"><span>'+esc(t('fromCity'))+'</span><select name="origin" required>'+cityOptions(origin)+'</select></label><label class="field"><span>'+esc(t('toCity'))+'</span><select name="destination" required>'+cityOptions(dest)+'</select></label></div><label class="field"><span>'+esc(t('destinationBranch'))+'</span><select name="recipient_branch">'+branchOptions(dest)+'</select></label><label class="field"><span>'+esc(t('shipmentValue'))+'</span><input name="declared_value" type="number" min="0" step="0.01" value="0"></label><div class="checks"><label class="check"><input type="radio" name="payment_method" value="cod" checked> '+esc(t('cod'))+'</label><label class="check"><input type="radio" name="payment_method" value="sender"> '+esc(t('senderPays'))+'</label></div><label id="codWrap" class="field"><span>'+esc(t('collection'))+'</span><input name="cod" type="number" min="0.01" step="0.01" value="1"></label><label class="field"><span>'+esc(t('pieces'))+'</span><input name="pieces" type="number" min="1" value="1" required></label><input type="hidden" name="eta" value="'+etaDefault()+'"><input type="hidden" name="package_type" value="طرد تجاري سريع"><input type="hidden" name="weight" value="1"><input type="hidden" name="length_cm" value="0"><input type="hidden" name="width_cm" value="0"><input type="hidden" name="height_cm" value="0"><div class="actions single"><button type="submit" class="btn orange">'+esc(t('createPrint'))+'</button></div></form>';
 const f=$('#shipmentForm');
 const syncDest=()=>{f.recipient_branch.innerHTML=branchOptions(f.destination.value);if(f.origin.value===f.destination.value){const other=[...f.destination.options].find(o=>o.value!==f.origin.value);if(other)f.destination.value=other.value;f.recipient_branch.innerHTML=branchOptions(f.destination.value)}};
 f.origin.onchange=syncDest;f.destination.onchange=syncDest;
 f.querySelectorAll('[name=payment_method]').forEach(x=>x.onchange=()=>{const cod=f.payment_method.value==='cod';$('#codWrap').style.display=cod?'grid':'none';f.cod.required=cod;if(!cod)f.cod.value='0'});
 async function saveAndPrint(){if(!f.reportValidity())return;const b=f.querySelector('button[type=submit]');b.disabled=true;b.textContent=t('creating');try{const data=Object.fromEntries(new FormData(f));['declared_value','cod','pieces','weight','length_cm','width_cm','height_cm'].forEach(k=>data[k]=Number(data[k]||0));if(data.payment_method!=='cod')data.cod=0;const created=await api('/api/shipments',{method:'POST',body:JSON.stringify(data)});toast(t('created')+': '+created.awb);await refresh();await printWaybill(created.awb);showSuccess(created.awb)}catch(err){toast(err.message);b.disabled=false;b.textContent=t('createPrint')}}
 f.onsubmit=e=>{e.preventDefault();saveAndPrint()};
}
function showSuccess(awb){
 const panel=$('#panel');if(!panel)return;
 panel.innerHTML='<div class="success-card"><div class="success-icon">✓</div><h2>'+esc(t('createdTitle'))+'</h2><div class="success-awb">'+esc(awb)+'</div><p>'+esc(t('printSent'))+'</p><button id="newShipmentBtn" class="btn primary">'+esc(t('newAgain'))+'</button><button id="reprintBtn" class="btn light">'+esc(t('printAgain'))+'</button></div>';
 $('#newShipmentBtn').onclick=createPanel;
 $('#reprintBtn').onclick=()=>printWaybill(awb);
}
function recentPanel(){
 const rows=[...shipments].sort((a,b)=>String(b.created_at||'').localeCompare(String(a.created_at||''))).slice(0,30);
 $('#panel').innerHTML='<div class="section-title">Recent Shipments / Reprint</div><label class="field"><span>Search AWB / Recipient</span><input id="search" placeholder="GHZ-..."></label><div id="list" class="shipment-list"></div>';
 const draw=()=>{const q=$('#search').value.trim().toLowerCase();const data=rows.filter(s=>!q||[s.awb,s.recipient,s.phone].some(v=>String(v||'').toLowerCase().includes(q)));$('#list').innerHTML=data.length?data.map(s=>'<article class="shipment"><div class="shipment-head"><div><div class="awb">'+esc(s.awb)+'</div><b>'+esc(s.recipient||'')+'</b></div><span class="badge">'+esc(s.status||'Created')+'</span></div><p>'+esc(s.origin||'')+' → '+esc(s.destination||'')+' · '+esc(s.phone||'')+'</p><div class="mini-actions"><button class="btn light" data-view="'+esc(s.awb)+'">View</button><button class="btn orange" data-print="'+esc(s.awb)+'">Print / Reprint</button></div></article>').join(''):'<div class="empty">No shipments found.</div>';document.querySelectorAll('[data-print]').forEach(b=>b.onclick=()=>printWaybill(b.dataset.print));document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>window.open('/#track='+encodeURIComponent(b.dataset.view),'_blank'))};
 $('#search').oninput=draw;draw();
}
async function codeSvg(awb,type){const r=await fetch('/api/shipments/'+encodeURIComponent(awb)+'/'+type,{credentials:'same-origin'});if(!r.ok)throw new Error(t('qrError')+' '+type);return await r.text()}
async function printWaybill(awb){
 try{
   const [doc,qr,bar]=await Promise.all([api('/api/shipments/'+encodeURIComponent(awb)+'/documents'),codeSvg(awb,'qr'),codeSvg(awb,'barcode')]);
   const s=doc.shipment||shipments.find(x=>x.awb===awb)||{awb};
   const qrUrl='data:image/svg+xml;base64,'+btoa(unescape(encodeURIComponent(qr)));
   const barUrl='data:image/svg+xml;base64,'+btoa(unescape(encodeURIComponent(bar)));
   const html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><style>@page{size:58mm auto;margin:0}body{margin:0;width:58mm;font:9px Arial;color:#111}.r{width:58mm;padding:2.5mm;box-sizing:border-box;text-align:center}.logo{width:15mm;height:15mm;object-fit:contain}.awb{font:bold 14px monospace;margin:2mm 0}.qr{width:23mm;height:23mm}.bar{width:51mm;height:12mm;object-fit:contain}.line{border-top:1px dashed #555;margin:2mm 0}.row{display:flex;justify-content:space-between;gap:2mm;text-align:left;margin:1mm 0}.row b{text-align:right}h2{font-size:12px;margin:1mm}.small{font-size:7px}.no-print{margin:3mm} @media print{.no-print{display:none}}</style></head><body><div class="no-print"><button onclick="print()">PRINT</button></div><main class="r"><img class="logo" src="/ghazala-logo.png?v=2"><h2>GHAZALA TRANSPORT</h2><div class="awb">'+esc(awb)+'</div><img class="qr" src="'+qrUrl+'"><br><img class="bar" src="'+barUrl+'"><div class="line"></div><div class="row"><span>Sender</span><b>'+esc(s.sender_name||'')+'</b></div><div class="row"><span>Recipient</span><b>'+esc(s.recipient||'')+'</b></div><div class="row"><span>Mobile</span><b>'+esc(s.phone||'')+'</b></div><div class="row"><span>Route</span><b>'+esc(s.origin||'')+' → '+esc(s.destination||'')+'</b></div><div class="row"><span>Payment</span><b>'+esc(s.payment_status||'')+'</b></div><div class="row"><span>Total</span><b>'+esc(s.total_fee||'0')+' SAR</b></div><div class="line"></div><div class="small">Track shipment by scanning QR code</div></main><script>setTimeout(()=>window.print(),350)<\/script></body></html>';
   const bridge=window.GhazalaPOSPrinter||window.AndroidPrinter||window.Android;
   if(bridge&&typeof bridge.printHtml==='function'){await Promise.resolve(bridge.printHtml(html,58));toast(t('sentPrinter'));return}
   const frame=document.createElement('iframe');frame.className='print-frame';document.body.appendChild(frame);frame.onload=()=>{};frame.srcdoc=html;setTimeout(()=>{try{frame.contentWindow.focus();frame.contentWindow.print()}catch(_){window.open('/api/shipments/'+encodeURIComponent(awb)+'/waybill/pdf','_blank')}setTimeout(()=>frame.remove(),2500)},500);
 }catch(err){toast(err.message)}
}
async function boot(){applyLanguage();try{await refresh();if(me&&canUsePos(me))render();else loginView()}catch(_){loginView()}}
function render(){if(!me||!canUsePos(me))return loginView();shell()}
boot();
})();