'use strict';
// Only backend-authenticated paired human sessions can decide or issue authority.
let approvalRefreshVersion = 0;
let integrationSecretTimer = null;
function clearIntegrationSecret() {
  $('integration-token').value = '';
  $('integration-token-area').hidden = true;
  if (integrationSecretTimer) clearTimeout(integrationSecretTimer);
  integrationSecretTimer = null;
}
window.addEventListener('pagehide', clearIntegrationSecret);
$('integration-clear').addEventListener('click', clearIntegrationSecret);
$('integration-copy').addEventListener('click', async () => {
  try {
    if (!$('integration-token').value) return;
    await navigator.clipboard.writeText($('integration-token').value);
    message('Copied once. Store in a private 0600 token file; never share in chats or logs.');
  } catch (error) { message('Clipboard unavailable. Use the private token field only in a trusted secure browser.', true); }
});
async function approvalRefresh() {
  const version = ++approvalRefreshVersion;
  const [pending, integrations, receipts] = await Promise.all([
    api('/api/approvals'), api('/api/integrations'), api('/api/integration-operations')]);
  if (version !== approvalRefreshVersion) return;
  $('approvals-list').replaceChildren();
  if (!pending.approvals.length) $('approvals-list').append(element('p', 'No approval proposals recorded.'));
  pending.approvals.forEach(proposal => {
    const card = element('article', undefined, 'registry');
    card.append(element('strong', proposal.actor_name + ' · ' + proposal.action),
      element('small', 'Resource: ' + proposal.resource + ' · ' + proposal.id),
      element('p', 'Status: ' + proposal.status + (proposal.expired ? ' · EXPIRED' : '') +
        (proposal.invalidated ? ' · INVALIDATED' : '') + ' · expires ' + new Date(proposal.expires_at * 1000).toLocaleString()));
    if (proposal.status === 'pending' && !proposal.expired && !proposal.invalidated) {
      card.append(element('p', 'Untrusted proposal: review the exact bound payload below. Approval grants this one action only.'),
        element('pre', proposal.canonical_payload));
      card.append(action('Approve exact action', async () => {
        if (!confirm('Approve exactly this displayed action for ' + proposal.actor_name + ' on ' + proposal.resource + '? A changed payload is not authorized.')) return;
        await api('/api/approvals/' + proposal.id + '/approve', {});
        await approvalRefresh();
      }), action('Reject action', async () => {
        await api('/api/approvals/' + proposal.id + '/reject', {});
        await approvalRefresh();
      }));
    }
    $('approvals-list').append(card);
  });
  $('integrations-list').replaceChildren();
  integrations.integrations.forEach(principal => {
    const row = element('article', undefined, 'registry');
    row.append(element('strong', principal.name), element('small', principal.id),
      element('p', (principal.revoked_at ? 'Revoked' : 'Expires ' + new Date(principal.expires_at * 1000).toLocaleString())),
      element('pre', JSON.stringify(principal.grants, null, 2)));
    if (!principal.revoked_at) row.append(action('Revoke integration', async () => {
      if (!confirm('Revoke ' + principal.name + '? This denies future admissions; it does not prove remote work stopped.')) return;
      await api('/api/integrations/' + principal.id + '/revoke', {});
      clearIntegrationSecret();
      await approvalRefresh();
    }));
    $('integrations-list').append(row);
  });
  $('integration-operations').replaceChildren();
  receipts.operations.forEach(receipt => $('integration-operations').append(element('pre', JSON.stringify(receipt, null, 2))));
}
form('integration-form', async data => {
  clearIntegrationSecret();
  const grants = JSON.parse($('integration-grants').value || '[]');
  if (!Array.isArray(grants)) throw new Error('Grants must be a JSON list of exact method/path pairs.');
  const payload = {name:data.name, expires_in:Number(data.expires_in)};
  // Empty UI grants request the server's minimal read-only defaults, never wildcard access.
  if (grants.length) payload.grants = grants;
  const result = await api('/api/integrations', payload);
  $('integration-token').value = result.token;
  $('integration-token-area').hidden = false;
  integrationSecretTimer = setTimeout(clearIntegrationSecret, 60000);
  await approvalRefresh();
});
