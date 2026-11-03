# Platform, compute, worker and chat APIs

> This is an incremental single-administrator backend, not a completed hostile-agent security system. Current requirements and evidence boundaries: [implementation status](../IMPLEMENTATION_STATUS.md), [architecture](ARCHITECTURE.md), [deployment](DEPLOYMENT.md). Historical acceptance is time-bound; current worker registry status is not a live health or protection claim.

## Persistent message broker — schema v4

The message broker is part of the same authenticated backend, logically separate from llama.cpp **inference** admission. The existing platform browser session/CSRF or administrative machine bearer can manage chats. Agent-scoped chat bearers cannot access registry/jobs/settings/compute/model/security-administration routes.

- `GET /api/chats`: newest 100 chats. Administrator sees all; agent sees only current memberships with an enabled chat identity. Each chat includes `id,title,kind,created_at,agent_ids`. Older-chat list pagination is not implemented.
- `POST /api/chats` (admin): `{title,kind,agent_ids}` → 201. `kind` is `individual` (exactly one agent) or `group` (1–32 distinct canonical registered agent UUIDs). No runtime/model execution occurs.
- `POST /api/chats/<chat UUID>/members` (admin): `{agent_ids:[...]}` replaces membership transactionally under the same kind/size rules. Unknown agents roll back the entire update. New members see all explicit shared history; removed members lose subsequent read/send access, not previously downloaded copies.
- `POST /api/chats/<chat UUID>/messages`: `{client_id:"<canonical UUID>",content:"<nonempty text>"}` → 201 persisted message including sequence, chat_id, sender, client_id, content, created_at. Text limit 16000 characters; HTTP JSON limit 64 KiB. **Do not supply sender/agent/role fields**; the broker derives sender (`admin` or authenticated agent UUID). Same `(chat,sender,client_id)` and content returns the original message; conflicting content returns 409. Preserve the ID after an uncertain transport result and retry the same payload.
- `GET /api/chats/<chat UUID>/messages?after=<sequence>`: oldest-first page of at most 100 subsequent messages, plus `has_more` and `next_after`. Cursor defaults to 0. Unknown/repeated query keys and invalid cursors fail. Only this read supports the `after` query. Membership and enabled identity are rechecked in the same transaction as message read/write.
- `POST /api/agents/<agent UUID>/chat-identity` (admin): `{credential_env:"AGENT_CHAT_TOKEN_REFERENCE",enabled:true|false}`. Only a variable **name**, never a token value. Duplicate references conflict. Resolve a separately provisioned high-entropy bearer of at least 32 characters in the platform process environment; disabled/missing/short/ambiguous credentials are refused. Reusing known platform/compute/Gateway/inference-administration credentials is refused at configuration; reused matching agent token values fail authentication. Keep all authorities distinct. Token rotation in the inherited process environment normally requires a reviewed server restart; this is not short-lived credential issuance.
- `GET /api/security/events` (admin): newest 100 chat metadata records, each sequence/UUID/time/agent/behavior/resource/outcome. Contains chat identity and membership changes and membership-denied message access, not message bodies, private reasoning, runtime telemetry or complete incident/containment records. No audit deletion/update API. Same-UID database writers remain trusted; this is not tamper-resistant external storage.

Agent chat clients send only `Authorization: Bearer <privately provisioned chat token>` and `Content-Type: application/json` on POST, omitting browser Origin/fetch/setup headers. The only agent routes are chat list and message read/send. They cannot create chats, alter membership or change their identity. Unknown/nonmember message resources return 403 without exposing history. Admin still uses the existing browser protections; do not issue administrative credentials to workers. Default loopback plus private SSH transport remains required; HTTP does not encrypt credentials. These APIs do not supply a guest connectivity/tunnel policy or prevent direct inter-VM traffic.

The source web UI supports create/select/member edits/history pages and idempotent retry after an in-tab transport failure. Refresh retrieves new messages; there is no automatic AI reply, private-memory assembly or agent adapter delivery loop. Authentication is still single administrator, not a multi-user account/RBAC service. The full [malicious-agent acceptance](SECURITY_ACCEPTANCE.md) remains unverified.

## Trusted security and inference controls — schema v5

