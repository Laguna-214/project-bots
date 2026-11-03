# Security backend increment (application/fixture scope only)

No stage is declared complete. The roadmap remains exactly five stages. No live
VM/service was mutated or restarted, no host policy weakened, and no commit/push
was performed.

## Implemented boundary

SQLite schema **v5** adds trusted state, durable global emergency-stop/per-agent
containment latches and incident records while retaining schema-v4 chat. Stop
commits revocation/cancellation before calling external adapters. Repository job
creation/claim/dispatch and worker registration, compute create/start/restart/
resume/snapshot-restore, shared admission and Gateway dispatch recheck relevant
latches; execution also requires fresh trusted coverage. Registry reads, admin
chat investigation, cancellation/shutdown and settings remain reachable.

There is no public health-report endpoint. `SecurityService.observe` is a Python
interface for separately configured trusted telemetry adapters. Required coverage
is `runtime`, `network`, `identity`, `audit`, `enforcer`, each with observation
source/time and bounded TTL. Missing/failed/stale coverage denies execution.
No OS/network adapters are installed, so production protection defaults to
**unavailable/unverified**, not protected. Tests explicitly install fixture
observations in their private test databases; this is not a production bypass.

Incidents persist UUID/time/agent/severity/behavior/resource/evidence, source,
action history, readbacks, acknowledgments and recovery. High/critical reports
latch the agent, disable chat identity, cancel queued/running jobs, leave remote
execution receipts uncertain, and request fixed Machine Manager graceful shutdown
with UUID operation and VM-identity/state readbacks. Confirmed shut-off marks
receipts terminated; late remote results cannot resurrect canceled work.
Every current high/critical outcome remains **partial**, because network isolation
and forced VM destruction are unavailable. Registry-only agents with no configured
worker and no execution receipt have `runtime_shutdown:not_applicable`, not a
fabricated termination. No shell/PID/command input is accepted. A compute operation
already in flight during stop is checked again on return and an owned runtime is
reconciled to shutdown; fixture coverage is not distributed hypervisor fencing.

Recovery is separate from acknowledgment. It requires acknowledgment, fresh trusted
coverage, a verified runtime-stop readback (or verified registry-only absence) and actual configured credential-value
rotation (private fingerprints, never values or fingerprints in API responses).
Unknown prior credential material blocks recovery rather than inventing rotation.
Old credential fingerprints remain revoked. Agent recovery does not clear global
stop; global recovery refuses contained agents. Neither recovery starts workers
nor re-enables chat identities. Administrators must configure new credentials and
separately authorize eventual starts; there is no automatic restart.

## Exact HTTP contract for UI

All routes require existing administrator session+CSRF or existing platform admin
bearer authentication. Chat credentials cannot access them. JSON only for POST.
No typed confirmation string is required; stop can be a single confirmed UI click.

| Method/path | JSON body | Response |
|---|---|---|
| GET `/api/security/status` | — | 200 `{global_stop, protected, coverage, agents, incidents, limitations}` |
| GET `/api/security/incidents` | — | 200 `{incidents:[...]}` |
| GET `/api/security/incidents/{uuid}` | — | 200 incident |
| POST `/api/security/emergency-stop` | `{reason: text}` | 200 full status, including partial actions |
| POST `/api/security/incidents` | `{agent_id:uuid,severity:"information\|warning\|high\|critical",behavior:text,resource:text,evidence:text}` | 201 incident; high/critical immediately contain |
| POST `/api/security/incidents/{uuid}/acknowledge` | `{note:text}` | 200 incident; no unlatch |
| POST `/api/security/incidents/{uuid}/recover` | `{note:text,credential_rotated:true}` | 200 incident after independently checked prerequisites |
| POST `/api/security/recover` | `{note:text}` | 200 status; does not implicitly recover agents |

