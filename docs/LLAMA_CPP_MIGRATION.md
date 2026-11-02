# Shared inference: llama.cpp migration checkpoint

## Current follow-up

The historical browser blocker below is superseded: the user approved a one-time
bounded root package installation through existing guest agents in the four named
VMs. Exact verified Chrome installed with no package upgrades/removals. All four
authenticated OpenClaw browser starts, offline controlled `about:blank` page
snapshots and referenced clicks passed with sandbox enabled and roles unchanged.
No private-network policy exception, host security edit, bot sudo or persistent
root endpoint. [STAGE3_BROWSER_ADMIN_GATE.md](STAGE3_BROWSER_ADMIN_GATE.md) records
actual challenges, sandbox/process/ownership and preserved identity readbacks.

Stage 4 began only afterward. Actual official-SDK stdio MCP job
`edae31ba-0bdc-419a-9653-be4a5a818032` executed retained OpenClaw `read` successfully;
full suite now 91 discovered / 90 pass / 1 optional schema skip. Stage 4 is partial
and paused at a bounded core checkpoint, without Hermes wiring or a new VM.
See [STAGE4_MCP_CHECKPOINT.md](STAGE4_MCP_CHECKPOINT.md). No live quota/reset feed
is available; no percentage, reset time or scheduled resume is invented.

## Historical migration readback (before browser authorization)


The four existing independent OpenClaw VMs now use **llama.cpp**, not Ollama. The managed Ollama services/binary trees and downloaded backend archive were removed **after real llama.cpp tool jobs passed**. All downloaded private model data is preserved. No root/sudo, host package/driver/group/AppArmor changes, VM replacement, cloud inference, Stage 4, Hermes changes, commit or push.

## Pinned runtime and model

- Official upstream release **b12058**, version `0.8.0-dev`, commit `3f8af15a7`; unmodified `llama-b12058-bin-ubuntu-vulkan-x64.tar.gz`, 35704848 bytes, SHA-256 **24049dae7485f90869b85a25ae6bc0caeabb1d257723017bbc61d1a08fc9b9e3**. GitHub release API supplied the digest; downloaded bytes matched before extraction. No compiler/build dependencies were installed and no Ollama ROCm libraries are borrowed.
- Compute runtime `/home/pbcompute/.local/opt/llama.cpp-b12058-vulkan/llama-b12058/llama-server`; existing system Mesa RADV Vulkan discovers RX 6800 and Intel UHD 770. Explicit `--device Vulkan0 --n-gpu-layers all` selects RX 6800, not the integrated GPU.
- Preserved GGUF blob `/home/pbcompute/.local/share/project-bots-models/blobs/sha256-3d0b790534fe4b79525fc3692950408dca41171676ed7e21db57af5c65ef6ab6`, **1359279776 bytes**. Magic `GGUF` and full SHA-256 **3d0b790534fe4b79525fc3692950408dca41171676ed7e21db57af5c65ef6ab6** verified directly. Imported alias **qwen3-1_7b**; embedded Qwen3 metadata and chat template retained. No conversion/redownload was necessary.
- Live logs identify RX 6800 `0000:03:00.0`, **offloaded 29/29 layers**, Vulkan0 model buffer **1123.71 MiB**, KV **3584 MiB**, compute **21 MiB**, context 32768, one slot. Actual AMD sysfs `/sys/class/drm/card2/device/mem_info_vram_used` measured **6215245824 bytes** while loaded (whole-GPU usage, including desktop, not per-model attribution). The b12058 `/models` response in this deployment omits documented per-device memory details; broker `memory_observation_available:false` and zero VRAM fields mean **unavailable**, not CPU-only and not measured VRAM. GPU proof is the current llama.cpp offload log plus hardware readback, never old Ollama `/api/ps` data.

## Security-critical router detail

Raw router remains on **compute 127.0.0.2:11434**, reached by management private tunnel **21434**. Worker reverse tunnels still map guest **127.0.0.1:11434** to authenticated management broker **21435**; OpenClaw uses `api:openai-completions`, provider `llamacpp`, base URL `http://127.0.0.1:11434/v1`, primary `llamacpp/qwen3-1_7b`, no fallback. Installed OpenClaw 2026.10.9 validated all four actual configs. VM UUIDs, tokens, SSH keys, workspaces, roles and boot identities are preserved.

**Do not secure this router with only `--api-key-file`.** Source `tools/server/server-models.cpp` strips that CLI option from children and forces children onto random **127.0.0.1** ports. A real guest bypass probe initially reached an unauthenticated child inference endpoint despite the private router bind. The fix is supported inherited **`LLAMA_ARG_API_KEY_FILE=/home/pbcompute/.local/share/project-bots-llama/backend.key`** in the router environment, set **inside the fresh compute SSH scope**, as well as the router option. Children inherit the private file setting and reject unauthenticated inference. This exact fix passed all four guest probes: raw router connection refused, child `/v1/chat/completions` **401**. Child public health/model metadata may still be readable; no inference bypass remains. Never put the backend key in worker configs. No firewall/passt/security-policy change was used.

