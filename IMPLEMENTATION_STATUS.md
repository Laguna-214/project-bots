# Implementation status

## Current: Stage 3 partial real-worker checkpoint — NOT complete

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
