# Historical Ollama Stage 3 GPU and four-worker checkpoint

> **Superseded:** shared inference has migrated to llama.cpp and the managed Ollama runtime/units were removed. Do not run the Ollama recovery instructions below. Current backend, child-port isolation, jobs, model lifecycle and service handoff: [LLAMA_CPP_MIGRATION.md](LLAMA_CPP_MIGRATION.md). Browser sandbox evidence below remains applicable.

**GPU acceleration, automated VM/Gateway deployment and four-worker tool dispatch passed. Full Stage 3 remains OPEN only for sandboxed guest-browser installation/interaction acceptance.** This is a measured checkpoint, not a claim that `browser.enabled` supplies an installed browser. No commit/push, Stage 4, Hermes configuration, host driver, AppArmor, device/group or other privileged change was performed. The administrator separately added `pbcompute` to `render` before this run.

## Verified GPU backend

- Fresh compute SSH: UID 1001, groups `pbcompute,users,render,kvm`; both AMD `/dev/kfd` and `/dev/dri/renderD129` readable/writable. Host remains Ubuntu 26.04.1, kernel 7.0.0-42-generic, PCI `0000:03:00.0`, amdgpu, RX 6800 / gfx1030. No passthrough.
- Official Ollama v0.40.13 AMD archive `ollama-linux-amd64-rocm.tar.zst`, 1052345675 bytes, verified against GitHub release asset SHA-256 **`5b1b0a7a6370755a3472b1fb2a63e569a5b0114acef2a9067047bf8e5d98ecc1`**. Separate user-local tree `/home/pbcompute/.local/opt/ollama-v0.40.13-rocm` contains official ROCm 7.2 libraries; original CPU tree untouched. The official Ollama support table lists RX 6800 / gfx1030. This records observed compatibility, not AMD certification of this OS combination.
- `hipInit` and `hipGetDeviceCount` succeeded with one AMD device. Actual Ollama logs identify ROCm/gfx1030, RX 6800, 16 GiB and **offloaded 29/29 layers to GPU**. For `qwen3:1.7b`, context 32768, native `/api/ps` reported **size = size_vram = 5112583945 bytes**; logs place 3584 MiB KV cache and 168.03 MiB compute buffer on ROCm0.
- First accelerated installed-platform jobs `29623e2e-daa2-4752-a8b9-08e9f110e99c` / `resp_817356a5-c3d3-4cf3-a10a-a7b899782a1f` and `27895d7a-a02b-4146-bba5-bad533710a35` / `resp_de56af9a-eae3-4532-9d5b-a2825919ab12` succeeded in 3.206 / 1.004 seconds. These individual load/reuse observations are not a throughput benchmark.

### Refreshing only inference groups

The existing compute user manager still has old groups. Neither `sg` nor `newgrp` exists on this host; an initial attempted `sg` unit failed before execution and was restored. Restarting the user manager would endanger its VMs and was not done. Instead management's enabled user unit **`project-bots-stage3-ollama.service`** supervises a fresh strict-key SSH login running `systemd-run --user --scope --unit=project-bots-ollama-gpu ... ollama serve`. That scope inherits fresh login groups. ExecStop stops only that dedicated scope; no VM or user manager restart. There is no inherited ROCR/CUDA visibility mask or HSA override; Vulkan stays explicitly disabled.

Original compute `~/.config/systemd/user/project-bots-ollama.service` is restored byte-for-byte and **disabled/stopped** to avoid a second CPU daemon. Backup: `.service.pre-render-rocm`. Management owns supervision of the GPU scope; after management/connectivity failure a restart stops/replaces only that scope. Interrupted inference remains uncertain in the durable admission DB and requires reviewed reconciliation, not blind retry.

## Four independent live workers

| Role | VM UUID | Agent UUID | Gateway / identity loopback ports |
|---|---|---|---|
| ProjectWorker, preserved original | `4accba4d-24c9-4942-aec9-fd54de816319` | `b4fdb7e8-d14c-482e-b415-eda8d84ad41b` | 19889 / 19890 |
| Researcher | `55545d36-bd05-4e48-9eb4-cea5fbe8c8f4` | `4501e5f0-9dae-4e2b-8bb9-f6b39803b584` | 19891 / 19892 |
| Programmer | `4c827ae7-02ab-40f8-8cc9-3af9c6340526` | `6ae5af9b-1c3f-4c62-90d0-ffd96a30a850` | 19893 / 19894 |
| HomelabEngineer, read-only | `b4974b11-1c8a-409a-9f04-6401b9407ff1` | `75e8ef4e-6371-44ad-b40e-55a28cda467f` | 19895 / 19896 |

