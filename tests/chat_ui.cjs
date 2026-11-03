// Fake DOM/API interaction contracts, not visual/native/VM acceptance.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const nodes = new Map(), calls = [], storage = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {value:'', data:{}, handlers:{}, children:[], options:[], disabled:false,
    textContent:'', classList:{toggle(){}},
    get selectedOptions(){return this.options.filter(o => o.selected);},
    add(o){this.options.push(o);}, addEventListener(e,f){this.handlers[e]=f;},
    querySelector(){return this;}, reset(){}, append(...items){this.children.push(...items);},
    replaceChildren(...items){this.children=items;this.options=[];},setAttribute(){}});
  return nodes.get(id);
}
const a = '11111111-1111-4111-8111-111111111111';
const chat = {id:'22222222-2222-4222-8222-222222222222',title:'Team',kind:'group',agent_ids:[a]};
const hostile = '<img src=x onerror=alert(1)>';
let fail = false;
let postGate = null;
let delayHistory = false;
const historyGates = [];
const context = {document:{getElementById:node, createElement:tag=>({children:[],textContent:'',className:'',append(...v){this.children.push(...v);},addEventListener(){},setAttribute(){}})},
  sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
  location:{origin:'http://127.0.0.1:8032'},prompt:()=>null,confirm:()=>false,
  crypto:require('crypto').webcrypto, Uint8Array, Option:function(text,value){this.text=text;this.value=value;},
  FormData:class{constructor(form){this.items=Object.entries(form.data);}[Symbol.iterator](){return this.items[Symbol.iterator]();}},
  fetch:async(path, req)=>{
    calls.push({path,method:req.method,body:JSON.parse(req.body||'{}')});
    if(fail && req.method==='POST') throw new Error('Transport failed');
    if(postGate && req.method==='POST') await postGate;
    if(delayHistory && path.includes('/messages?')) {
      const deferred = new Promise(resolve => historyGates.push(resolve));
      return {ok:true,json:async()=>await deferred};
    }
    let data = {};
    if(path==='/api/chats') data=[chat];
    else if(path==='/api/security/events') data={events:[]};
    else if(path.includes('/messages?')) data={messages:[{sender:a,created_at:1,content:path.includes('33333333-3333-4333-8333-333333333333')?'B history':hostile,sequence:1}],next_after:1,has_more:false};
    else if(path.endsWith('/members')) data=chat;
    return {ok:true,json:async()=>data};
  }};
vm.createContext(context);
vm.runInContext(fs.readFileSync('project_bots/dashboard.js','utf8'),context);
vm.runInContext(fs.readFileSync('project_bots/chat.js','utf8'),context);
(async()=>{
  vm.runInContext(`agents=[{id:'${a}',name:'A'}]`,context);
  await context.chatRefresh();
  await context.openChat(chat);
  assert.equal(node('chat-history').children[0].children[1].textContent,hostile);
  const submit = id=>node(id).handlers.submit({preventDefault(){},currentTarget:node(id)});
  node('chat-message-form').data={content:'Hello'};
  fail=true;
  await submit('chat-message-form');
  const failed=calls.find(c=>c.method==='POST' && c.path.endsWith('/messages'));
  fail=false;
  await submit('chat-message-form');
  const posts=calls.filter(c=>c.method==='POST' && c.path.endsWith('/messages'));
  assert.equal(posts.length,2);
  assert.equal(posts[1].body.client_id,failed.body.client_id,'Retry must preserve message id');
  assert(!('sender' in posts[1].body));
  let release;
  postGate = new Promise(resolve => {release=resolve;});
  node('chat-content').value='Sending draft';
  node('chat-message-form').data={content:'Sending draft'};
  const sending=submit('chat-message-form');
  node('chat-content').value='New unsent draft';
  release();
  await sending;
  postGate=null;
  assert.equal(node('chat-content').value,'New unsent draft','In-flight send must preserve a newer draft');
  delayHistory=true;
  const page = {messages:[{sender:a,created_at:1,content:hostile,sequence:1}],next_after:1,has_more:false};
  const first=context.chatHistory(), repeated=context.chatHistory();
  assert.equal(historyGates.length,1,'Repeated pagination must issue only one request');
  historyGates.shift()(page);
  await Promise.all([first,repeated]);
  assert.equal(node('chat-history').children.length,1,'Duplicate sequences must not render twice');
  const oldPage=context.chatHistory(), resetPage=context.chatHistory(true);
  assert.equal(historyGates.length,2);
  historyGates[1](page);
  await resetPage;
  historyGates[0]({...page,next_after:99});
  await oldPage;
  assert.equal(vm.runInContext('chatCursor',context),1,'Stale page must not overwrite reset cursor');
  assert.equal(node('chat-history').children.length,1);
  delayHistory=false;
  await submit('chat-members-form');
  assert(calls.some(c=>c.path.endsWith('/members') && c.body.agent_ids[0]===a));
  assert.equal(storage.get('project-bots-selected-chat'),chat.id);
  const other = {...chat,id:'33333333-3333-4333-8333-333333333333',title:'B'};
  for (const returnToA of [false,true]) {
    await context.openChat(chat);
    postGate = new Promise(resolve => {release=resolve;});
    const saving=submit('chat-members-form');
    await context.openChat(other);
    if (returnToA) await context.openChat({...chat,title:'New A'});
    const heading=node('chat-heading').textContent;
    const history=node('chat-history').children;
    const content=returnToA?hostile:'B history';
    assert.equal(history[0].children[1].textContent,content);
    release(); await saving; postGate=null;
    assert.equal(node('chat-heading').textContent,heading,'Stale membership save must not replace current heading');
    assert.strictEqual(node('chat-history').children,history,'Stale membership save must not reload history');
    assert.equal(node('chat-history').children[0].children[1].textContent,content);
    assert.equal(vm.runInContext('selectedChat.id',context),returnToA?chat.id:other.id);
    node('chat-message-form').data={content:'Current target'};
    await submit('chat-message-form');
    assert.equal(calls.filter(c=>c.method==='POST' && c.path.endsWith('/messages')).at(-1).path,
      '/api/chats/'+(returnToA?chat.id:other.id)+'/messages');
  }
  console.log('Chat safe rendering, membership and retry contracts passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