Administrator-only status, incident/evidence, emergency-stop, acknowledgment and
explicit recovery APIs are specified in [SECURITY_INCREMENT.md](SECURITY_INCREMENT.md).
The Security dashboard consumes those routes and reports unavailable/partial
actions. Agent chat credentials cannot access them. Global/per-agent stop and
revoked credential fingerprints survive restart; recovery never starts workers.

Worker execution and broker inference require fresh trusted coverage. Missing
OS/network adapters deny execution; optional inference hooks cannot bypass the
mandatory registry-backed security gate. See [INFERENCE_INCREMENT.md](INFERENCE_INCREMENT.md)
for fair scheduling, queue/rate/token budgets, independent credential maps,
owner-only `/v1/requests/cancel`, deadlines and uncertain backend reservations.
Cancellation of forwarding is not verified remote generation termination. Historical
serial admission descriptions below describe prior deployment, not the new source
scheduler. No deployment was performed.

## Stage 3 routes

All routes require the existing platform browser-pairing/CSRF or machine API bearer credential. `POST /api/agents/<agent UUID>/worker` registers `{vm_id,endpoint,credential_env,profile,identity_endpoint?}`; `GET` reads that record and `GET /api/workers` lists configured workers. A profile requires `model` (local tag, no `cloud`), `context` (2048–131072), `temperature` (0–2), `max_output` (1–context), `memory_mib` (512–65536), and `priority` (0–100). The endpoint must use verified HTTPS or an explicit loopback SSH tunnel. Without an identity endpoint this is only **configured** and cannot execute real work. With an identity endpoint, the agent must have an assigned compute machine: registration observes its running compute-owned VM UUID, fresh authenticated sidecar UUID/boot/profile evidence and authenticated Gateway readiness **before** saving `verified`. `GET /api/agents/<agent UUID>/worker/health` repeats those read-only observations. `verified` is a prior observation, not a permanent online claim or hardware attestation. Every real dispatch repeats fresh identity/profile and native model memory checks; unavailable/mismatched evidence prevents dispatch. The profile does not silently reconfigure the guest. Current production reservation budget is 8192 MiB, so a profile above that budget cannot be admitted.

`POST /api/jobs/<job UUID>/dispatch` with `{"confirmation":"dispatch:<job UUID>"}` synchronously calls the configured worker Gateway's authenticated `/v1/responses` endpoint and persists the receipt/result; `GET /api/jobs/<job UUID>/execution` reads the receipt. The agent must already be assigned to a queued job. A running/uncertain receipt blocks worker replacement, another execution on that worker, and manual legacy job mutations; execution is not retried automatically. A Gateway timeout is **uncertain**, not proof of failure. Gateway bearer access has full operator authority inside that VM, so keep the worker isolated and use a distinct secret per VM. Treat task input and outputs as untrusted; never place credentials in them.

`GET /api/models` and `/api/models/loaded` return normalized registry/router observations from the authenticated llama.cpp broker; `POST /api/models/show` accepts `{"model":"<registered local identifier>"}`. `POST /api/models/load`, `/unload`, `/pull` and `/delete` require exact `<action>:<identifier>` confirmations. Load/unload use native llama.cpp `/models/load` and `/models/unload`, retaining durable admission until observed state completion. `pull` is the retained platform action name for administrator-catalog-pinned GGUF download with immutable URL/size/SHA-256/format verification, not Ollama pull. Delete refuses assigned or preserved models and removes only exact hash-verified store-owned files after unload. Unknown outcomes retain reservations and require inspection, never blind retry. One active 8192-MiB logical reservation, four queued requests and priority/FIFO/default 30-second queue deadline remain. Separate job/inference databases avoid recursive deadlock. These are admission controls, not OS memory quotas. OpenClaw provider `llamacpp` uses `api: "openai-completions"`, base URL `http://127.0.0.1:11434/v1`, with no fallback; its inbound Gateway `/v1/responses` is a separate API. See [current backend, model-store and recovery details](LLAMA_CPP_MIGRATION.md).