Each has its own guest disk, non-sudo `bot`, workspace/configuration, unique SSH and Gateway credentials, browser profile configuration and independently generated local model profile. All currently select the same installed `qwen3:1.7b` tag intentionally; sharing one GPU does not force source worker/model profiles to be identical. Only Researcher permits browser tools; browser binaries/readiness remain the open gate below. Original worker policy/workspace/VM and boot UUID were preserved; only its private provider authentication and inference reverse-tunnel destination changed with backups. No live homelab write credentials were supplied.

Original VM keeps 4 vCPU; each added VM has 1 vCPU / 8192 MiB / 32 GiB. Total admission reservation: 7 vCPU, 32768 MiB RAM, 128 GiB virtual disks. With all four up and inference loaded, observed host available RAM was 24091 MiB of 62967 MiB; swap used 1 MiB, storage available 872177061888 bytes. These are snapshots, not OS memory quotas, sustained desktop responsiveness or browser-load benchmarks. Inference remains serial, not four simultaneous GPU models.

### Actual automated workflow

Public **`scripts/provision_worker.py`**, `project_bots/provision.py` and `project_bots/guest_bootstrap.py` created/deployed all three new guests through authenticated installed-platform/compute APIs and strict SSH. No caller-supplied root commands, shell provisioning API, cloud scripts or guest sudo. Fixed trusted Stage 2 cloud-init installs Desktop/SSH/guest-agent; fixed non-root bootstrap downloads Node 24.22.2 (pinned SHA-256) and OpenClaw 2026.10.9 (pinned npm SHA-512), installs user-local, validates generated config on the actual runtime and enables Gateway/identity services. npm verifies transitive package integrity; a completely frozen transitive toolchain is not claimed.

Durable private intent is saved **before** create/start. A prior absent/uncertain create is refused, not replaced by a new UUID. Unmanaged existing OpenClaw configuration is refused. A known existing manifest resumes its exact VM; completed manifests only read fresh health. The final Researcher resume redeployed/revalidated the same UUID without duplicating it, then a second run was health-only. This is explicit maintenance, **not an unattended autoscaler**. Do not provision while jobs run; service dependency reload/restarts are part of this workflow. Initial guest SSH host-key enrollment is TOFU through authenticated compute SSH to the API-owned loopback port, then cloud-init UUID is checked; not hardware attestation.

Example for an already authorized Stage 3 deployment (paths contain secrets; never publish contents):

```sh
python3 scripts/provision_worker.py \
  --confirm 'CREATE AND DEPLOY ONE WORKER' \
  --manifest /PRIVATE_0700_DIRECTORY/worker.json --role Researcher \
  --machine COMPUTE_REGISTRY_UUID --platform http://127.0.0.1:8033 \
  --platform-env /PRIVATE_0700_DIRECTORY/platform.env \
  --compute-host pbcompute@COMPUTE_HOST --compute-key /PRIVATE_PATH/compute_key \
  --gateway-port 19891
```

Use a free pair of management ports; preserve/reuse the same manifest. Roles also accept Programmer and HomelabEngineer. This reference command defaults to the accepted qwen3 profile; changing deployment profiles remains an explicit validated deployment, not a dashboard write that silently reconfigures guests. The authenticated inference broker must already be installed and active. Host dependency/service installation and privileged browser installation are not automated by this command.

## Shared durable priority admission, including direct native requests

Management's enabled **`project-bots-stage3-inference.service`**, loopback **21435**, provides authenticated native Ollama routes, not an arbitrary URL proxy. Each guest reverse-tunnels its `127.0.0.1:11434` to that broker and authenticates using its own private provider key. Worker requests can infer only their assigned local tag/context/output/temperature profile. Unbounded caller batch/GPU/thread options are not forwarded. Workers cannot pull/delete models. Administrator model inventory/mutations use a separate private broker token; no browser credential values are returned.

Two explicit durable gates avoid recursive deadlock: existing `stage3-acceptance/platform.db` schedules entire job dispatch; **`stage3-inference/platform.db`** schedules actual streamed native inference/model mutations for every worker, including direct Gateway/native calls. Both use the existing transactional priority/FIFO bounded queue, one active operation, 8192 MiB reservation and conservative weights/KV/loaded-model budget. Active/uncertain reservations do not expire. Streams retain their lease until actual upstream EOF. A downstream/client failure after sending inference conservatively retains an uncertain lease; it does not pretend remote cancellation occurred. Separate job and inference gates are not OS/cgroup VRAM quotas and do not control trusted compute-UID/root activity.

A real direct native request queued behind a held full-budget inference lease: observed rows were `active(priority=0,memory=8192)` and `queued(priority=10,memory=8192)`; the HTTP future remained incomplete until release, then completed on the real model and left no reservation. Missing authentication returned 403. This proves direct native traffic is admitted, not silently bypassed.

