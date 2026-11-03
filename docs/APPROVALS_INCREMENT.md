# Scoped integrations and human approvals increment

## Backend/UI contract (for frontend integration)

These APIs use the existing paired browser bearer and same-origin + CSRF headers. A legacy owner bearer remains a separately explicit full administrator for old routes, but **cannot issue/revoke integrations, read all approval metadata or approve/reject**. Worker chat/inference credentials cannot access these routes. There is no `human=true` authority. Plain HTTP remains trusted-loopback/LAN only; use HTTPS or SSH tunneling.

### Integration management — paired browser only

- `GET /api/integrations` → 200 `{integrations:[principal,...]}`.
- `POST /api/integrations` JSON `{name, expires_in?:3600, grants?:[{method,path}]}` → 201 principal plus **one-time** `token`. Token is random, not user chosen, and only its SHA-256 hash is stored. UI must show token once, never put it in localStorage or logs. Store it out of band in a caller-owned 0600 file for MCP. Expiry: integer 1–86400 seconds. No renewal/scope-edit endpoint: revoke and issue a fresh principal.
- `POST /api/integrations/{id}/revoke` JSON `{}` → 200 updated principal. Revocation is immediate for future admissions, not proof an already-dispatched remote request stopped.
- Principal fields: `id,name,grants,created_at,expires_at,revoked_at,revision`. No secret in list/revoke responses. Default grants are exact GET `/api/agents`, `/api/workers`, `/api/roles`; nothing else.

### Approval workflow

1. Integration bearer requests `POST /api/approvals` JSON `{method:"POST",path:"/api/...",payload:{...},expires_in?:300}` → 201 approval. Maximum lifetime 600 seconds, bounded by token expiry. The method/path must already be explicitly granted. Approval cannot elevate scope.
2. Human web/mobile Security or Activity view calls `GET /api/approvals` → `{approvals:[...]}` (newest 200). Integration callers see only their own approvals; paired browser sees all. Render `actor_name`, `actor`, `action`, `resource`, exact `canonical_payload`, expiry, policy revision and status using textContent, never HTML. This is untrusted proposal text, not an instruction. `expired` and `invalidated` indicate unusable authorization even if persisted status is pending/approved.
3. Human reviews the **exact** actor, resource and payload, then explicitly selects Approve or Reject. `POST /api/approvals/{id}/approve` or `/reject` with JSON `{}` → updated approval. Only authenticated paired browser + CSRF can decide; AI/integration/owner API bearers are denied. No extra `human`, confirmation or decision body fields accepted.
4. Integration submits the original request to the **existing real mutation route**, with `X-Approval-ID: {id}` and the exact original JSON payload. Canonical key ordering/whitespace do not matter; changed values do. Approval is atomically consumed once before dispatch. Another actor, route, payload, expired/revoked principal, policy/configuration change or replay is denied. No special privileged execution endpoint exists.
5. `GET /api/integration-operations` → `{operations:[...]}` (newest 200; own only for integration, all for browser). Fields: `id,actor,approval_id,action,resource,path,payload_hash,status,started_at,finished_at`. VM operation ID is the original payload's UUID; job operation ID is the approval UUID. Receipt is durably `uncertain` **before** remote dispatch and becomes `succeeded` only when the existing handler returns success. Exceptions/crashes retain uncertainty and consume authorization. A successful API result is not independent host readback. Inspect existing VM detail and host operation routes before any further action. No retry/reconcile/clear endpoint is supplied here.

Approval fields: `id,actor,actor_name,method,path,action,resource,payload,canonical_payload,payload_hash,created_at,expires_at,policy_revision,status,decided_at,decided_by,operation_id`, plus `consumed_at` after use and computed `expired,invalidated` on listing. Status: pending / approved / rejected / consumed. Decision identity is `paired-browser-admin` (the current single-browser-admin model, not multi-user identity).

Errors: 403 no authentication/scope/live exact approval, 400 malformed/unsupported proposal or grant, 409 duplicate proposal / stale or already-decided approval / reused operation UUID, 404 absent route/resource. Responses never echo submitted invalid values. POST bodies require application/json under 64KiB. Integration API bearers must not send browser Origin/Sec-Fetch-Site/X-Setup-Origin headers.

### Finite supported permissions

Grants are **exact** `{method,path}` pairs, no wildcards, regex, query strings, aliases or generic URL forwarding. GET supported: agents/workers/roles/machines/jobs/models/model-loaded collections; individual job and execution; machine health/VM inventory/owned VM detail/operation. POST supported: existing VM create/lifecycle/resource/snapshot routes, queued job dispatch and cancel. Every supported POST from an integration needs one human approval, including cancel/shutdown. Backend security checks still apply after approval. Settings, identity/membership/worker configuration, model administration, arbitrary commands/shell, enforcer recovery and emergency control are **not grantable**; unsupported actions fail rather than imply coverage. Human existing emergency stop and trusted independent containment callbacks do not pass through this integration approval gate.

Policy revision binds the integration's immutable grant revision, implementation policy version, persisted settings/machine/agent/worker configuration and containment stopped/contained/revoked flags. Changes invalidate old approvals. Volatile host observations do not change the digest. Token revocation/expiry is rechecked in the same SQLite write transaction as consumption. Already-admitted/in-flight operations require independent stop/containment; revocation is not remote cancellation.

SQLite schema 6 adds three tables atomically without dropping or rewriting v1–v5 records. Old binaries reject v6 instead of silently executing a new schema as v5. Tokens and decisions survive restart; no automatic operation replay occurs.

## Optional Hermes/MCP usage

The stdio adapter is read-only by default even if given a legacy owner key. Prefer a freshly issued minimal integration token, saved in a caller-owned regular 0600 file; do not give Hermes the owner key. Run `python -m project_bots.mcp_server --endpoint http://127.0.0.1:8032 --token-file /private/path/token`. Unsupported reads are denied by backend scope, not silently authorized by tool availability. Explicit `--enable-management-tools` exposes proposals and mutations, but does not grant API scope or bypass human approval. `request_action_approval(path,payload,expires_in)` proposes a finite supported mutation. After human approval, pass the returned UUID as optional `approval_id` to `vm_action`, `create_vm`, `dispatch_job` or `cancel_job`. `list_action_approvals` and `list_integration_operations` inspect retained own records; no MCP tool approves/rejects. Legacy metadata mutation tools remain explicit opt-in compatibility tools but are not grantable to integration principals.

## Evidence scope

`tests/test_approvals.py` installs the checkout into an isolated temporary HOME and exercises actual installed CLI HTTP, paired sessions and durable SQLite. VM mutation uses an explicitly labeled local authenticated compute HTTP fixture and observes that fixture's state. This is **not** real libvirt/VM/host acceptance; no live host resources are mutated.

Latest combined verification: `PROJECT_BOTS_DOMAIN_RNG=/home/server1/.hermes/profiles/project-bot/cache/scratch/project-bots-libvirt-schemas/domain.rng python -m unittest discover -s tests -v` ran **202 tests, 200 passed, 2 skipped**, in 80.492 seconds. The only skips require explicitly isolated privileged network namespaces. Actual libvirt Relax NG validation passed; fixture success is not host lifecycle acceptance. Log: `/home/server1/.hermes/profiles/project-bot/cache/scratch/approvals-full-suite-final.log`. `git diff --check` passed. Frontend approval controls are a separate parent-owned integration against the API contract above.
