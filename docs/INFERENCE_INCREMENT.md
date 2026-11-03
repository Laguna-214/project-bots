# Shared inference increment — 2026-11-02

## Scope and changed files

This is a source/fixture-tested increment, **not a deployment or real-model/GPU
acceptance**. Existing llama.cpp router, GGUF registry, RX6800 Vulkan architecture,
model store, four preserved VMs and existing dirty chat/UI work are retained.
No VM/service restart, host-policy change, model download or Hermes edit occurred.
No commit or push was made.

Changed by the inference workstream:

- `project_bots/llama_proxy.py`
- `project_bots/models.py` (optional bounded native-read timeout only)
- `project_bots/inference_scheduler.py` (new)
- `tests/test_inference_scheduler.py` (new)
- `tests/test_shared_inference.py` (new)
- `docs/INFERENCE_INCREMENT.md` (new; this file)

`inference_proxy.py` remains the compatibility entry point; `llama_store.py` is
unchanged. This workstream did not edit security-owned repository, workers,
service, chat or platform HTTP code. Other concurrent work changes those files.

## Implemented behavior

- One existing shared upstream and centrally assigned model profiles; no agent
  subprocess/model copy, Ollama migration, provider fallback or session pool.
- SQLite-coordinated concurrency, memory reservations, global queue bound,
  per-agent active/queued bounds, rolling 60-second request/token admission budgets.
  Full profile memory reservations are intentionally conservative, not measured
  VRAM, and may keep actual concurrency below the configured maximum.
- Least-recently-served agent turns; trusted profile priority breaks equal-turn
  ties. Once a queued request ages past the starvation threshold, oldest eligible
  aged work wins over priority. This deliberately prioritizes fairness over an
  unlimited stream of interactive work. Request JSON cannot set priority.
- Profile output/temperature enforcement; conservative UTF-8 serialized context +
  tools + template reserve + output admission estimate. This is **not an exact
  model tokenizer/template measurement**; backend context allocation remains the
  centrally registered preset. Oversized requests are rejected before dispatch.
- Request identity derives exclusively from unique strong bearer credentials.
  Duplicate/equal-valued agent credentials, protected admin/backend aliases and
  custom-admin/Gateway aliasing are denied. Model management stays admin-only;
  admin credentials cannot run agent inference. Worker/profile changes are
  rechecked before dispatch and during execution.
- An optional independent inference-only credential map rejects legacy Gateway
  credentials and equal-valued Gateway aliases. Missing configured agent entries
  deny authentication rather than falling back. Without this map, legacy
  per-worker Gateway/inference credential coupling remains for compatibility;
  **the live installation has not been decoupled by these source edits**.
- Queued cancellation prevents dispatch; active cancellation/revocation suppresses
  further forwarding and interrupts a blocked established response read. Before
  upstream response headers exist, interruption may wait until the backend socket
  deadline. Socket disconnection is never claimed as verified model cancellation.
- Backend execution deadlines, bounded response bytes, truncated fixed-length
  response detection; metadata-only request logs contain UUID, authenticated
  agent ID, registered model, admission token estimate, status and elapsed time,
  never prompts, tool definitions, memory, output or bearer values.
- Model load/unload/download/removal reserve the whole configured broker memory
  budget to exclude overlapping inference even with concurrency greater than one.
  Existing asynchronous router transition readbacks and pinned store rules remain.

## Configuration / security integration contract

The executable remains `python3 -m project_bots.inference_proxy`. New options:

| Option | Default |
|---|---:|
| `--memory-mib` | 8192 |
| `--concurrency` | **1** |
| `--queue-limit` | 4 |
| `--queue-timeout` | 30 seconds |
| `--request-timeout` | 300 seconds after scheduler admission, including inventory |
| `--per-agent-active` | 1 |
| `--per-agent-queue` | 2 |
| `--requests-per-minute` | 60 per agent |
| `--tokens-per-minute` | 131072 admission-estimate tokens per agent |
| `--starvation-seconds` | 5 |

Budgets charge the full admission estimate on enqueue and do not refund failed or
cancelled attempts. Limits apply separately to each authenticated agent; changing
the common operator limit changes all agents' ceilings. The proxy does not provide
an untrusted policy-update API. Keep all processes addressing one backend on the
**same private admission DB and consistent limits**. Do not share the job DB with
an admission path that already holds its transaction. HTTP 429 means queue/rate/
token backpressure; queue deadlines return 503, post-dispatch timeouts 504 when
headers have not yet been forwarded. An interrupted already-started stream closes
without falsely appending a successful completion marker.