**Passt bypass found and closed:** a guest's observed default gateway `10.0.50.1:11434` initially reached host `127.0.0.1` and returned raw Ollama 200, despite the daemon's loopback bind. Therefore raw Ollama now binds **compute `127.0.0.2:11434`**, while the management host tunnel's 21434 destination is that exact address. The guest gateway probe then returned ConnectionRefused; the authorized management tunnel still returned Ollama 0.40.13. Recheck this negative gate after any networking change. Raw backend access is still intentionally available to trusted management/compute administrators, not workers through that gateway mapping. No firewall/AppArmor/driver or passt configuration was changed.

## Four-worker real job/readback evidence

Four dispatch HTTP requests were submitted together; actual remote execution receipts did not overlap. Each job succeeded and retained OpenClaw SQLite `audit_events` matching its exact job session and response/run ID, including `tool.action.finished status=succeeded`:

| Role | Job | Gateway response | Actual tool |
|---|---|---|---|
| ProjectWorker | `0c52fb89-d512-4e39-bd39-4d5367169c6d` | `resp_33ca2693-dfcf-4676-9d37-273cb3c864a8` | session_status |
| Researcher | `87457e4e-490d-45b0-9353-aaaf272bd453` | `resp_05396e53-5d6f-46f0-ba52-c87f017581ea` | read |
| Programmer | `cab4f2ac-42b8-44d9-bfaa-e54c36647583` | `resp_0c335e5c-d1d0-4d60-a22c-885692f64ee0` | read |
| HomelabEngineer | `05c0c247-0bc9-44ce-a134-6c0333377ed1` | `resp_ffc45ddc-a29a-4339-97d3-345e777f5624` | read |

The three read reports contained fresh random challenges absent from prompts, and exact challenge results matched. Each job and exact execution receipt survived restarting the **installed** 8033 platform. Fresh identity/Gateway health for all four passed again; both admission DBs were empty with no FK violations. Native loaded model VRAM was nonzero.

Separate actual Programmer write/read job `f56fe02a-70e3-4b04-a877-9821be43cb23`, response `resp_1ec9e0e8-f4d1-4dde-a914-11f418fbe4c5`, created and read back an exact random workspace value; both retained tools succeeded. HomelabEngineer job `cec74cba-e49d-4f95-9549-891ec173a95e`, response `resp_3b2626d5-0fdc-4058-8f3e-8831fc9560a2`, was asked to write but had no mutation tools, attempted only read (failed for absent target), left the target absent, and direct write invocation returned 404. As before, direct-invoke 404 alone is not a universal tool-policy proof; actual allowed read and no successful mutation audit plus deployed allow/deny policy are the retained evidence.

Final identity-gated installed dispatch after code refresh: `fdb4da12-3875-42ca-9cc7-ff236dc0f948`, response `resp_7cc7160a-1b12-4095-be39-af66a8a84653`, succeeded and loaded inventory still reported 5112583945 VRAM bytes. After the isolated raw-bind change, a final four-request batch again verified actual tool audit results, non-overlapping execution intervals, GPU VRAM, all-worker health and exact job/receipt restart readback:

| Role | Final job | Final response | Total HTTP seconds including queue |
|---|---|---|---:|
| ProjectWorker | `a6ebf909-56a0-4b67-8eed-8f3038dcad39` | `resp_fbbb6cc3-6a7d-4452-a1d1-70d3f38e4c11` | 3.778 |
| Researcher | `6d7eb96f-72c4-4cb5-989a-65c5a7d1c8a9` | `resp_caed2784-f1cc-43ab-b318-db34e846190b` | 13.815 |
| Programmer | `8d09e30f-cf4a-45b9-9171-131a96cb3b4a` | `resp_eb997072-1934-44d9-a311-3c01d2cff5f2` | 17.828 |
| HomelabEngineer | `e9c76235-b6ce-499c-a83b-72b481649c49` | `resp_8eaadbc7-88ab-465b-b158-214affa1ee72` | 7.263 |

Final isolation readback verified raw backend refusal from all four observed default gateways, original worker boot UUID unchanged, nine management/Stage 2 user units enabled/active, 20 installed file hashes matched, both admission tables empty. Ollama PID 83295 ran UID/GID 1001 with supplementary groups `100 990 991 1001` in the active dedicated GPU scope. All four compute libvirt UUIDs were still running.

## Exact remaining blocker: sandboxed guest browser

Researcher's actual supported `openclaw browser doctor --json` reached the Gateway and enabled plugin/profile, but `browser start --json` failed **No supported browser found**. A signed official Google Chrome package was then independently verified and extracted **user-local**, without package installation or privileged commands:

