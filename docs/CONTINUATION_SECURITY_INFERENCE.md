# Continuation — security, shared inference and recovery

## State

Working tree continues from `3091edd` with the earlier chat increment intact.
No stage is declared complete. Exactly five stages remain; see
IMPLEMENTATION_PLAN.md. Changes are source-tested, uncommitted and undeployed.
No existing worker/domain/service/model state or Hermes configuration was changed.

## Implemented

- `security.py`, `repository.py`, `service.py`, `workers.py`, `chat.py`,
  `platform_web.py`: schema v5 incidents/security state; durable global and
  per-agent containment latches; job cancellation; disabled messaging;
  execution admission at repository/service/dispatch boundaries; independent
  graceful-shutdown reconciliation; exact runtime identity/state readbacks;
  evidence/action history; acknowledgment and explicit credential-rotation-gated
  recovery without automatic startup.
- `llama_proxy.py`, `models.py`, `inference_scheduler.py`: one shared llama.cpp
  backend, durable per-agent fair turns/aging, trusted priority, bounded queue/
  concurrency/rate/token admission, per-profile output/context controls, owner
  cancellation, metadata-only logs and retained uncertain backend reservations.
  Mandatory security checks use the workers registry DB before queue/dispatch,
  during forwarding and active watching. Optional checks are additive; unknown
  agents, missing coverage and contained agents deny. Separate inference references
  must match the registered identity, preventing credential-map recovery bypass.
- `security.js`, `dashboard.html`, `dashboard.js`, static asset route: administrator
  stop-one/stop-all, real coverage and partial outcomes, incident evidence,
  acknowledgment/recovery controls, safe text rendering, stale-response guards,
  and no claim of successful network/runtime containment from a latched flag.
- `backup.py`, `cli.py`: private validated SQLite online backup and restore to NEW
  offline destinations only; committed WAL state retained; corrupt/symlink/
  nonprivate/overwrite attempts rejected. No automatic service/runtime activation.
- README, API, architecture, deployment, implementation plan/status and dedicated
  security/inference/recovery documents describe current scope and limitations.

Tests added/updated include `test_security.py`, `test_security_http.py`,
`test_security_enforcer.py`, `security_fixtures.py`, `test_shared_inference.py`,
`test_inference_scheduler.py`, `test_inference_proxy.py`, `test_backup.py`,
`test_platform.py`, worker/machine/scheduler/chat fixtures and `security_ui.cjs`.
Earlier chat production/tests remain part of this dirty tree; preserve them.

## Parent-verified final execution

```sh
python3 -W always -m unittest discover -s tests -q
node --check project_bots/dashboard.js
node --check project_bots/chat.js
node --check project_bots/security.js
node tests/dashboard_vm.cjs
node tests/chat_ui.cjs
node tests/security_ui.cjs
git diff --check
```

Final Python run: **150 tests, OK with one optional skip**, 55.600 seconds.
All three Node interaction suites, syntax checks and whitespace validation passed.
Earlier SQLite ResourceWarnings were traced to backup test connections whose
transaction contexts did not close the connections; fixtures now close explicitly.
The final warnings-enabled full run emitted no warning lines.

Real installed-CLI/HTTP/SQLite/restart fixtures demonstrate persistence and
application authorization, stop/recovery, old-token rejection and failure handling.
The independent enforcer fixture terminates a real disposable child through an
authenticated fixture Machine Manager and verifies no self-restart. It is **not**
a real hypervisor, packet-isolation, sandbox-escape or hostile-VM acceptance test.
Node suites use fake DOM/API, not a visual-browser/native-app acceptance.

Four registered fixture agents used one actual local HTTP FIXTURE backend:
concurrency 1 peak 1, 4.836 requests/s; concurrency 2 peak 2, 6.582 requests/s.
These values measure artificial fixture delays and framework overhead, not model
speed/GPU throughput. They do not justify increasing production concurrency.
The required four-real-agent/one-loaded-model acceptance is still NOT RUN.

Full local test log:
`/home/server1/.hermes/profiles/project-bot/cache/scratch/project-bots-final-tests.log`
(transient scratch, not a committed permanent evidence archive).

## Mandatory incomplete work and release blockers

1. Real trusted OS/VM/process/filesystem/network monitors, default-deny packet
   isolation and direct-peer/broker-bypass enforcement are not installed or proven.
2. Machine Manager offers graceful shutdown only; critical force-termination and
   verified network isolation remain unavailable. Incidents intentionally say
   `partial`, never fully contained. No protected external watchdog or immutable
   external audit store is implemented. Shared trusted UID/DB is not independence
   against host compromise.
3. Required five coverage adapters default unavailable. New execution/inference
   fails closed. Do not fake `SecurityService.observe` values in production to
   restore functionality. The enforcer is opt-in and can request shutdown, not a
   harmless live-read command.
4. Actual four worker VMs were previously observed shut off and remain untouched.
   Real loaded-model context/memory/history/permission isolation, fresh RX6800
   Vulkan/GPU/CPU telemetry, continuous batching and hardware benchmarks are pending.
5. All 15 malicious-agent denial/detection/incident/containment/evidence chains need
   real disposable-host acceptance. App fixtures do not close these gates.
6. Automatic conversational replies/context-memory assembly and runtime message
   delivery, full human approval workflows, short-lived identity issuer, full
   multi-user RBAC, notifications, and native mobile/desktop clients remain unfinished.
7. Private database backup/restore is tested; complete VM/model/secret/environment
   disaster recovery, real upgrade/rollback and release acceptance remain pending.

## Next work boundary

Review the dirty changes before any commit/push or installation. No blanket
`git add .`, live restart, worker startup or host-policy broadening. Keep existing
VMs and the unknown stopped domain. Integrate trusted host/network adapters with
separate least-privilege identities and administrator-reviewed host prerequisites;
then authorize disposable-only enforcement and four-agent model acceptance.
Do not represent unfinished code/client work as merely a permission blocker.
No native app or production security completion claim is justified.
