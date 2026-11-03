# Product update checkpoint — 2026-11-02

## Scope and starting boundary

Started at **20:12:06 America/New_York**, not before the scheduled 20:12 time.
Clean `main` **3091edd** was inspected with history, tracked files, parent/root
AGENTS checks, existing implementation/status/checkpoints, tests, deployment and
read-only live observations before changing code. No unrelated dirty files existed.
The change plan was to add a bounded Stage 1 chat/security-identity foundation,
not rebuild the platform or declare five stages complete.

The fixed roadmap is [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), exactly:
Core Application; Machine Manager; AI Workers & Model Manager;
User Control & Collaboration; Final Product & Hardening. Expanded security and
shared-inference requirements are retained in PRODUCT_REQUIREMENTS.md and
SECURITY_ACCEPTANCE.md. No sixth stage exists.

## Increment 1 — working backend and responsive web foundations

- Additive SQLite **v4** chat/member/message/identity/security-event tables.
  Existing registry/jobs/workers/admission rows are retained; no real DB was migrated.
- Persistent application-owned individual/group chats, explicit current members,
  sequenced history pages and per-sender client UUID idempotency. Conflicting retries
  return 409. No worker dispatch or inference occurs from a message submission.
- Separate agent chat credentials: administrator configures only environment-variable
  references, never values. Scoped HTTP callers can list their chats/read/send, not
  access administrative registry/jobs/compute/models/settings/security routes.
  Sender derives from authentication; spoof fields fail validation.
- Membership removal and disabled identity block subsequent reads/sends. Checks and
  message operations share one transaction. Current members see all explicit shared
  history; revocation cannot erase previously downloaded messages.
- Metadata-only chat identity/membership/denial events persist outside worker authority
  in the backend DB. They are not tamper-resistant external audit or complete incidents.
- Responsive chat/member/history forms, safe text rendering, Chats/Agents/Activity/
  Security anchors, advanced infrastructure panels collapsed. No automatic replies,
  live polling, notifications or native applications are claimed. Security UI explicitly
  warns that runtime/network monitoring and containment are not implemented.
- Review found and fixed custom inference-admin credential aliasing, send-response
  draft erasure and concurrent history duplication/stale-cursor races, with observed
  failing-first regressions. Chat secrets must remain separate from all known
  platform, compute, Gateway and inference administration references/values.

## Exact changed files

Production:
- `project_bots/chat.py` (new)
- `project_bots/chat.js` (new)
- `project_bots/repository.py`
- `project_bots/platform_web.py`
- `project_bots/dashboard.html`
- `project_bots/dashboard.js`

Tests:
- `tests/test_chat.py` (new)
- `tests/chat_ui.cjs` (new)
- `tests/test_platform.py`

Documentation:
- `README.md`
- `IMPLEMENTATION_STATUS.md`
- `docs/API.md`
- `docs/STAGE4_MCP_CHECKPOINT.md`
- `docs/PRODUCT_REQUIREMENTS.md` (new)
- `docs/ARCHITECTURE.md` (new)
- `docs/IMPLEMENTATION_PLAN.md` (new)
- `docs/SECURITY_ACCEPTANCE.md` (new)
- `docs/DEPLOYMENT.md` (new)
- `docs/PRODUCT_UPDATE_2026-11-02.md` (this file)

No commit, push, deployment or live restart was performed. Git HEAD remains the
baseline; working-tree edits are the deliverable, not changes to installed services.

## Executed verification

Baseline: `python3 -m unittest discover -s tests -q`: **97 discovered, 96 passed,
one optional libvirt-schema skip**. Added chat behavior through observed RED→GREEN
HTTP slices: first missing chat/identity/UI routes failed, then passed. Security
review regressions also failed before their fixes.

Current full suite: **106 discovered, 105 passed, one optional libvirt-schema skip**.
Installed CLI tests use disposable HOME/DB, actual HTTP and process restart. They
exercise persistence/idempotency, agent-scoped collaboration, spoof-field/admin-route
rejection, membership revocation, identity disable and ambiguity, malformed members,
metadata-only denials and existing installation/update/uninstall regression coverage.
SQLite tests cover retained v3 state, uncertain admission, existing worker rows,
concurrent duplicate writers, history isolation/paging and atomic membership rollback.

