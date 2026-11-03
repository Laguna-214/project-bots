# Architecture: observed source and required boundaries

Read with [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md). **Observed** means inspected working-tree source/tests, not live deployment or a fresh passing test. **Required** means target behavior, not a security claim.

## Observed implementation

| Boundary | Source and behavior | Limitation |
|---|---|---|
| Web/API | `platform_web.py`, `web.py`, `dashboard.html/js`: stdlib threaded HTTP server, browser pairing/session/CSRF/host-origin guards, separate environment-reference machine bearer, authenticated platform routes | Security controls are source/fixture-tested, not visual/mobile/native or full approval acceptance. HTTP is for private loopback/trusted tunnel use, not exposed deployment. |
| Domain | `service.py`: registry, settings, atomic job transitions, compute routing, explicit worker binding/dispatch, identity/model preflights | Registration is metadata. Confirmation text is intent validation, not human approval. |
| Persistence | `repository.py`: private directory/database, foreign keys, `BEGIN IMMEDIATE` transactions; schema 1 registry/jobs/settings, 2 workers/executions, 3 admission, 4 chat metadata, 5 durable security state/incidents | Same SQLite store/service authority is not an independently protected audit store. Only isolated fixture databases were migrated, not live databases. |
| Security | `security.py`: per-agent/global latches, health-gated admission, incident/evidence/action histories, explicit recovery and independent reconciliation process; `security.js` exposes administrator controls | No installed OS/network monitors, packet isolation, forced VM termination, protected watchdog or external immutable audit. Outcomes remain partial. See SECURITY_INCREMENT.md. |
| Compute | `compute.py`, `machine_http.py`, `machine_client.py`: owned VM operations, trusted template policy, operation UUIDs/idempotency, lifecycle and offline resource/snapshot guards | Unit tests largely mock commands; no live VM/escape/network enforcement acceptance follows from them. |
| Worker | `workers.py`, `provision.py`, `guest_bootstrap.py`, `worker_health.py`: separate OpenClaw Gateway configurations, credential references, role/tool policies, identity/profile checks | Runtime settings/prompts do not prove adversarial isolation. `gateway_run` sends job input with job-scoped user ID and generation parameters; source alone does not prove private-memory/context assembly or end-to-end isolation. |
| Inference | `models.py`, `inference_proxy.py`, `llama_proxy.py`, `llama_store.py`: centralized local model/broker operations, bounded transport, model/profile validation, memory reservation estimates | Admission is not measured host/GPU quota; model inventory is not GPU-use evidence. |
| Scheduling | `inference_scheduler.SharedScheduler` plus `models.DurableAdmission`: durable per-agent turns, trusted priority/aging, bounded concurrency/queue/rate/token admission, owner cancellation and retained uncertain reservations | Default concurrency one. Token estimates are conservative bytes, not exact tokenization. Interrupted forwarding does not establish actual backend generation termination; no real-model concurrency benchmark yet. |
| Adapter | `mcp_server.py`: typed MCP interface delegates to authenticated backend | Optional client, not backend owner/enforcer. SDK initialize/list/call is not Hermes-native integration acceptance or product completion. |

### In-progress message broker

`chat.py` is a separate logical message service on the platform API and SQLite database, **not** the inference broker. Schema v4 adds `chats`, `chat_members`, `chat_messages`, `chat_identities`, `security_events`.

- Individual conversations require one agent; groups allow distinct configured members. Admin creates conversations/configures membership and identities.
- Agent identity resolves a separate environment-referenced bearer; authentication rejects duplicate matching token values and reuse of configured platform/worker authority. This is not a short-lived credential service.
- Non-admin routes are restricted to conversation listing and message read/send. Sender derives from the authenticated actor, not a payload field.
- Membership plus enabled identity are checked in the message transaction; removal/revocation denies subsequent access. Existing implementation exposes retained conversation history to newly added members. Product policy must explicitly confirm or restrict this before broader release.
- Messages persist with sequence cursors, bounded history pages and `(chat_id, sender, client_id)` idempotency; conflicting retries fail. Lists are capped, not a complete pagination implementation.
- Security records contain metadata (UUID/time/actor/behavior/resource/outcome), not message bodies. They lack incident severity/state/actions/evidence integrity and are not an external incident engine.
- There is no automatic model response, runtime message delivery loop, private memory sharing, full credential lifecycle or network prevention of out-of-band channels here.