There is no separate `/security/agents/{id}/contain` route: create an explicit
high/critical incident to stop one. Recovery uses the owning incident UUID.
Conflicting/unsafe admission/recovery returns 409; authentication failure 403;
missing target 404; invalid body 400. Incident fields include `id`, `created_at`,
`agent_id`, `severity`, `behavior`, `resource`, `evidence`, `source`, `status`,
`actions`, `outcome`, `acknowledgments`, and optional `action_history`, `recovery`.
Actions contain `action`, `status`, `readback` (and sanitized `error_kind` on failure).
Coverage entries contain `status` plus available `healthy/source/observed_at/ttl`.
Agent entries contain `agent_id`, `contained`, and available containment/recovery time.

## Reusable admission hooks

```python
from project_bots.security import check_global, check_agent_execution, check_agent_capability
check_global(repository, db=None, require_health=True)
check_agent_execution(repository, agent_id, db=None)
check_agent_capability(repository, agent_id, db=None)  # messaging/queue revocation, not OS telemetry
```

Follow-up integration now makes `check_agent_execution` mandatory against the
workers registry database before queueing/dispatch and during response forwarding
and active watching. Optional external hooks are additive, never a bypass. Actual
HTTP tests cover unavailable coverage, global/per-agent stop, queued revocation,
active interruption and restored old credentials. Owner cancellation and admin
investigation remain available. See INFERENCE_INCREMENT.md.

`db` and `require_health` are keyword-only. Hooks are read-only and raise
`service.ConflictError`; supplied `db` makes checks atomic with the caller's SQLite
mutation. Gateway raw dispatch now requires `repository=` and rejects omission.
Trusted code can instantiate `SecurityService(repository, compute_request)` with
the existing PlatformService compute-request adapter. No arbitrary shell or runtime
control channel is added.

## Independent reconciler

`python -m project_bots.security --db /PRIVATE/path/platform.db [--once] [--interval 2]`

The standalone process reads durable state, refreshes only its own enforcer heartbeat,
contains configured workers when required coverage is missing, and reconciles owned
containment incidents through fixed Machine Manager GET/shutdown/GET. It does not
start anything, accept arbitrary commands/PIDs, or accept unauthenticated IPC.
This is opt-in source functionality, **not an installed/restarted live service**.
It shares trusted DB/service-UID authority; distinct privileged identities, protected
IPC, an external watchdog of this process, immutable audit and host containment
remain unimplemented. A crash may leave existing work running until an independent
reconciler returns; fail-safe admission alone is not runtime termination.

## Files and verification

Production changed: `project_bots/security.py` (new), `repository.py`, `service.py`,
`workers.py`, `platform_web.py`, `chat.py`. No inference module, dashboard or CLI edit
belongs to this security increment. Existing fixture files updated explicitly for
required trusted coverage/schema-v5: `tests/test_platform.py`, `test_workers.py`,
`test_machine.py`, `test_scheduler.py`, `test_chat.py`. New:
`tests/security_fixtures.py`, `test_security.py`, `test_security_http.py`,
`test_security_enforcer.py`, and this document.

Executed RED→GREEN tests include missing security module/routes, credential
re-enable bypass, late result resurrection, raw Gateway bypass, monitor-loss
reconciliation, and false credential-rotation assertions. Installed executable
HTTP tests restart the actual private fixture process and re-read latches/incidents.
Independent-enforcer fixture uses a real disposable subprocess, authenticated HTTP
Machine Manager fixture, actual termination and state readbacks, enforcer process
restart, blocked API restart, explicit recovery and old-credential rejection.

Latest executed commands (concurrent tree may contain other increments):

- `python3 -m unittest discover -s tests -p 'test_security*.py' -v`: **15 passed**.
- `python3 -m unittest discover -s tests -q`: **142 discovered; 141 passed, 1 optional skip**.
  Full-suite ResourceWarnings about SQLite connections were observed; their source
  was not isolated in this increment. The security-specific suite is clean. Counts will change as
  concurrent work lands; parent must rerun final whole-tree verification.
- `git diff --check`: passed.

These are application/HTTP/subprocess fixtures, not the S01–S15 malicious acceptance
chain. Actual OS exec/privilege/filesystem/escape monitoring, packet-level default
deny/peer isolation, direct raw endpoint prevention, forced critical VM destruction,
external tamper-resistant evidence/notifications, distinct service identities,
short-lived credential issuance and hostile-runtime race/containment acceptance
are **unimplemented or unverified**, never simulated passes.
