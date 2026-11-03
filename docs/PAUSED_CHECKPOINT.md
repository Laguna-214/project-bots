# Paused checkpoint — 2026-11-02 21:43 EST

**Development is STOPPED at Beckett's explicit request.** This checkpoint saves
progress only; it does not authorize resuming development, tests, deployments,
worker startup, host changes, commits or publication. Both delegated workers ended.

Repository `/home/server1/project-bots`, branch `main`, base HEAD **3091edd**.
Preserve all modified and untracked files. No reset/clean/revert or blind `git add .`.
A private complete source snapshot and machine-readable manifest are saved outside
the repo under the active profile's `checkpoints/project-bots/` directory; see the
checkpoint receipt supplied with this save. Do not infer installed service contents
from the checkout. No commit or push is part of this save operation.

## Requirements and architecture

The full product/security and shared-one-loaded-model requirements are retained in
`docs/PRODUCT_REQUIREMENTS.md`. Keep **exactly five stages** in
`docs/IMPLEMENTATION_PLAN.md`, preserve the existing llama.cpp/RX6800 Vulkan
architecture, backend independence, optional permissioned Hermes and existing VMs.
Prior "all stages complete" claims and physical/AppArmor 32-GiB limit claims were
incorrect and have been corrected in the source documentation.

## Last independently verified combined baseline

Before the most recent conversation/host-security/client additions:
- **150 Python tests: 149 passed, one optional skip**; final warnings-enabled run
  had no warning lines after fixing backup fixture connection leaks.
- Three Node interaction suites, JavaScript syntax and diff checks passed.
- Durable chats; security latches/incidents/recovery and reconciler; mandatory
  inference security gates; fair shared scheduling/budgets/cancellation; database
  backup/restore; Security dashboard. See
  `docs/CONTINUATION_SECURITY_INFERENCE.md`, `SECURITY_INCREMENT.md`,
  `INFERENCE_INCREMENT.md`, and `BACKUP_RECOVERY.md`.

Those results **do not describe the entire current dirty tree**.

## Additional progress after that baseline

### Shared clients — focused tests verified by parent

`client.js`, `client-sw.js`, `manifest.webmanifest`, `client-icon.svg`, dashboard
mobile navigation and optional direct HTTPS listener/CLI with actual-TLS origin
checks; `tests/test_client.py`, `test_https_client.py`, `client_ui.cjs`.
Focused Python and Node client tests passed. A real browser verified 390px layout,
Agents navigation, hidden advanced panels and desktop restoration; layout check
used DOM visibility overrides, not browser authentication acceptance. Service
worker active, CacheStorage empty; stopping only the disposable browser fixture
produced a real browser 503/no-queued-action response. Fixture server was killed;
no ongoing browser test server should be resumed implicitly. Details in
`docs/SHARED_CLIENT_INCREMENT.md`.

These are responsive/installable-PWA features, not native/app-store applications.
Background push is not implemented. HTTPS certificates/trust are not provisioned
for existing deployment. Do not claim current installed mobile/client acceptance.

### Automatic conversations — delegated completion, not parent combined verification

New `conversations.py`, `chat_runner.py`, `tests/test_conversations.py`;
modified `chat.py` and platform `chat_request()` routing. Standalone opt-in runner:
`python3 -m project_bots.chat_runner --db PRIVATE_DB --broker http://127.0.0.1:21435`.
`--once` supported. `--recover-offline` only marks interrupted work uncertain, never
blindly retries it. Do not invoke against a live DB without authorization.

Admin routes: GET/POST `/api/agents/{uuid}/conversation`,
GET `/api/conversations/jobs[?chat_id={uuid}]`,
POST `/api/conversations/jobs/{uuid}/cancel` with `{}`.
Enrollment fields all required: `enabled`, `system_instructions`, `memory`,
`tools` (empty only), `max_replies` (1–32 lifetime per-agent/per-chat cap).

Child reported 16 focused tests, six chat tests and 15 platform tests passed.
Human messages create idempotent reply jobs; no recursive peer-response triggers.
Group context excludes all private instructions/memory/other-chat history.
Identity/membership epochs, security health, cancellation/uncertainty and separate
inference credentials gate requests. Separate reasoning fields discarded and
reasoning-tag/tool-call responses rejected. Source uses additive tables while
retaining schema version 5: review migration/version policy before rollout.
Fixture four-agent HTTP broker testing is not live loaded-model/GPU acceptance.
UI enrollment/runner deployment and final review remain unfinished.

### Host security — INTERRUPTED, partial implementation

Modified `compute.py`, `machine_http.py`, `machine_client.py`, `security.py`;
new `host_security.py`, `tests/test_host_enforcement.py`,
`tests/test_host_security.py`. The worker was interrupted on Stop and did not
return a completed handoff. Treat this code as **unfinished/unverified**. Inspect
actual diffs before relying on force-termination, network enforcement or monitoring.
Do not claim those features complete or install host policy automatically.

The conversation child observed an interleaved full-suite run with failures in:
- `test_stop_racing_authorized_start_reconciles_owned_runtime`
- `test_independent_process_terminates_fixture_and_restart_never_starts_it`

No final combined test was run after these concurrent edits. The precise current
failure set is unknown. Do not describe the current tree as fully passing.

## Live-resource boundaries and remaining security gates

Original four VMs and an additional unknown stopped domain must be preserved.
Previously observed original VMs were shut off; stored "verified" worker records
are stale, not current liveness/protection. Source work is not deployed. Exact host
references and deployment caveats are in `docs/DEPLOYMENT.md`; secrets stay under
the active profile `private/`, never in Git/chat/checkpoint manifests.

Still unaccepted: real trusted OS/network monitoring, packet isolation/anti-bypass,
critical force-stop enforcement on real disposable VMs, protected watchdog,
external tamper-resistant audit, all 15 full malicious-agent acceptance chains,
four real agents sharing one loaded model with measured GPU/context/permission
isolation, native-client testing, complete approvals/RBAC/credential lifecycle,
full disaster recovery/release preparation. Fail-safe coverage must not be faked.

## Resume only after explicit user authorization

1. Read this checkpoint and inspect actual git state and all latest partial edits.
2. Confirm there is no concurrent worker/service mutation. Preserve unknown domains,
   unfinished edits, private keys and services; no automatic cleanup/startup.
3. Review interrupted host-security code and resolve regressions with failing-first
   tests; verify conversation/client integration and schema compatibility.
4. Re-run combined Python/Node suite and report actual passed/skipped/failed gates.
5. Obtain precise administrator/disposable-target prerequisites for live acceptance.
   Never weaken security or label fixture success as real-host enforcement.

Saving this checkpoint does not itself authorize any of these resume steps.
