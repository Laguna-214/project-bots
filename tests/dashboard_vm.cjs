// Browser logic contract with a fake DOM/HTTP, not visual or real-VM acceptance.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const html = fs.readFileSync('project_bots/dashboard.html','utf8');
assert(!html.includes('CPU-only real-worker acceptance'), 'Dashboard must not hardcode a stale CPU-only deployment status');
const nodes = new Map(), calls = [], storage = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {value:'', data:{}, handlers:{}, disabled:false,
    classList:{toggle(){}}, addEventListener(event, callback){this.handlers[event]=callback;},
    querySelector(){return this;}, reset(){}, append(){}, replaceChildren(){}, setAttribute(){}});
  return nodes.get(id);
}
let approval = null;
const context = {document:{getElementById:node, createElement:node},
  sessionStorage:{getItem:k=>storage.get(k), setItem:(k,v)=>storage.set(k,v), removeItem:k=>storage.delete(k)},
  location:{origin:'http://127.0.0.1:8032'}, confirm:()=>false, prompt:()=>approval,
  crypto:require('crypto').webcrypto, Uint8Array, Option:function(){},
  FormData:class {constructor(form){this.items=Object.entries(form.data);} [Symbol.iterator](){return this.items[Symbol.iterator]();}},
  fetch:async(path, request)=>{calls.push({path, body:JSON.parse(request.body || '{}')}); return {ok:true,json:async()=>({state:'shut off'})};}
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('project_bots/dashboard.js','utf8'),context);
(async()=>{
  assert(node('vm-action-form').handlers.submit, 'VM action form must be wired');
  const id = '11111111-1111-4111-8111-111111111111';
  node('compute-machine').value = '22222222-2222-4222-8222-222222222222';
  node('vm-action-form').data = {vm_id:id, action:'delete', operation_id:id, cpus:'2', ram_mib:'4096', disk_gib:'24', snapshot:'clean'};
  await node('vm-action-form').handlers.submit({preventDefault(){},currentTarget:node('vm-action-form')});
  assert.equal(calls.length,0, 'Cancelling must never send a mutation');
  approval = 'delete:' + id;
  await node('vm-action-form').handlers.submit({preventDefault(){},currentTarget:node('vm-action-form')});
  assert.equal(calls.length,1);
  assert.equal(calls[0].path, '/api/machines/' + node('compute-machine').value + '/vms/' + id + '/delete');
  assert.equal(calls[0].body.confirmation,approval);
  assert.equal(calls[0].body.operation_id,id);
  assert(!('cpus' in calls[0].body));
  assert(node('worker-form').handlers.submit, 'Worker registration must be wired');
  assert(node('dispatch-form').handlers.submit, 'Real dispatch must be wired');
  assert(node('model-form').handlers.submit, 'Model manager must be wired');
  approval = null;
  node('dispatch-form').data = {job_id:id};
  await node('dispatch-form').handlers.submit({preventDefault(){},currentTarget:node('dispatch-form')});
  assert.equal(calls.length,1, 'Canceled dispatch must not send');
  approval = 'dispatch:' + id;
  await node('dispatch-form').handlers.submit({preventDefault(){},currentTarget:node('dispatch-form')});
  assert.equal(calls[1].path, '/api/jobs/' + id + '/dispatch');
  assert.equal(calls[1].body.confirmation,approval);
  approval = null;
  node('model-form').data = {action:'delete', model:'qwen3:1.7b'};
  await node('model-form').handlers.submit({preventDefault(){},currentTarget:node('model-form')});
  assert.equal(calls.length,2, 'Canceled model mutation must not send');
  approval = 'delete:qwen3:1.7b';
  await node('model-form').handlers.submit({preventDefault(){},currentTarget:node('model-form')});
  assert.equal(calls[2].path, '/api/models/delete');
  assert.equal(calls[2].body.confirmation,approval);
  assert(node('roles-list').handlers.click, 'Role presets must be inspectable');
  await node('roles-list').handlers.click();
  assert.equal(calls[3].path, '/api/roles');
  assert(node('worker-health-form').handlers.submit, 'Worker identity health check must be wired');
  node('worker-health-form').data = {agent_id:id};
  await node('worker-health-form').handlers.submit({preventDefault(){},currentTarget:node('worker-health-form')});
  assert.equal(calls[4].path, '/api/agents/' + id + '/worker/health');
  console.log('VM and Stage3 dashboard confirmation contracts passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
