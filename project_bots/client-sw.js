'use strict';
// Network-only: never retain authenticated pages, tokens, messages or action queues.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  if (new URL(event.request.url).origin !== self.location.origin) return;
  event.respondWith(fetch(event.request, {cache:'no-store'}).catch(() =>
    new Response(JSON.stringify({error:'Project Bots is offline. No action was queued; verify uncertain outcomes after reconnecting.'}),
      {status:503, headers:{'Content-Type':'application/json', 'Cache-Control':'no-store'}})));
});