Commands:
```sh
python3 -m unittest discover -s tests -q
node --check project_bots/dashboard.js
node --check project_bots/chat.js
node tests/dashboard_vm.cjs
node tests/chat_ui.cjs
git diff --check
```

Node suites pass: existing VM/worker confirmation contracts and chat safe rendering,
idempotent retry, preserved in-flight draft, membership and history race checks.
They are fake DOM/API tests, **not** visual-browser, native-app or VM acceptance.
Tests use Python 3.14.9 with MCP SDK 2.3.0 in the actually resolved managed
interpreter. Existing deployed platform/broker processes use `/usr/bin/python3.14`;
no assumption that their environment loads these edits. See DEPLOYMENT.md.

## Live state and corrected historical claims

Read-only SSH/libvirt found **all four original worker domains shut off**, plus
stopped domain `80578231-c09e-4624-ab45-cbf676df91d0`. No worker was started,
stopped, deleted or changed. Additional domain provenance remains unverified;
its presence is not proof of a successful disposable lifecycle. Platform 8033
returned four registered agents/workers and 39 jobs; stored `verified` is stale.
Shared loaded-model inventory reported `qwen3-1_7b` at context 32768, unavailable
memory accounting and zero reported VRAM; this is neither fresh GPU-offload proof
nor proof of CPU-only execution. Existing llama.cpp/Vulkan setup was preserved.

Recovered useful bounded MCP evidence from `2251905`, which `91f08b0` had overwritten,
into the corrected checkpoint without reverting unrelated implementation. Historical
read-tool/canceled-job IDs and authenticated-call evidence are retained separately
from unverified Hermes-native wiring and policy-blocked disposable acceptance.
The 32768-MiB setting is application admission policy, **not a physical/AppArmor RAM
ceiling**. MCP initialize and passing unit tests do not establish Stage 5 completion.

## Measured completion and known risks

All five stages remain **partial against the expanded brief**. Existing historically
verified functionality is preserved, but historical narrower gates are not full
current security acceptance.

- No independent monitor, incident/containment engine, network anti-bypass policy,
  fail-safe enforcement-health gate, VM emergency termination or durable global stop
  latch is implemented by this increment. Agents are not marked protected.
- Chat API acceptance is fixture integration, not real hostile VM acceptance. All
  15 malicious scenarios still require the full real denial→detection→incident→
  containment→evidence chain on authorized disposable targets. Privileged/host/escape
  tests were **NOT RUN**; no simulated success substitutes for them.
- Four real agents using one loaded model with instruction/private memory/history/
  permission isolation and actual scheduling is **BLOCKED / NOT RUN** in the observed
  stopped-worker state. No VM capacity/security policy was relaxed to run it.
- Existing inference admission remains conservative serial priority/FIFO, not fair
  per-agent scheduling, full token/rate budgets, continuous batching benchmarks,
  trustworthy GPU utilization telemetry or actual active-request cancellation.
- No automatic conversational worker adapter/context assembly, full multi-user RBAC,
  short-lived chat token issuer, complete approval/recovery UI, native mobile/desktop
  apps, production DoS/rate limits or complete backup/restore acceptance.
- Backend/metadata audit share service/SQLite authority; same-UID/administrator writes
  remain trusted. No database tamper-resistance or hostile host compromise guarantee.
- Plaintext HTTP is only appropriate behind reviewed private transport. Existing
  Gateway/inference credential coupling and unrestricted worker egress remain known
  pre-existing risks; this increment does not claim to fix them.

## Next safe bounded work

Review this exact dirty tree; do not blindly add/reset. Add and exercise trusted
security-state/admission contracts and independent enforcement capabilities on
isolated fixtures before enabling automatic chat execution. Design durable stop/
revocation with actual runtime/network action readbacks and partial failures, then
obtain scoped disposable/administrator prerequisites for live acceptance. Preserve
all existing workers and unknown domain. Do not restart workers, broaden policy,
edit Hermes configuration or rerun old one-shot mutation scripts from this note.
