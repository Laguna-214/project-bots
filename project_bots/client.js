'use strict';
// One authenticated API/client state. No native shell, private offline cache or push service.
let clientInstallEvent = null;
let clientPollBusy = false;
const clientIncidentIds = new Set();
function clientView(view) {
  if (!['chats', 'agents', 'activity', 'security'].includes(view)) return;
  document.body.dataset.mobileView = view;
  document.querySelectorAll('[data-client-view]').forEach(button => {
    button.setAttribute('aria-current', button.dataset.clientView === view ? 'page' : 'false');
  });
}
document.querySelectorAll('[data-client-view]').forEach(button => {
  button.addEventListener('click', event => {
    clientView(button.dataset.clientView);
    if (window.matchMedia('(max-width:700px)').matches) event.preventDefault();
  });
});
clientView('chats');
$('client-stop-all').addEventListener('click', () => $('security-stop-all').click());
$('client-security').addEventListener('click', () => clientView('security'));
function clientConnectivity() {
  $('client-status').textContent = navigator.onLine === false ?
    'Offline · security state unverified. Actions are not queued.' :
    (window.isSecureContext ? 'Web client · backend/security health is shown in Security.' :
      'Web mode · HTTPS or localhost required for installation and notifications.');
}
window.addEventListener('online', clientConnectivity);
window.addEventListener('offline', clientConnectivity);
clientConnectivity();
window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault(); clientInstallEvent = event; $('client-install').hidden = false;
});
$('client-install').addEventListener('click', async () => {
  if (!clientInstallEvent) return;
  const event = clientInstallEvent; clientInstallEvent = null;
  await event.prompt();
  await event.userChoice;
  $('client-install').hidden = true;
});
$('client-notifications').addEventListener('click', async () => {
  if (!window.isSecureContext || !('Notification' in window)) {
    message('Notifications require supported browser and trusted HTTPS/localhost.', true); return;
  }
  const permission = await Notification.requestPermission();
  message(permission === 'granted' ?
    'Notifications enabled while this client remains open. Background push is not configured.' :
    'Notifications not enabled. Security incidents remain visible in the dashboard.');
});
async function clientPoll() {
  if (clientPollBusy || document.hidden || navigator.onLine === false || typeof token === 'undefined' || !token) return;
  clientPollBusy = true;
  try {
    if (typeof chatRefresh === 'function') await chatRefresh();
    const status = await securityRefresh();
    const serious = (status.incidents || []).filter(i => ['high', 'critical'].includes(i.severity) && i.status !== 'recovered');
    $('client-security').textContent = serious.length ? 'Security · ' + serious.length + ' alert(s)' : 'Security';
    serious.forEach(incident => {
      if (!clientIncidentIds.has(incident.id) && window.isSecureContext && 'Notification' in window && Notification.permission === 'granted') {
        // Never put agent names, private evidence, messages or tokens on lock screens.
        const notice = new Notification(incident.severity.toUpperCase() + ' Project Bots security alert',
          {body:'Review Security for evidence and containment outcomes.', tag:incident.id});
        notice.onclick = () => { window.focus(); clientView('security'); notice.close(); };
      }
      clientIncidentIds.add(incident.id);
    });
    if (clientIncidentIds.size > 256) clientIncidentIds.clear();
  } catch (error) {
    $('client-status').textContent = 'Backend/security state unverified · ' + error.message;
  } finally { clientPollBusy = false; }
}
setInterval(clientPoll, 15000);
if (window.isSecureContext && 'serviceWorker' in navigator) {
  navigator.serviceWorker.register('/client-sw.js', {scope:'/', updateViaCache:'none'}).catch(() => {
    message('Web client works, but installation support could not be registered.', true);
  });
}
