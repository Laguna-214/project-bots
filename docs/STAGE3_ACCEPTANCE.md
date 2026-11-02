# Stage 3 acceptance: GPU/four-worker checkpoint; browser gate open

**Current outcome:** RX 6800 ROCm GPU offload, automated deployment of four independent role VMs, authenticated brokered tool jobs, durable admission and exact installed-process restart persistence passed. Full Stage 3 remains blocked on a supported **sandboxed guest-browser installation** requiring a human-owned trusted privileged guest bootstrap/package step; no sandbox/security bypass was used. Exact current evidence, final UUIDs/jobs, measured VRAM and recovery: **[STAGE3_GPU_POOL_ACCEPTANCE.md](STAGE3_GPU_POOL_ACCEPTANCE.md)**.

Everything below is the **superseded CPU-only checkpoint**, retained as historical evidence; its GPU-access/scale/automatic-deployment pending statements no longer describe the current deployment.

# Historical: installed CPU worker platform

**CPU-only operational acceptance passed; Stage 3 GPU/scale acceptance remains open.**
This is not a claim of four deployed workers, GPU acceleration, an autonomous job daemon, or automatic guest installation/profile deployment. No cloud fallback, MCP/Stage 4 or Hermes runtime/configuration changes were made. Parent handles commit/push.

## Live deployment and identifiers

| Boundary | Verified target |
|---|---|
| Management | EliteDesk `server1`, `10.0.50.10` |
| Installed Stage 3 platform | `http://127.0.0.1:8033/`, enabled/active user unit `project-bots-stage3-platform.service` |
| Previous Stage 2 platform | `http://127.0.0.1:8032/`, not restarted/migrated by this run |
| Compute transport | Registered machine `e0778e6a-8b1c-484d-8372-0cf60a780b30`, `http://127.0.0.1:19443`, compute host `pbcompute@10.0.50.56` |
| Existing worker VM | `4accba4d-24c9-4942-aec9-fd54de816319`, running, 4 vCPU / 8192 MiB / 32 GiB |
| Existing agent | `b4fdb7e8-d14c-482e-b415-eda8d84ad41b` |
| Guest account | `bot`, UID 1000, own group only, key-only/non-sudo |
| Gateway | OpenClaw `2026.10.9`, Node `24.22.2`, guest loopback `18789`, management tunnel `http://127.0.0.1:19889` |
| Read-only identity | Guest loopback `18790`, management tunnel `http://127.0.0.1:19890`, enabled guest user unit `project-bots-worker-identity.service` |
| Shared native Ollama | Compute loopback `11434`, management tunnel `http://127.0.0.1:21434`, guest reverse tunnel loopback `11434` |
| Actual local model | `qwen3:1.7b`, observed `/api/ps` context 32768, size 5296619519 bytes, `size_vram: 0` |

No duplicate/replacement VM was created or existing VM deleted. Actual libvirt UUID, cloud-init instance UUID and identity sidecar UUID matched. Guest boot UUID was `04b7c161-cd3d-4efd-a2d4-37952055d6c4`; cloud-init was done with empty errors, system state running and Gateway active.

### Private local state — paths only, never publish contents

Base `P=/home/server1/.hermes/profiles/project-bot/private`:

- Installed executable: `$P/stage3-installed/.local/bin/project-bots`.
- Installed package: `$P/stage3-installed/.local/lib/project-bots/project_bots`.
- Durable DB: `$P/stage3-acceptance/platform.db`; schema **3**. Stage 2 DB was read through SQLite `mode=ro` only when copying its existing machine record.
- Credential environment files: `$P/stage3-platform.env`, `$P/stage3-worker.env`, existing `$P/gaming-compute.env`. Tokens never enter browser form fields or documentation.
- Existing guest SSH key/known-hosts: `$P/stage3-worker-ed25519`, `$P/stage3-known-hosts`.
- Management enabled user units: `project-bots-stage3-{platform,host-tunnel,worker-tunnel}.service` under `~/.config/systemd/user/`.
- Guest identity package: `~bot/.local/lib/project-bots-worker/project_bots`; identity unit uses `OPENCLAW_GATEWAY_TOKEN` from the existing private Gateway environment file.

The installed revision marker still names base Git HEAD `8bdec74`: the installer copies this uncommitted working tree. It is not evidence of publication. Compare deployed source hashes, not that revision marker, before handing off an update.

## Real acceptance evidence

### Authenticated installed executable, dispatch and restart

The private acceptance harness installed with `install.sh` into the isolated Stage 3 home, launched **that installed executable** on a dynamically allocated loopback port, checked missing authentication returns 403, dispatched through the API, stopped it, restarted against the same DB and compared exact job and execution receipts.