`--requester-credentials /private/inference-identities.json` accepts a trusted JSON
object mapping existing agent IDs to independent environment-variable references
(no values). Provision the actual high-entropy values privately and configure the
runtime separately; this increment does not mutate existing runtime credentials.

The broker now **always** calls `security.check_agent_execution(workers_repository,
agent_id)` against the workers/agents registry DB, not the independent admission
DB. Unknown/unregistered agents deny. Global stop, containment, retained revoked
credential fingerprints and missing/stale/failed runtime, network, identity, audit
or enforcer coverage deny without any optional hook. Checks run before request
admission, while queued, immediately before upstream dispatch, after blocking
reads/before forwarding and in the active-request watcher. All five production
coverage adapters remain unavailable: production inference therefore fails closed;
fixture observations are not a monitoring downgrade or deployment proof.

With independent credentials, each map reference must exactly match that agent's
`config.credential_env`, so the security service fingerprints and verifies rotation
of the credential the broker actually accepts. A different or missing configured
reference denies rather than silently tracking a different credential.

`make_handler(..., admission_check=check)` accepts an **additional** trusted callable
`check(agent_id, action)`. It can restrict admission but cannot replace or bypass
the mandatory security gate. `action` is the requested broker route. Return **exactly
True** to admit; False, non-True values or exceptions deny. It is called initially,
while waiting, immediately before dispatch, before forwarding chunks and by the
active-request watcher. The hook must perform bounded checks, be thread-safe and
not log private inputs; no permissive exception fallback exists.
`--admission-check module:name` loads the same additive callable at startup; an
invalid module/name aborts startup. This option is not a production monitor.

A caller can supply a canonical UUID in `X-Request-ID`; otherwise the broker
allocates one. Successful responses return it in the same header. Cancellation:
`POST /v1/requests/cancel` with `{"request_id":"<uuid>"}` under the requesting
agent's bearer credential. It cannot cancel a peer's request. The 202 response
reports `cancel_requested` and always `backend_stopped:false`: it is not proof of
remote termination. Authenticated owner cancellation remains available after
containment, monitor loss or additive-hook denial; it grants no execution authority
and still cannot cancel peer work. Administrator inventory/investigation reads
remain accessible under a global stop. Request IDs correlate active work; this is not a persistent
idempotent generation/replay API.

## Crash and uncertain-work safety

The existing `inference_admission` reservation table remains authoritative;
`broker_requests`, `broker_usage` and `broker_turns` are additive coordination
metadata in the admission database. No prompt or response data is stored there.
Queued rows may expire; **active/uncertain rows never expire automatically**.
After dispatch, any timeout, transport error, cancellation, revocation or incomplete
response retains the reservation as uncertain. A killed broker leaves active work
reserved. Both block capacity after a new scheduler/process starts. Release occurs
only after ordinary observed response EOF or explicit administrator reconciliation
outside this increment. Do not clear retained reservations merely because the
client disconnected, a job was cancelled or a process restarted. Verify actual
backend quiescence first. No automatic remote retry/restart or lease purge exists.

## Executed verification

Observed RED runs included the missing scheduler, missing hook option, credential
alias acceptance, oversized-context acceptance, missing CLI options, overlapping
admin unload, deadline dispatch after delayed inventory and custom-admin/Gateway
alias acceptance. They were followed by passing runs.

Earlier full-tree run before mandatory security integration (historical):
`python3 -m unittest discover -s tests -q`: **141 discovered, 140 passed, one optional
libvirt-schema skip**, 41.216 seconds. Other agents were concurrently adding tests,
so this is the exact run snapshot rather than a permanent suite size. Existing
unclosed SQLite connection ResourceWarnings appeared during the full run; they
were not hidden or treated as clean warning-free execution. Focused runs passed:
**19 inference tests** (final focused rerun: 15.429 seconds), nine llama migration/store
tests, eight model tests. `git diff --check` and compilation of the three changed
Python production modules passed.

The local integration fixture runs actual TCP HTTP servers, authenticated broker
requests, threads, SQLite transactions and a subprocess crash. **Its backend is a
fixture echo/delay server, NOT llama.cpp and NOT real-model acceptance.** Tests cover
four independent authenticated identities against the same backend, no cross-agent
request/context merging, serial/parallel limits, HTTP priority/fairness, aging,
queue overload, per-agent budgets, owner-only queued/active cancellation,
fail-closed hooks, revocation, timeouts, admin exclusion, metadata-only logs and
retention after crash/uncertainty.

Final full-suite fixture benchmark, four requests/four identities, backend delay
80 ms per request, including local HTTP/SQLite/authentication overhead:

| Configured concurrency | Observed peak | Total wall seconds | Requests/sec | Sorted end-to-end latencies, ms |
|---:|---:|---:|---:|---|
| 1 | 1 | 0.5831 | 6.860 | 148.136, 308.074, 438.138, 582.170 |
| 2 | 2 | 0.3918 | 10.208 | 166.325, 202.934, 351.873, 386.387 |

These tiny fixture samples do **not** justify increasing the live default. No real
model token/sec, TTFT, GPU memory/utilization or throughput benchmark was obtained.

## Mandatory security integration verification

This follow-up changed only `project_bots/llama_proxy.py`,
`tests/test_shared_inference.py`, `tests/test_inference_proxy.py` and this document.
Shared HTTP fixtures now use actual registered UUID agents/workers in a separate
SQLite registry with explicit `fixture_security` observations, never a permissive
production fallback. The legacy inference fixture also installs explicit telemetry.

Observed RED: a contained agent with an always-True optional hook received HTTP
**200 instead of 403** before the mandatory gate. Owner cancellation then produced
**403 instead of 202** until execution admission was separated from cancellation.
Both regressions now pass. Additional actual HTTP/SQLite tests cover each missing
coverage adapter, global stop, queued containment, failed monitor health during
inventory, active streaming containment/monitor loss/global stop, unknown agent
denial, mismatched independent credential references, explicit recovery followed
by rejected restoration of an old inference token, preserved admin inventory,
owner-only cancellation and retained uncertain reservations. Recovery's runtime
readback is explicitly a trusted fixture, not a live Machine Manager observation.

Executed final integration verification:

- `PYTHONPATH=tests:. python3 -m unittest test_shared_inference test_inference_proxy test_inference_scheduler -q`: **27 tests passed**, 28.125 seconds.
- `python3 -m unittest discover -s tests -q`: **150 discovered, OK with one optional skip**, 56.293 seconds. Existing unclosed SQLite connection ResourceWarnings remain in the whole-tree run; the focused inference run emitted none.
- `git diff --check` and `python3 -m py_compile project_bots/llama_proxy.py tests/test_shared_inference.py tests/test_inference_proxy.py`: passed.

No real-model, malicious-runtime or production-monitor acceptance was performed.
All five production coverage adapters remain unavailable and required, so the
mandatory gate refuses production execution rather than silently downgrading.

## Read-only live observation and exact acceptance prerequisites

Read-only socket inspection found listeners at `127.0.0.1:21434` and `:21435`.
An unauthenticated GET to the existing backend tunnel `/models` returned **401**.
No credentials were retrieved or printed, and no live generation was submitted.
This does not verify child inference-port authentication or GPU offload. Earlier
docs' loaded `qwen3-1_7b` observation remains historical, not fresh model proof.

Still BLOCKED / NOT RUN:

1. Separately authorized rollout/restart of the broker and independent inference
   credentials, with installed-file/config verification and protected DB backups.
2. Permission to use four actual independent runtime identities/VMs; the four
   original VMs were previously observed stopped and are preserved. Obtain explicit
   authorization before starting any. Preserve the extra unknown stopped domain.
3. Fresh pinned llama.cpp version/hash, actual selected RX6800 Vulkan device,
   offloaded-layer logs and current VRAM/utilization telemetry. Loaded inventory or
   zero/unavailable memory reporting is not GPU proof.
4. Read actual backend `--parallel`/context/continuous-batching configuration and
   benchmark concurrency 1 before 2, with TTFT, token/sec, tails, queue depth,
   cancellation behavior and sustained GPU/CPU/memory observations. No backend
   batching configuration or hardware telemetry implementation was changed here.
5. Run four real agents against one verified loaded model, retaining instruction,
   memory/history/tool-permission isolation, queue/fairness/revocation measurements.
   Fixture identities and request echoes are not four real runtime agents.
6. Verify authenticated raw backend child inference ports from every guest and
   enforce default-deny anti-bypass networking. **Loopback child-port bypass remains
   unresolved/unverified**, including guest gateway-to-host-loopback mappings.
7. Install independently trusted production coverage/enforcement adapters (the
   mandatory application admission hooks are now wired and fixture-tested); prove
   actual backend stop/quiescence before reconciling retained uncertain leases.
   This proxy cannot terminate hostile VMs or prove server-side cancellation, and
   it does not independently assemble private history or authorize tool execution.

Front-door connection/thread DoS limits, cryptographically tamper-resistant audit,
exact tokenizer/template admission, per-agent differentiated policy editing and
hostile VM/network containment remain separate work. No production-security or
expanded product-completion claim is made by these fixture tests.
