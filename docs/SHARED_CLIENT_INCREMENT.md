# Shared web, mobile and desktop client increment

This increment preserves one backend/API and business logic. It delivers a
responsive **web client with installable-PWA support**, not native iOS/Android or
Electron applications and not app-store publication.

## User experience

- At phone width, primary navigation is Chats, Agents and Activity, with separate
  Security alerts and immediate Stop all access. Normal phone views hide VM,
  network, model-server and machine-administration panels. Desktop width retains
  the complete web administration view.
- Security and chat metadata refresh while the authenticated client is visible.
  Notifications require explicit browser permission and secure context. Lock-screen
  messages omit private evidence, conversations, agent names and credentials.
- The browser may install the PWA when it supports the manifest/service worker.
  Installation prompts, support and OS behavior differ; iOS/Android installation
  has not been exercised. No automatic filesystem/terminal integration is added.
- A closed browser does not stop the backend or separately launched chat/security
  services. However, **background push is not implemented**: notifications here
  require an open, active client. Do not treat this as an always-on incident pager.

## Network and transport

The service worker is network-only: no private offline cache, queued mutations,
credential storage or successful-looking stale security state. An unreachable
backend returns 503 and explicitly states no action was queued. A disconnected
client cannot prove whether an earlier remote mutation completed; retain IDs and
inspect after reconnection.

For a phone on a private network, use an administrator-provisioned certificate
trusted by that device, with the actual private IP in its subject alternative names:

```sh
project-bots serve --host YOUR_PRIVATE_IP --port 8032 \
  --tls-cert /private/server-chain.pem --tls-key /private/server-key.pem
```

Certificate and key are both required. TLS uses a minimum of TLS1.2. Browser
Origin/CSRF validation derives HTTPS only from the actual TLS socket, never
untrusted forwarded headers. Existing HTTP loopback/SSH workflows remain available.
Do not dismiss certificate warnings or disable validation to deploy the phone UI.
Arbitrary DNS Host names remain unsupported by existing host policy: use the actual
private IP or localhost. Certificates/keys and trust distribution are administrator
prerequisites, not provisioned automatically by this update.

## Files

`client.js`, `client-sw.js`, `manifest.webmanifest`, `client-icon.svg`,
`dashboard.html`, `security.js`, static asset routes/HTTPS listener in
`platform_web.py`, HTTPS CLI arguments in `cli.py`, TLS-origin/CSP changes in
`web.py`; `tests/test_client.py`, `tests/test_https_client.py`, `tests/client_ui.cjs`.

## Executed checks

- Actual installed HTTPS executable with disposable certificate: trusted HTTPS
  page and pairing/session flow; wrong HTTP Origin denied; missing CSRF denied;
  correct CSRF agent registration accepted; untrusted certificate refused by the
  client. Test keys/certificates belong only to temporary test homes.
- Real local HTTP static/manifest/CSP contracts and Node client interactions pass.
- A real browser loaded an actual disposable Project Bots backend. DOM/computed
  layout at **390px** showed document width 390, Chats visible, Agents hidden and
  both advanced containers hidden; clicking Agents switched panels correctly.
  At **1280px**, advanced containers returned to display:block with no horizontal
  document overflow. Authentication was not exercised through this browser: the
  fixture's platform/pairing visibility was changed only for layout inspection.
  Installed HTTP tests cover authentication separately.
- Real browser service-worker registration became active with **zero CacheStorage
  stores**. After stopping only the disposable fixture server, an actual browser
  fetch returned **503** with the offline/no-queued-action response; CacheStorage
  remained empty. No existing production service was stopped or restarted.
- Native OS installation, visual screenshot review, background push, real-device
  notification delivery, accessibility audit and native shell integrations are
  not accepted by these checks.
