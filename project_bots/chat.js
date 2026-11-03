'use strict';
let selectedChat = null;
let selectionGeneration = 0;
let chatCursor = 0;
let pendingMessage = null;
let historyGeneration = 0;
let historyRequest = null;
let renderedSequences = new Set();
function chatMembers(id) {
  return Array.from($(id).selectedOptions, option => option.value);
}
function memberOptions(id, selected = []) {
  $(id).replaceChildren();
  agents.forEach(agent => {
    const option = new Option(agent.name, agent.id);
    option.selected = selected.includes(agent.id);
    $(id).add(option);
  });
}
async function chatHistory(reset = false) {
  if (!selectedChat || (!reset && historyRequest)) return;
  if (reset) historyGeneration++;
  const generation = historyGeneration;
  const id = selectedChat.id;
  const request = {};
  historyRequest = request;
  $('chat-more').disabled = true;
  try {
    const result = await api('/api/chats/' + id + '/messages?after=' + (reset ? 0 : chatCursor));
    if (selectedChat?.id !== id || generation !== historyGeneration) return;
    if (reset) {
      $('chat-history').replaceChildren();
      renderedSequences = new Set();
    }
    result.messages.forEach(item => {
      if (renderedSequences.has(item.sequence)) return;
      renderedSequences.add(item.sequence);
      const line = element('article', undefined, 'chat-line');
      const sender = item.sender === 'admin' ? 'You' : (agents.find(a => a.id === item.sender)?.name || item.sender);
      line.append(element('strong', sender + ' · ' + new Date(item.created_at * 1000).toLocaleString()), element('p', item.content));
      $('chat-history').append(line);
    });
    chatCursor = result.next_after;
    $('chat-more').hidden = !result.has_more;
  } finally {
    if (historyRequest === request) {
      historyRequest = null;
      $('chat-more').disabled = false;
    }
  }
}
async function openChat(chat) {
  selectionGeneration++;
  selectedChat = chat;
  pendingMessage = null;
  $('chat-content').value = '';
  sessionStorage.setItem('project-bots-selected-chat', chat.id);
  $('chat-heading').textContent = chat.title;
  memberOptions('chat-members', chat.agent_ids);
  await chatHistory(true);
}
async function chatRefresh() {
  const [chats, security] = await Promise.all([api('/api/chats'), api('/api/security/events')]);
  $('chats').replaceChildren();
  if (!chats.length) $('chats').append(element('p', 'No chats yet.'));
  chats.forEach(chat => $('chats').append(action(chat.title, () => openChat(chat))));
  memberOptions('chat-create-agents', chatMembers('chat-create-agents'));
  const remembered = selectedChat?.id || sessionStorage.getItem('project-bots-selected-chat');
  const current = chats.find(chat => chat.id === remembered);
  if (current) {
    selectedChat = current;
    $('chat-heading').textContent = current.title;
    memberOptions('chat-members', current.agent_ids);
    await chatHistory(true);
  }
  $('security-events').replaceChildren();
  if (!security.events.length) $('security-events').append(element('p', 'No chat security events recorded. This does not prove runtime protection.'));
  security.events.forEach(event => $('security-events').append(element('p', new Date(event.created_at * 1000).toLocaleString() + ' · ' + event.behavior + ' · ' + event.outcome + ' · ' + event.resource)));
  if (typeof conversationRefresh === 'function') await conversationRefresh();
  if (typeof approvalRefresh === 'function') await approvalRefresh();
}
form('chat-create-form', async data => {
  const chat = await api('/api/chats', {...data, agent_ids: chatMembers('chat-create-agents')});
  $('chat-create-form').reset();
  await openChat(chat);
  await chatRefresh();
});
form('chat-message-form', async data => {
  if (!selectedChat) throw new Error('Select a chat first.');
  // Retain the same ID/content after transport failures; never duplicate a retry.
  if (!pendingMessage || pendingMessage.chat !== selectedChat.id || pendingMessage.content !== data.content) {
    pendingMessage = {chat: selectedChat.id, content: data.content, client_id: operationUUID()};
  }
  const sent = pendingMessage;
  await api('/api/chats/' + sent.chat + '/messages', {client_id: sent.client_id, content: sent.content});
  if (selectedChat?.id === sent.chat && pendingMessage === sent) {
    pendingMessage = null;
    if ($('chat-content').value === sent.content) $('chat-content').value = '';
    await chatHistory(true);
  }
});
form('chat-members-form', async () => {
  if (!selectedChat) throw new Error('Select a chat first.');
  const id = selectedChat.id;
  const generation = selectionGeneration;
  const updated = await api('/api/chats/' + id + '/members', {agent_ids: chatMembers('chat-members')});
  if (selectedChat?.id !== id || selectionGeneration !== generation) return;
  selectedChat = updated;
  await chatRefresh();
});
$('chat-more').addEventListener('click', () => chatHistory().catch(error => message(error.message, true)));
if (token) unlock().catch(() => {
  token = ''; csrf = ''; sessionStorage.removeItem('project-bots-session');
  message('Session unavailable. Pair with the current console code. If already consumed, restart the server for a new code.', true);
});