`GET /api/roles` returns fresh source-owned presets with instructions and explicit tool allow/deny policy: ProjectWorker, Researcher, Programmer and read-only HomelabEngineer, plus legacy Reviewer/HomelabObserver names. Generate guest config with `worker_config(profile, role=...)`; source-owned opt-in `scripts/provision_worker.py` performs fixed non-root deployment, actual schema validation and identity-gated registration using durable private intent. HomelabEngineer/HomelabObserver only read supplied workspace reports and have no live write credentials. A preset still is not proof that a VM or browser is deployed.

### Shared llama.cpp OpenAI inference broker

`python3 -m project_bots.llama_proxy --workers-db /PRIVATE/platform.db --admission-db /PRIVATE/inference/platform.db --registry /PRIVATE/registry.json --store-config /PRIVATE/store.json` runs the authenticated loopback-only broker (default port 21435). Configure `PROJECT_BOTS_LLAMA_ENDPOINT=http://127.0.0.1:21435` and `PROJECT_BOTS_LLAMA_TOKEN_ENV=PROJECT_BOTS_INFERENCE_ADMIN_TOKEN`; private EnvironmentFiles supply distinct administrator/backend/worker tokens. Broker OpenAI worker routes are only `GET /v1/models` and `POST /v1/chat/completions`; Project Bots `/management/models`, `/management/loaded`, `/management/show`, `/management/download` plus native `/models/load` and `/models/unload` are administrator-only. No Ollama-native API emulation or arbitrary URL proxy exists. Worker requests are pinned to their registered model/profile; temperature/output are enforced and caller GPU/cache/thread/batch options are stripped.

The broker uses a **separate durable inference DB/gate** from job dispatch for all streamed OpenAI worker traffic and model mutations. Raw router is compute **127.0.0.2:11434**, management tunnel **21434**; workers reach only broker **21435** through reverse tunnels. Stock llama.cpp router spawns random loopback child ports and strips CLI API-key options from children: the router MUST inherit **LLAMA_ARG_API_KEY_FILE** set inside the fresh compute SSH scope. Verified all-four guest probes refuse raw router connections and return 401 for unauthenticated child inference. Management **project-bots-stage3-llama.service** supervises only its dedicated fresh-render-group scope; managed Ollama services/binaries have been removed. See [migration evidence/security details](LLAMA_CPP_MIGRATION.md).

The separate in-VM identity sidecar runs as `python3 -m project_bots.worker_health`, fixed loopback port 18790 by default, using the existing `OPENCLAW_GATEWAY_TOKEN`. Only authenticated `GET /v1/health` is supported; it exposes bounded identity/profile observations, not shell/command/configuration/file access. Run it in the worker VM and tunnel it privately, never on a management host as a substitute for guest identity.

The platform server is a local administrative control plane with explicit compute and local-worker adapters, **not the in-VM worker runtime**. Launch with `project-bots serve` (loopback `127.0.0.1:8032`), or explicitly `project-bots serve --host 0.0.0.0 --port 8032` on a trusted LAN. Use numeric private/loopback IPs or `localhost`; arbitrary DNS Host headers are rejected. IPv6 listening is not implemented. All endpoints below are exact paths (no trailing slash or query parameters). The separate `machine-service` API is documented below; Stage 2 lifecycle and Stage 3 CPU acceptance are documented separately from remaining GPU/scale gates.

## Authentication

### Browser pairing

1. `GET /` and `GET /dashboard.js` are public static assets. No credentials appear in them.
2. `POST /api/pair`, body `{"code":"01234567"}` (example only), with `Content-Type: application/json`, `Origin: http://127.0.0.1:8032`, and `X-Setup-Origin: http://127.0.0.1:8032`.
3. The actual code is printed only in the server console, expires after 600 seconds, and works once. Five incorrect attempts lock pairing until restart. Successful exchange returns `{"token":"<random session bearer>"}`. The code itself is never an API credential.
4. `GET /api/session` with `Authorization: Bearer <session bearer>` and `X-Setup-Origin` returns `csrf` (and legacy provider preset/Codex status metadata). Each browser POST additionally requires matching `Origin` and `X-CSRF-Token: <csrf>`.