`tests/test_platform.py` contains installed fixture HTTP contracts for chat persistence/restart, sender spoof-field rejection, membership filtering, unauthorized send/read/admin routes, immediate member/identity revocation, event metadata, schema migration, browser guards and atomic claims. `tests/test_scheduler.py` covers priority order, queue timeout, cross-process admission and retained uncertainty. `tests/test_workers.py` covers mocked dispatch receipts, role policies and preflights; `tests/test_machine.py` explicitly labels mocked libvirt contracts. These are useful contracts, **not** a real hostile-VM security suite. The full executed suite and review regressions are recorded in [the handoff](PRODUCT_UPDATE_2026-11-02.md).

## Required target topology

```text
Responsive web / future native clients / optional Hermes-MCP
                         |
              Authenticated backend API
           identity + authz + approvals + state
             /             |                 \
  Message broker      Job scheduler       Admin control
  sender/membership   per-agent budgets   durable stop latch
  recipient policy    fairness/cancel     recovery authority
       |                   |                  |
       |          private inference broker    Machine Manager
       |                   |                  |
       |       one selected loaded llama.cpp  VM lifecycle/enforcer
       |       server, shared by four agents  |
       +-------- independent agent VMs --------+
                  |
      external runtime/network/identity monitors
                  |
      deterministic incident/containment engine
                  |
       protected external evidence + dashboard
```

These are logical boundaries; separate identity, privilege, storage and network enforcement are required even if initial application components share a process. Do not give an agent backend/admin, hypervisor, model-management, monitor or audit authority.

## Required data and trust flows

1. **Control:** authenticated operator request → backend authorization/approval → bounded internal API → Machine Manager/enforcer → read back exact operation and resource state. Persist intent/outcome and unknown states; never retry an uncertain mutation with a fresh ID.
2. **Inference:** authorized queued job → health/security/stop-latch checks → fair admission and context assembly → per-agent authorized inference route → one loaded server → agent-private result/history. Broker credentials bind caller/model/limits; agents cannot reach model administration. Share weights, not private contexts; prevent cross-request cache/session leakage.
3. **Messaging:** agent credential → authenticated sender → current membership and recipient visibility → durable explicit message → authorized recipients. Network controls deny direct peers, alternate listeners/services, bypass and unauthorized transfers. Membership grants no file/tool/secret access.
4. **Security:** trusted OS/VM/network/control telemetry → deterministic rules/anomalies → incident UUID/evidence → severity policy → credential revocation, network isolation, job cancellation/start denial, runtime stop and critical VM termination → independent readbacks/notification. Keep failures/uncertainty visible, retain management/security reachability.
5. **Recovery:** explicit admin investigation and remediation → policy/config/monitor integrity and credential rotation → verified recovery conditions → deliberate latch release. Acknowledge alone cannot release containment; agents cannot self-restart.

Default-deny segmentation must isolate clients, backend, message/inference brokers, Machine Manager, monitors/audit and each runtime. Trusted service identities need narrow authenticated internal APIs and short-lived credentials. Required monitor heartbeat/config integrity failures stop admission and contain active agents; no unmonitored fallback.

## Evidence caveats and preserved history

The inherited baseline `3091edd` subject claimed completion but did not establish these gates. [The corrected MCP checkpoint](STAGE4_MCP_CHECKPOINT.md) recovers useful bounded evidence from `2251905:docs/STAGE4_MCP_CHECKPOINT.md`, replaced by `91f08b0`. It distinguishes historical MCP job/read-tool evidence from blocked disposable lifecycle and pending native wiring. Do not erase that distinction or rerun its one-shot mutation harnesses blindly.

The **32 GiB setting is configurable application admission policy** (`PROJECT_BOTS_COMPUTE_RAM_CAP`), not proof of physical RAM or an AppArmor-enforced ceiling. Historical reports of capacity, runtime health or model loading are time-bound. [Fresh read-only deployment observations](DEPLOYMENT.md) found stopped worker domains and a loaded-model report lacking trustworthy memory accounting. No host/VM/service/Hermes mutation or fresh GPU workload verification was performed.
