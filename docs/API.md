# Stage 1 API

The stdlib HTTP server is a local administrative control plane, **not a worker or VM service**. Launch with `project-bots serve` (loopback `127.0.0.1:8032`), or explicitly `project-bots serve --host 0.0.0.0 --port 8032` on a trusted LAN. Use numeric private/loopback IPs or `localhost`; arbitrary DNS Host headers are rejected. IPv6 listening is not implemented. All endpoints below are exact paths (no trailing slash or query parameters).

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

JSON responses are objects except collection GETs, which return arrays. Creation returns `201`; reads, settings writes and job actions return `200`. API paths are authenticated except pairing. IDs are canonical UUID strings; optional references may be `null`. There is no delete, arbitrary SQL, subprocess, shell, host-probe or VM-execution endpoint.

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

Machine creation always reports `status: "unverified"`; agent creation always reports `status: "registered"`. A queued/claimed job is just persisted state. No worker exists, no endpoint is contacted, and completing/canceling a job does not execute or signal a process. Agent status never changes to suggest a live worker. No endpoint editing/deletion is shipped; register a new record for changed machine/agent definitions.

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
- Credential references match `[A-Z_][A-Z0-9_]{0,127}`. The API does not resolve registry credential references; only the configured administrative machine API variable is read for authentication.
- Platform settings cannot enable cloud fallback. Existing provider configuration is separate and **not exposed** through the platform's `/api/config`; legacy setup commands retain their own API when launched separately.

Lists are unpaginated, there is no retention policy, and the stdlib server is suitable for a small trusted local administrative deployment, not public multi-tenant production traffic. Back up the private database while the server is stopped. Never put secrets in task text or results: these are deliberately returned to authenticated administrators.
