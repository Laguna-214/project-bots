const fs=require('fs'),vm=require('vm'),assert=require('assert');
assert(fs.existsSync('project_bots/conversations.js'),'Missing conversational enrollment and activity UI');
const nodes=new Map(),calls=[],forms={};
let loadGate=null;
function node(id){if(!nodes.has(id))nodes.set(id,{value:'',checked:false,textContent:'',children:[],handlers:{},append(...v){this.children.push(...v);},replaceChildren(){this.children=[];},addEventListener(e,f){this.handlers[e]=f;}});return nodes.get(id);}
const agent='11111111-1111-4111-8111-111111111111',job='22222222-2222-4222-8222-222222222222';
const context={console,agents:[{id:agent,name:'Researcher'}],selectedChat:null,$:node,
  options:(select,rows)=>{select.value=select.value||rows[0]?.id||'';},
  element:(tag,text)=>({textContent:text||'',children:[],append(...v){this.children.push(...v);}}),
  action:(label,fn)=>({textContent:label,click:fn}),message:()=>{},form:(id,fn)=>forms[id]=fn,
  api:async(path,data)=>{calls.push({path,data});if(loadGate&&!data)await loadGate;if(path==='/api/conversations/jobs')return [{id:job,agent_id:agent,chat_id:'chat',status:'uncertain',updated_at:1}];return {enabled:true,system_instructions:'Private instructions',memory:'Private memory',max_replies:8};}};
vm.createContext(context);vm.runInContext(fs.readFileSync('project_bots/conversations.js','utf8'),context);
(async()=>{
 await context.conversationRefresh();
 assert(node('conversation-jobs').children.some(n=>JSON.stringify(n).includes('uncertain')));
 node('conversation-enabled').checked=true;
 await forms['conversation-form']({agent_id:agent,system_instructions:'Own instructions',memory:'Own memory',max_replies:'8',tools:'malicious'});
 const sent=calls.find(c=>c.data&&c.path.endsWith('/conversation'));
 assert.equal(sent.data.enabled,true);assert.deepEqual(Array.from(sent.data.tools),[]);assert.equal(sent.data.max_replies,8);
 assert(!('agent_id' in sent.data));
 await node('conversation-load').handlers.click();
 assert.equal(node('conversation-memory').value,'Private memory');
 assert.equal(node('conversation-instructions').value,'Private instructions');
 assert.equal(node('conversation-enabled').checked,true);
 let release;loadGate=new Promise(r=>release=r);
 const loading=node('conversation-load').handlers.click();
 node('conversation-memory').value='New unsaved private draft';
 if(node('conversation-form').handlers.input)node('conversation-form').handlers.input();
 release();await loading;loadGate=null;
 assert.equal(node('conversation-memory').value,'New unsaved private draft','Delayed load must not overwrite a newer draft');
 console.log('Conversation enrollment, tool-free payload, private configuration and job-state UI contracts passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
