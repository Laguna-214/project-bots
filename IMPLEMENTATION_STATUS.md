# Implementation status

> **RESUMED on 2026-11-03 with explicit user authorization.**
> Published development source checkpoint: `e93415b` ([draft PR #1](https://github.com/Laguna-214/project-bots/pull/1)), not merged/released.
> Latest parent-executed checkpoint suite: **209 tests, OK with 3 skips**.
> Subsequent opt-in protected VM authority source is implemented but not deployed.
> Parent post-fix suite: **227 tests, OK with 2 privileged skips**, with actual XML
> schema validation enabled. A critical-stop ordering bug was fixed; final scoped
> source-publication re-review **passed** (`deleg_54a86c27`). BPF compilation/loading, real VM/packet effects and protected
> monitoring/watchdog acceptance remain unperformed. Both earlier GitHub source/UI CI
> runs passed on `0afa60c`; the new increment is not privileged-execution accepted.
> Optional XML validation separately passed; all **5 privileged namespace tests**
> passed inside the approved disposable administrator VM. They prove kernel/network
> and subprocess primitives, **not hostile VM containment**. Six Node UI programs,
> nine native shell contracts and two artifact checks passed. Android debug APK
> rebuilt/linted/signature-verified; real sandboxed Linux GUI/setup tests passed.
> The old Android WebView design failed redirect-confinement review and was
> replaced by the user-approved native design. **Android remains not accepted.**
> The user-approved native Android replacement is built (no WebView). Parent
> reran the build/signature, two-origin redirect/body/TLS/API/state tests and full
> **209-test suite, OK with 3 skips**. All 300–399 redirects caused zero second-origin
> contacts in host tests. Parent verified the subsequent emergency-stop fix:
> global controls render before data loads and use a reserved zero-queue lane;
> failed/oversized sections cannot hide them. New app/test APKs exist; independent
> scoped independent re-review **passed** (`deleg_9c4a7a48`), with no blocking findings.
> Instrumentation is compiled but **not executed**; Android runtime/header fidelity
> and physical-device acceptance remain unverified. Full product acceptance is incomplete. Only the approved CPU-cap/lab deployment exception is established;
> do not infer rollout of this source tree or permission to mutate original VMs.
>
> Current evidence, artifact hashes and continuation:
> **[resumed checkpoint](docs/RESUME_CHECKPOINT_2026-11-03.md)** and
> **[native clients](docs/NATIVE_CLIENTS.md)**. Subsequent sections are historical
> checkpoints, not current feature absence/completion assertions.

## Previous — durable security controls, shared scheduling and recovery (source increment)

Continuation implements schema-v5 incident/state persistence, durable global/per-agent
stop latches, fail-safe execution admission, explicit acknowledgment/recovery and an
independent graceful-shutdown reconciler. Security dashboard controls expose agent
state, health, incident evidence and partial action outcomes. Shared inference adds
fair turns/aging, bounded queues/concurrency/rate/token budgets, owner cancellation,
revocation checks and retained uncertain backend reservations. One centralized
llama.cpp model architecture is preserved. Private validated database backup/restore
commands are included. Full source contracts and limitations:
[security](docs/SECURITY_INCREMENT.md), [inference](docs/INFERENCE_INCREMENT.md),
[backup/recovery](docs/BACKUP_RECOVERY.md).

**Not product completion:** no installed OS/network adapters, packet isolation,
forced VM termination, protected external watchdog, immutable audit storage,
automatic AI chat replies, native mobile/desktop apps, or four-real-agent/shared-model
acceptance. Required health defaults unavailable; execution must fail closed, not
silently fall back. No existing services, VMs or Hermes configuration were changed.
Do not run the enforcer against production as a harmless read-only check: with
missing coverage it requests worker shutdown. Reviewed deployment/host prerequisites
and real security acceptance remain mandatory. Mandatory inference/security
integration is verified against the workers registry DB (optional hooks cannot
bypass it). Final combined run: **150 tests, OK with 1 optional skip**, all three
Node interaction suites, JavaScript syntax and `git diff --check` passed. Backup
fixture SQLite connection leaks were fixed; the final warnings-enabled full run
emitted no warning lines. See the [continuation handoff](docs/CONTINUATION_SECURITY_INFERENCE.md).

## Previous increment — Nov 2 source-tested chat foundation; security acceptance incomplete

Started **2026-11-02 20:12:06 America/New_York**, after the scheduled start, from
clean `main` **3091edd**. This is incremental work, not a rebuild or Stage 5 closure.
The authoritative expanded roadmap has exactly five stages:
**Core Application; Machine Manager; AI Workers & Model Manager; User Control &
Collaboration; Final Product & Hardening**. See [requirements](docs/PRODUCT_REQUIREMENTS.md),
[architecture](docs/ARCHITECTURE.md), [plan](docs/IMPLEMENTATION_PLAN.md) and
[security acceptance](docs/SECURITY_ACCEPTANCE.md). Historical narrower completion
statements below are retained history, not acceptance of this expanded brief.

Implemented additive SQLite v4 persistent individual/group chats, memberships,
idempotent messages/history, independently referenced agent chat credentials,
transactional membership/enablement authorization and metadata-only security events.
Responsive web chat/member forms and explicit unprotected-security status are added;
advanced infrastructure controls are collapsed. No automatic AI replies/private-memory
sharing, independent monitoring, network containment, incident engine, global stop
latch, full user RBAC or native apps are claimed. Backend remains independent of
Hermes; existing llama.cpp shared inference is preserved, no Ollama migration.

Verification: **106 discovered, 105 passed, one optional libvirt-schema skip**;
Node syntax and both VM/worker and chat fake-DOM contracts pass; whitespace check
passes. Installed fixture HTTP/process-restart tests cover actual persistent chat
API authorization/revocation and retained records. They do not prove real malicious
VM containment, visual UI/native apps or four-agent model-context isolation.

**Fresh read-only live state differs from earlier chat:** four original worker VMs
are all **shut off**; additional stopped domain `80578231-c09e-4624-ab45-cbf676df91d0`
is present, provenance unverified. Four registered `verified` worker records are
stale, not running/protected proof. Platform 8033 and inference/tunnel/compute user
services are active; loaded `qwen3-1_7b` report lacks trustworthy memory/GPU accounting.
Four-real-agent/one-loaded-model acceptance is **BLOCKED / NOT RUN**. No VM, worker,
job, service, inference configuration or host protection was changed. No Hermes
configuration edits, commit, push or deployment of this source increment.

The [corrected MCP checkpoint](docs/STAGE4_MCP_CHECKPOINT.md) recovers useful bounded
evidence from `2251905`, superseding `91f08b0`'s unsupported lifecycle and physical/
AppArmor RAM-limit claims. 32768 MiB is configurable application admission policy.
MCP initialize alone is not authenticated API/native discovery or product completion.

Exact files, interpreter/dependency findings, tests, limitations and next safe gate:
**[product-update handoff](docs/PRODUCT_UPDATE_2026-11-02.md)** and
[deployment boundaries](docs/DEPLOYMENT.md). Existing installed services remain on
their prior copies; checkout changes have only run in isolated tests. All five
stages remain partial against the expanded requirements. Privileged hostile-host
and the 15 full malicious-agent acceptance chains are unverified, not simulated passes.

## Previous: Stage 4 bounded MCP coverage checkpoint; VM admission blocked

Continued from published `b37ce01` with strict observed RED→GREEN slices. **21**
real SDK tools now include queued/manual cancellation, metadata-only agent
registration, existing worker model/profile binding and role inventory. Inference
observation uses actual loaded-model/worker/receipt APIs; no invented approvals,
remote-inference cancellation, agent service lifecycle or arbitrary shell.
`--token-file` privately loads an owner-only regular 0600 raw credential without
putting a literal key in MCP env/config. An actual null execution receipt exposed
an SDK schema mismatch; a failing-first regression and real exact-job readback
now prove explicit `{"execution": null}` for undispatched jobs.

Actual fresh stdio initialize/list/call (protocol **2025-11-25**, all 21 tools)
reached installed platform **8033**. All four authenticated worker health checks
passed; before/after exact VM and worker records match. Queued-only MCP job
**`5e21722b-825e-4572-aa67-3f576a455d7e`** was canceled and read back canceled with
no execution; original read-tool job `edae31ba-0bdc-419a-9653-be4a5a818032` remains
succeeded. **VM lifecycle is blocked before mutation:** actual policy RAM is
32768 MiB and existing four reservations already sum to 32768 MiB (7/8 vCPU).
Even a 1-vCPU/2048-MiB disposable cannot fit; physical available RAM does not
supersede policy. No VM/operation UUID allocated, worker stopped/resized, capacity
policy changed or snapshot attempted. Real create/start/shutdown/delete remains
unverified pending separately authorized capacity resolution.

**96 tests discovered, 95 passed, 1 optional schema skip**; Node syntax and
`git diff --check` passed. No Hermes native connection/config change, Stage 5,
schedule, invented quota reading, commit or push. Parent owns reviewed supported
custom registration and native-call acceptance. Private evidence and verified
CLI syntax: [docs/STAGE4_MCP_CHECKPOINT.md](docs/STAGE4_MCP_CHECKPOINT.md).
Bounded checkpoint reached; extras frozen and paused.

## Previous: Stage 3 browser passed; Stage 4 initial real MCP core checkpoint

The user explicitly approved one-time **fixed guest-agent root Chrome packaging**
inside the four existing VMs only. Exact SHA-256-pinned Chrome 156.0.8078.79-1 was
transferred through ordinary SSH, copied to root-only staging and hashed before
parsing/installing. All four simulated/actual transactions: **0 upgraded, 1 newly
installed, 0 removed**. Browser/sandbox helper root ownership verified. No host
root/security change, bot sudo or permanent root command endpoint.

All four authenticated OpenClaw browser starts and offline controlled-page
navigation → random-challenge snapshot → referenced click → matching snapshot
passed, with sandbox enabled, renderer seccomp/NoNewPrivs and no `--no-sandbox`.
Loopback HTTP/data navigation policy remained restrictive; the controlled page
used `about:blank` plus an offline DOM fixture, not a private-network exception.
All non-browser config objects/roles/credentials/models and original VM boot IDs
are preserved; Programmer/HomelabEngineer still deny the model browser access.
Details/evidence: [docs/STAGE3_BROWSER_ADMIN_GATE.md](docs/STAGE3_BROWSER_ADMIN_GATE.md).
Stage 3's isolated sandboxed browser gate is closed on that explicit basis.

Only then began Stage 4: official-SDK **2.3.0 stdio MCP**, 17 narrow structured
tools backed by supported authenticated APIs, typed intent/operation IDs and no
shell/root tool. Actual MCP initialize/list/call → installed platform → existing
Researcher → retained successful OpenClaw `read` job
**`edae31ba-0bdc-419a-9653-be4a5a818032`** passed; exact job/receipt readback through
a fresh MCP process and wrong-token/confirmation refusal passed. Full tests:
**91 discovered, 90 passed, 1 optional schema skip**; Node syntax/dashboard
confirmation contracts and whitespace checks pass.

**Stage 4 remains partial and checkpointed** per subscription-budget steering:
no reliable quota percentage/reset metadata is available; no guessed 10% claim,
blind resume schedule or polling. Real disposable VM lifecycle via MCP and parent
Hermes-native connection wiring remain unverified. No new disposable, Hermes
configuration, Stage 5, commit or push. Exact supported tools, launch/credential
contract, private evidence and bounded next steps:
[docs/STAGE4_MCP_CHECKPOINT.md](docs/STAGE4_MCP_CHECKPOINT.md).

## Previous: browser packaging administrator gate (superseded)


At clean baseline `cc7ac9f`, the actual **authenticated Researcher OpenClaw browser start** still fails `No supported browser found`. Fresh inventory of **all four preserved guests** finds no system Chrome/Chromium executable and no installed Chromium snap. Ubuntu Desktop did not supply a browser. Researcher's existing root-owned Chrome AppArmor rule names the standard vendor path and permits userns; this may support a normal package install but is not proof of a usable sandbox. No binary relocation/confinement workaround, sandbox disabling, privileged access, VM replacement or policy change was attempted.

**Blocked on explicit guest-administrator approval/access, not GPU.** Exact bounded, hash-pinned administrator package mechanism, approval wording and required per-profile navigation/snapshot acceptance: **[docs/STAGE3_BROWSER_ADMIN_GATE.md](docs/STAGE3_BROWSER_ADMIN_GATE.md)**. It is proposed, not executed. Fresh default tests: **86 discovered, 85 pass, 1 optional schema skip**; Stage 3 llama/inference/platform and Stage 2 platform active; all four observed boot identities preserved. **Stage 3 remains incomplete; Stage 4 MCP deliberately not started.** No commit/push or Hermes changes.

## Previous: Ollama removed; llama.cpp Vulkan inference and four-worker tool checkpoint

Shared inference now uses unmodified official **llama.cpp b12058** Vulkan on RX 6800: pinned release SHA-256 verified, **29/29 layers offloaded**, 1123.71 MiB model + 3584 MiB KV on Vulkan0, nonzero AMD hardware VRAM readback. Preserved GGUF hash verified; all four existing OpenClaw configs validated using native **openai-completions / llamacpp**, no fallback. Managed Ollama binaries, archive and live units were deleted after successful replacement jobs; original model blobs/manifests and every VM/key/workspace are preserved.

Broker, model manager, source bootstrap/defaults and private installed config are migrated. Durable admission covers streamed OpenAI requests, including direct worker traffic, and model load/unload/pinned download/delete. Real official disposable GGUF hash-verified download → inventory → load → unload → remove → absent readback passed; registry persisted across broker restart. Native router asynchronous transitions now retain their lease until state readback. A real random-port child inference bypass was found and closed with **inherited LLAMA_ARG_API_KEY_FILE**; all four guest child inference probes returned 401 and raw private router connections were refused. No security-policy/root changes.

**86 tests discovered: default 85 pass + 1 optional schema skip; actual libvirt 12 schema: 86 pass/no skips on management.** Node syntax/dashboard confirmation contracts and git diff --check pass. Real installed four-role tool dispatch, serialization and exact platform restart persistence passed; final evidence is in **[docs/LLAMA_CPP_MIGRATION.md](docs/LLAMA_CPP_MIGRATION.md)**. Stage 2 remains unchanged. Browser sandbox prerequisite remains blocked; no full Stage 3/browser/autonomous executor, Stage 4, Hermes changes or commit/push claimed.

## Previous: Ollama Stage 3 GPU + four-worker checkpoint (superseded by llama.cpp)

Real RX 6800 acceleration now passes: official v0.40.13 ROCm 7.2 user-local artifact SHA-256 verified; running Ollama UID 1001 has render group; logs **offloaded 29/29 layers** and native `/api/ps` reports **5112583945 bytes size_vram** at context 32768. Only the dedicated inference process was refreshed via a fresh strict SSH foreground user scope supervised by `project-bots-stage3-ollama.service`; the VM-owning user manager was **not** restarted. Original compute CPU unit/tree/config backup preserved, CPU unit disabled to prevent a duplicate. No host root, driver, AppArmor, group or security change was performed.

Public tested `scripts/provision_worker.py` + fixed non-root bootstrap **actually created/deployed three additional independent VMs**, preserving original `4accba4d-24c9-4942-aec9-fd54de816319`. Four roles are live/verified: ProjectWorker, Researcher `55545d36-bd05-4e48-9eb4-cea5fbe8c8f4`, Programmer `4c827ae7-02ab-40f8-8cc9-3af9c6340526`, read-only HomelabEngineer `b4974b11-1c8a-409a-9f04-6401b9407ff1`. Unique keys/tokens/configs/workspaces and authenticated identity/Gateways; 7 aggregate vCPU / 32768 MiB RAM. Final four concurrent installed-HTTP dispatch requests succeeded with actual retained `session_status`/`read` tool audit results, non-overlapping remote receipts, exact restart persistence and nonzero GPU memory. Programmer write/read passed; HomelabEngineer requested write stayed absent with no successful mutation tool. All four currently intentionally share qwen3:1.7b; profile configuration remains independent.

New authenticated native broker `project-bots-stage3-inference.service` on 21435 adds a second durable priority/FIFO inference gate for **all** native worker requests and model mutations, including direct Gateway/native traffic; the existing job-level gate remains. A real direct request queued behind a held full-budget lease and completed only after release. A real passt host-loopback bypass was found and closed by binding raw Ollama to compute **127.0.0.2:11434** and updating only its SSH forwarding destination; raw default-gateway access was then refused from **all four VMs**, while brokered GPU jobs still passed. No firewall/passt/AppArmor change. Both admission DBs empty, no uncertain executions/FK errors; enabled/active user-unit readbacks and 20 installed public file hashes verified. Stage 2 8032 unchanged.

**Full Stage 3 is NOT claimed complete. Concrete remaining root-owned guest prerequisite:** browser doctor/plugin/Gateway works but browser start initially found no supported binary. Official signed Google Chrome metadata/package were verified and extracted user-local; actual sandbox-preserving headless launch aborted because its SUID helper is not root-owned/configured. Guest user namespaces are restricted and unshare failed. No `noSandbox`, sandbox bypass, guest sudo/root command, chown/chmod, sysctl or security-policy change was used. A human-approved supported sandboxed browser installation in a root-owned guest system path through reviewed trusted bootstrap/administrator packaging is required before real browser-tool interaction acceptance. This is **not another GPU permission request**. No authenticated dashboard visual review or unattended autonomous executor is claimed.

**Checks:** 77 discovered; default **76 pass + 1 optional schema skip**. With actual libvirt 12 RNG: **77 pass/no skips on management and compute**. Node syntax/UI confirmation contracts and whitespace checks pass. Durable manifests and source-owned workflow resume were exercised without duplicate VMs. No commit/push, Stage 4 or Hermes configuration changes. Exact final jobs, UUIDs, service/private paths, measured headroom, raw-bind restriction, browser error and recovery: **[docs/STAGE3_GPU_POOL_ACCEPTANCE.md](docs/STAGE3_GPU_POOL_ACCEPTANCE.md)**; earlier CPU evidence below is retained history.

## Previous: Stage 3 installed CPU worker acceptance passed; GPU / scale gate then OPEN

Resumed clean `main` `8bdec74` without replacing or deleting the existing worker. **68 tests discovered: 67 pass, 1 optional libvirt-schema skip**; original 54 passing tests preserved. Node syntax, expanded VM/Stage 3 dashboard confirmation contracts and whitespace checks pass. SQLite migrates v1/v2 to **v3** with durable inference admission. No commit/push, privileged host mutation, group/security-policy change, cloud fallback or Stage 4/Hermes configuration change.

**Closed with actual installed HTTP and VM evidence:** management's dedicated installed user service `project-bots-stage3-platform.service` is enabled/active at **http://127.0.0.1:8033/**, separate from unchanged Stage 2 `8032`. Real worker remains VM `4accba4d-24c9-4942-aec9-fd54de816319` (4 vCPU / 8192 MiB / 32 GiB), OpenClaw 2026.10.9, Node 24.22.2, key-only non-sudo `bot`. New read-only authenticated identity sidecar observes the root-owned cloud-init instance UUID, boot UUID, deployed local-only model/profile and authenticated Gateway readiness. Registration with that sidecar verifies the running VM against the compute API **before saving verified status**; every real dispatch repeats identity/health/profile and conservative model-budget checks. Legacy configuration without identity remains explicitly unverified and cannot execute a real Gateway job. Actual installed registration and fresh health passed for agent `b4fdb7e8-d14c-482e-b415-eda8d84ad41b` and registry machine `e0778e6a-8b1c-484d-8372-0cf60a780b30`.

**Actual OpenClaw tools, not model tool JSON:** job `6dd1431a-7020-4be1-8098-d628d87b87b6` returned the model name; retained Gateway trajectory contains `tool.call session_status` followed by **`tool.result session_status ok`**. Latest isolated installed-process dispatch/restart proof: job `85cd83d8-3189-4d1a-a97f-3612ec1ab022`, response `resp_fe8584f8-20b4-4971-9e82-4bff63fd2f95`, persisted `succeeded`; exact job and execution receipt survived stopping/restarting the installed executable. Missing authentication returned 403. Native model inventory, loaded inventory, unload/readback and actual pull → inventory → remove → absent readback of a previously absent disposable `smollm2:135m` all passed; assigned `qwen3:1.7b` removal returned 409. Queue cancellation passed; active dispatched cancellation correctly returned 409 without claiming remote cancellation. CPU load/reuse observations include 17.572 s and 5.899 s through the persistent installed service, with `/api/ps` reporting **size_vram 0**; these are individual measurements, not a throughput benchmark.

**Software gates:** cross-process SQLite priority/FIFO admission, bounded queue/deadline, one active inference and an 8192 MiB reservation budget replace the process-local gate on all production paths. Active leases survive process death; uncertain execution or model mutation retains its reservation until reviewed local reconciliation. Queued timeouts leave the job queued and return HTTP 503 without a remote execution receipt. Native preflight budgets model weights, full FP16 context KV cache, other loaded models and headroom; actual current model requires **7125 MiB**, with **8192 MiB** reserved. Unknown cache geometry fails closed. These are conservative admission reservations, **not OS RAM/VRAM quotas**. Dashboard now exposes worker binding, fresh identity/health, dispatch/receipt inspection and list/show/pull/remove/unload model actions with typed mutation confirmations. Four source-owned role presets are inspectable; all four generated configurations passed **actual installed OpenClaw schema validation**. Temporary HomelabObserver configuration executed OpenClaw `read` successfully against a workspace report containing an unprompted random challenge, refused `write` with 404 and left no requested output file; original minimal worker config was restored and Gateway readiness rechecked. No live homelab write credentials were supplied.

**Open gates / explicit limits:** GPU acceleration remains blocked for dedicated UID `pbcompute`: `/dev/kfd` and AMD `/dev/dri/renderD129` are `0660 root:render`, no read/write access. No bypass, sudo, chmod, group or AppArmor change was attempted. Administrator-only minimal temporary prerequisite: `sudo setfacl -m u:pbcompute:rw /dev/kfd /dev/dri/renderD129`; do not run this as the bot. After separate approval, device readback, removing this dedicated Ollama unit's explicit CPU-only visibility masks, compatible ROCm userspace and measured nonzero offload still need verification—ACLs alone do not prove GPU support. Four concurrent VM deployments are **not** claimed: one stable worker remains; a possible 4+1+1+1 vCPU / 4×8 GiB plan fits current logical admission caps but is deferred until the first accelerated worker/resource-performance gate is accepted. Role presets are validated, not four deployed workers. No automatic guest installation/profile deployment, background autonomous job executor, browser interaction acceptance or new visual dashboard review is claimed. Full evidence, recovery and exact service/private-path handoff: [docs/STAGE3_ACCEPTANCE.md](docs/STAGE3_ACCEPTANCE.md).

## Previous: Stage 3 partial real-worker checkpoint — superseded, retained history

On 2026-11-02, resumed the interrupted Stage 3 changes without resetting the tree. The Stage 1/2 repository now migrates SQLite v1 to v2 (workers/executions), with a regression test preserving existing machine, agent and job rows. **55 tests discovered: 54 pass, 1 optional libvirt-schema skip**; Node syntax/dashboard contract and `git diff --check` pass. The new unit/API tests use fake transports; they are not a substitute for the following hardware evidence.

The compute host currently has one **running** Stage 3 disposable VM `4accba4d-24c9-4942-aec9-fd54de816319` (4 vCPU, 8192 MiB, 32 GiB), not a Stage 2 leftover. The interrupted work installed OpenClaw 2026.10.9 and Node 24.22.2 inside that guest, with its own 0700 configuration/workspace, 0600 config/token, role file, browser enabled in config, and active user Gateway service; a live `openclaw config validate` passed. Management's stage3 SSH tunnels and compute host's Ollama service were active on readback. The local host model `qwen3:1.7b` is present; `/api/tags` advertises `tools`, and a **real native Ollama `/api/chat`** invocation returned a structured `checkpoint` tool call with `value: verified` (not text pretending to invoke a tool). This proves the model API path, not an OpenClaw browser tool end-to-end.

**Real job proof:** using an isolated Stage 3 management DB, a registered agent/worker and explicit `dispatch:<job UUID>` confirmation, `PlatformService.dispatch_job` reached the VM's authenticated OpenClaw `/v1/responses` endpoint over loopback SSH forwarding, returned `Checkpoint-ok.`, and persisted `succeeded` plus response ID `resp_9d9d4501-753a-4559-a4ee-85a3dff7b5a0`; a fresh repository read returned `succeeded`. Job UUID `ddeef7aa-4ea9-4de3-8058-988c41cb7252`. The scratch acceptance script's final assertion initially failed solely because it compared the model's capitalized `Checkpoint-ok.` case-sensitively; the persisted success and readback were real, but the script itself did not exit zero. The assertion was corrected without replaying the job. This is a **CPU-only Ollama checkpoint**: the dedicated `pbcompute` service UID lacked read/write access to `/dev/kfd` and the AMD render node in the earlier probe; no GPU or policy change was made, and GPU acceleration is **not** claimed.

**Remaining Stage 3 gates:** verify actual GPU/ROCm access under a separately approved least-privilege change rather than silently claiming acceleration; test tool execution through OpenClaw (not just Ollama's structured tool output); add authenticated installed-platform HTTP real-dispatch/restart acceptance (live Stage 2 platform process was not restarted or migrated); confirm VM identity/health against compute before registration, durable multi-process inference admission and timeout/cancellation semantics, and document recovery/rollback. Current `Admission` is single-process advisory memory reservation, not VRAM enforcement; a configured worker is not automatically verified as its VM; unresolved execution blocks re-dispatch. No Stage 4 Hermes/MCP changes. Preserve the running VM and its dedicated tunnels; do not create a duplicate. Scratch evidence/scripts reside under the active profile's `cache/scratch/stage3_*`, private credentials under its `private/`; neither is published. Do not print secrets.

## Previous: Stage 2 runtime acceptance complete and published at 4fbb418

Final clean-boot regression is fixed with TDD in the standard Ubuntu Desktop seed: fixed cloud-init runcmd enables NetworkManager, disables/stops only stale systemd-networkd-wait-online, and resets that exact unit's failure state after package installation. No arbitrary caller commands, broad failure reset, host privileged/security change or bot sudo/password change. Existing guests are not retrofitted.

New disposable VM `ddeb8488-6c06-4e38-918c-e1f187415b6b` was created/started/restarted/shut down/deleted entirely through the authenticated platform API using existing machine `e0778e6a-8b1c-484d-8372-0cf60a780b30`. Reboot changed boot ID; post-reboot cloud-init done/errors empty, NetworkManager-connected ens3/DNS/key-only SSH, active display-manager/guest agent, visually inspected Ubuntu greeter, **system running / zero failed units**. Total measured reboot startup **4.916 seconds**; obsolete networkd waiter disabled/not executed, NM's own waiter still enabled. Initial package-install boot took 4 min 47.832 s and Desktop became active after the tested reboot; no first-boot graphical readiness or logged-in bot graphical session is claimed.

Together with prior real resource/snapshot/lifecycle/negative tests below, Stage 2's authorized runtime gates are complete. Final platform/libvirt lists empty, new VM directory absent, no QEMU/passt/VM listeners, amdgpu preserved. Compute and management platform/tunnel user units remain enabled/active. Prior remote dirty channel/test edits were preserved/backed up, fixed files copied and compute restarted before create; local/remote code/test hashes and actual generated seed matched. Units run explicit checkout-backed Python modules, not a new standalone CLI installation.

Final tests: management **45 pass/no skips** with copied actual compute-host libvirt 12 RNG schemas (default without the opt-in environment: 44 pass + 1 skip); remote **45 pass/no skips** with actual installed libvirt 12 RNG; management Node syntax/dashboard contract pass with identical remote JS/test hashes. Remote Node is absent; no remote Node execution/package install is claimed. No commit/push; parent review/publication and closure acknowledgment precede Stage 3. No Stage 3 code or deployment yet. Exact operation IDs, logs, tests, deployment hashes and remaining non-gate limits: [docs/STAGE2_ACCEPTANCE.md](docs/STAGE2_ACCEPTANCE.md).

## Prior run: Stage 2 real guest/integration gates passed; clean-boot caveat then OPEN

The administrator's approved passt AppArmor repair was read back; running passt/libvirtd remained enforcing. Fresh VM `a14a9007-861a-436c-b962-6ab72b86823f` passed DHCP, key-only non-sudo bot SSH, cloud-init done with empty errors, Ubuntu Desktop packages, active display-manager/guest agent, visually observed Ubuntu greeter, reboot boot-ID change, pause/resume, graceful shutdown/re-start, offline resource growth/snapshot restore, live resources/snapshot/delete rejection, shrink rejection and cleanup. API tombstone/delete operation, empty managed/libvirt lists, removed VM directory, no orphan passt/QEMU or VM listeners and preserved host amdgpu were read back. No unrelated VM was touched.

Authenticated platform integration is now real, not only direct compute: management `http://127.0.0.1:8032/`, registry machine `e0778e6a-8b1c-484d-8372-0cf60a780b30`, compute via `http://127.0.0.1:19443`. Enabled/active management-only user units `project-bots-stage2-{platform,tunnel}.service` retain the working integration; isolated acceptance DB `/home/server1/.local/share/project-bots-stage2-acceptance/platform.db` was used because no live platform/default DB existed. Registry/compute API access survived service restarts; missing-auth requests returned 403. This is not production-platform migration, browser pairing/visual dashboard review or Stage 3 deployment. No Hermes config, privileged host policy, GPU/Ollama, remote dirty edits, commit or push changed.

**Open caveat:** Desktop switches ens3 to NetworkManager, but systemd-networkd-wait-online remains enabled and times out, adding about 120 seconds and leaving guest system state degraded. Functional SSH/DHCP/cloud-init/greeter/agent readiness passed after the wait; no privileged guest fix or unqualified clean-boot/full-stage completion is asserted. Bot has no graphical password/autologin, so only the GDM greeter, not a bot graphical session, was verified. Stock cloud-image growpart/resizefs automatically expanded the root partition/filesystem on the post-growth boot; the service itself sends no guest resize command. No snapshot application-data roundtrip or crash-injection/real-domain tampering rerun was performed.

Tests rerun: remote **45 pass/no skips**, including installed libvirt 12 RNG; management **44 pass + 1 optional schema skip**; Node syntax and dashboard confirmation contract pass. Only documentation changed in the repository in this acceptance rerun; remote base 815f145 plus earlier channel/test edits was preserved. Full exact hardware evidence, operation IDs, services and private evidence locations: [docs/STAGE2_ACCEPTANCE.md](docs/STAGE2_ACCEPTANCE.md).

## Historical first compute deployment (before approved repair): PARTIAL / BLOCKED

On 2026-11-02 the authorized compute PC `10.0.50.56` was deployed as unprivileged `pbcompute` (UID 1001) from public Git revision `815f145975b91fae19697de68edcfc58a9929f74`. The enabled/active user service listens only on `127.0.0.1:9443`; management SSH tunnel endpoint is `http://127.0.0.1:19443`. Official Ubuntu 24.04 qcow2 signed checksums were verified against the host's package-installed Ubuntu cloud-image trust keyring. **No privileged package installation, sudo, GPU/Ollama change, commit or push was performed in this deployment.**

Real disposable VM `9bc73046-7528-4d31-ba65-8b8e9029c5d1` completed create/start/inspect/pause/resume/graceful shutdown/offline resource growth/snapshot create+restore/delete. Readback confirms tombstone, empty libvirt/managed lists, no VM directory, and active service. **Guest SSH and cloud-init Desktop readiness FAILED:** no guest IPv4 lease; passt independently reproduces `Failed to add fd to epoll: Bad file descriptor` and leaves an orphan after guest shutdown. One failed repeat-start was preserved/reconciled locally against a stopped backup before cleanup. Root-level kernel/AppArmor diagnostics are required next; no security policy bypass was attempted. Restart/graphical session/live-operation negative cases remain unverified on hardware.

A separate missing guest-agent transport was fixed with observed RED→GREEN regression test and actual libvirt definition/schema validation. Remote checkout contains the same uncommitted `compute.py`/test patch. **45 tests pass on compute including installed libvirt 12 schema; management default discovery is 44 pass + 1 optional schema skip.** Node syntax/dashboard contract and whitespace checks pass. Full evidence, exact operation IDs, deployment paths, tunnel handoff, and next administrator diagnostics: [docs/STAGE2_ACCEPTANCE.md](docs/STAGE2_ACCEPTANCE.md).

The following is the **historical software checkpoint before compute access**, retained to distinguish its claims from the later deployment. Its pending/no-deployment statements do not describe the current deployment above.

## Historical checkpoint: Stages 1–2 software; real host acceptance then PENDING

Baseline for this change: public `main` **80fef4c**, Stage 1 with **22 passing tests**. No commit/push, host package/service installation, actual VM mutation, guessed-IP probe, Ollama change or Hermes environment configuration was performed in this checkpoint. Parent review/publication is separate.

This is a **software implementation and test report, not a compute deployment report**. User-supplied management context is EliteDesk `10.0.50.10`, `/dev/kvm` present and `virsh` absent. It does not establish compute capability. Compute access has not been supplied; `10.0.50.30` remains an example, not a verified address. Intended compute is the existing Ubuntu Desktop i7-12700K/64 GB/RX 6800 PC; no Proxmox migration or GPU passthrough is proposed. Real virtualization, connectivity, passt support, guest boot/SSH/Desktop and host resource impact remain unverified.

## Stage 1 preserved

- Existing setup local/web, provider JSON, pairing/Host/Origin/CSRF protections, Codex helpers, installer, development-main updater and cautious/idempotent uninstaller remain available.
- `project-bots serve`: default loopback port 8032; persistent separate private SQLite machine/agent/job/settings state, FK enforcement, atomic claims, transitions, input limits and machine token reference remain intact.
- Registry machines remain **unverified** records, agents **registered** definitions. Jobs/progress/results are reports, not real worker execution. No inference endpoint is contacted by settings/registry/job operations; cloud fallback stays false.
- Dashboard retains registration, jobs, assignment/cancel/inspection/settings and pairing-session refresh behavior. Stage 2 compute calls occur only through explicit controls.
- All original **22 tests** pass, including disposable-home installation/update/uninstall, installed platform restart persistence, authentication/browser guards and job claim races.

## Stage 2 shipped software

### Dedicated compute boundary

`project-bots machine-service --catalog /absolute/trusted/catalog.json --state-dir /private/state` defaults to **127.0.0.1:9443**, separately configurable from the platform. Environment token reference (`--token-env`, default `PROJECT_BOTS_COMPUTE_TOKEN`) requires >=32 ASCII/non-whitespace characters and >=16 distinct characters, with cryptographically random generation documented. This rejects obviously weak inputs but cannot prove entropy. All routes authenticate; browser Origin/fetch metadata is refused. Non-loopback binds require configured TLS certificate/key; no raw libvirt LAN socket or general shell/command/XML/path endpoint.

`compute.py` uses supported `virsh --connect qemu:///session` fixed argv, plus fixed `qemu-img` and `cloud-localds` invocations, **never shell=True**. Domain definition requests `--validate`. Host commands have 120-second deadlines and redacted errors. No automatic dependency/service installation occurs.

Supported operations: health/resource/capability observations; managed list/detail; provision; start, graceful shutdown/restart, pause/resume; offline CPU/RAM/disk-growth changes; offline standalone-qcow2 internal disk snapshot create/restore; offline delete; operation inspection; localhost console/SSH connection information. Shutdown/restart are requests, not forced transitions; callers poll fresh detail.

### Confinement and provisioning

- Managed names `pb-<canonical UUID>` plus persistent VM intent, durable service-owner UUID, matching domain UUID/owner XML metadata and exact managed disk sources; name prefix alone is insufficient authority. Symlinked managed disks/directories and non-loopback graphics/GPU hostdev mismatches are refused.
- Separate private per-VM directories, standalone qcow2 converted disks, read-only seed, and fixed-file-only deletion after ownership/offline verification. No writable shared backing disks, arbitrary storage paths or GPU passthrough.
- Trusted admin-local catalog pinning actual image path/SHA-256; canonical paths, trusted owners, no group/other write, standalone qcow2 and virtual-size validation. Administrator must independently establish publisher/image trust; same-UID/root administrators remain trusted.
- Fixed Ubuntu cloud-init package list (`ubuntu-desktop-minimal`, `openssh-server`, `qemu-guest-agent`), package update, locked non-sudo `bot`, disabled root/password SSH and ed25519 public key only. No supplied commands, raw YAML/XML, custom packages, password or private key inputs.
- Session user-mode **passt** networking with loopback-only allocated SSH forwards; SPICE localhost graphics. Generated XML validates against libvirt v10.0.0 schema. Actual host network/socket behavior is still pending.
- Per-VM CPU/RAM/disk bounds and conservative aggregate reservations/headroom; start checks current available RAM. These are admission controls, not guaranteed quotas against concurrent desktop/Ollama load. Disk snapshots/growth/guest writes can still consume storage.

### Management integration and explicit intent

`machine_client.py` resolves the registry endpoint and credential environment reference, requires verified HTTPS except explicit loopback SSH-tunnel HTTP, refuses redirects/proxies/URL credentials/path/query/fragment and bounds reads. An optional admin-local CA bundle is selected by `PROJECT_BOTS_MACHINE_CA_FILE`. No hardcoded compute host or automatic discovery. Calls occur outside platform repository transactions. Narrow authenticated `/api/machines/<id>/health`, `/vms`, `/vms/<id>/<action>` and `/operations/<id>` routes preserve Stage 1 browser protections; compute credentials never enter browser requests/responses.

Every mutation requires an operation UUID and exact per-action confirmation (`create` or `<action>:<VM UUID>`). Dashboard typed prompts send no mutation on cancellation/mismatch, display result data through textContent only, retain request/operation information after errors and support explicit operation inspection. These fields express **caller intent, not cryptographic human approval**; authenticated programs must obtain actual permission. Job/VM/result text never authorizes or executes a command.

### Durability and uncertainty

A separate private compute SQLite DB stores singleton owner identity, VM desired intent/resources/phase/tombstones and operation ID/target/action/digest/timestamps/status/result. OS flock serializes mutations across threads/processes, without SQL transactions spanning host commands. Exact successful replays are cached without re-execution, including after restart; changed payload/ID or busy/uncertain operations conflict. Partial provisioning intent/disks remain inspectable. Crashed/running or unknown operations block later target mutations until **local administrator reconciliation**; no automatic retries, destructive cleanup or remote force-unlock exists.

Adapter HTTP timeout is 15 seconds, deliberately shorter than a possible conversion: callers must keep the original UUID/payload and inspect, not blindly create again. Mutation failures or failed post-mutation observation become uncertain operations. Graceful power-operation success means the request completed; observed state can still differ from desired.

## Files and audit scope

New production files: `project_bots/compute.py`, `machine_http.py`, `machine_client.py`. Modified production files: `cli.py`, `service.py`, `platform_web.py`, `dashboard.html`, `dashboard.js`. Stage 1 `repository.py`, provider setup/config, installer/update/uninstaller implementation remain unchanged. Installer copies the whole package, so new modules ship automatically; installed-platform tests import the new modules successfully.

New verification files: `tests/test_machine.py`, `tests/test_domain_schema.py`, `tests/dashboard_vm.cjs`, `scripts/accept_machine.py`. Documentation updated: `README.md`, `docs/API.md`, this status; new `docs/COMPUTE_HOST.md` gives administrator/user prerequisites, session-libvirt limitations, transport/catalog setup, actual acceptance, rollback and uncertainty handling. No systemd unit or host setup script is installed.

## Verification actually performed

Development followed red→green vertical slices: authenticated compute HTTP/transport policy; trusted provision/generated XML/private disk; lifecycle/offline edits/snapshots/ownership; durable idempotency/timeouts; input/storage policy and health/console; fake HTTP adapter; CLI launch/refused insecure bind; registry-backed platform routes/confirmation; dashboard canceled-versus-authorized mutation contract/forms; trusted catalog/snapshot format checks; low-memory/partial provisioning; post-mutation uncertain observation; singleton owner/schema validation; CA configuration errors. New acceptance checks additionally exercise already implemented behavior. No fabricated host results.

```sh
python3 -m unittest discover -s tests -v
node --check project_bots/dashboard.js
node tests/dashboard_vm.cjs
# Optional, no daemon/VM needed, with administrator-supplied sibling schemas:
PROJECT_BOTS_DOMAIN_RNG=/path/to/libvirt/schemas/domain.rng \
  python3 -m unittest discover -s tests -p test_domain_schema.py -v
# Checkout hygiene:
git diff --check
```

Current discovery: **44 tests**, **43 pass + 1 optional schema skip** when the schema environment variable is absent. The optional test was separately executed and **passed** against actual upstream **libvirt v10.0.0 Relax NG schemas** (nine files downloaded into temporary scratch), using installed libxml2 through ctypes; generated domain XML is not merely a mock string. Node syntax and fake-DOM confirmation contract pass. Stage 1's 22 tests all pass. Temporary TLS test verifies a trusted chain succeeds, untrusted chain and hostname mismatch fail. Local HTTP tests exercise real sockets with a **fake backend**, distinctly not real VM integration. Mocked fixed argv covers provisioning/lifecycle/resources/offline snapshots/delete, ownership mismatch, resource admission, concurrent duplicates, persistent replay and uncertain failure. Opt-in script refusal is tested before keys/network access; its lifecycle flow is tested with a fake client, not libvirt.

No real browser visual review of the new Stage 2 UI is claimed; the existing Stage 1 browser review is historical, not evidence about these new controls. No actual libvirt VM has been created, started, paused, edited, snapshotted, shut down or deleted by this checkpoint.

## Remaining limitations / acceptance gate

1. **Real host gate remains open.** Obtain actual compute access/addresses and administrator approval. Verify Ubuntu/libvirt/QEMU/passt/KVM, catalog signature/hash, user daemon/runtime, resource headroom and TLS/SSH/firewall. Do not infer compute access from management `/dev/kvm` or an example IP.
2. **Host install is manual and privileged where necessary.** Prefer dedicated service UID + `qemu:///session`; no blanket system-libvirt group membership recommendation. Session daemon activation/user runtime and KVM device access must be reviewed locally. Same-UID/root processes are trusted; no defense against their direct libvirt/file races. No Proxmox, GPU passthrough or host Ollama changes.
3. **Actually exercise the lifecycle.** `scripts/accept_machine.py` requires `--confirm-real-host-mutation 'CREATE START SHUTDOWN DELETE DISPOSABLE VM'` and an actual public key/endpoint/token. It creates only a disposable VM and stops on uncertainty without forced cleanup. Perform the manual extended/resource/snapshot/SSH/cloud-init/Desktop checks in host docs too. A running domain or installed Desktop package list does not prove graphical session readiness; key-only guest has no configured graphical password/autologin.
4. **Recovery is deliberately conservative.** No automatic reconciliation/force-unlock CLI/API, orphan adoption, rollback of uncertain host mutations or snapshot retention/deletion. Local reviewed repair of a stopped backed-up state/domain may be needed. Preserve owner DB. Cached successful operation results can be stale; read detail for current observations.
5. **Small trusted deployment only.** Single administrator, no RBAC/mTLS, pagination/retention, durable approval policy or public-facing DoS hardening. No custom networking, live snapshots, force-off/reset, disk shrinking, guest filesystem expansion or guest command API. No absolute CPU/RAM/disk quota guarantee against concurrent host activity.
6. **Software delivery is not publication/deployment.** No commit/push/remote update/host install was performed; parent reviews and publishes separately. Update/uninstall preserves VM state/domains and requires manually stopping processes; it does not tear down host packages/users/firewall/tunnels.

## Historical Stage 3–5 plan (superseded in part by current checkpoint)

- **Stage 3:** per-VM OpenClaw worker runtime/bootstrap/identity, heartbeats, leases/claim ownership, results/cancellation and shared host Ollama integration with measured resource limits.
- **Stage 4:** Hermes remains the user's assistant, later connected through narrow authenticated MCP operations. No Hermes configuration/plugin/service changes here.
- **Stage 5:** orchestration, independent approval/reliability/recovery and operational hardening after actual Stage 2 acceptance. No autonomous workforce is claimed.
