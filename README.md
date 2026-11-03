# Project Bots

A self-hosted workforce control plane with one authenticated backend/API, private persistent SQLite state, responsive web UI, constrained KVM/libvirt management and independent OpenClaw workers sharing centralized llama.cpp inference. **Incremental development, not a completed secure multi-agent product.** Current source includes persistent chats, scoped agent messaging, an opt-in tool-free conversational runner, durable emergency-stop/containment latches, incidents and explicit recovery, a Security dashboard, bounded fair shared-inference scheduling and private database backup/restore. Owner-validated force-stop and isolated namespace-enforcement primitives are source-tested, but production VM network adapters/OS monitors and real hostile-VM acceptance remain unavailable. Responsive installable-PWA support and development native clients are present: Android native Chats/Agents/Activity widgets use the same API, and a sandboxed Linux Electron shell uses the shared UI. Artifacts build, but native-device and full production acceptance are incomplete. See [client build/use notes](clients/README.md) and [evidence/limitations](docs/NATIVE_CLIENTS.md). Hermes/MCP is optional; the backend operates without it. No cloud fallback or Ollama migration. Read [current status](IMPLEMENTATION_STATUS.md) before operating hardware.

## Product roadmap — exactly five stages

1. **Core Application**
2. **Machine Manager**
3. **AI Workers & Model Manager**
4. **User Control & Collaboration**
5. **Final Product & Hardening**

Security belongs in every stage; none is newly declared complete against the expanded brief. See [requirements](docs/PRODUCT_REQUIREMENTS.md), [architecture](docs/ARCHITECTURE.md), [implementation plan](docs/IMPLEMENTATION_PLAN.md), [security acceptance](docs/SECURITY_ACCEPTANCE.md), and [deployment boundaries](docs/DEPLOYMENT.md). Historical hardware evidence remains linked below but is not current health or full security acceptance.

### Chat increment

After pairing, use **Chats** to create an individual conversation (one agent) or a group, send persistent messages and manage members. **Refresh** and visible-client polling read updates. The optional [conversation runner](docs/CONVERSATIONS.md) produces bounded replies only for explicitly enrolled agents with independent credentials and actual security coverage; the UI offers enrollment and reply cancellation. The backend/runner operate independently of the browser; no always-on push service is installed. Newly added members can read all explicit shared history. Removing members or disabling their separate chat identity denies subsequent read/send requests; it cannot erase already downloaded messages. No private files, memory, credentials or tool authority are shared by membership. Agent chat credentials must be provisioned by the administrator through [documented APIs](docs/API.md); existing Gateway/inference credentials are not automatically authorized. Infrastructure controls are collapsed under Advanced; this remains responsive web, not a native app.

The Security view displays monitor coverage, agent containment state, incidents/evidence and partial action outcomes. Administrator controls stop one/all agents, acknowledge incidents and request recovery; stop commits durable revocation before requesting Machine Manager shutdown. Missing trusted coverage blocks execution by default. **Application stop is not packet isolation or forced VM termination**; no runtime is marked protected merely because it is registered. See [security contracts](docs/SECURITY_INCREMENT.md), [shared inference](docs/INFERENCE_INCREMENT.md), and [backup/recovery](docs/BACKUP_RECOVERY.md), [shared client/HTTPS](docs/SHARED_CLIENT_INCREMENT.md), and [host prerequisites and blocked acceptance](docs/HOST_SECURITY_INCREMENT.md). Do not expose this development backend publicly or deploy malicious agents under a claim of complete containment.

## Install and launch (Linux, Python 3, no root)

```sh
git clone https://github.com/Laguna-214/project-bots.git
cd project-bots
sh install.sh
export PATH="$HOME/.local/bin:$PATH"
project-bots serve
# Open http://127.0.0.1:8032 in your browser.
```

Enter the **8-digit one-time pairing code printed in the terminal**. It expires in 10 minutes; five incorrect attempts lock pairing until restart. The dashboard exchanges it for a random bearer stored in this browser tab's sessionStorage, so **refresh works in the same tab**. Restarting the server revokes the browser session and prints a new code; records remain in the database. Closing the tab/clearing storage loses its session: if the code has been consumed, restart and pair again. This is a single-administrator, single-browser-session design, not a user account system.

Try it without any compute machine:

1. Expand **Register agent**, enter a name and role, and leave its machine unassigned.
2. **Create job**, optionally select that agent, and inspect the queued task. Existing queued tasks can be reassigned or canceled.
3. Stop the server with Ctrl-C, run `project-bots serve` again, and pair using the new console code. The agent and job are still there.
4. Register a machine only when you have a service endpoint to record. Registration stays **unverified** and issues no network request. Explicit Stage 2 health/VM controls contact that endpoint only when selected.

Progress/results/failure are recorded through the authenticated API and inspected in the dashboard; no worker updates them automatically. See [API reference and executable machine-client example](docs/API.md).

### Remote browser / LAN access

The default bind is **loopback**, port **8032**. Recommended remote access:

```sh
# On the management server:
project-bots serve
# On the browser computer, in another terminal:
ssh -L 8032:127.0.0.1:8032 YOUR_MANAGEMENT_SERVER
# Open http://127.0.0.1:8032 locally.
```

