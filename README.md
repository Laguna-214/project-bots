# Project Bots

A self-hosted workforce control plane for a small homelab. **Stages 1–2 software is implemented:** persistent SQLite registry/jobs, authenticated dashboard/API, and a separate narrow authenticated KVM/libvirt VM service. **Real compute-host lifecycle acceptance is pending.** VM controls are opt-in and require a configured host; the registry/queue still works without one. No workers, inference, MCP integration, cloud fallback, or autonomous execution. Agents remain definitions, not running bots.

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

Use the real private numeric IP or localhost; arbitrary DNS Host headers and public IPs are rejected. Listening on IPv6 is not implemented. **Plain HTTP is not encrypted**: the pairing code, session bearer, and task data can be intercepted on the network. Do not expose this port publicly. Host/Origin/CSRF validation is not a substitute for TLS or SSH. No actual management/compute IP or hardware connectivity has been discovered by this project.

## Data and settings

| Purpose | Default | Override |
|---|---|---|
| Stage 1 SQLite records and platform settings | `~/.local/share/project-bots/platform.db` | `PROJECT_BOTS_DB=/dedicated/private/directory/platform.db` |
| Existing provider configuration | `~/.config/project-bots/config.json` | `PROJECT_BOTS_CONFIG=/path/config.json` |

The database is mode `0600`; its **dedicated parent directory is created as `0700`**. An existing parent with group/other permissions is rejected without changing it. Use a dedicated private directory for overrides. A symlink at the database file is refused. The database and rollback journal remain private; settings are stored inside SQLite, separately from legacy provider JSON. No other software/configuration is changed. Stop the server before copying the database for backup or upgrading/downgrading it; schema version 1 is migrated transactionally on first launch and newer schemas are rejected.

Platform settings default to `http://127.0.0.1:11434` for future **local inference**, `PROJECT_BOTS_API_TOKEN` as the administrative machine API credential reference, and cloud fallback **disabled**. Use the settings form to record the actual local inference endpoint later. Endpoint settings do not install, contact, or validate Ollama. Registry and agent settings accept only credential **environment variable names**, not values. Free-text task inputs/results are returned to authenticated administrators: never paste secrets into them.

Machine API access is optional; the dashboard does not depend on it. Set the referenced environment variable to a high-entropy secret of at least 32 characters in the server environment before launch. The API returns/logs no credential values; browser requests cannot use the machine credential to bypass CSRF. Machine credentials currently grant full administrative access, not per-worker permissions. See [docs/API.md](docs/API.md) for provisioning and exact authentication headers.

## Stage 2: dedicated Ubuntu Desktop compute service

The control plane remains on the management PC; the dedicated VM service belongs on the **actual Ubuntu Desktop gaming PC**, not an assumed IP. No Proxmox conversion, remote root shell, raw libvirt LAN listener, GPU passthrough, or Ollama configuration changes. Use an unprivileged dedicated service identity and `qemu:///session`; host setup requires a separate administrator review. See **[compute-host prerequisites, secure setup and acceptance](docs/COMPUTE_HOST.md)** before running anything on the compute host.

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

No third-party Python dependencies. Tests install the real CLI into isolated temporary homes, launch actual HTTP servers, pair, register machines/agents, create and transition jobs, stop/restart against the same DB, and assert persistence. Coverage includes authorization, malformed/oversized input, unknown foreign keys, private files, non-ASCII credentials, concurrent claims, terminal transitions, no credential-value exposure, and existing installer/updater/uninstaller behavior.

Stage 2 tests explicitly separate mocked libvirt commands, local fake HTTP adapter tests, TLS verification, generated-domain schema validation, and **opt-in real VM acceptance**. Default tests never create host VMs. See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for verified software versus pending hardware checks. **Stages 3–5 remain unimplemented:** per-VM OpenClaw workers, shared local Ollama, then Hermes as the user's MCP-connected assistant. This repository does not install host dependencies/services or change the existing Hermes environment.

[MIT](LICENSE).
