'use strict';
// Trusted server responses describe observations, not an isolation guarantee.
let securityRefreshVersion = 0;
function securityButton(label, callback) {
  const button = element('button', label, 'secondary');
  button.type = 'button';
  button.addEventListener('click', async () => {
    if (button.disabled) return;
    button.disabled = true;
    try { await callback(); }
    catch (error) { message(error.message, true); }
    finally { button.disabled = false; }
  });
  return button;
}
function securityRender(status) {
  const coverage = Object.entries(status.coverage || {});
  const healthy = coverage.length === 5 && coverage.every(([, value]) => value.status === 'healthy');
  $('security-status').textContent = (status.global_stop ? 'Emergency stop latched. ' : 'Emergency stop not latched. ') +
    (healthy ? 'Required coverage reports fresh observations; review enforcement limitations.' :
      'Monitoring unavailable or stale: new execution is denied. Running workloads require verified containment.');
  $('security-health').replaceChildren();
  coverage.forEach(([name, value]) => {
    $('security-health').append(element('p', name + ': ' + value.status +
      (value.source ? ' · ' + value.source : '') +
      (value.observed_at ? ' · observed ' + new Date(value.observed_at * 1000).toLocaleString() : '')));
  });
  (status.limitations || []).forEach(text => $('security-health').append(element('p', text)));
  $('security-agents').replaceChildren();
  (status.agents || []).forEach(state => {
    const name = agents.find(a => a.id === state.agent_id)?.name || state.agent_id;
    const row = element('article', undefined, 'registry');
    row.append(element('strong', name), element('p', state.contained ?
      'Contained in control plane; inspect incident for runtime and network outcomes.' :
      'Not contained; registration does not establish runtime/network protection.'));
    row.append(securityButton('Stop agent', async () => {
      const incident = await api('/api/security/incidents', {agent_id:state.agent_id, severity:'high',
        behavior:'Administrator requested agent stop', resource:'worker runtime and communication',
        evidence:'Explicit Security dashboard stop control'});
      message('Agent stop recorded: ' + incident.id + '. Review partial actions; not proof of network isolation.');
      await securityRefresh();
    }));
    $('security-agents').append(row);
  });
  $('security-incidents').replaceChildren();
  const incidents = status.incidents || [];
  if (!incidents.length) $('security-incidents').append(element('p', 'No incidents recorded. This does not prove absence of compromise.'));
  incidents.forEach(incident => {
    const card = element('article', undefined, 'registry');
    card.append(element('strong', incident.severity.toUpperCase() + ' · ' + incident.behavior),
      element('small', incident.id + ' · ' + new Date(incident.created_at * 1000).toLocaleString()),
      element('p', 'Status: ' + incident.status + ' · containment: ' + incident.outcome));
    card.append(securityButton('Review evidence', async () => {
      const detail = await api('/api/security/incidents/' + incident.id);
      $('security-evidence').textContent = JSON.stringify(detail, null, 2);
    }));
    card.append(securityButton('Acknowledge', async () => {
      const note = prompt('Investigation note. Acknowledgment does not recover or restart the agent.');
      if (!note || !note.trim()) return;
      await api('/api/security/incidents/' + incident.id + '/acknowledge', {note:note.trim()});
      await securityRefresh();
    }));
    if (['high', 'critical'].includes(incident.severity) && incident.status !== 'recovered') {
      card.append(securityButton('Authorize recovery', async () => {
        const note = prompt('Recovery note. Stop/readback, fresh coverage and independently verified credential rotation are required. No runtime is restarted.');
        if (!note || !note.trim()) return;
        if (!confirm('Authorize recovery only after investigation and credential rotation? The server independently checks prerequisites.')) return;
        await api('/api/security/incidents/' + incident.id + '/recover', {note:note.trim(), credential_rotated:true});
        message('Recovery authorized; no worker was automatically started.');
        await securityRefresh();
      }));
    }
    $('security-incidents').append(card);
  });
}
async function securityRefresh() {
  const version = ++securityRefreshVersion;
  try {
    const status = await api('/api/security/status');
    if (version === securityRefreshVersion) securityRender(status);
    return status;
  } catch (error) {
    if (version === securityRefreshVersion) $('security-status').textContent = 'Security status unverified: ' + error.message;
    throw error;
  }
}
$('security-stop-all').addEventListener('click', async () => {
  const button = $('security-stop-all');
  if (button.disabled) return;
  button.disabled = true;
  ++securityRefreshVersion;
  $('security-status').textContent = 'Emergency stop requested; runtime/network outcomes unverified until readback.';
  try {
    const status = await api('/api/security/emergency-stop', {reason:'Administrator emergency stop from dashboard'});
    securityRender(status);
    message('Emergency stop latch recorded. This is not proof all runtimes or networks stopped; review incident actions.');
  } catch (error) {
    $('security-status').textContent = 'Emergency stop outcome unverified. Keep workloads independently isolated; investigate management connectivity.';
    message(error.message, true);
  } finally { button.disabled = false; }
});
$('security-restore').addEventListener('click', async () => {
  const note = prompt('Explicit global recovery note. Contained agents need separate incident recovery first. This will not restart workers.');
  if (!note || !note.trim()) return;
  if (!confirm('Clear the global stop only after investigation and verified enforcement health?')) return;
  const button = $('security-restore');
  if (button.disabled) return;
  button.disabled = true;
  try {
    securityRender(await api('/api/security/recover', {note:note.trim()}));
    message('Global execution latch restored. No runtime was started.');
  } catch (error) { message(error.message, true); }
  finally { button.disabled = false; }
});
