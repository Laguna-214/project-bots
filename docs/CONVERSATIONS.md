# Conversational agents and group collaboration

The opt-in trusted conversation runner uses the **existing shared llama.cpp broker**;
it never launches a model server per agent. All clients use the same persistent
chat API. It is a tool-free adapter, not an OpenClaw replacement or a native app.

## Administrator setup

Provision separate high-entropy environment secrets privately for chat identity,
inference identity and the worker Gateway; never reuse control-plane/admin/backend
credentials or put secret values into the UI, memory, task text or Git. The agent's
registered `config.credential_env` must match the broker's independent inference
credential map. Existing runtime/model/profile/identity and real security-health
prerequisites still apply. No secret issuer or live deployment is performed here.

1. Register the agent and its intended worker/model profile through the existing
   authenticated administrator APIs. Registration alone is not an online agent.
2. Bind its independent message identity using
   `POST /api/agents/{uuid}/chat-identity` with a credential environment **reference**
   and `enabled:true`.
3. Use Agents → **Advanced · conversational enrollment**, or the administrator API
   `GET|POST /api/agents/{uuid}/conversation`. POST requires all fields:
   `enabled`, `system_instructions`, `memory`, `tools:[]`, `max_replies`.
4. Only after trusted monitoring/enforcement and independent credentials are actually
   available, run the backend service independently of the browser:

```sh
python3 -m project_bots.chat_runner --db /PRIVATE/platform.db \
  --broker http://127.0.0.1:21435
```

Missing coverage fails closed; do not fabricate observations to bypass it. `--once`
processes at most one eligible job. Do not run `--recover-offline` concurrently with
another runner: that explicit offline command marks abandoned work uncertain and
never retries it. Service installation/startup is an administrator deployment action,
not something triggered by opening a client tab.

## Context and communication boundaries

- Human messages atomically enqueue at most one reply per enabled assigned agent.
  Retried message UUIDs do not duplicate work. Generated/peer messages do not create
  recursive loops. Independent agents may execute concurrently through the shared
  broker where its conservative limits permit.
- Individual conversations use only the responding agent's enrolled instructions,
  relevant private memory and that chat's bounded history. No peer's private context
  is loaded. Group requests deliberately omit **all private instructions and memory**
  and use the responding agent's public registered name/role plus shared history.
- A later group participant can see an already-completed peer reply from the same
  human turn. The history join binds message sender/chat/job/root turn; arbitrary
  client IDs are not evidence of a trusted reply. Concurrent replies that begin
  before a peer commits may not see that peer until the next human turn. This is
  bounded collaboration, not an unlimited autonomous peer-to-peer conversation loop.
- Peer messages remain untrusted user-role data, never system/tool authority.
  No tools execute through this adapter; unsupported tool calls and tagged reasoning
  responses are rejected, and separate reasoning fields are not published. This is
  not a semantic guarantee that any arbitrary model output can be classified as
  private reasoning; model/backend configuration remains a separate review gate.
- Identity/membership revision, enrollment changes, security state and cancellation
  are rechecked while running and at reply commit. Remove→re-add races cannot publish
  stale authorized context. Uncertain remote work blocks new dispatch for that agent.

## Budgets and Activity

`max_replies` is **1–32 admissions per agent, per conversation, per rolling 60 seconds**,
not a permanent lifetime cap. Canceled/blocked attempts still count; editing config
is not a refund. Broker rate/token/context/queue budgets apply independently.
Human messages remain visible when a reply admission is rate-limited; the next
eligible human turn can admit a reply after the window. There is no automatic
retry/replay of previously rate-limited turns.

Activity shows reply IDs/statuses and offers cancellation for queued/running work.
Administrator endpoints:
- `GET /api/conversations/jobs[?chat_id={uuid}]`
- `POST /api/conversations/jobs/{uuid}/cancel` with `{}`.

Cancellation of a job/stream is not proof that remote generation stopped. Keep
uncertain receipts and reconcile actual backend state; never clear reservations or
retry blindly. Changing enrollment may cancel pending work and invalidate an
in-flight request; the UI warns about independently required runner/health setup.

## Verified scope

The focused conversation suite passes **19 tests**, including actual local HTTP
fixtures, broker-bound four-UUID-agent requests, subprocess runner, restart
uncertainty, revocation races, private context separation, rolling budgets and
same-turn shared peer visibility. The new Node enrollment/activity suite passes
payload/tool restrictions, safe private-field loading and delayed-load draft
preservation. Existing chat/security/client/VM Node suites also pass.

These are fixture/application contracts, **not** the mandatory four-real-agent
loaded-model/Vulkan acceptance, hostile-VM containment, full approved tool execution,
native device/app installation, short-lived credential issuance or deployed uptime.
The full combined suite must be rerun after concurrent security/permission changes.
