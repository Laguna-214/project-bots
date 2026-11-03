// Shared mobile/PWA behavior; fake browser APIs, not install/native acceptance.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const nodes=new Map(),listeners={},notifications=[],messages=[];
function node(id){if(!nodes.has(id))nodes.set(id,{id,handlers:{},dataset:{},textContent:'',hidden:true,attributes:{},
  addEventListener(e,f){this.handlers[e]=f;},setAttribute(k,v){this.attributes[k]=v;},click(){if(this.handlers.click)return this.handlers.click({preventDefault(){}});}});return nodes.get(id);}
const views=['chats','agents','activity','security'].map(v=>{const n=node(v);n.dataset.clientView=v;return n;});
let permissionRequests=0,stopped=0,polled=0,registered=0;
const window={isSecureContext:true,matchMedia:()=>({matches:true}),addEventListener:(n,f)=>listeners[n]=f,focus(){}};
function Notification(title,options){notifications.push({title,...options});this.close=()=>{};}
Notification.permission='granted';Notification.requestPermission=async()=>{permissionRequests++;return 'granted';};window.Notification=Notification;
const navigator={onLine:true,serviceWorker:{register:async(path,options)=>{registered++;assert.equal(path,'/client-sw.js');assert.equal(options.updateViaCache,'none');}}};
const context={window,navigator,Notification,document:{body:{dataset:{}},hidden:false,querySelectorAll:()=>views},
  $:node,token:'isolated-browser-fixture',message:(t,e)=>messages.push({t,e}),setInterval:(f,ms)=>assert.equal(ms,15000),
  securityRefresh:async()=>{polled++;return {incidents:[{id:'test-incident',severity:'critical',status:'open',evidence:'private secret evidence'}]};},chatRefresh:async()=>{}};
node('security-stop-all').addEventListener('click',()=>stopped++);
vm.createContext(context);vm.runInContext(fs.readFileSync('project_bots/client.js','utf8'),context);
(async()=>{
  assert.equal(context.document.body.dataset.mobileView,'chats');
  await views[1].click();assert.equal(context.document.body.dataset.mobileView,'agents');
  context.clientView('arbitrary');assert.equal(context.document.body.dataset.mobileView,'agents');
  await node('client-stop-all').click();assert.equal(stopped,1);
  assert.equal(permissionRequests,0,'Never request notifications without user action');
  await node('client-notifications').click();assert.equal(permissionRequests,1);
  await context.clientPoll();await context.clientPoll();assert.equal(polled,2);
  assert.equal(notifications.length,1,'Do not repeatedly alert for the same incident');
  assert(!JSON.stringify(notifications).includes('private secret evidence'));
  context.document.hidden=true;await context.clientPoll();assert.equal(polled,2);
  navigator.onLine=false;listeners.offline();assert(node('client-status').textContent.includes('unverified'));
  assert.equal(registered,1);
  console.log('Mobile navigation, emergency control, private notifications and offline-state contracts passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
