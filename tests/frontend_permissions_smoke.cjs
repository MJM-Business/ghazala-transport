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
