const fs=require('fs'),vm=require('vm'),assert=require('assert');
assert(fs.existsSync('project_bots/approvals.js'),'Missing human approval interface');
const nodes=new Map(),forms={},calls=[],handlers={},buttons=[];
function node(id){if(!nodes.has(id))nodes.set(id,{value:'',hidden:true,textContent:'',children:[],addEventListener(e,f){this[e]=f;},append(...v){this.children.push(...v);},replaceChildren(...v){this.children=v;}});return nodes.get(id);}
const approval={id:'approval',actor_name:'<img src=x>',action:'start',resource:'vm-id',canonical_payload:'{"operation_id":"exact-op"}',status:'pending',expires_at:9999999999,expired:false,invalidated:false};
let confirmation=false,cleartimer=null;
const context={console,$:node,form:(id,fn)=>forms[id]=fn,api:async(path,data)=>{calls.push({path,data});if(data&&path==='/api/integrations')return {id:'new',token:'TEST-ONE-TIME-SECRET'};if(path==='/api/approvals')return {approvals:[approval]};if(path==='/api/integrations')return {integrations:[]};return {operations:[]};},
 element:(tag,text)=>({textContent:text||'',children:[],append(...v){this.children.push(...v);}}),action:(label,fn)=>{const b={textContent:label,click:fn};buttons.push(b);return b;},message:()=>{},confirm:()=>confirmation,
 setTimeout:fn=>{cleartimer=fn;return 1;},clearTimeout:()=>{},window:{addEventListener:(event,fn)=>handlers[event]=fn},navigator:{clipboard:{writeText:async()=>{}}},Date};
vm.createContext(context);vm.runInContext(fs.readFileSync('project_bots/approvals.js','utf8'),context);
(async()=>{await context.approvalRefresh();const text=JSON.stringify(node('approvals-list').children);assert(text.includes('<img src=x>'));assert(text.includes('exact-op'));
 const approve=buttons.find(b=>b.textContent==='Approve exact action');await approve.click();assert(!calls.some(c=>c.path.endsWith('/approve')));
 confirmation=true;await approve.click();assert(calls.some(c=>c.path==='/api/approvals/approval/approve'&&Object.keys(c.data).length===0));
 node('integration-grants').value='[]';await forms['integration-form']({name:'Read-only helper',expires_in:'3600'});assert.equal(node('integration-token').value,'TEST-ONE-TIME-SECRET');assert(!JSON.stringify(node('integrations-list').children).includes('TEST-ONE-TIME-SECRET'));
 cleartimer();assert.equal(node('integration-token').value,'');
 console.log('Human approval review/decision and ephemeral token UI contracts passed');})().catch(e=>{console.error(e);process.exitCode=1;});
