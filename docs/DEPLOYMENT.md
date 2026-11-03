# Deployment and current operational boundaries

## This increment is source-tested, not deployed to existing services

The 2026-11-02 product update began at 20:12:06 America/New_York, after the
scheduled 20:12 start. Baseline was clean `main` at `3091edd`. No repository
`AGENTS.md` was tracked; checks for `/AGENTS.md`, `/home/AGENTS.md`,
`/home/server1/AGENTS.md` and the repository root found none.

Read-only inspection verified these site-specific endpoints; they are not product
defaults or authority to mutate resources:

- Management checkout `/home/server1/project-bots`, host reference `10.0.50.10`.
- Platform listeners `127.0.0.1:8033` (Stage 3 installed copy) and `:8032`
  (separate Stage 2 service), compute tunnel `:19443`, inference broker `:21435`,
  backend tunnel `:21434`. Relevant user units were active.
- Compute SSH `pbcompute@10.0.50.56`, `qemu:///session`; compute user unit
  `project-bots-compute.service` active, loopback `127.0.0.1:9443`.
- Compute observed 62967 MiB physical RAM. Source `capacity()` has a configurable
  application admission cap, not an AppArmor physical-RAM ceiling. No capacity,
  host protection, sudo, device or network-policy changes were made.
- All four original worker domains were **shut off**:
  `4accba4d-24c9-4942-aec9-fd54de816319`,
  `55545d36-bd05-4e48-9eb4-cea5fbe8c8f4`,
  `4c827ae7-02ab-40f8-8cc9-3af9c6340526`,
  `b4974b11-1c8a-409a-9f04-6401b9407ff1`.
  Additional stopped domain `80578231-c09e-4624-ab45-cbf676df91d0` was present;
  its provenance/ownership is unverified. Preserve it, do not infer cleanup rights.
- Actual authenticated platform reads returned four agents, four worker bindings
  and 39 jobs. Worker records still say `verified`: that is stale registration
  evidence, not current liveness/security. No job was created, canceled or dispatched.
- Loaded-model read returned `qwen3-1_7b`, context 32768, loaded true,
  `memory_observation_available=false` and `size_vram=0`. This establishes only the
  broker's loaded-state report. It neither proves CPU-only execution nor proves
  fresh Vulkan offload. Historical GPU evidence remains in LLAMA_CPP_MIGRATION.md.

No existing worker, service, tunnel, model, key or job was restarted, resized,
removed, reconfigured or replaced. No Hermes profile configuration was changed.
The four-agent/one-loaded-model acceptance remains **BLOCKED / NOT RUN**. Starting
important VMs or conducting hostile-host probes is not part of this read-only check.

## Source continuation — security, shared inference and recovery

Subsequent source increments add schema-v5 security state/incidents, durable global
and per-agent stop/recovery, independent reconciliation, shared inference fairness/
budgets/cancellation, Security dashboard controls and validated database backup/
restore. See [security implementation](SECURITY_INCREMENT.md), [inference implementation](INFERENCE_INCREMENT.md)
and [backup procedures](BACKUP_RECOVERY.md). These changes remain undeployed.

**Rollout safety:** execution now requires fresh trusted runtime/network/identity/
audit/enforcer coverage. No real monitor adapters are installed. New execution must
therefore remain denied; never fabricate healthy observations to make a demo work.
The independent enforcer can request shutdown of registered workers when coverage
is absent, so do not launch it against an existing live database as a harmless
health check. Review targets and explicitly authorize rollout first. It provides
application/fixture-tested graceful shutdown, not host packet isolation, forced VM
termination, an immutable external audit store or a protected watchdog.

Before rollout, provision the distinct inference credential map, trusted telemetry
and enforcement adapters; review child inference-port authentication from guests;
retain off-host evidence and independently isolate workloads. Preserve all original
VMs. Security UI must expose unavailable/partial actions and blocked recovery.
Neither global nor per-incident recovery automatically starts workers.

## Interpreter and dependency boundaries

The actual test interpreter resolved to
`/home/server1/.hermes/installs/9c2ca299b9e983f3/environments/af340bfcecb5463fb0b4561e49b19819/venv/bin/python3`,
Python **3.14.9**, with optional MCP SDK **2.3.0**. The running installed platform
and inference broker resolve `/proc/<PID>/exe` to `/usr/bin/python3.14`; they do not
automatically load checkout edits. The llama supervisor is `/usr/bin/ssh`, which
supervises the remote backend. Do not infer deployed SDK/provider configuration
from the managed test environment. Base platform/chat remain stdlib-only; optional
MCP dependencies stay in `requirements-mcp.txt`. No dependencies were installed.

## Isolated validation and future rollout

Run from the checkout using a reviewed interpreter:

```sh
python3 -m unittest discover -s tests -v
node --check project_bots/dashboard.js
node --check project_bots/chat.js
node --check project_bots/security.js
node tests/dashboard_vm.cjs
node tests/chat_ui.cjs
node tests/security_ui.cjs
git diff --check
```

Tests install the real CLI under disposable homes, use private fixture databases
and actual local HTTP, and restart fixture processes. They do not operate live VMs.
Node checks use a fake DOM/API, not visual/native-browser acceptance. The optional
libvirt domain-schema test is skipped unless a trusted actual schema is supplied;
see COMPUTE_HOST.md. No full malicious-agent integration suite is passed here.

Do not copy new files over active processes as an implicit deployment. Before a
separately reviewed rollout: inventory installed files/interpreter/unit/database
paths; use validated private database backups and separately preserve configurations; preserve
in-flight/uncertain jobs and inference leases; review the additive **v5** migration;
install the complete package including chat/security modules and JavaScript assets; then perform an explicitly
approved restart only of intended Project Bots processes. No Hermes restart/config
edit is required. Verify exact deployed file hashes and authenticated routes,
retained records and rejection paths after rollout. Do not restart important worker
VMs just to refresh a control-plane package.

`sh install.sh` copies source to the selected user's install location, so first use
a disposable HOME for testing. Existing updater tracks development main, not a
signed release. It will not publish these uncommitted checkout changes. Review
before publication; never `git add .` blindly. Uninstall preserves data/VMs and is
not containment. Private database backup/restore CLI fixtures now pass; full release, VM/environment
backup, upgrade/rollback and disaster-recovery acceptance remain mandatory Stage 5 work.

For rollback, retain the old executable and a stopped pre-migration database backup.
Earlier code rejects newer schemas; do not decrement PRAGMA user_version or drop chat/security data
in a real database to force compatibility. The migration tests drop fixture tables
only to reconstruct older schemas; that is not an operator recovery procedure.

## Chat credentials and transport

Administrators provision independent high-entropy chat tokens through private
service environment files/channels, then configure only variable references with
`POST /api/agents/<id>/chat-identity`. Never place values in Git, URLs, UI, job input,
logs or public reports. Do not reuse platform, compute, Gateway, inference-admin or
raw backend credentials; custom inference-admin references are checked too. No
existing worker credential is enrolled automatically. A credential change in an
inherited process environment usually requires a reviewed process restart;
`enabled:false` in SQLite revokes subsequent chat authentication without a restart.

The current platform binds loopback by default and has no direct TLS listener;
remote clients need a reviewed private SSH/TLS transport. No guest message tunnel
or default-deny anti-bypass network policy is provisioned by this increment. Keep
agent tokens off unrestricted administrative endpoints. Shared history is explicit,
visible to all current members and to the administrator; membership never conveys
private filesystem/memory/tool permissions. These are development controls, not a
complete hostile-agent deployment guarantee.