Host must include the actual listening port. Cross-origin requests are rejected and no CORS permission is granted. GET requests may omit `Origin` but still require `X-Setup-Origin` for browser-session authentication. The dashboard stores its random bearer in **sessionStorage**, not a cookie, URL, or persistent local storage; refresh in the same tab works. Closing the tab/removing its storage loses that session. The server keeps one session in memory; restart revokes it, resets pairing, and retains the database. After losing a consumed session, restart and pair again. There is no multi-user login, logout endpoint, or durable session store.

### Non-browser machine client

The settings field `machine_api_env` names an environment variable **on the platform server** (default `PROJECT_BOTS_API_TOKEN`). Provision a random secret of at least 32 characters there **before launch**; for example, in a private terminal:

```sh
# Do not print the generated value or enable shell tracing.
export PROJECT_BOTS_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
project-bots serve
```

This credential is optional; missing/short credentials disable machine API access, not the dashboard. Copy the credential to a trusted API client through a separate secure channel; do not paste it into dashboard settings. Settings and responses contain only its variable name. Changing the name takes effect on the next API request; provision that variable in the running server's inherited environment (a new variable normally requires restarting the process). Rotating the environment credential requires restart.

Machine API requests supply `Authorization: Bearer <environment credential>` and `Content-Type: application/json` for POST. They must **omit** `Origin`, `X-Setup-Origin`, and `Sec-Fetch-Site`. No CSRF header or pairing is needed. These credentials grant full administrative access to the registry, jobs, and platform settings, not per-agent isolation. They do not authenticate any real VM or worker, and `/api/session` is browser-only. No request logging or credential-value response is provided. Do not place credentials in URLs. HTTP is plaintext: use loopback plus SSH forwarding, or a separately secured transport; never expose this service publicly.

A real stdlib client, executed on a trusted machine with `PROJECT_BOTS_API_TOKEN` already provisioned securely:

```python
import json
import os
import urllib.request

BASE = 'http://127.0.0.1:8032'  # SSH-forwarded address, not an invented compute host

def api(path, body=None):
    headers = {'Authorization': 'Bearer ' + os.environ['PROJECT_BOTS_API_TOKEN']}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(BASE + path,
        data=None if body is None else json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)

agent = api('/api/agents', {'name': 'Manual API reporter', 'role': 'planner'})
job = api('/api/jobs', {'title': 'Demonstrate durable state', 'input': 'No inference will run'})
path = '/api/jobs/' + job['id']
api(path + '/assign', {'agent_id': agent['id']})
api(path + '/claim', {'agent_id': agent['id']})
api(path + '/progress', {'progress': 50, 'message': 'Recorded by this client'})
api(path + '/complete', {'result': 'Manually supplied example result'})
assert api(path)['status'] == 'succeeded'
# Never print headers or the credential.
```

## Endpoints and bodies

JSON responses are objects except collection GETs, which return arrays. Registry/job creation returns `201`; reads, settings writes and job actions return `200`. API paths are authenticated except pairing. IDs are canonical UUID strings; optional references may be `null`. Stage 1 routes below do not execute tasks; Stage 2 VM actions are a separate explicit boundary. No arbitrary SQL, commands, shell, client paths or XML are accepted.

| Method | Path | Request / response |
|---|---|---|
| GET | `/api/session` | Browser-only `csrf`, legacy `presets`, `codex` metadata |
| POST | `/api/pair` | `{"code":"<8 digits>"}` → `{"token":"<session>"}` |
| GET | `/api/machines` | Machine array |
| POST | `/api/machines` | `{"name":"Compute","endpoint":"https://YOUR_COMPUTE_HOST:9443","credential_env":"COMPUTE_SERVICE_TOKEN"}`; credential reference optional |
| GET | `/api/agents` | Agent array |
| POST | `/api/agents` | `{"name":"Researcher","role":"researcher","config":{"model":"local-model","instructions":"Non-secret instructions","credential_env":"LOCAL_MODEL_TOKEN"},"machine_id":null}`; config and machine optional |
| GET | `/api/jobs` | Job array in creation order |
| POST | `/api/jobs` | `{"title":"Task","input":"Non-secret task text","agent_id":null}`; agent optional |
| GET | `/api/jobs/<id>` | Full job including input, assignment, status, progress, message, result and error |
| POST | `/api/jobs/<id>/assign` | `{"agent_id":"<agent UUID>"}` or `{"agent_id":null}`; queued only |
| POST | `/api/jobs/<id>/claim` | `{"agent_id":"<agent UUID>"}`; queued only, assigned agent must match (or job must be unassigned) |
| POST | `/api/jobs/<id>/progress` | `{"progress":40,"message":"Drafting"}`; message optional, running only |
| POST | `/api/jobs/<id>/complete` | `{"result":"Non-secret result text"}`; running only |
| POST | `/api/jobs/<id>/fail` | `{"error":"Failure explanation"}`; running only |
| POST | `/api/jobs/<id>/cancel` | `{}`; queued or running only |
| GET | `/api/settings` | Platform settings object |
| POST | `/api/settings` | Full replacement: `{"inference_endpoint":"http://127.0.0.1:11434","machine_api_env":"PROJECT_BOTS_API_TOKEN","cloud_fallback":false}` |

