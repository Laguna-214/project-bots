# Implementation status

## Scope and baseline audit

Stage 1 only. The prior tracked-file audit found a Python standard-library CLI, provider JSON configuration, LAN setup UI/pairing, installer, revision-aware updater and cautious/idempotent uninstaller. Baseline `70fcc55` had **11 passing unittest tests**, no SQLite persistence, agent/machine registry, durable jobs, main dashboard, or compute runtime. The implementation preserves those existing commands and scripts; provider config is not reused as platform state.

This is a software implementation/test result, **not a hardware or network deployment report**. User-provided intended hosts are:

- Management: EliteDesk, Ubuntu, i5-9500, 16 GB RAM.
- Separate compute: Ubuntu Desktop gaming PC, i7-12700K, 64 GB RAM, RX 6800 16 GB plus UHD 770; shared Ollama and libvirt are later-stage targets.

Neither host was probed. Example `10.0.50.10` / `10.0.50.30` addresses are placeholders, not verified addresses. No connectivity, inference compatibility, GPU utilization, virtualization capability, network layout, or available capacity is claimed.

## Shipped Stage 1

- `project-bots serve`: loopback by default on port 8032, explicit `--host`/`--port` for trusted LAN/alternate-port use.
- SQLite schema migration v0→v1 in one transaction, version guard, private database/directory, bound SQL parameters, FK enforcement. New connections are closed after every operation.
- Persistent machines: UUID, name, configurable endpoint, optional credential environment reference, always **unverified**.
- Persistent agents: UUID, name, role, narrow non-secret config, optional assigned machine, always **registered**. These statuses never imply a running worker.
- Durable jobs: UUID, input, assignment, queued/running/succeeded/failed/canceled state, latest progress/message/result/error; validated transitions, terminal-state protection, atomic claim under a serialized write transaction. Claims do not execute tasks.
- Service/repository boundary: HTTP routes call application rules; SQL/transactions live only in `SQLiteRepository`. A future Postgres repository can implement the same insert/list/get/settings/atomic-mutation contract without coupling services to SQLite SQL. No Postgres adapter is shipped.
- Responsive dashboard: register machines and agents, create/assign/cancel jobs, inspect input/progress/results/failure, change platform settings, explicit refresh. Empty state works with no machine at all.
- Legacy pairing adapted without replacing provider setup: 8 digits, 600-second deadline, one successful consumption, five incorrect attempts then lock, strong in-memory bearer. New dashboard uses per-tab sessionStorage for refresh continuity; restart invalidates the session. Legacy page retains memory-only/restart-on-refresh behavior.
- Host/Origin/custom-origin and CSRF checks for browser operations, no CORS permission, CSP, no request logging, generic validation errors that do not reflect submitted credential values.
- Optional administrative machine API credential resolved only from an environment-variable reference, disabled when unset/under 32 characters. Machine auth refuses browser Origin/fetch metadata instead of creating a CSRF escape hatch. Variable names, not values, are stored/returned.
- Local inference endpoint setting defaults to loopback Ollama; **no connection is made** and cloud fallback is fixed false. Existing cloud provider setup remains inert configuration, never an automatic runtime fallback.
- `PROJECT_BOTS_DB` and existing `PROJECT_BOTS_CONFIG` path overrides. Registry/settings and provider JSON remain separate. Installer/update/uninstaller scripts are unchanged; retained database/config are not deleted.

## Verification and TDD

Development used red→green vertical slices: machine persistence/private schema; validated agents/FKs; durable job lifecycle; transition/concurrent-claim rules; settings; installed CLI/HTTP restart persistence; machine auth/browser guards; dashboard forms/client; malformed Unicode/multiline handling. Tests were run failing before each production slice, then the full suite was rerun. Extra acceptance tests exercise already implemented boundaries rather than introducing untested behavior.

```sh
python3 -m unittest discover -s tests -v
node --check project_bots/dashboard.js  # optional, no Node runtime dependency
# From a git checkout:
git diff --check
```

Current suite: **22 tests**, including the original 11. Acceptance tests install to a temporary HOME, launch the installed executable through HTTP, pair, register machine/agent, create/assign/claim/progress/complete jobs, stop and restart against the same DB, re-pair, and read identical persistent records. Further tests cover failure/cancellation, HTTP and repository eight-way claim races (one winner), bad UUIDs/FKs/inputs, unauthorized/Host/Origin/CSRF rejection, malformed JSON/Unicode, oversized bodies, short machine credentials, terminal transitions, and absence of API credential values in responses/server output. Existing update tests use a disposable local Git origin; no deployment/update against the production remote was performed in this change.

A real browser paired successfully, submitted machine/agent/job forms, displayed the new records and system status, and retained its session across a same-tab reload. At 390px mobile width, document scroll width matched viewport width (no horizontal overflow). Installed HTTP acceptance tests independently verify persistence across server restart. Screenshot capture timed out; no screenshot-based visual review is claimed. There are no fabricated worker/inference/hardware test results.

## Design choices and limitations