Latest complete harness job: `85cd83d8-3189-4d1a-a97f-3612ec1ab022`, response `resp_fe8584f8-20b4-4971-9e82-4bff63fd2f95`, status `succeeded`, output `Model name: ollama/qwen3:1.7b`. Harness exited zero with `installed_http_restart_readback PASS` and native unload/pull/remove readback passes.

The persistent installed `8033` service independently completed:

| Job | Gateway response | Wall seconds |
|---|---|---:|
| `3f78c617-6327-4eb9-9aa8-cdaed4039346` | `resp_bd6f2124-5910-4aec-bea8-3680ac8ca1a3` | 17.572 |
| `46781c36-a062-48be-a092-5b2c29f71bc6` | `resp_30868a25-88f8-4bd8-99e8-9dabb4d60e94` | 5.899 |

Both returned the real local model name, persisted success and retained the same loaded-model digest. Final deployed-source check compared **17 public source/assets** against both the management installation and guest identity package. After restarting the persistent installed unit, exact prior job, receipt and worker records matched; a fresh identity-gated dispatch completed as job `71fa186e-d5fb-41bb-99a9-4a7e8e549b27`, response `resp_82c316f4-a016-4e89-bf4f-3e3f0a8a16f0`, returning `Model name: ollama/qwen3:1.7b`. Its retained trajectory shows `session_status` call/result **ok** at `19:16:24Z`. Final DB checks found no active/uncertain admission or executions and no foreign-key violations.

These are individual CPU load/reuse observations, not statistical performance or GPU evidence. Earlier load/reuse measurements were 14.882 / 6.218 seconds. No invented token-throughput or VRAM result is supplied.

### Actual OpenClaw tools

Retained trajectory for successful tool-proof job `6dd1431a-7020-4be1-8098-d628d87b87b6`, response `resp_acc141e9-ecdb-428d-8857-1b0b0d9095b1`:

```text
18:33:27Z tool.call    session_status
18:33:27Z tool.result  session_status ok
18:33:29Z model.completed ollama/qwen3:1.7b done
18:33:29Z session.ended success
```

This is execution inside OpenClaw, not merely structured JSON returned by Ollama. Explicit `tools.toolSearch: false` exposes the tiny catalog directly; the small local model did not reliably navigate the automatic deferred-tool catalog.

Four named preset generators exist: `ProjectWorker`, `Researcher`, `Reviewer`, `HomelabObserver`. `worker_config(profile, role=...)` generates per-VM policy and `role_instructions(role)` supplies workspace instructions. All four configurations passed the **installed OpenClaw 2026.10.9** `config validate --json`, with no warnings. These checks do not deploy four role VMs.

A temporary HomelabObserver config on the same existing guest allowed only `read` / `session_status`, workspace-only files, and explicit denial of write/edit/patch/exec/process/browser/gateway/nodes/message. A report contained a fresh challenge not included in the prompt; the model retrieved it through actual `read`:

```text
session user homelab-readonly-9f2eeba9-2296-4168-bdc4-e2a3bcc61af0
response resp_d0cfb48b-8654-474a-ac15-68ad3c521da5
18:52:33Z tool.call    read
18:52:34Z tool.result  read ok
18:52:36Z session.ended success
```

A direct HTTP `write` invoke returned 404 and the requested output file was absent. This negative invoke alone is not proof about all policy layers: direct `/tools/invoke` also does not expose the core `read` tool on this installed runtime. The positive read proof therefore used an agent Responses run, not direct HTTP tool invocation. Original minimal Gateway config was restored byte-for-byte in `finally`, its service restarted and authenticated readiness checked. No live homelab write credentials were granted; HomelabObserver consumes explicitly supplied workspace reports only.

### Registration and fresh identity/health

New `project_bots.worker_health` is a fixed **read-only** loopback HTTP sidecar: authenticated `GET /v1/health` only, no shell/command/job/file/configuration API. It reports the guest's cloud-init instance ID, boot ID, actual local model/context/temperature/output configuration and a successful authenticated Gateway `/v1/models` check. It refuses browser Origin/fetch metadata; loopback Host ports may differ across SSH forwarding. Error responses do not echo config/credentials.

With an `identity_endpoint`, platform registration requires an agent assigned to a compute machine, verifies the compute-owned domain is running with the expected VM UUID, verifies fresh sidecar UUID/boot/profile evidence and authenticates the configured Gateway using that worker's unique credential. It saves `verified` only after those observations. The actual worker above was registered through installed HTTP and read back; subsequent fresh health returned its expected UUID, boot ID, `qwen3:1.7b`, context 32768, temperature 0, max output 256, native Ollama true, cloud fallback false.

