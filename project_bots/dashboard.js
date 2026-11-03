'use strict';
// Per-tab bearer persists through refresh, but is invalid after a server restart.
let token = sessionStorage.getItem('project-bots-session') || '';
let csrf = '';
let agents = [];
const $ = id => document.getElementById(id);
function message(text, error = false) {
  $('message').textContent = text;
  $('message').classList.toggle('error', error);
}
async function api(path, data) {
  const headers = {'X-Setup-Origin': location.origin};
  if (token) headers.Authorization = 'Bearer ' + token;
  if (csrf) headers['X-CSRF-Token'] = csrf;
  if (data !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {method: data === undefined ? 'GET' : 'POST', headers,
    body: data === undefined ? undefined : JSON.stringify(data), credentials: 'omit'});
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'Request failed');
  return body;
}
function element(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
function options(select, rows, empty) {
  const old = select.value;
  select.replaceChildren(new Option(empty, ''));
  rows.forEach(row => select.add(new Option(row.name, row.id)));
  if (rows.some(row => row.id === old)) select.value = old;
}
function action(label, callback) {
  const button = element('button', label, 'secondary');
  button.type = 'button';
  button.addEventListener('click', async () => {
    button.disabled = true;
    try { await callback(); message('Saved.'); }
    catch (error) { message(error.message, true); }
    finally { button.disabled = false; }
  });
  return button;
}
async function inspect(id) {
  $('inspect').textContent = JSON.stringify(await api('/api/jobs/' + id), null, 2);
  $('inspector').hidden = false;
}
function renderJobs(jobs) {
  $('jobs').replaceChildren();
  if (!jobs.length) $('jobs').append(element('p', 'No jobs yet. Create a task below; it stays queued until explicitly claimed through the API.'));
  jobs.slice().reverse().forEach(job => {
    const card = element('article', undefined, 'job');
    card.append(element('h3', job.title), element('p', job.status + ' · ' + job.progress + '% · ' + (agents.find(a => a.id === job.agent_id)?.name || 'Unassigned')));
    const progress = element('progress');
    progress.max = 100; progress.value = job.progress;
    progress.setAttribute('aria-label', 'Job progress');
    card.append(progress);
    if (job.message) card.append(element('p', job.message));
    if (job.error) card.append(element('p', 'Failure: ' + job.error));
    const tools = element('div', undefined, 'toolbar');
    tools.append(action('Inspect input / result', () => inspect(job.id)));
    if (job.status === 'queued') {
      const select = element('select');
      select.setAttribute('aria-label', 'Assign agent for ' + job.title);
      options(select, agents, 'Unassigned'); select.value = job.agent_id || '';
      tools.append(select, action('Assign', async () => {
        await api('/api/jobs/' + job.id + '/assign', {agent_id: select.value || null});
        await refresh();
      }));
    }
    if (['queued', 'running'].includes(job.status)) tools.append(action('Cancel job', async () => {
      if (confirm('Cancel this queued/manual job? Dispatched jobs cannot be canceled remotely and will be refused; a timeout does not stop inference.')) {
        await api('/api/jobs/' + job.id + '/cancel', {});
        await refresh();
      }
    }));
    card.append(tools); $('jobs').append(card);
  });
}
function registry(id, rows, detail) {
  $(id).replaceChildren();
  if (!rows.length) $(id).append(element('p', 'None registered.'));
  rows.forEach(row => {
    const item = element('div', undefined, 'registry');
    item.append(element('strong', row.name), element('small', detail(row)), element('small', row.id));
    $(id).append(item);
  });
}
async function refresh() {
  const [newAgents, machines, jobs, settings, workers] = await Promise.all([
    api('/api/agents'), api('/api/machines'), api('/api/jobs'), api('/api/settings'), api('/api/workers')]);
  agents = newAgents;
  $('system-status').textContent = 'API connected · ' + agents.length + ' registered agents · ' + machines.length + ' unverified machines · ' + jobs.filter(j => j.status === 'queued').length + ' queued / ' + jobs.filter(j => j.status === 'running').length + ' running reports · refreshed ' + new Date().toLocaleTimeString();
  options($('agent-machine'), machines, 'No machine assigned');
  options($('compute-machine'), machines, 'Select a compute service');
  options($('job-agent'), agents, 'Unassigned');
  registry('agents', agents, a => {
    const worker = workers.find(w => w.agent_id === a.id);
    return a.role + ' · ' + (worker ? 'worker ' + worker.status + ' (last registration observation; use fresh health check)' : 'definition only') + (a.machine_id ? ' · machine assigned' : '');
  });
  registry('machines', machines, m => m.endpoint + ' · unverified');
  renderJobs(jobs);
  $('inference-endpoint').value = settings.inference_endpoint;
  $('machine-api-env').value = settings.machine_api_env;
  if (typeof chatRefresh === 'function') await chatRefresh();
  if (typeof securityRefresh === 'function') await securityRefresh();
}
async function unlock() {
  csrf = (await api('/api/session')).csrf;
  await refresh();
  $('pairing').hidden = true; $('platform').hidden = false; $('refresh').hidden = false;
}
function form(id, submit) {
  $(id).addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.currentTarget.querySelector('button');
    button.disabled = true;
    try { await submit(Object.fromEntries(new FormData($(id)))); message('Saved.'); }
    catch (error) { message(error.message, true); }
    finally { button.disabled = false; }
  });
}
form('pair-form', async data => {
  token = (await api('/api/pair', data)).token;
  sessionStorage.setItem('project-bots-session', token);
  $('pair-code').value = '';
  await unlock();
});
form('machine-form', async data => {
  if (!data.credential_env) delete data.credential_env;
  await api('/api/machines', data); $('machine-form').reset(); await refresh();
});
form('agent-form', async data => {
  const config = {};
  if (data.model) config.model = data.model;
  if (data.instructions) config.instructions = data.instructions;
  await api('/api/agents', {name: data.name, role: data.role, machine_id: data.machine_id || null, config});
  $('agent-form').reset(); await refresh();
});
form('job-form', async data => {
  data.agent_id = data.agent_id || null;
  await api('/api/jobs', data); $('job-form').reset(); await refresh();
});
form('settings-form', async data => {
  await api('/api/settings', {...data, cloud_fallback: false}); await refresh();
});
function operationUUID() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, x => x.toString(16).padStart(2, '0')).join('');
  return [hex.slice(0,8), hex.slice(8,12), hex.slice(12,16), hex.slice(16,20), hex.slice(20)].join('-');
}
function computePath(route) {
  const machine = $('compute-machine').value;
  if (!machine) throw new Error('Select a registered compute service.');
  return '/api/machines/' + machine + '/' + route;
}
function showCompute(value) { $('compute-output').textContent = JSON.stringify(value, null, 2); }
async function mutateVM(route, data, expected, operationInput) {
  const approval = prompt('This changes a real VM. Type exactly ' + expected + ' to authorize this one action.');
  if (approval !== expected) throw new Error('Not confirmed; no operation sent.');
  // Preserve the ID on errors/timeouts. Retrying the same payload is idempotent.
  data.confirmation = approval;
  $('compute-output').textContent = 'Operation ' + data.operation_id + ' pending. Keep this ID; inspect before retrying after errors.';
  sessionStorage.setItem('project-bots-last-compute-operation', JSON.stringify({machine: $('compute-machine').value, route, data}));
  showCompute(await api(computePath(route), data));
  $(operationInput).value = operationUUID();
}
form('vm-create-form', async data => {
  for (const key of ['cpus', 'ram_mib', 'disk_gib']) data[key] = Number(data[key]);
  await mutateVM('vms', data, 'create', 'vm-create-operation');
});
form('vm-action-form', async data => {
  const {vm_id, action: verb, operation_id} = data;
  const payload = {operation_id};
  if (verb === 'resources') for (const key of ['cpus', 'ram_mib', 'disk_gib']) payload[key] = Number(data[key]);
  if (verb.startsWith('snapshot-')) payload.snapshot = data.snapshot;
  if (verb === 'detail') { showCompute(await api(computePath('vms/' + vm_id))); return; }
  await mutateVM('vms/' + vm_id + '/' + verb, payload, verb + ':' + vm_id, 'vm-action-operation');
});
for (const [id, route] of [['compute-health', 'health'], ['compute-list', 'vms']]) {
  $(id).addEventListener('click', async () => {
    try { showCompute(await api(computePath(route))); }
    catch (error) { message(error.message, true); }
  });
}
form('operation-form', async data => { showCompute(await api(computePath('operations/' + data.operation_id))); });
form('worker-form', async data => {
  const {agent_id, vm_id, endpoint, credential_env, model, identity_endpoint} = data;
  const profile = {model};
  for (const key of ['context', 'temperature', 'max_output', 'memory_mib', 'priority']) profile[key] = Number(data[key]);
  const expected = 'configure:' + agent_id;
  if (prompt('Bind this worker. A supplied identity endpoint must verify its running compute VM, Gateway and deployed profile before saving. Type ' + expected) !== expected) throw new Error('Not confirmed; no operation sent.');
  const payload = {vm_id, endpoint, credential_env, profile};
  if (identity_endpoint) payload.identity_endpoint = identity_endpoint;
  $('worker-output').textContent = JSON.stringify(await api('/api/agents/' + agent_id + '/worker', payload), null, 2);
});
form('worker-health-form', async data => {
  $('worker-output').textContent = JSON.stringify(await api('/api/agents/' + data.agent_id + '/worker/health'), null, 2);
});
form('dispatch-form', async data => {
  const expected = 'dispatch:' + data.job_id;
  if (prompt('Run this job on its configured real worker. No automatic retry or remote cancellation. Type ' + expected) !== expected) throw new Error('Not confirmed; no operation sent.');
  $('worker-output').textContent = 'Dispatch pending for ' + data.job_id + '. Inspect execution after connection errors; do not replay.';
  $('worker-output').textContent = JSON.stringify(await api('/api/jobs/' + data.job_id + '/dispatch', {confirmation: expected}), null, 2);
});
form('execution-form', async data => {
  $('worker-output').textContent = JSON.stringify(await api('/api/jobs/' + data.job_id + '/execution'), null, 2);
});
form('model-form', async data => {
  const payload = {model: data.model};
  if (data.action !== 'show') {
    const expected = data.action + ':' + data.model;
    if (prompt('Change the shared local model daemon. Type ' + expected) !== expected) throw new Error('Not confirmed; no operation sent.');
    payload.confirmation = expected;
  }
  $('model-output').textContent = JSON.stringify(await api('/api/models/' + data.action, payload), null, 2);
});
for (const [id, path] of [['models-list', '/api/models'], ['models-loaded', '/api/models/loaded'], ['workers-list', '/api/workers'], ['roles-list', '/api/roles']]) {
  $(id).addEventListener('click', async () => {
    try { $(id === 'workers-list' || id === 'roles-list' ? 'worker-output' : 'model-output').textContent = JSON.stringify(await api(path), null, 2); }
    catch (error) { message(error.message, true); }
  });
}
$('vm-create-operation').value = operationUUID();
$('vm-action-operation').value = operationUUID();
const lastCompute = sessionStorage.getItem('project-bots-last-compute-operation');
if (lastCompute) $('compute-output').textContent = 'Previous request (inspect operation before retrying): ' + lastCompute;
$('refresh').addEventListener('click', () => refresh().then(() => message('Refreshed.')).catch(e => message(e.message, true)));
