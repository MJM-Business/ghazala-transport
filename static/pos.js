(()=>{
const $=s=>document.querySelector(s);
const app=$('#app'),toastEl=$('#toast');
let me=null,shipments=[],branches=[],posView='create';
let lang=localStorage.getItem('ghz-pos-lang')==='ar'?'ar':'en';
const deviceId=localStorage.getItem('ghz-pos-device-id')||('POS-'+Math.random().toString(36).slice(2,8).toUpperCase());
window.onerror=function(message,source,line){
  try{
    var box=document.createElement('div');
    box.style.cssText='position:fixed;left:8px;right:8px;bottom:8px;z-index:9999;background:#7f1d1d;color:#fff;padding:10px;border-radius:8px;font:12px Arial';
    box.textContent='POS JS error: '+String(message||'Unknown error')+' @ '+String(line||'');
    document.body.appendChild(box);
  }catch(_){}
};
localStorage.setItem('ghz-pos-device-id',deviceId);
const api=async(path,options={})=>{
  const requestOptions=Object.assign({},options||{});
  requestOptions.credentials='same-origin';
  requestOptions.headers=Object.assign({'Content-Type':'application/json'},(options&&options.headers)||{});
  const res=await fetch(path,requestOptions);
  let data={};try{data=await res.json()}catch(_){}
  if(!res.ok)throw new Error(data.error||('Request failed ('+res.status+')'));
  return data;
};
function validateShipmentForm(form){
 const required=Array.prototype.slice.call(form.querySelectorAll('[required]'));
 for(var i=0;i<required.length;i++){
   var el=required[i];
   if(el.type==='radio')continue;
   if(String(el.value||'').trim()===''){
     try{el.focus();}catch(_){}
     toast('Please complete all required shipment fields.');
     return false;
   }
 }
 var checked=form.querySelector('[name="payment_method"]:checked');
 if(!checked){
   toast('Please select a payment method.');
   return false;
 }
 return true;
}
function formObject(form){
 const data={};
 const els=Array.prototype.slice.call(form.elements||[]);
 els.forEach(function(el){
   if(!el.name||el.disabled)return;
   if((el.type==='radio'||el.type==='checkbox')&&!el.checked)return;
   data[el.name]=el.value;
 });
 return data;
}
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
  sentPrinter:'Sent to POS printer',qrError:'Could not generate',language:'Language',settings:'Settings',records:'Records',profile:'Profile & Account',name:'Name',account:'Account',branch:'Relevant Branch',save:'Save Changes',currentPassword:'Current Password',newPassword:'New Password',passwordHint:'Leave password fields empty if you do not want to change it.',recordsTitle:'Shipment Records',noRecords:'No POS shipments yet.',search:'Search AWB / recipient',backCreate:'Create Shipment',saved:'Settings saved',dispatch:'Dispatch Shipment',dispatching:'Dispatching...',dispatched:'Dispatched',dispatchConfirm:'Dispatch this shipment to the destination branch?',dispatchDone:'Shipment dispatched successfully'
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
  sentPrinter:'تم الإرسال إلى طابعة الجهاز',qrError:'تعذر إنشاء',language:'اللغة',settings:'الإعدادات',records:'السجلات',profile:'الملف والحساب',name:'الاسم',account:'الحساب',branch:'الفرع المرتبط',save:'حفظ التغييرات',currentPassword:'كلمة المرور الحالية',newPassword:'كلمة المرور الجديدة',passwordHint:'اترك حقول كلمة المرور فارغة إذا لم ترغب في تغييرها.',recordsTitle:'سجلات الشحنات',noRecords:'لا توجد شحنات POS حتى الآن.',search:'بحث برقم AWB أو المستلم',backCreate:'إنشاء شحنة',saved:'تم حفظ الإعدادات',dispatch:'ترحيل الشحنة',dispatching:'جارٍ الترحيل...',dispatched:'تم الترحيل',dispatchConfirm:'هل تريد ترحيل هذه الشحنة إلى فرع الوجهة؟',dispatchDone:'تم ترحيل الشحنة بنجاح'
 }
};
const t=k=>(TXT[lang]&&TXT[lang][k])||TXT.en[k]||k;
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
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function userRole(u){return (u&&u.role)||(u&&u.access_role)||''}
function canUsePos(u){return !!u&&String((u&&u.username)||'').trim().toLowerCase().indexOf('pos.')===0}
function primaryBranch(u){const list=Array.isArray(u&&u.branches)?u.branches:[];return list.find(b=>Number(b.id)===Number(u&&u.primary_branch_id))||list[0]||null}
function userBranch(u){const b=primaryBranch(u);return b?localBranchName(b):'Ghazala Branch'}
function defaultCity(){const b=primaryBranch(me);return (b&&b.city)||(branches[0]&&branches[0].city)||'Jeddah'}
function localCity(value){
 const v=String(value||'').trim();
 const map={
  'جدة':{en:'Jeddah',ar:'جدة'},'Jeddah':{en:'Jeddah',ar:'جدة'},
  'جازان':{en:'Jazan',ar:'جازان'},'Jazan':{en:'Jazan',ar:'جازان'},
  'جيزان':{en:'Jazan',ar:'جازان'}
 };
 return (map[v]&&map[v][lang])||v;
}
function localBranchName(branch){
 if(!branch)return '';
 const code=String(branch.code||'').toUpperCase();
 if(code==='JED-MAIN')return lang==='ar'?'المقر الرئيسي جدة':'Jeddah Main Branch';
 if(code==='JAZ-MAIN')return lang==='ar'?'مركز جازان':'Jazan Branch';
 return branch.name||branch.code||'';
}
function cityOptions(selected=''){const cities=Array.from(new Set(branches.filter(b=>b.is_active!==0).map(b=>b.city).filter(Boolean)));return cities.map(c=>'<option value="'+esc(c)+'" '+(c===selected?'selected':'')+'>'+esc(localCity(c))+'</option>').join('')}
function branchOptions(city,selected=''){return '<option value="">'+esc(t('chooseBranch'))+'</option>'+branches.filter(b=>b.city===city&&b.is_active!==0).map(b=>'<option value="'+esc(b.code)+'" '+(b.code===selected?'selected':'')+'>'+esc(localBranchName(b))+'</option>').join('')}
function loginView(){
 applyLanguage();
 app.innerHTML='<section class="screen login"><div class="login-card"><div class="login-language">'+languageSelect('loginLanguage')+'</div><img class="logo" src="/ghazala-logo.png?v=2" alt="Ghazala Transport"><h1>Ghazala POS</h1><p>'+esc(t('dedicated'))+' · '+esc(deviceId)+'</p><form id="loginForm"><label class="field"><span>'+esc(t('username'))+'</span><input name="username" autocomplete="username" required></label><label class="field"><span>'+esc(t('password'))+'</span><input name="password" type="password" autocomplete="current-password" required></label><button class="btn primary">'+esc(t('login'))+'</button><div id="loginStatus" class="status"></div></form></div></section>';
 bindLanguage('loginLanguage');
 $('#loginForm').onsubmit=async e=>{e.preventDefault();const f=e.currentTarget,s=$('#loginStatus');s.textContent='';const b=f.querySelector('button');b.disabled=true;try{const r=await api('/api/login',{method:'POST',body:JSON.stringify({username:f.username.value,password:f.password.value})});if(!canUsePos(r.user))throw new Error(t('denied'));me=r.user;await refresh();render()}catch(err){s.textContent=err.message}finally{b.disabled=false}};
}
async function refresh(){const [auth,br]=await Promise.all([api('/api/me'),api('/api/public/branch-directory')]);me=auth.user;branches=Array.isArray(br)?br:(br.branches||[]);if(me&&canUsePos(me)){try{shipments=await api('/api/shipments')}catch(_){shipments=[]}}}
function shell(){
 applyLanguage();
 app.innerHTML='<header class="top"><img src="/ghazala-logo.png?v=2"><div class="identity"><b>Ghazala POS</b><small>'+esc(userBranch(me))+' · '+esc(deviceId)+'</small></div><div class="top-controls">'+languageSelect()+'<button id="logout" class="btn light logout">'+esc(t('logout'))+'</button></div></header><div class="pos-nav"><button class="nav-btn '+(posView==='create'?'active':'')+'" data-pos-view="create">'+esc(t('backCreate'))+'</button><button class="nav-btn '+(posView==='records'?'active':'')+'" data-pos-view="records">'+esc(t('records'))+'</button><button class="nav-btn '+(posView==='settings'?'active':'')+'" data-pos-view="settings">'+esc(t('settings'))+'</button></div><div class="content"><section id="panel" class="panel"></section></div>';
 bindLanguage();
 $('#logout').onclick=async()=>{try{await api('/api/logout',{method:'POST',body:'{}'})}catch(_){}me=null;shipments=[];loginView()};
 document.querySelectorAll('[data-pos-view]').forEach(b=>b.onclick=()=>{posView=b.dataset.posView;render()});
 if(posView==='records')recordsPanel();
 else if(posView==='settings')settingsPanel();
 else createPanel();
}
function etaDefault(){const d=new Date(Date.now()+24*3600*1000);return d.toISOString().slice(0,16)}
function createPanel(){
 const origin=defaultCity(),destBranch=branches.find(b=>b.city&&b.city!==origin),dest=(destBranch&&destBranch.city)||origin;
 $('#panel').innerHTML='<div class="section-title">'+esc(t('newShipment'))+'</div><form id="shipmentForm"><div class="split"><label class="field"><span>'+esc(t('senderName'))+'</span><input name="sender_name" required></label><label class="field"><span>'+esc(t('senderMobile'))+'</span><input name="sender_phone" type="tel" required></label></div><div class="split"><label class="field"><span>'+esc(t('senderId'))+'</span><input name="sender_id"></label><label class="field"><span>'+esc(t('recipientId'))+'</span><input name="recipient_id"></label></div><label class="field"><span>'+esc(t('pickup'))+'</span><textarea name="sender_address" required></textarea></label><div class="split"><label class="field"><span>'+esc(t('recipientName'))+'</span><input name="recipient" required></label><label class="field"><span>'+esc(t('recipientMobile'))+'</span><input name="phone" type="tel" required></label></div><div class="split"><label class="field"><span>'+esc(t('fromCity'))+'</span><input value="'+esc(localCity(origin))+'" readonly><input type="hidden" name="origin" value="'+esc(origin)+'"></label><label class="field"><span>'+esc(t('toCity'))+'</span><select name="destination" required>'+cityOptions(dest)+'</select></label></div><label class="field"><span>'+esc(t('destinationBranch'))+'</span><select name="recipient_branch">'+branchOptions(dest)+'</select></label><label class="field"><span>'+esc(t('shipmentValue'))+'</span><input name="declared_value" type="number" min="0" step="0.01" value="0"></label><div class="checks"><label class="check"><input type="radio" name="payment_method" value="cod" checked> '+esc(t('cod'))+'</label><label class="check"><input type="radio" name="payment_method" value="sender"> '+esc(t('senderPays'))+'</label></div><label id="codWrap" class="field"><span>'+esc(t('collection'))+'</span><input name="cod" type="number" min="0.01" step="0.01" value="1"></label><label class="field"><span>'+esc(t('pieces'))+'</span><input name="pieces" type="number" min="1" value="1" required></label><input type="hidden" name="eta" value="'+etaDefault()+'"><input type="hidden" name="package_type" value="طرد تجاري سريع"><input type="hidden" name="weight" value="1"><input type="hidden" name="length_cm" value="0"><input type="hidden" name="width_cm" value="0"><input type="hidden" name="height_cm" value="0"><div id="createStatus" class="create-status" aria-live="polite"></div><div class="actions single"><button type="submit" class="btn orange">'+esc(t('createPrint'))+'</button></div></form>';
 const f=$('#shipmentForm');
 const syncDest=()=>{f.recipient_branch.innerHTML=branchOptions(f.destination.value);if(f.elements.origin.value===f.destination.value){const other=Array.from(f.destination.options).find(o=>o.value!==f.elements.origin.value);if(other)f.destination.value=other.value;f.recipient_branch.innerHTML=branchOptions(f.destination.value)}};
 f.destination.onchange=syncDest;
 f.querySelectorAll('[name=payment_method]').forEach(x=>x.onchange=()=>{const cod=f.payment_method.value==='cod';$('#codWrap').style.display=cod?'grid':'none';f.cod.required=cod;if(!cod)f.cod.value='0'});
 async function saveAndPrint(){
 if(!validateShipmentForm(f))return;
 const b=f.querySelector('button[type=submit]');
 const statusBox=$('#createStatus');
 if(statusBox){statusBox.className='create-status';statusBox.textContent='Sending shipment to server...'}
 b.disabled=true;b.textContent=t('creating');
 try{
   const data=formObject(f);
   ['declared_value','cod','pieces','weight','length_cm','width_cm','height_cm'].forEach(k=>data[k]=Number(data[k]||0));
   if(data.payment_method!=='cod')data.cod=0;
   data.pos_device_id=deviceId;
   const created=await api('/api/shipments',{method:'POST',body:JSON.stringify(data)});
   if(statusBox){statusBox.className='create-status ok';statusBox.textContent='Shipment saved: '+created.awb}
   toast(t('created')+': '+created.awb);
   await refresh();
   showSuccess(created.awb);
   setTimeout(function(){printWaybill(created.awb)},250);
 }catch(err){
   const message='Create failed: '+(err&&err.message?err.message:String(err));
   if(statusBox){statusBox.className='create-status error';statusBox.textContent=message}
   toast(message);
   b.disabled=false;b.textContent=t('createPrint');
 }
}
 f.onsubmit=e=>{e.preventDefault();saveAndPrint()};
}
function showSuccess(awb){
 const panel=$('#panel');if(!panel)return;
 panel.innerHTML='<div class="success-card"><div class="success-icon">✓</div><h2>'+esc(t('createdTitle'))+'</h2><div class="success-awb">'+esc(awb)+'</div><p>'+esc(t('printSent'))+'</p><button id="newShipmentBtn" class="btn primary">'+esc(t('newAgain'))+'</button><button id="reprintBtn" class="btn light">'+esc(t('printAgain'))+'</button></div>';
 $('#newShipmentBtn').onclick=()=>{posView='create';render()};
 $('#reprintBtn').onclick=()=>printWaybill(awb);
}
async function recordsPanel(){
 const panel=$('#panel');if(!panel)return;
 panel.innerHTML='<div class="section-title">'+esc(t('recordsTitle'))+'</div><label class="field"><span>'+esc(t('search'))+'</span><input id="recordSearch" placeholder="GHZ-..."></label><div id="recordList" class="shipment-list"><div class="empty">...</div></div>';
 try{
   const rows=await api('/api/pos/records');
   const draw=()=>{const searchEl=$('#recordSearch');const q=String((searchEl&&searchEl.value)||'').trim().toLowerCase();const data=rows.filter(s=>!q||[s.awb,s.recipient,s.phone].some(v=>String(v||'').toLowerCase().includes(q)));$('#recordList').innerHTML=data.length?data.map(s=>{const dispatched=!!s.dispatched_at||String(s.status||'').includes('الترحيل')||String(s.status||'').toLowerCase().includes('dispatch');return '<article class="shipment"><div class="shipment-head"><div><div class="awb">'+esc(s.awb)+'</div><b>'+esc(s.recipient||'')+'</b></div><span class="badge">'+esc(s.status||'')+'</span></div><p>'+esc(localCity(s.origin||''))+' → '+esc(localCity(s.destination||''))+' · '+esc(s.phone||'')+'</p><div class="record-meta"><span>'+esc(s.pos_created_at||s.created_at||'')+'</span><span>Prints: '+esc(s.print_count||0)+'</span><span>'+esc(s.payment_status||'')+'</span></div><div class="mini-actions"><button class="btn light" data-record-print="'+esc(s.awb)+'">'+esc(t('printAgain'))+'</button>'+(dispatched?'<button class="btn dispatched-btn" disabled>'+esc(t('dispatched'))+'</button>':'<button class="btn orange" data-dispatch="'+esc(s.awb)+'">'+esc(t('dispatch'))+'</button>')+'</div></article>'}).join(''):'<div class="empty">'+esc(t('noRecords'))+'</div>';document.querySelectorAll('[data-record-print]').forEach(b=>b.onclick=()=>printWaybill(b.dataset.recordPrint));document.querySelectorAll('[data-dispatch]').forEach(b=>b.onclick=()=>dispatchShipment(b.dataset.dispatch,b))};
   $('#recordSearch').oninput=draw;draw();
 }catch(err){panel.innerHTML='<div class="empty">'+esc(err.message)+'</div>'}
}
async function dispatchShipment(awb,button){
 if(!confirm(t('dispatchConfirm')))return;
 button.disabled=true;button.textContent=t('dispatching');
 try{
   const res=await api('/api/pos/records/'+encodeURIComponent(awb)+'/dispatch',{method:'POST',body:'{}'});
   toast(t('dispatchDone')+' · '+res.awb);
   await refresh();
   await recordsPanel();
 }catch(err){
   toast(err.message);
   if(button&&button.isConnected){button.disabled=false;button.textContent=t('dispatch')}
 }
}
async function settingsPanel(){
 const panel=$('#panel');if(!panel)return;
 panel.innerHTML='<div class="empty">...</div>';
 try{
   const data=await api('/api/pos/profile');me=data.user||me;const branch=data.branch||primaryBranch(me)||{};
   panel.innerHTML='<div class="section-title">'+esc(t('profile'))+'</div><div class="settings-note"><b>Printer:</b> <span id="printerStatus">Checking...</span><button id="printerTestBtn" type="button" class="btn orange" style="margin-top:8px">Printer Test</button></div><form id="settingsForm"><label class="field"><span>'+esc(t('name'))+'</span><input name="display_name" value="'+esc(me.display_name||'')+'" required></label><label class="field"><span>'+esc(t('account'))+'</span><input value="'+esc(me.username||'')+'" readonly></label><label class="field"><span>'+esc(t('branch'))+'</span><input value="'+esc(localBranchName(branch)+(branch.city?' · '+localCity(branch.city):''))+'" readonly></label><div class="settings-note">'+esc(t('passwordHint'))+'</div><label class="field"><span>'+esc(t('currentPassword'))+'</span><input name="current_password" type="password" autocomplete="current-password"></label><label class="field"><span>'+esc(t('newPassword'))+'</span><input name="new_password" type="password" autocomplete="new-password"></label><button class="btn primary" type="submit">'+esc(t('save'))+'</button></form>';
   const printerBridge=window.GhazalaPOSPrinter||window.AndroidPrinter||window.Android;
   const printerStatusEl=$('#printerStatus');
   if(printerStatusEl){
     try{
       printerStatusEl.textContent=printerBridge&&typeof printerBridge.getPrinterStatus==='function'
         ? String(printerBridge.getPrinterStatus())
         : 'BRIDGE_NOT_AVAILABLE';
     }catch(err){printerStatusEl.textContent='ERROR: '+err.message}
   }
   const printerTestBtn=$('#printerTestBtn');
   if(printerTestBtn){
     printerTestBtn.onclick=()=>{try{
       if(!printerBridge||typeof printerBridge.testPrinter!=='function'){toast('Printer bridge not available');return}
       const result=String(printerBridge.testPrinter());
       if(printerStatusEl)printerStatusEl.textContent=result;
       toast(result==='OK'?'Printer test sent successfully':result);
     }catch(err){toast('Printer test failed: '+err.message)}};
   }
   $('#settingsForm').onsubmit=async e=>{e.preventDefault();const f=e.currentTarget,b=f.querySelector('button');b.disabled=true;try{const payload=formObject(f);const res=await api('/api/pos/profile',{method:'POST',body:JSON.stringify(payload)});me=res.user||me;toast(t('saved'));render()}catch(err){toast(err.message)}finally{if(b.isConnected)b.disabled=false}};
 }catch(err){panel.innerHTML='<div class="empty">'+esc(err.message)+'</div>'}
}
function recentPanel(){
 const rows=Array.from(shipments).sort((a,b)=>String(b.created_at||'').localeCompare(String(a.created_at||''))).slice(0,30);
 $('#panel').innerHTML='<div class="section-title">Recent Shipments / Reprint</div><label class="field"><span>Search AWB / Recipient</span><input id="search" placeholder="GHZ-..."></label><div id="list" class="shipment-list"></div>';
 const draw=()=>{const q=$('#search').value.trim().toLowerCase();const data=rows.filter(s=>!q||[s.awb,s.recipient,s.phone].some(v=>String(v||'').toLowerCase().includes(q)));$('#list').innerHTML=data.length?data.map(s=>'<article class="shipment"><div class="shipment-head"><div><div class="awb">'+esc(s.awb)+'</div><b>'+esc(s.recipient||'')+'</b></div><span class="badge">'+esc(s.status||'Created')+'</span></div><p>'+esc(s.origin||'')+' → '+esc(s.destination||'')+' · '+esc(s.phone||'')+'</p><div class="mini-actions"><button class="btn light" data-view="'+esc(s.awb)+'">View</button><button class="btn orange" data-print="'+esc(s.awb)+'">Print / Reprint</button></div></article>').join(''):'<div class="empty">No shipments found.</div>';document.querySelectorAll('[data-print]').forEach(b=>b.onclick=()=>printWaybill(b.dataset.print));document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>window.open('/#track='+encodeURIComponent(b.dataset.view),'_blank'))};
 $('#search').oninput=draw;draw();
}
async function codeSvg(awb,type){const r=await fetch('/api/shipments/'+encodeURIComponent(awb)+'/'+type,{credentials:'same-origin'});if(!r.ok)throw new Error(t('qrError')+' '+type);return await r.text()}
async function printWaybill(awb){
 try{
   try{await api('/api/pos/records/'+encodeURIComponent(awb)+'/printed',{method:'POST',body:'{}'})}catch(_){}
   const [doc,qr,bar]=await Promise.all([api('/api/shipments/'+encodeURIComponent(awb)+'/documents'),codeSvg(awb,'qr'),codeSvg(awb,'barcode')]);
   const s=doc.shipment||shipments.find(x=>x.awb===awb)||{awb};
   const qrUrl='data:image/svg+xml;base64,'+btoa(unescape(encodeURIComponent(qr)));
   const barUrl='data:image/svg+xml;base64,'+btoa(unescape(encodeURIComponent(bar)));
   const html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><style>@page{size:52mm 74mm;margin:0}html,body{margin:0;width:52mm;height:74mm;overflow:hidden}body{font:8px Arial;color:#111}.r{width:52mm;height:74mm;padding:2mm;box-sizing:border-box;text-align:center;overflow:hidden}.logo{width:10mm;height:10mm;object-fit:contain}.awb{font:bold 12px monospace;margin:1mm 0}.qr{width:18mm;height:18mm}.bar{width:46mm;height:9mm;object-fit:contain}.line{border-top:1px dashed #555;margin:1mm 0}.row{display:flex;justify-content:space-between;gap:1mm;text-align:left;margin:.6mm 0}.row b{text-align:right}h2{font-size:10px;margin:.5mm}.small{font-size:6px}.no-print{margin:3mm} @media print{.no-print{display:none}}</style></head><body><div class="no-print"><button onclick="print()">PRINT</button></div><main class="r"><img class="logo" src="/ghazala-logo.png?v=2"><h2>GHAZALA TRANSPORT</h2><div class="awb">'+esc(awb)+'</div><img class="qr" src="'+qrUrl+'"><br><img class="bar" src="'+barUrl+'"><div class="line"></div><div class="row"><span>Sender</span><b>'+esc(s.sender_name||'')+'</b></div><div class="row"><span>Recipient</span><b>'+esc(s.recipient||'')+'</b></div><div class="row"><span>Mobile</span><b>'+esc(s.phone||'')+'</b></div><div class="row"><span>Route</span><b>'+esc(s.origin||'')+' → '+esc(s.destination||'')+'</b></div><div class="row"><span>Payment</span><b>'+esc(s.payment_status||'')+'</b></div><div class="row"><span>Total</span><b>'+esc(s.total_fee||'0')+' SAR</b></div><div class="line"></div><div class="small">Track shipment by scanning QR code</div></main><script>setTimeout(()=>window.print(),350)<\/script></body></html>';
   const bridge=window.GhazalaPOSPrinter||window.AndroidPrinter||window.Android;
   if(bridge&&typeof bridge.printReceipt==='function'){
     const receiptData={
       awb:awb,
       sender:s.sender_name||'',
       recipient:s.recipient||'',
       mobile:s.phone||'',
       route:(s.origin||'')+' -> '+(s.destination||''),
       payment:s.payment_status||'',
       total:String(s.total_fee||'0')
     };
     const nativeResult=String(await Promise.resolve(bridge.printReceipt(JSON.stringify(receiptData))));
     if(nativeResult!=='OK')throw new Error('SUNMI '+nativeResult);
     toast(t('sentPrinter'));
     return;
   }
   if(bridge&&typeof bridge.printHtml==='function'){await Promise.resolve(bridge.printHtml(html,58));toast(t('sentPrinter'));return}
   const frame=document.createElement('iframe');frame.className='print-frame';document.body.appendChild(frame);frame.onload=()=>{};frame.srcdoc=html;setTimeout(()=>{try{frame.contentWindow.focus();frame.contentWindow.print()}catch(_){window.open('/api/shipments/'+encodeURIComponent(awb)+'/waybill/pdf','_blank')}setTimeout(()=>frame.remove(),2500)},500);
 }catch(err){toast(err.message)}
}
async function boot(){applyLanguage();try{await refresh();if(me&&canUsePos(me))render();else loginView()}catch(_){loginView()}}
function render(){if(!me||!canUsePos(me))return loginView();shell()}
boot();
})();