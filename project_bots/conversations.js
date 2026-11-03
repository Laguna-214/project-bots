'use strict';
// Administrator configures enrollment; workers never acquire admin API authority.
let conversationLoadVersion = 0;
async function conversationRefresh() {
  options($('conversation-agent'), agents, 'Select an agent');
  const jobs = await api('/api/conversations/jobs');
  $('conversation-jobs').replaceChildren();
  if (!jobs.length) $('conversation-jobs').append(element('p', 'No conversational reply jobs recorded.'));
  jobs.slice().reverse().forEach(job => {
    const row = element('article', undefined, 'registry');
    const name = agents.find(a => a.id === job.agent_id)?.name || job.agent_id;
    row.append(element('strong', name + ' · ' + job.status),
      element('small', job.id), element('small', 'Conversation ' + job.chat_id));
    if (['running', 'cancelling', 'uncertain'].includes(job.status)) {
      row.append(element('p', 'A remote request may still be active. Uncertain work is not retried automatically.'));
    }
    if (['queued', 'running'].includes(job.status)) {
      row.append(action('Cancel reply', async () => {
        await api('/api/conversations/jobs/' + job.id + '/cancel', {});
        message('Reply cancellation requested; this is not proof remote generation stopped.');
        await conversationRefresh();
      }));
    }
    $('conversation-jobs').append(row);
  });
}
$('conversation-load').addEventListener('click', async () => {
  const id = $('conversation-agent').value;
  if (!id) { message('Select an agent first.', true); return; }
  const version = ++conversationLoadVersion;
  try {
    const config = await api('/api/agents/' + id + '/conversation');
    if (version !== conversationLoadVersion || $('conversation-agent').value !== id) return;
    $('conversation-instructions').value = config.system_instructions;
    $('conversation-memory').value = config.memory;
    $('conversation-budget').value = config.max_replies;
    $('conversation-enabled').checked = config.enabled;
  } catch (error) { message(error.message + '. An unenrolled agent must be explicitly configured before it can reply.', true); }
});
$('conversation-agent').addEventListener('change', () => {
  ++conversationLoadVersion;
  $('conversation-instructions').value = '';
  $('conversation-memory').value = '';
  $('conversation-enabled').checked = false;
  $('conversation-budget').value = 8;
});
$('conversation-form').addEventListener('input', () => { ++conversationLoadVersion; });
form('conversation-form', async data => {
  ++conversationLoadVersion;
  if (!data.agent_id) throw new Error('Select an agent.');
  const payload = {enabled:$('conversation-enabled').checked,
    system_instructions:data.system_instructions, memory:data.memory || '', tools:[],
    max_replies:Number(data.max_replies)};
  await api('/api/agents/' + data.agent_id + '/conversation', payload);
  message('Enrollment saved. Replies require a separately running trusted runner, independent credentials and verified security coverage.');
  await conversationRefresh();
});