Machine registration always reports `status: "unverified"`; agent creation always reports `status: "registered"`. A queued/claimed job is just persisted state. No worker exists; registration/job actions contact no compute endpoint. Completing/canceling a job does not execute or signal a process. Explicit Stage 2 requests alone contact compute. Registry status is intentionally not a cached health claim; read the health response for the actual observation. No registry endpoint editing/deletion is shipped; register a new record for changed machine/agent definitions.

Job responses have `id`, `title`, `input`, `agent_id`, `status`, `progress` (initially 0), `message` (initially empty), `result` and `error` (initially null). These are the latest values, not an event log.

### Job transitions

```text
queued --assign/unassign--> queued
queued --claim-----------> running
queued ------------------> canceled
running --progress-------> running
running --complete-------> succeeded  (progress becomes 100)
running --fail-----------> failed
running --cancel---------> canceled
```

Terminal states have **no outgoing transitions**, including repeated cancellation/completion. Progress is a non-boolean integer 0–100 and cannot decrease. Reassignment of a running job is forbidden. Claim reads and writes happen in one SQLite `BEGIN IMMEDIATE` transaction; simultaneous claims have exactly one winner, the rest return `409`. There is no lease, heartbeat, auto-retry, idempotency key, scheduler, or automatic recovery of running jobs after restart. An administrator may cancel a stale running job and create a new one.

### Validation, errors, limits

- `400 {"error":"Invalid request"}`: malformed JSON, duplicate fields, wrong/unknown fields/types, oversized request, invalid UUID/endpoint/reference, unknown assigned machine/agent, or invalid action. Submitted values are never echoed in errors.
- `403`: missing/incorrect authorization, invalid/expired/consumed code, bad Host/Origin, missing CSRF, or using a machine credential as a browser credential.
- `404`: unknown path or a valid but nonexistent job UUID.
- `409`: transition or assignment conflict.
- `429`: five failed pairing attempts exhausted; restart required.
- POST bodies: `application/json`, positive Content-Length, maximum **65,536 bytes** (pairing maximum 128 bytes). No chunked request bodies.
- Names, roles, titles and model identifiers: 1–200 characters. Input/result: 1–16,000 characters. Instructions/progress message/error: at most 4,000 characters (empty progress message allowed). Task input, result and instructions permit line breaks. Unknown configuration fields, including raw `api_key`/`token` fields, are rejected.
- HTTP(S) endpoints: maximum 2,048 characters, no embedded username/password, query or fragment. Endpoint URLs are references, not connectivity evidence. Never embed credentials in URL paths or free-text fields either.
- Credential references match `[A-Z_][A-Z0-9_]{0,127}`. Stage 2 resolves the selected registry credential reference on the management server for its compute adapter; the separate administrative API variable authenticates platform clients.
- Platform settings cannot enable cloud fallback. Existing provider configuration is separate and **not exposed** through the platform's `/api/config`; legacy setup commands retain their own API when launched separately.

Lists are unpaginated, there is no retention policy, and the stdlib server is suitable for a small trusted local administrative deployment, not public multi-tenant production traffic. Back up the private database while the server is stopped. Never put secrets in task text or results: these are deliberately returned to authenticated administrators.

## Stage 2 compute API

### Transport and scope