1. **Metadata only.** No endpoint is contacted, VM created, agent launched, model downloaded, provider called, or host changed. Administrative clients can manually report progress/results; those reports are not evidence a worker exists.
2. **Local single administrator.** One process-local browser session, no accounts/RBAC or per-machine scopes. Machine tokens have full API administrative privilege. There is no claim lease, ownership authentication, heartbeat, retry, scheduler, worker reconciliation, or cancellation signal.
3. **Trusted transport required.** Stdlib HTTP is plaintext; prefer loopback plus SSH forwarding. No public-facing hardening, TLS listener, rate limiting beyond pairing attempts, reverse-proxy support contract, or IPv6 listener. Numeric private/loopback Host values or localhost only; arbitrary DNS names are not accepted.
4. **Small deployment persistence.** SQLite transactions serialize mutations (including claim validation) for correctness. Reads also use the repository transaction helper; suitable for small local control-plane traffic, not high throughput. JSON payloads preserve narrow records alongside SQL UUID/FK columns. Collections are unpaginated; no retention, timestamps/event history, import/export, deletion or editing registry records is implemented. Back up while stopped.
5. **Private data, not encrypted data.** DB mode 0600, dedicated parent 0700; overrides must use a dedicated private directory. An existing parent with group/other permissions is rejected without modifying it (regression-tested). No encryption at rest. Task/result text deliberately persists and is visible to authorized administrators: never submit secrets there. Credential values are not accepted as credential settings.
6. **Restart semantics.** Durable job/registry/settings state remains. Browser bearer is revoked. Running jobs stay running until explicitly completed/failed/canceled through the API; nothing silently resumes or retries them. Platform and legacy setup cannot share the same listening port simultaneously.
7. **No cloud fallback.** Platform setting cannot enable it. Old provider presets are preserved for compatibility, but there is no inference engine and no automatic cloud send.

## Exact next Stage 2 work — not implemented

Stage 2 should add the **compute-host VM management boundary only**, preserving this working metadata platform. It must be explicitly authorized and executed on the actual Ubuntu Desktop compute PC, not assumed from example addresses:

1. Confirm real management/compute addresses, routing, intended trusted transport and administrator approval; inspect the actual Ubuntu Desktop version, CPU virtualization flags/KVM availability, storage capacity, and existing libvirt/Ollama installations without disrupting desktop use. Record discovered values; do not substitute `10.0.50.*` examples.
2. Establish KVM/QEMU/libvirt on the Ubuntu Desktop compute PC with administrator approval, least-privilege service identity, reviewed storage pool, and an explicit VM resource/network policy. Do **not** replace the desktop with Proxmox, expose the raw libvirt socket/TCP API, grant generic remote shell, or configure GPU passthrough. Shared host Ollama should retain access to host GPU resources; no GPU or backend compatibility is assumed until tested separately.
3. Specify and implement a **narrow authenticated compute service**: health/capabilities, list/detail, provision from an allowlisted Ubuntu template, and start/stop/delete only managed VMs. Use a managed-VM identifier namespace, explicit input/resource limits, template/image allowlists, idempotent operations and durable operation records. No arbitrary commands, domain XML, file paths, libvirt methods or shell strings accepted from clients.
4. Protect that service with approved TLS/mTLS or an explicitly documented SSH transport, credential references and rotation, binding/firewall restricted to the management host. Read compute credentials from a private environment/file provider, never browser values or database secrets. Define timeouts and safe redacted errors.
5. Add a management-side adapter behind a service interface. Persist provisioning intent and actual managed VM IDs/status, separating **desired** from **observed** state. Reconcile safely after restarts/timeouts and mark a machine verified only after an actual authenticated capability check. Keep all external calls out of the SQLite repository and avoid blocking DB transactions across network calls.
6. TDD adapter/contracts with a local fake HTTP compute service, then opt-in integration against an administrator-approved disposable libvirt test VM on the actual compute host. Exercise auth rejection, allowlists/limits, create/start/stop/delete, duplicate requests, unreachable host, partial failure and reconciliation. Do not describe a fake-service test as real hardware validation.
7. Surface real VM status and narrowly scoped lifecycle controls in the dashboard only after those operations work. Document installation/rollback and destructive-operation confirmation; require an explicit Stage 2 acceptance review before moving to workers.

## Stages 3–5 — all not implemented

- **Stage 3:** per-VM **OpenClaw** worker bootstrap/runtime and lifecycle, real worker identity/permissions, heartbeats, lease/claim ownership, results/cancellation handling, shared host-local Ollama integration and measured resource limits. No OpenClaw worker exists in Stage 1.
- **Stage 4:** **Hermes remains the user's assistant**, connected through a narrow authenticated MCP surface for approved workforce operations. No Hermes configuration, skill, plugin, service or MCP installation was changed by this implementation.
- **Stage 5:** orchestration/approval/reliability/operational hardening after the earlier stages are working and accepted. No autonomous multi-agent workforce, scheduling, recovery or public multi-user product is claimed here.