- Google active primary signing fingerprint `EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796` verified Release.gpg → Release SHA256 → Packages.gz → package SHA256.
- Chrome `156.0.8078.79-1`, SHA256 `be1a1e161419f5c8272432f6860912550d8e29985e925913fa800493a0d0c955`.
- Real headless launch **with sandbox preserved** aborted with return code -6: `The SUID sandbox helper binary was found, but is not configured correctly ... chrome-sandbox is owned by root and has mode 4755`.
- Guest `kernel.apparmor_restrict_unprivileged_userns = 1`; `unshare -Ur true` failed to write uid_map with Operation not permitted. No sysctl/AppArmor/user-namespace or sandbox change was attempted. No `noSandbox`, `--no-sandbox`, root chown/chmod, guest sudo or host group change was used.

**Minimal human-owned next decision:** approve/provide a supported sandboxed Chrome installation in a root-owned guest system path through the reviewed trusted guest bootstrap/administrator package process, preserving existing VMs. The bot does not have that authority. Do not root-own a helper inside the bot's writable download tree as an ad-hoc fix. Then explicitly configure its executable, prove actual browser navigation/tool trajectory, and repeat headroom checks. The current user-local package is verified evidence, not an installed working sandbox. Until that gate passes, full Stage 3 is not complete.

A management-browser visual smoke test viewed the installed dashboard unlock page at 1280×577 without layout clipping; no authenticated visual review was performed because this isolated browser had no saved pairing/login item and child user interaction was forbidden. Node dashboard/model confirmation contracts pass. Public footer no longer hardcodes obsolete CPU-only deployment status.

## Exact paths, checks and recovery

Private base `P=/home/server1/.hermes/profiles/project-bot/private`:

- Existing platform install/state and Stage 2 8032 remain as in [the earlier acceptance record](STAGE3_ACCEPTANCE.md). 8033 is still the installed Stage 3 service, not a development server.
- New manifests/unique keys/known-hosts/env/logs: `$P/stage3-{researcher,programmer,homelab}.{json,ed25519,ed25519.pub,known-hosts,env,bootstrap.log}`. JSON/env contain private credentials. Researcher `.pre-resume.json` is a private backup.
- Inference admin token `$P/stage3-inference.env`; admission state `$P/stage3-inference/platform.db`. Never restore a stale DB while upstream may still be running.
- Management units `project-bots-stage3-{ollama,inference}.service`, three `project-bots-stage3-worker-<VM UUID>.service` plus existing host/worker tunnels. Per-worker credential drop-ins remain private path references under the Stage 3 platform/inference user units. Enabled/active service readback, not files alone, establishes deployment.
- Original guest config backups `~bot/.openclaw/pre-inference-broker.json`; original worker tunnel backup `.service.pre-broker`. The new source workflow refuses existing unmanaged workers.
- Evidence prefix `/home/server1/.hermes/profiles/project-bot/cache/scratch/stage3_`: `runtime_evidence.json`, `gpu_runner_evidence.log`, `pool_evidence.json`, `role_boundary_evidence.json`, `direct_admission_evidence.json`, `pool_final_evidence.json`, `chrome/verification.json`, `chrome/sandbox_attempt.json`. Scripts of corresponding names retain exact probes. Do not blindly replay job-generating harnesses.
- Remote isolated test copy: `/home/pbcompute/.cache/project-bots-stage3/current-check`; existing remote compute checkout/dirty state was not overwritten. Official GPU archive cache under `/home/pbcompute/.cache/project-bots-stage3`.

Current source software checks: **77 tests discovered; default 76 pass / 1 optional RNG skip**. With copied actual libvirt 12 domain RNG on management: **77 pass/no skips**; on compute's actual `/usr/share/libvirt/schemas/domain.rng`: **77 pass/no skips**. Management Node syntax + dashboard confirmation contracts and `git diff --check` pass. Remote Node remains absent; no remote Node UI execution is claimed. Installed management **20 public source/assets** matched source hashes. Unit tests include fake transports, so they supplement rather than replace the real evidence above.

Rollback is targeted: first stop dispatch/verify no active or uncertain executions; stop the management GPU supervisor to stop only its dedicated compute scope. Restore original CPU unit and compatible tunnel bind deliberately if returning to CPU. **Do not re-expose raw 127.0.0.1 inference to guest gateway mapping while claiming broker-enforced admission.** Preserve all four VM disks/owner state, manifests, credentials and both admission DBs. Do not restart the whole compute user manager. Browser repair requires separate guest administrator approval; there is no reason to grant host GPU permissions again.

Official sources checked: [Ollama GPU support](https://docs.ollama.com/gpu), [manual ROCm installation](https://docs.ollama.com/linux), [v0.40.13 release metadata](https://api.github.com/repos/ollama/ollama/releases/tags/v0.40.13), [Google signing key fingerprint](https://www.google.com/linuxrepositories/), [OpenClaw Linux browser troubleshooting](https://docs.openclaw.ai/tools/browser-linux-troubleshooting). The browser guide's sandbox-disabling alternative was **not** adopted.
