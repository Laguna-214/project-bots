// Browser logic contract with a fake DOM/HTTP, not visual or real-VM acceptance.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
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
  console.log('VM dashboard confirmation contract passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