For a trusted LAN only, explicitly opt in:

```sh
project-bots serve --host 0.0.0.0 --port 8032
# Open http://YOUR_ACTUAL_MANAGEMENT_SERVER_IP:8032
```

Use the real private numeric IP or localhost; arbitrary DNS Host headers and public IPs are rejected. Listening on IPv6 is not implemented. **Plain HTTP is not encrypted**: the pairing code, session bearer, and task data can be intercepted on the network. Do not expose this port publicly. Host/Origin/CSRF validation is not a substitute for TLS or SSH. Site-specific live observations are recorded separately in [deployment notes](docs/DEPLOYMENT.md), not hardcoded as product defaults.

## Data and settings

| Purpose | Default | Override |
|---|---|---|
| Stage 1 SQLite records and platform settings | `~/.local/share/project-bots/platform.db` | `PROJECT_BOTS_DB=/dedicated/private/directory/platform.db` |
| Existing provider configuration | `~/.config/project-bots/config.json` | `PROJECT_BOTS_CONFIG=/path/config.json` |

The database is mode `0600`; its **dedicated parent directory is created as `0700`**. An existing parent with group/other permissions is rejected without changing it. Use a dedicated private directory for overrides. A symlink at the database file is refused. The database and rollback journal remain private; settings are stored inside SQLite, separately from legacy provider JSON. No other software/configuration is changed. Use `project-bots backup --database /private/platform.db --output /private-backups/new.db` for a consistent validated online SQLite backup; restore writes only to a new offline path. See [backup/recovery](docs/BACKUP_RECOVERY.md); worker disks, model blobs and environment secrets are separate. Schema versions 1–5 migrate transactionally to **v6** on first launch; newer schemas are rejected. Keep a compatible pre-upgrade backup for rollback; do not point older code at a v6 database.

Platform settings default to `http://127.0.0.1:11434` for future **local inference**, `PROJECT_BOTS_API_TOKEN` as the administrative machine API credential reference, and cloud fallback **disabled**. Use the settings form to record the actual local inference endpoint later. Endpoint settings do not install, contact, or validate llama.cpp. The deployed shared adapter uses the separately authenticated private llama.cpp broker, not this legacy settings hint. Registry and agent settings accept only credential **environment variable names**, not values. Free-text task inputs/results are returned to authenticated administrators: never paste secrets into them.

Machine API access is optional; the dashboard does not depend on it. Set the referenced environment variable to a high-entropy secret of at least 32 characters in the server environment before launch. The API returns/logs no credential values; browser requests cannot use the machine credential to bypass CSRF. Machine credentials currently grant full administrative access, not per-worker permissions. See [docs/API.md](docs/API.md) for provisioning and exact authentication headers.

## Stage 2: dedicated Ubuntu Desktop compute service

The control plane remains on the management PC; the dedicated VM service belongs on the **actual Ubuntu Desktop gaming PC**, not an assumed IP. No Proxmox conversion, remote root shell, raw libvirt LAN listener, GPU passthrough, or privileged host inference configuration changes. Use an unprivileged dedicated service identity and `qemu:///session`; host setup requires a separate administrator review. See **[compute-host prerequisites, secure setup and acceptance](docs/COMPUTE_HOST.md)** before running anything on the compute host.

```sh
# Compute host, AFTER administrator-reviewed KVM/libvirt/template setup:
# Provision PROJECT_BOTS_COMPUTE_TOKEN securely (secrets.token_urlsafe(32)).
project-bots machine-service --catalog /absolute/trusted/catalog.json \
  --state-dir "$HOME/.local/share/project-bots-compute"
# Default: http://127.0.0.1:9443; --host/--port configurable.
# Non-loopback requires BOTH --tls-cert and --tls-key.
```

For SSH transport, forward a chosen management-loopback port to compute-loopback `9443`, then register that forwarded `http://127.0.0.1:PORT` endpoint. For direct LAN use register `https://ACTUAL_COMPUTE_NAME:PORT`, with a valid trusted certificate; `PROJECT_BOTS_MACHINE_CA_FILE` optionally selects an admin-local CA bundle. The adapter verifies TLS/hostname, forbids redirects and refuses remote plaintext HTTP. The registry's `credential_env` references a compute token variable on the **management service**, separate from the platform API token; no token values enter the dashboard.