`project-bots machine-service --catalog /absolute/catalog.json --state-dir /private/state` listens on **127.0.0.1:9443** by default. `--port`/`--host` are configurable. `--token-env` defaults to `PROJECT_BOTS_COMPUTE_TOKEN`. The token must be high entropy, ASCII/no whitespace, at least 32 characters and at least 16 distinct characters (this only rejects obviously weak values, not proves entropy). Generate with `secrets.token_urlsafe(32)`, provision securely, restart to rotate. Non-loopback listeners require both `--tls-cert`/`--tls-key`; verified TLS or a loopback SSH tunnel is mandatory for the management adapter. No insecure TLS bypass or raw libvirt LAN access.

Direct compute clients send `Authorization: Bearer <compute token>` and JSON POSTs; **no Origin, Sec-Fetch-Site or X-Setup-Origin**. There is no browser pairing/CORS on compute. The browser must use the authenticated platform adapter, retaining the existing Host/Origin/CSRF rules. Compute tokens authorize the entire dedicated compute namespace, not arbitrary libvirt administration or human approval. Limit firewall exposure to the management host. Endpoint registration is administrative configuration, never a discovered or hardcoded IP.

| Direct compute path | Platform adapter path |
|---|---|
| `GET /v1/health` | `GET /api/machines/<machine UUID>/health` |
| `GET /v1/vms` | `GET /api/machines/<machine UUID>/vms` |
| `POST /v1/vms` | `POST /api/machines/<machine UUID>/vms` |
| `GET /v1/vms/<VM UUID>` | `GET /api/machines/<machine UUID>/vms/<VM UUID>` |
| `POST /v1/vms/<VM UUID>/<action>` | `POST /api/machines/<machine UUID>/vms/<VM UUID>/<action>` |
| `GET /v1/operations/<operation UUID>` | `GET /api/machines/<machine UUID>/operations/<operation UUID>` |

All Stage 2 successes return `200`; lists are arrays. Adapter resolves the selected machine's `endpoint` and `credential_env` only at request time, outside platform database transactions. It refuses remote plaintext HTTP, URL credentials/path/query/fragment, redirects, environmental proxies, untrusted certificates and hostname mismatches. Optional `PROJECT_BOTS_MACHINE_CA_FILE` is an **admin-local environment** CA bundle, not a client-supplied path. API errors are redacted. There is no inference route, agent startup, shell, arbitrary libvirt method, XML, package list, disk/image path, cloud-init text or user command input.

### Provision

```json
{
  "template": "ubuntu-desktop",
  "cpus": 2,
  "ram_mib": 4096,
  "disk_gib": 24,
  "ssh_key": "ssh-ed25519 <base64 public key, no trailing comment>",
  "operation_id": "<fresh canonical UUID>",
  "confirmation": "create"
}
```

This is a schema example, not executable input or a granted approval. Supply an actual key and UUID, and authorize the action yourself. The create operation UUID also becomes the VM UUID (`pb-<UUID>` domain). VM disks are standalone private qcow2 conversions, not shared writable backing images; seed is read-only. SHA-256 and standalone qcow2 format are checked against the trusted **admin-local catalog** before conversion. Cloud-init is generated internally with only `ubuntu-desktop-minimal`, `openssh-server`, `qemu-guest-agent`, package update, a locked non-sudo `bot` user, disabled root/password SSH, and the supplied ed25519 public key. It accepts no extra commands/packages. Provisioning defines a **shut-off** VM; Desktop packages install on first boot and require working package mirrors/network. Host GPU/Ollama is not configured or passed through.

Per VM bounds: integer/non-boolean **1–8 CPUs, 2048–32768 MiB RAM, 16–256 GiB disk**. Aggregate reservation policy caps CPUs at min(8, host CPUs minus 2), RAM at min(32768 MiB, host total minus 8192 MiB), and disk at available filesystem GiB minus 10 GiB. Existing non-deleted reservations count even when off or provisioning is uncertain; disk reservations are conservative and also count against currently free space. Start additionally requires requested RAM plus 4096 MiB currently available. These are admission bounds, not a cgroup guarantee against concurrent host/Ollama pressure.

### Actions and confirmation

