'use strict';
/* Offline Phase 4 frontend checks: no server, network, camera or database access. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const project=process.argv[2]||path.join(__dirname,'..');
const source=fs.readFileSync(path.join(project,'static/ops.js'),'utf8');
const appSource=fs.readFileSync(path.join(project,'static/app.js'),'utf8');
function section(start,end){const first=source.indexOf(start),last=source.indexOf(end,first);assert.ok(first>=0&&last>first);return source.slice(first,last)}
const helpers=appSource.slice(appSource.indexOf('const accessRoleLabels='),appSource.indexOf('function applyLanguage('));
const state=source.match(/^\s*const state=\{[^\r\n]+\};/m)[0];
const functions=section('  function transferBranches(', '  function routeCard(');
const fixtures=[
 {id:1,code:'R-IN',origin:'جدة',destination:'جازان',status:'وصلت',driver_name:'Driver',vehicle_plate:'123',started_at:'2026-10-06',arrived_at:'2026-10-07',shipments:[{awb:'GHZ-IN',transfer_status:'awaiting_receipt',origin_branch_id:1,receiving_branch_id:2,received_by:null,received_by_name:null,status:'قيد النقل'}]},
 {id:2,code:'R-OUT',origin:'جازان',destination:'جدة',status:'مجدولة',shipments:[{awb:'GHZ-OUT',transfer_status:'planned',origin_branch_id:2,receiving_branch_id:1,received_by:null,received_by_name:null,status:'تم إنشاء الشحنة'}]},
 {id:3,code:'R-SAME-CITY',origin:'جدة',destination:'جازان',status:'وصلت',shipments:[{awb:'GHZ-OTHER',transfer_status:'awaiting_receipt',origin_branch_id:2,receiving_branch_id:3,received_by:null,received_by_name:null,status:'قيد النقل'}]}
];
const employee=(extra={})=>({id:7,role:'employee',access_role:'office_employee',permissions:['routes.read','shipments.read','shipments.status','routes.manage'],branch_ids:[2],branches:[{id:2,name:'My receiving office',city:'جازان'}],global_scope:false,...extra});
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no});return{promise,resolve,reject}}
function fixture(account=employee()){
 const calls=[],toasts=[],nodes={},buttons={};let apiHandler=async()=>[],refresh=0,loads=0,dispatches=0,closed=0;
 const modal={innerHTML:'',querySelector:q=>nodes[q]||null,querySelectorAll:q=>buttons[q]||[]};
 const history={innerHTML:'',textContent:'',isConnected:true};nodes['#transferHistory']=history;
 const input={value:'',focus(){}},submit={disabled:false,isConnected:true};
 const form={isConnected:true,elements:{awb:input},querySelector:()=>submit,reset(){input.value=''},requestSubmit(){return form.onsubmit({preventDefault(){}})}};
 nodes['#transferReceiveForm']=form;nodes['#transferReceiveResult']={textContent:''};nodes['#transferReceiveCamera']={};
 nodes['#transferReceiveVideo']={srcObject:null,hidden:true,isConnected:true,play:async()=>{}};
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const context={user:account,window:{},navigator:{},page:'dispatch',document:modal,
  $:(q,root=modal)=>q==='#modalRoot'?modal:root.querySelector(q),$$:(q,root=modal)=>root.querySelectorAll(q),
  tr:value=>value,phrase:value=>value,safe:esc,toast:value=>toasts.push(value),
  wireModal(){},localizeNow(){},closeModal(){closed++;modal.innerHTML='';form.isConnected=false;history.isConnected=false},render(){},
  setTimeout,clearTimeout,
  api:async(url,options={})=>{calls.push({url,...options});return apiHandler(url,options)},
  refreshOps:async()=>{refresh++},load:async()=>{loads++},routeStatus:async(id,status)=>{dispatches++;context.test.state.routes.find(r=>r.id===id).status=status}
 };
 vm.createContext(context);
 vm.runInContext(helpers+'\n'+state+'\n'+section('  function opsOwnerKey(', '  function baseFeeQuote(')+'\n'+functions+'\nglobalThis.test={state,opsOwnerKey,syncOpsOwner,transferRows,transferPanel,transferCustody,transferButtons,canReceiveTransfer,normalizeTransferAwb,openTransferDetail,confirmTransferReceipt,promptTransferReceiveScan,startTransferReceiveCamera,stopTransferCamera,bindTransferControls,routeTransferParcel};',context);
 // Use an isolated refresh to observe transfer actions without loading unrelated endpoints.
 vm.runInContext('refreshOps=async()=>globalThis.onRefresh();',context);context.onRefresh=()=>{refresh++};
 const t=context.test;t.syncOpsOwner();t.state.routes=structuredClone(fixtures);t.state.branches=account?.branches||[];
 return {context,t,calls,toasts,modal,history,form,input,submit,nodes,buttons,setApi(fn){apiHandler=fn},get refresh(){return refresh},get loads(){return loads},get dispatches(){return dispatches},get closed(){return closed}};
}
const checks=[];function test(name,fn){checks.push({name,fn})}

test('incoming/outgoing lists use assigned office IDs, not city names',()=>{
 const f=fixture();assert.deepEqual(Array.from(f.t.transferRows('incoming'),e=>e.shipment.awb),['GHZ-IN']);
 assert.deepEqual(Array.from(f.t.transferRows('outgoing'),e=>e.shipment.awb),['GHZ-OUT','GHZ-OTHER']);
 const html=f.t.transferPanel();assert.match(html,/التحويلات الواردة/);assert.match(html,/التحويلات الصادرة/);assert.match(html,/GHZ-IN/);assert.doesNotMatch(html,/GHZ-OTHER/);
 f.t.state.transferView='outgoing';assert.match(f.t.transferPanel(),/GHZ-OUT/);assert.match(f.t.transferPanel(),/data-transfer-dispatch/);
});
test('both assigned offices classify the same transfer as incoming and outgoing using exact origin IDs',()=>{
 const admin=fixture(employee({access_role:'system_admin',global_scope:true,branch_ids:[]}));assert.equal(admin.t.transferRows('incoming').length,3);assert.equal(admin.t.transferRows('outgoing').length,3);
 const multi=fixture(employee({branch_ids:[1,2]}));assert.equal(multi.t.transferRows('incoming').length,2);assert.equal(multi.t.transferRows('outgoing').length,3);
 assert.ok(multi.t.transferRows('incoming').some(e=>e.route.id===1));assert.ok(multi.t.transferRows('outgoing').some(e=>e.route.id===1));
 // Current route scope must not replace the recorded transfer origin.
 multi.t.state.routes[0].origin_branch_id=99;assert.ok(multi.t.transferRows('outgoing').some(e=>e.route.id===1));
 multi.t.state.routes[0].shipments[0].origin_branch_id=99;assert.equal(multi.t.transferRows('outgoing').some(e=>e.route.id===1),false);
 delete multi.t.state.routes[2].shipments[0].origin_branch_id;assert.equal(multi.t.transferRows('outgoing').some(e=>e.route.id===3),false);
});
test('receipt visibility requires office role, exact receiving office and status permission',()=>{
 for(const role of ['courier','accountant','customer']){const f=fixture(employee({access_role:role})),r=f.t.state.routes[0];assert.equal(f.t.canReceiveTransfer(r,r.shipments[0]),false);assert.doesNotMatch(f.t.routeTransferParcel(r,r.shipments[0]),/data-route-receive/)}
 const denied=fixture(employee({permissions:['routes.read']})),r=denied.t.state.routes[0];assert.equal(denied.t.canReceiveTransfer(r,r.shipments[0]),false);
 const wrong=fixture(employee({branch_ids:[3]})),wr=wrong.t.state.routes[0];assert.equal(wrong.t.canReceiveTransfer(wr,wr.shipments[0]),false);
 assert.equal(fixture(null).t.transferPanel(),'');
});
test('arrival retains transport custody and receipt requires a separate per-AWB action',()=>{
 const f=fixture(),r=f.t.state.routes[0],s=r.shipments[0];assert.match(f.t.transferCustody(r,s),/عهدة النقل/);assert.doesNotMatch(f.t.transferCustody(r,s),/تم تسليم العهدة/);
 assert.equal(f.calls.length,0);r.status='في الطريق';assert.equal(f.t.canReceiveTransfer(r,s),false);r.status='وصلت';assert.equal(f.t.canReceiveTransfer(r,s),true);
 s.transfer_status='received';s.received_at='2026-10-07';assert.equal(f.t.canReceiveTransfer(r,s),false);assert.match(f.t.transferCustody(r,s),/My receiving office/);
});
test('dispatch control calls the existing route action and is hidden without manage permission',async()=>{
 const f=fixture(),button={dataset:{transferDispatch:'2'},disabled:false,isConnected:true};f.buttons['[data-transfer-dispatch]']=[button];f.t.bindTransferControls(f.modal);await button.onclick();assert.equal(f.dispatches,1);assert.equal(f.t.state.routes[1].status,'في الطريق');assert.equal(f.calls.length,0);
 const denied=fixture(employee({permissions:['routes.read']})),r=denied.t.state.routes[1];assert.doesNotMatch(denied.t.transferButtons(r,r.shipments[0]),/data-transfer-dispatch/);
 denied.buttons['[data-transfer-dispatch]']=[{dataset:{transferDispatch:'2'}}];denied.t.bindTransferControls(denied.modal);await denied.buttons['[data-transfer-dispatch]'][0].onclick();assert.equal(denied.dispatches,0);
});
test('receipt posts only to receive endpoint and suppresses concurrent or repeated submissions',async()=>{
 const f=fixture(),p=deferred();f.setApi(()=>p.promise);const first=f.t.confirmTransferReceipt(1,'ghz-in');
 assert.equal(await f.t.confirmTransferReceipt(1,'GHZ-IN'),false);assert.equal(f.calls.length,1);assert.equal(f.calls[0].url,'/api/routes/1/receive');assert.equal(f.calls[0].method,'POST');assert.deepEqual(JSON.parse(f.calls[0].body),{awb:'GHZ-IN'});
 p.resolve({received_by:7,received_by_name:'Authorized receiver',received_at:'receipt-at'});assert.equal(await first,true);assert.equal(f.refresh,1);assert.equal(f.loads,1);assert.equal(f.t.state.routes[0].shipments[0].transfer_status,'received');assert.equal(f.t.state.routes[0].shipments[0].received_by,7);assert.equal(f.t.state.routes[0].shipments[0].received_by_name,'Authorized receiver');assert.equal(f.t.state.routes[0].shipments[0].received_at,'receipt-at');assert.equal(await f.t.confirmTransferReceipt(1,'GHZ-IN'),false);assert.equal(f.calls.length,1);
});
test('AWB/QR receive form accepts the scoped arrived parcel and rejects unrelated AWBs',async()=>{
 const f=fixture();f.t.promptTransferReceiveScan();assert.match(f.modal.innerHTML,/المسح يؤكد استلام بوليصة واحدة/);f.input.value='GHZ-OTHER';await f.form.requestSubmit();assert.equal(f.calls.length,0);
 f.input.value='GHZ-UNKNOWN';await f.form.requestSubmit();assert.equal(f.calls.length,0);
 f.input.value='https://local/#track=ghz-in';await f.form.requestSubmit();assert.equal(f.calls[0].url,'/api/routes/1/receive');assert.equal(f.input.value,'');assert.match(f.nodes['#transferReceiveResult'].textContent,/GHZ-IN/);
 assert.equal(f.t.normalizeTransferAwb('invalid'),'');assert.equal(f.calls.some(c=>c.url.endsWith('/scan')),false);
});
test('failed receipt leaves custody pending and offers retry without false success',async()=>{
 const f=fixture();f.setApi(async()=>{throw Error('Receipt refused')});assert.equal(await f.t.confirmTransferReceipt(1,'GHZ-IN'),false);assert.equal(f.t.state.routes[0].shipments[0].transfer_status,'awaiting_receipt');assert.equal(f.refresh,0);assert.match(f.toasts.at(-1),/Receipt refused/);assert.equal(f.t.state.transferPending.size,0);
});
test('transfer detail displays separate arrival/receipt milestones and escaped shipment history',async()=>{
 const f=fixture();f.setApi(async()=>[{awb:'GHZ-IN-OTHER',events:[{stage:'Wrong parcel'}]},{awb:'GHZ-IN',events:[{stage:'<script>alert(1)</script>',status:'قيد النقل',location:'Branch',created_at:'2026-10-07'}]}]);await f.t.openTransferDetail(1,'GHZ-IN');
 assert.equal(f.calls[0].url,'/api/shipments?q=GHZ-IN');assert.match(f.modal.innerHTML,/وصول المركبة لا يؤكد استلام الشحنة/);assert.match(f.modal.innerHTML,/2026-10-06/);assert.match(f.modal.innerHTML,/عهدة النقل/);assert.match(f.history.innerHTML,/&lt;script&gt;/);assert.doesNotMatch(f.history.innerHTML,/<script>|Wrong parcel/);
 f.t.state.routes[0].shipments[0].transfer_status='received';f.t.state.routes[0].shipments[0].received_at='receipt-timestamp';f.t.state.routes[0].shipments[0].received_by=7;f.t.state.routes[0].shipments[0].received_by_name='<img src=x onerror=alert(1)>';await f.t.openTransferDetail(1,'GHZ-IN');assert.match(f.modal.innerHTML,/receipt-timestamp/);assert.match(f.modal.innerHTML,/الفرع المرسل/);assert.match(f.modal.innerHTML,/تأكيد الاستلام بواسطة/);assert.match(f.modal.innerHTML,/&lt;img src=x onerror=alert\(1\)&gt;/);assert.match(f.modal.innerHTML,/#7/);assert.doesNotMatch(f.modal.innerHTML,/<img|data-route-receive/);
});
test('stale detail and receipt responses cannot update a different account or closed modal',async()=>{
 const f=fixture(),p=deferred();f.setApi(()=>p.promise);const open=f.t.openTransferDetail(1,'GHZ-IN');f.history.isConnected=false;p.resolve([{awb:'GHZ-IN',events:[{stage:'Stale'}]}]);await open;assert.doesNotMatch(f.history.innerHTML,/Stale/);
 const g=fixture(),q=deferred();g.setApi(()=>q.promise);const receive=g.t.confirmTransferReceipt(1,'GHZ-IN');g.context.user=employee({id:8});g.t.syncOpsOwner();q.resolve({});assert.equal(await receive,false);assert.equal(g.loads,0);assert.equal(g.t.state.routes.length,0);
});
test('camera receives barcode via the same explicit receipt form and stops on close',async()=>{
 const f=fixture();f.t.promptTransferReceiveScan();let stopped=0;const stream={getTracks:()=>[{stop(){stopped++}}]};
 f.context.window.BarcodeDetector=f.context.BarcodeDetector=class{async detect(){return[{rawValue:'GHZ-IN'}]}};
 f.context.navigator.mediaDevices={getUserMedia:async()=>stream};await f.t.startTransferReceiveCamera(f.form);await new Promise(resolve=>setImmediate(resolve));assert.equal(stopped,1);assert.equal(f.calls[0].url,'/api/routes/1/receive');assert.equal(f.t.state.transferCamera,null);
 const g=fixture(),p=deferred();g.t.promptTransferReceiveScan();g.context.window.BarcodeDetector=g.context.BarcodeDetector=f.context.BarcodeDetector;g.context.navigator.mediaDevices={getUserMedia:()=>p.promise};const start=g.t.startTransferReceiveCamera(g.form);g.t.stopTransferCamera();p.resolve(stream);await start;assert.equal(stopped,2);assert.equal(g.calls.length,0);
 const closeButton={tagName:'BUTTON'};g.buttons['[data-close]']=[closeButton];g.t.promptTransferReceiveScan();g.t.state.transferCamera={stream};closeButton.onclick({target:closeButton});assert.equal(stopped,3);
});
test('mirrored assets match and transfer phrases exist in all four supported languages',()=>{
 for(const name of ['ops.js','workflow-locales.js']){const root=fs.readFileSync(path.join(project,name));for(const dir of ['static','public'])assert.deepEqual(fs.readFileSync(path.join(project,dir,name)),root)}
 const context={window:{LOCALES:{}}};vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(project,'workflow-locales.js'),'utf8'),context);
 for(const lang of ['ar','en','ur','hi'])for(const phrase of ['التحويلات الواردة','التحويلات الصادرة','تفاصيل التحويل','مسح بوليصة للاستلام','عهدة التحويل','تم تأكيد استلام الفرع','الفرع المرسل','تأكيد الاستلام بواسطة','المستخدم'])assert.ok(context.window.LOCALES[lang].phrases[phrase],`${lang}: ${phrase}`);
 assert.match(section('  function dispatchLive(', '  function promptRouteScan('),/\$\{transferPanel\(\)\}/);assert.match(section('  function bindOps(', '  function pricingLive('),/bindTransferControls\(app\)/);
});
(async()=>{let passed=0;for(const {name,fn} of checks){await fn();passed++;console.log(`PASS ${name}`)}console.log(`${passed}/${checks.length} targeted frontend/transfer checks passed`);})().catch(error=>{console.error(error);process.exitCode=1});