The dashboard provides explicit health/list/detail, Ubuntu Desktop provisioning, start/graceful shutdown/restart/pause/resume, offline CPU/RAM/grow-disk edits, offline qcow2 disk snapshots/restore and offline deletion. Every mutation needs typed per-action confirmation and an operation UUID. Resource limits, trusted image SHA-256, private VM disks, UUID + owner metadata checks, SSH keys only and loopback graphics/SSH forwarding are enforced. Keep operation IDs after timeouts; inspect before retrying. These confirmations express caller intent, **not cryptographic proof of a human approval**; never derive authorization from job/VM output. [API details](docs/API.md#stage-2-compute-api).

## Update

```sh
project-bots update
```

The installer copies the stdlib-only package to `~/.local/lib/project-bots` and creates `~/.local/bin/project-bots` and `~/.local/bin/project-bots-uninstall`; the source clone can then be removed. Python 3.9+ recommended. No services, global packages, or root privileges are required. Re-running `sh install.sh` also updates the local installation.

The installed updater requires `git`, fetches the latest official GitHub **main development branch**, and reinstalls without deleting provider config or the platform database. It works after the original clone is deleted. If the revision already matches, it reports up to date. These are manual branch updates, not signed/pinned releases: review changes first and back up your database. **Stop and restart any running setup/platform/compute server** to load new code. Package installation and update/uninstall behavior remain covered by isolated-home tests.

## Uninstall

```sh
~/.local/bin/project-bots-uninstall
# Or, from the clone: sh uninstall.sh
```

Stop running servers first. This removes the installed CLI, package, and uninstaller, **not provider config, platform/compute databases, catalog, VM disks or libvirt domains**. Delete intended managed VMs through the service before uninstalling; otherwise retain state for ownership/recovery. Uninstallation is idempotent and refuses unrecognized files in its installation targets.

## Existing provider setup remains available

```sh
project-bots setup local                # terminal wizard
project-bots setup web                  # legacy setup, binds 0.0.0.0:8032
project-bots setup web --host 127.0.0.1  # safer SSH-forwarded provider setup
```

These commands configure provider JSON only. Run them separately from `serve` (or choose another port) to avoid port conflicts. Legacy setup still uses the original 8-digit one-time pairing flow and **memory-only** browser token: unlike the new dashboard, refreshing/closing the legacy setup page requires a server restart and new code. Both flows use 10-minute codes, five-attempt lockout, strong in-memory session authentication, Host/Origin checks and CSRF tokens for browser writes. Request URLs/headers/bodies are not logged; pages have a restrictive Content Security Policy.

Provider presets remain available for OpenAI, Anthropic, Google Gemini, xAI, OpenRouter, DeepSeek, Mistral, Groq, Together AI, Fireworks AI, Ollama, LM Studio, Codex/ChatGPT, and custom OpenAI-compatible HTTPS endpoints. Legacy explicit HTTP provider endpoints are restricted to loopback. A preset is a configuration hint, **not an inference adapter**. Saving cloud-provider config does not send anything to the cloud and never enables a cloud fallback. Provision named provider API key variables in a private server environment, not the web page or shell history. Codex uses only its official installed CLI:

```sh
project-bots codex login   # official CLI: codex login --device-auth
project-bots codex status
```

Project Bots does not read/copy Codex credentials or implement OAuth. Install the official CLI separately if you want these legacy helpers.

## Tests and implementation boundaries

```sh
python3 -m unittest discover -s tests -v
# Optional JS syntax check if Node is already installed:
node --check project_bots/dashboard.js
node tests/dashboard_vm.cjs  # fake DOM/HTTP confirmation contract, NOT a real VM
```

The base backend/chat have no third-party Python dependencies; optional MCP uses the pinned SDK in `requirements-mcp.txt`. Tests install the real CLI into isolated temporary homes, launch actual HTTP servers, pair, register machines/agents, create and transition jobs, stop/restart against the same DB, and assert persistence. Coverage includes authorization, malformed/oversized input, unknown foreign keys, private files, non-ASCII credentials, concurrent claims, terminal transitions, no credential-value exposure, and existing installer/updater/uninstaller behavior.

Stage 2 tests separate mocked libvirt commands, fixture HTTP/TLS, optional domain-schema validation and opt-in real VM acceptance. Current suite: **106 discovered, 105 passed, one optional libvirt-schema skip** with Python 3.14.9 and MCP SDK 2.3.0 in the managed test interpreter. Installed CLI tests now exercise chat persistence across process restart, agent-scoped HTTP access, spoof-field rejection, membership/identity revocation, duplicate messages and metadata events. Additional SQLite tests cover v3 migration, concurrent SQLite writers, paging and rollback; `node tests/chat_ui.cjs` exercises fake-DOM safe rendering, retry IDs and membership. These do not prove a visually reviewed UI or hostile-VM isolation.

Historical [llama.cpp evidence](docs/LLAMA_CPP_MIGRATION.md) retains RX 6800 Vulkan offload, model-store, four-worker tool-job and inference-bypass checks. Historical [browser evidence](docs/STAGE3_BROWSER_ADMIN_GATE.md) records the later approved packaging/offline-browser gate. Fresh read-only inspection now found all four original VMs stopped; registry health is stale. Shared model inventory reported loaded `qwen3-1_7b` but unavailable memory accounting, not current GPU-use proof. The new four-agent/single-loaded-model isolation and scheduling acceptance has **not run**. No VM was started to manufacture that result.

Optional typed MCP code exists, but [corrected checkpoint](docs/STAGE4_MCP_CHECKPOINT.md) separates authenticated historical calls from unverified Hermes-native discovery/permission handling and disposable lifecycle. Stages 1–5 remain partial against the expanded product/security brief; no autonomous secured workforce, independent containment or completed native apps are claimed. Existing installed services and Hermes configuration were not changed by this increment.

[MIT](LICENSE).