Every mutation requires a fresh `operation_id` UUID and exact `confirmation: "<action>:<VM UUID>"`. Dashboard prompts require typing that string, and no mutation is sent on cancellation/mismatch. These are explicit caller-intent fields, **not an independent approval/RBAC system**. An authenticated program can supply them: callers/assistants must obtain real authorization and never infer it from untrusted VM/job/tool text. Requests, responses and error strings never become executable commands.

| Action | Extra fields | Preconditions / effect |
|---|---|---|
| `start` | none | Shut off → running request |
| `shutdown` | none | Running/paused → graceful ACPI shutdown request, no force |
| `restart` | none | Running → graceful reboot request, no reset |
| `pause` | none | Running → suspended |
| `resume` | none | Paused → running |
| `resources` | `cpus`, `ram_mib`, `disk_gib` | Shut off; same bounds, disk may only grow; no disk growth with snapshots |
| `snapshot-create` | `snapshot` | Shut off; internal disk-only snapshot of standalone qcow2 |
| `snapshot-restore` | `snapshot` | Shut off; restore an existing service-recorded disk-only snapshot |
| `delete` | none | Shut off; undefine verified-owned domain, remove only fixed files inside its private directory; retain tombstone/operation metadata |

Snapshot names match `[a-z][a-z0-9-]{0,31}`. No live snapshots, RAM snapshots, backing chains, external snapshot paths, shrinking, forced power-off, snapshot deletion, guest filesystem resizing, custom networking or GPU passthrough. Restoring a disk snapshot does not restore CPU/RAM settings. Disk growth must be followed by separately approved guest filesystem expansion (not implemented here). Shutdown/restart return **observed** state immediately; poll detail until desired state is reached. Paused guests may need resume before ACPI shutdown can complete.

Detail exposes durable `desired`/`phase`/requested resources and fresh `state`, with UUID/owner metadata/exact disk-path verification. Failed observation returns `state: "unavailable"`, never assumes the domain is absent. Console info includes SPICE `listen: "127.0.0.1"`, observed port (null/unassigned when off), `ssh_user: "bot"`, allocated `ssh_port` in 22000–22099, and `requires_tunnel: true`. User-mode passt forwards that loopback port to guest 22; no raw graphics or SSH listener is intentionally exposed to LAN. Validate actual bindings on the compute host. See host docs for tunnel/access checks.

Health performs an authenticated `virsh ... version` read and reports CPU count, memory total/available, free storage, KVM device access, template IDs, reservation policy and backend URI `qemu:///session`. It does **not** prove VM boot, package installation, SSH, Desktop readiness, passt support or Ollama capacity.

### Durability, idempotency, errors

Compute has a separate private SQLite DB, durable service owner UUID, VM intent/tombstones and operations. Operations store ID, target, action, request digest (not credentials/raw key), timestamps, state (`running`, `succeeded`, `rejected`, `unknown`) and success result. Writes serialize with an OS flock across HTTP threads/processes; SQL transactions are not held over subprocess/network calls. Exact successful replays return the original cached result without commands, even after restart. Changed payload/action/target with the same ID returns `409`. A fresh detail read, not cached operation output, supplies current observed state.

Host commands use fixed argv with no shell and a 120-second timeout. Adapter timeout is 15 seconds: create/conversion may outlast it **without failing on the host**. Keep the original UUID/payload, inspect its operation and VM, and never blindly submit a new create UUID. Successful host completion remains inspectable/cached. Incomplete/crashed/unknown operations block further mutations of that target, including after restart; they are not automatically retried or cleaned up. Local administrator reconciliation while service is stopped is required; no API exists to clear uncertainty. Partial disks/definitions are retained deliberately rather than risk deleting unrelated state. Rejected IDs also cannot be reused; correct the request under a new ID only after confirming no mutation occurred.

Compute POSTs require non-chunked JSON with Content-Length **1–16384 bytes**; duplicate fields/unknown action fields are rejected. `400` validation, `403` authentication/browser-origin rejection, `404` unknown resource, `409` state/ownership/operation conflict or busy host, `503` unavailable/uncertain host outcome. The adapter reads bounded responses (2 MiB). No secrets or subprocess stderr are returned. These stdlib servers are for a small trusted administrator deployment, not public multi-tenant traffic. [Host setup and actual acceptance](COMPUTE_HOST.md) must be completed before claiming Stage 2 works on hardware.
