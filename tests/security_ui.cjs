// Security UI contracts with fake DOM/API, not visual or hostile-VM acceptance.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
assert(fs.existsSync('project_bots/security.js'), 'Missing Security dashboard controls');
const nodes = new Map(), calls = [];
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {id, children:[], handlers:{}, textContent:'', disabled:false,
    append(...v){this.children.push(...v);}, replaceChildren(...v){this.children=v;},
    addEventListener(e,f){this.handlers[e]=f;}, setAttribute(){}});
  return nodes.get(id);
}
const aid='11111111-1111-4111-8111-111111111111';
const iid='22222222-2222-4222-8222-222222222222';
const incident={id:iid,agent_id:aid,severity:'critical',status:'open',outcome:'partial',
  created_at:1,behavior:'<script>hostile evidence</script>',resource:'private workspace',evidence:'private log',
  actions:[{action:'network_isolation',status:'unavailable'}]};
let status={global_stop:false,protected:false,coverage:{runtime:{status:'unavailable'}},
  agents:[{agent_id:aid,contained:false}],incidents:[incident],limitations:['Network isolation unavailable']};
let fail=false, answer=null, deferred=null;
const messages=[];
const context={console,Date,document:{getElementById:node,createElement:tag=>node('generated-'+nodes.size)},
  agents:[{id:aid,name:'Researcher'}], prompt:()=>answer, confirm:()=>false,
  $:node, element:(tag,text)=>{const n=node('generated-'+nodes.size);n.textContent=text||'';return n;},
  message:(text,error)=>messages.push({text,error}),
  api:async(path,data)=>{
    calls.push({path,data});
    if(fail) throw new Error('Enforcement unavailable');
    if(deferred) await deferred;
    if(path.endsWith('/emergency-stop')) {status={...status,global_stop:true}; return status;}
    if(path==='/api/security/status') return status;
    if(path==='/api/security/incidents/'+iid) return incident;
    return incident;
  }};
vm.createContext(context);
vm.runInContext(fs.readFileSync('project_bots/security.js','utf8'),context);
(async()=>{
  await context.securityRefresh();
  assert(node('security-status').textContent.includes('unavailable'));
  assert(!node('security-status').textContent.includes('protected'));
  const incidentCard=node('security-incidents').children[0];
  assert(incidentCard.children.some(n=>n.textContent.includes('<script>hostile evidence</script>')));
  let release; deferred=new Promise(r=>release=r);
  const stopping=node('security-stop-all').handlers.click();
  assert(node('security-stop-all').disabled);
  assert.equal(calls.filter(c=>c.path.endsWith('/emergency-stop')).length,1);
  release(); await stopping; deferred=null;
  assert(node('security-status').textContent.includes('latched'));
  assert(messages.some(m=>m.text.includes('not proof')),'Do not claim all networks/runtimes stopped');
  const before=calls.length;
  await node('security-restore').handlers.click();
  assert.equal(calls.length,before,'Recovery without explicit note must send nothing');
  fail=true;
  await node('security-stop-all').handlers.click();
  assert(messages.at(-1).error);
  assert(!node('security-stop-all').disabled);
  assert(node('security-status').textContent.includes('unverified'));
  console.log('Security UI unavailable-health, safe rendering, emergency latch and failure contracts passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