Management unit **project-bots-stage3-llama.service**, enabled/active, supervises fresh strict SSH `systemd-run --user --scope --unit=project-bots-llama-gpu env LLAMA_ARG_API_KEY_FILE=... llama-server ...`; the scope inherits fresh render membership. It never restarts the VM-owning user manager. Router limits include `--models-max 1 --ctx-size 32768 --parallel 1 --threads 4 --threads-batch 4 --batch-size 512 --ubatch-size 128 --fit off --jinja --reasoning off --offline --cache-ram 0 --no-webui`. No built-in host tools, MCP, external media paths or connect tunnel are enabled.

## Model manager and admission

Production modules `llama_proxy.py` and `llama_store.py` replace native Ollama routes; `inference_proxy.py` is only a compatibility entry point. There is **no `/api/chat`, `/api/generate`, `/api/tags`, `/api/ps`, `/api/pull` or `/api/delete` llama.cpp emulation**.

- `GET /api/models`, `/api/models/loaded`, `POST /api/models/show` retain platform-level normalized inventory contracts.
- `POST /api/models/load` and `/unload` require exact `load:<name>` / `unload:<name>` confirmations and use native router `/models/load`, `/models/unload`. The router acknowledges asynchronously: broker holds its durable lease until `/models` readback reaches the requested state. Already-loaded/unloaded is observed before sending another mutation.
- `POST /api/models/pull` is the legacy platform action name for **administrator-catalog-pinned GGUF download**, not Ollama pull. Only trusted local catalog entries containing HTTPS Hugging Face URL, immutable revision, size, SHA-256, context and reviewed metadata are accepted. Fixed strict SSH executes source-owned model-store code as `pbcompute`; streamed size/hash/GGUF magic are verified before atomic publication under `.local/share/project-bots-llama/gguf`. Browser requests cannot supply URLs, hashes, SSH argv, paths or shell commands. Redirects are allowed for Hugging Face's CDN download; final bytes must match the pin. See `llama-model-catalog.example.json`.
- Deletion only removes exact store-owned name/hash files after observed unload, ownership/hash verification and assigned-worker checks. Imported preserved blobs are **not deletable**, even if later unassigned. Other models/files/apps are untouched.
- Actual HTTP acceptance downloaded official ggml-org **SmolLM2-135M Q4_K_M**, revision `1076b85d135017971845b19b8d07df1479155988`, 101016128 bytes, SHA-256 **e3131339bf4e8065265593d4fd8f7bb7ff2d3abff1edb5618aa1197b89cad9f5**; inventory/load/unload/delete/absent readback passed and Qwen was restored. This disposable base model is not advertised as tool-capable or assigned to a worker.
- `PROJECT_BOTS_LLAMA_ENDPOINT=http://127.0.0.1:21435`, `PROJECT_BOTS_LLAMA_TOKEN_ENV=PROJECT_BOTS_INFERENCE_ADMIN_TOKEN` replace the old Ollama environment variables. Broker invocation requires `--registry`, and `--store-config` enables pinned downloads/deletion.
- Separate durable SQLite job and inference gates remain; direct native OpenAI worker requests and every model mutation share the inference gate. A direct real request was observed queued behind an 8192-MiB held lease and completed only after release; missing auth returned 403. Streams retain admission to upstream EOF. Unknown outcomes retain uncertain reservations. A known already-unloaded error during acceptance was reconciled only after both callers stopped and exact router/lease readback; the bug has a RED→GREEN idempotency test. Exact reconciliation evidence is retained privately.

Independent worker model/temperature/output/priority/reservation profiles remain. Temperature/output are forced by the broker, not caller options. **Context is a server/preset allocation, not a per-request OpenAI option**: the worker context must match its registered preset and deployed config. Different contexts require separately reviewed presets/aliases (possibly sharing weights), not silently forwarding Ollama `num_ctx`. Router `models-max=1`, conservative full FP16 KV reservation and serialized inference limit memory; these are not OS/cgroup quotas. Arbitrary model download, model autopromotion to tool capability, automatic guest reconfiguration and unattended jobs are not enabled.

## Files, services and private state

Private management base `P=/home/server1/.hermes/profiles/project-bot/private`:

- `stage3-llama-registry.json`, `stage3-llama-store.json` (trusted catalog + fixed SSH argv), `stage3-llama-backend.env` (secret; never print).
- Existing `stage3-inference.env`, per-worker env/keys/manifests and two admission DBs are retained; installed package remains `$P/stage3-installed/.local/lib/project-bots/project_bots` and platform **8033**. Stage 2 **8032** unchanged.
- Compute `.local/share/project-bots-llama/{models.ini,registry.json,backend.key,gguf/}`. Original blob/manifests/metadata remain in `.local/share/project-bots-models/`. Guest config backups `~bot/.openclaw/pre-llamacpp.json`. DB backup `stage3-acceptance/platform.pre-llama.db` and private old unit backups are not live services.
- Enabled/active management `project-bots-stage3-{llama,inference,platform,host-tunnel,worker-tunnel}.service` plus the three existing per-VM tunnel services; compute `project-bots-llama-gpu.scope`; all four Gateway/identity services remain.
- **Removed and absent on readback:** compute `.local/opt/ollama-v0.40.13`, `.local/opt/ollama-v0.40.13-rocm`, managed `.cache/project-bots-stage3/ollama-linux-amd64-rocm.tar.zst`, compute `.config/systemd/user/project-bots-ollama.service`, management `.config/systemd/user/project-bots-stage3-ollama.service`. Old inference scope inactive/not loaded. No other host's Ollama/apps or private model data was searched/deleted. Backup unit text is retained, not executable runtime trees.

Private evidence prefix `.../cache/scratch/stage3_llama_`: `pool_evidence.json`, `direct_admission_evidence.json`, `model_evidence.json`, `isolation_evidence.json`, `ollama_removal_evidence.json`, `reconciled_unload.json`. Corresponding scripts retain exact API/SSH checks; **do not blindly rerun job-generating harnesses**.

## Completion and remaining gate

Real installed HTTP jobs on all four roles executed audited OpenClaw `session_status` or `read`; read challenges were absent from prompts and exact outputs matched. Concurrent dispatch receipts did not overlap; exact jobs/receipts survived installed platform restart. Model registry persistence after broker restart passed. Final job IDs and latest source/test/service readbacks are appended below after the final verification.

**Fresh browser gate recheck:** authenticated OpenClaw start still fails and all four guests have neither a supported system browser nor an installed Chromium snap. The existing vendor-path AppArmor rule is not launch evidence. Exact proposed bounded administrator packaging mechanism and acceptance boundary: [STAGE3_BROWSER_ADMIN_GATE.md](STAGE3_BROWSER_ADMIN_GATE.md). No privileged installation was attempted; Stage 4 remains stopped.

**Browser remains blocked, unchanged:** user-local Chrome cannot start with its sandbox under current root-owned guest policy. No sandbox disabling, guest sudo, userns/AppArmor workaround or new browser acceptance is claimed. Full Stage 3 is still open on that separate administrator-owned guest browser prerequisite. See historical `STAGE3_GPU_POOL_ACCEPTANCE.md` for the precise browser evidence. No new VMs, role broadening, autonomous executor or Stage 4.

## Final verified readback

All four dispatched together after restarting the new router/broker/platform and after Ollama removal; audited actual tools succeeded, challenges matched, receipts did not overlap, exact job/receipt restart readback passed:

| Role | Job UUID | Gateway response | HTTP seconds including queue |
|---|---|---|---:|
| ProjectWorker | `1a983f8c-80df-4824-b191-d931ca554a57` | `resp_2e4361e8-a160-487a-92c1-9f93c743820a` | 12.576 |
| Researcher | `e188ef6b-3e65-4053-b083-452bb8d1201c` | `resp_63b05f10-f288-4e2c-ae5b-82f3e8dd9c86` | 10.056 |
| Programmer | `d181c1e3-6f28-456f-b03f-21c9317c6c27` | `resp_f6cdd6b3-fa93-428e-82dc-dcefbc382bda` | 4.801 |
| HomelabEngineer | `a00583c1-2ae4-499f-9aac-15c17bc8b0fd` | `resp_d07b598b-1ec8-4ad0-89ce-8114b62159e7` | 16.359 |

Final management and compute suites: **86 pass/no skips** using actual libvirt 12 schema; default discovery has 85 pass/1 optional schema skip. Node syntax/dashboard contracts and whitespace checks pass. Final installed **22 public file hashes** match source. Nine checked management units enabled/active, all four VM boot identities unchanged, both admission tables empty/no FK violations. Raw private router refused from all guests; random child inference returned 401 from all guests. Compute Ollama unit and old scope read back **LoadState=not-found / inactive**, both exact runtime trees absent, original GGUF 1359279776 bytes preserved. Latest whole-GPU VRAM readback **6247194624 bytes**. Browser sandbox blocker unchanged. No commit/push; parent review/publication remains.

Official provenance/reference: [b12058 release](https://github.com/ggml-org/llama.cpp/releases/tag/b12058), [pinned server docs](https://github.com/ggml-org/llama.cpp/blob/b12058/tools/server/README.md), [pinned router source](https://github.com/ggml-org/llama.cpp/blob/b12058/tools/server/server-models.cpp), [official small GGUF revision](https://huggingface.co/ggml-org/SmolLM2-135M-GGUF/tree/1076b85d135017971845b19b8d07df1479155988).