Registration without identity remains a legacy **configured** record, not an online worker. Every real dispatch performs fresh checks before recording remote execution. Worker health is an observation under trusted VM/service credentials, not TPM/hardware attestation or protection against a compromised same-UID worker. A prior `verified` record is not a permanent online claim; use fresh health. There is no periodic heartbeat daemon or automatic agent profile deployment.

### Model management and cancellation

Through the installed authenticated platform:

- Native `/api/tags`, `/api/ps`, `/api/show` worked.
- Explicit unload used `/api/generate` with no prompt, `keep_alive: 0`, `stream: false`; loaded inventory read back absent.
- Previously absent disposable `smollm2:135m` was pulled, present inventory verified, explicitly deleted and absent inventory verified. It was never assigned to or used by a worker; existing `qwen3:1.7b` was preserved.
- Attempting to remove assigned `qwen3:1.7b` returned 409.
- Queued cancellation persisted canceled with no execution receipt.
- Cancellation during a real dispatched run returned 409; the run completed normally. No remote stop/cancel is claimed.

## Durable admission, resource bounds and uncertainty

SQLite v3 adds `inference_admission` with durable priority/FIFO sequence, queued deadline and active/uncertain reservation state. Production uses this gate for Gateway dispatch and model mutations. Defaults: one active operation, 8192 MiB logical reservation budget, four queued tickets, 30-second queue wait. Lower numeric priority wins; equal priority follows SQL sequence. Transactions cover admission decisions, never network/host commands.

Independent-process tests prove no overlapping full-budget inference. A killed process leaves its active reservation intact; an uncertain Gateway/model mutation retains its reservation. Queued wait expiration deletes only queued intent and does not mark remote execution or cancel any remote work. Active reservations do **not** expire by clock or PID: a dead client does not prove a remote run stopped.

Real dispatch requires an installed tool-capable local tag. Reservation floor includes weights, full FP16 KV cache using observed layer/KV-head/key/value geometry and requested context, 25% overhead, workspace headroom, other loaded models and an observed-loaded-size floor. Unknown geometry or inconsistent loaded context fails closed. Current observed model preflight returned **required 7125 MiB / reserved 8192 MiB**. This is not a universal model estimator, GPU offload proof or an OS/cgroup memory quota. Uncoordinated external Ollama/desktop users can still change host load; separate management DBs do not share platform tickets, while the dedicated Ollama daemon additionally enforces one parallel inference and one loaded model.

Gateway request deadline is 300 seconds; generated Gateway config has a 240-second agent timeout. Ollama pull request deadline is 600 seconds. A transport timeout/error after sending work is **uncertain**, not automatically canceled or safely retryable. Gateway failure details/credentials are not echoed. Execution receipts retain started/finished timestamps and response IDs. Queue timeouts happen before a receipt and return 503 with the job still queued.

### Reviewed local reconciliation performed

First new tool attempt `932789b1-7f2b-4f9c-84ee-43b30260f27d` produced an upstream Gateway format failure with `tools=0`, response `resp_ca4f6d32-2100-4c91-ad78-ccf375036498`; the platform correctly retained uncertain state. A second attempt `8cbaa026-452a-4757-a014-3c6d38b3bd03` hit Gateway startup before readiness and created no guest session. After inspecting guest session/runtime evidence and restarting the Gateway, these exact failed runs were locally reconciled to failed with DB backups and their sole retained reservations removed. Neither job was replayed, and no generic remote force-unlock endpoint was added. The later successful jobs are distinct explicit tasks, not retries of those uncertain IDs.

## GPU prerequisite and scale decision — still open

Live checks under `pbcompute` UID 1001 showed groups `pbcompute,users,kvm` and no read/write access to either device:

```text
/dev/kfd             0660 root render
/dev/dri/renderD129  0660 root render  # AMD 1002:73bf, amdgpu
/dev/dri/renderD128  0660 root render  # Intel 8086:4680, i915; not requested
```

A separately approved administrator can grant the narrow temporary device ACL:

```sh
# Administrator on compute host, not the bot; NOT executed by this task:
sudo setfacl -m u:pbcompute:rw /dev/kfd /dev/dri/renderD129
```

This leaves normal group/device modes and AppArmor enforcement intact, but ACL/device persistence must be reviewed locally; enumeration can change after reboot. Capture prior ACLs before an approved change and restore those exact ACLs for rollback. Do not add broad group memberships or chmod devices as a workaround.

**Additional non-root follow-up is essential:** the dedicated `project-bots-ollama.service` intentionally still forces CPU-only visibility (`ROCR_VISIBLE_DEVICES=-1`, `CUDA_VISIBLE_DEVICES=-1`, `GGML_VK_VISIBLE_DEVICES=-1`, `OLLAMA_VULKAN=0`). After approval/device access, review compatible local ROCm userspace/backend availability, remove only appropriate CPU-only masks in that dedicated unit, restart it, and prove real offload with runner logs and nonzero `/api/ps` VRAM. A targeted file-name probe under the current local artifact tree `~pbcompute/.local/opt/ollama-v0.40.13` found **zero ROCm/HIP/rocBLAS/HSA-related backend files**; this does not establish whether compatible libraries exist elsewhere on the host. Local compatible backend availability remains unverified. ACL success alone cannot establish RX 6800 runtime compatibility or performance. No GPU verification is claimed here.

Latest host resource observation: total 62967 MiB, available 45730 MiB, zero used swap, 902007197696 bytes available on managed storage. Only the existing VM was present. A possible future pool preserving its 4 vCPUs and adding three 1-vCPU / 8192-MiB / 32-GiB VMs uses seven aggregate vCPUs and 32768 MiB RAM, within existing logical caps; shared inference must remain serial until measured otherwise. No new scale VMs were created: accelerated first-worker acceptance, sustained headroom/desktop impact and throughput remain unverified. Do not claim four-worker acceptance from preset/schema tests or current free memory alone.

## Recovery, update and rollback

1. Keep original job/operation IDs and inspect exact execution/compute records. Never re-dispatch uncertain work or assume closing HTTP stopped it.
2. For stuck active/uncertain admission, stop all platform processes using the DB, back it up via SQLite backup, inspect the matching guest session/response and actual remote run state. Stop/resolve that exact remote run through an approved local administrative procedure if needed. Only then reconcile the exact execution and reservation locally. Reservations are not automatically reclaimed; no public force-unlock exists.
3. Back up SQLite before deploying schema 3. Older schema-2 code deliberately refuses a schema-3 database. Do not downgrade code against live schema-3 state or restore a stale DB while a remote job may still run.
4. Install updated code into the isolated Stage 3 home and restart only `project-bots-stage3-platform.service`. Updating copied files does not reload Python already running. Read exact successful job/receipt and fresh worker health back after restart; keep Stage 2 untouched.
5. Guest role/profile changes are separate explicit deployment: back up private config, generate `worker_config(profile, role=...)`, validate with installed OpenClaw, update workspace role instructions, restart/poll authenticated readiness, then register the matching profile. Model/context changes in the dashboard do not silently alter the guest; mismatches are refused. Preserve each VM's unique Gateway credential and workspace.
6. To stop Stage 3 without destructive cleanup: stop its management platform/tunnel user units and the dedicated guest worker/identity units as appropriate. Do not delete VM disks, owner DB, credentials or unrelated Stage 2 units; uninstalling a CLI does not delete VMs.

## Evidence harnesses and software checks

Private scratch prefix: `/home/server1/.hermes/profiles/project-bot/cache/scratch/stage3_`.

- `installed_accept.py`: isolated installed executable, actual authenticated dispatch/restart and native model mutations/readbacks.
- `runtime_verify.py` / `runtime_evidence.json`: persistent installed service, wall timings, loaded inventory, active-cancel refusal, queued cancellation and assigned-model deletion guard.
- `verify_identity_http.py`: installed registration, exact worker readback and fresh compute/guest/Gateway health.
- `role_validate.py`: all four configs validated on actual guest OpenClaw.
- `homelab_readonly.py`: temporary scoped role, random report read proof, negative write/absence and guaranteed config restore.
- `deploy_identity.py` / `bind_identity.py`: one-time deployment/binding harnesses with explicit assertions; **not rerunnable public bootstrap installers**.

Do not blindly rerun one-time harnesses: they retain private intent/backups and some deliberately refuse an existing target. Inspect live state first. Scripts/private credentials are not committed.

```sh
python3 -m unittest discover -s tests -q
node --check project_bots/dashboard.js
node tests/dashboard_vm.cjs
git diff --check
```

Observed default result: **68 discovered / 67 pass / 1 optional libvirt-schema skip**. Tests use fake transports where named, real independent processes for admission, real installed executable/HTTP for platform tests, and separately documented real hardware scripts above. No new visual browser review is asserted.

Official references checked:

- https://docs.openclaw.ai/providers/ollama — native Ollama base URL **without `/v1`**, because OpenAI compatibility can break tool calls.
- https://docs.openclaw.ai/gateway/openresponses-http-api — authenticated normal agent execution through `/v1/responses`.
- https://docs.openclaw.ai/tools/tool-search — `tools.toolSearch: false` restores direct schemas.
- https://docs.openclaw.ai/cli/config — explicit schema validation and `OPENCLAW_CONFIG_PATH`.
- https://docs.openclaw.ai/gateway/tools-invoke-http-api — trusted operator token scope, normal tool policy, and direct-invoke limits.
- https://docs.ollama.com/api/generate — `keep_alive: 0` unloading.
