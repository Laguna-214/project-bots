# Product requirements

## Authority and scope

This is the durable product brief, not a claim that the product or its security is complete. **MUST** denotes a requirement; implementation observations are explicitly labeled. Develop incrementally in exactly the five stages in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), with basic security and evidence at every stage. Historical stage labels and commit subjects are not acceptance authority.

Preserve the working llama.cpp RX6800 Vulkan path and four independent workers. No destructive live host/VM changes, broad privilege changes, extra model installations, or unrelated Hermes configuration changes are authorized by these documents. Real mutation/hostile testing requires separately authorized disposable resources; do not repurpose important workers.

## Product and clients

- One authenticated backend owns state and authorization independently of any client, Hermes session, or MCP adapter. Clients cannot implement the only security boundary.
- Deliver responsive web first. Mobile prioritizes **Chats / Agents / Activity**: individual and group chats, membership management, agent creation by name/role/model, security alerts, approvals, stop one and stop all. Hide infrastructure detail from the normal mobile workflow, not from enforcement.
- The final product requires complete web, native mobile and desktop client experiences on the same backend. Desktop offers the full web capabilities; optional native features include notifications, files, terminal integration, multiple windows and debugging, subject to permissions. Native mobile/desktop applications are **not implemented** and must not be advertised as done.
- Persist agents, machines, jobs, execution receipts, shared conversations, memberships, model profiles, security events/incidents and recovery state. Show actual health with observation times; registration/configuration alone never means running, healthy or protected.
- Provide explicit human approvals for sensitive operations, scoped to actor/action/resource and invalidated on relevant changes. Confirmation strings alone are not authenticated human approval.

## Independent hostile agents

Assume agents can be malicious or compromised. Prefer **one VM per runtime**. An optional lighter mode requires hardened containers plus sandboxing, least privilege and additional isolation; it is not equivalent to a hostile-workload VM guarantee.

Each agent MUST have its own identity, workspace, private memory, history, secrets, tool permissions, network policy and resource limits. It cannot escalate privileges, read another agent's private data, control peers, modify permissions, reach host files or manage runtimes/model servers. Role prompts and runtime tool allowlists are defense in depth, not containment. Homelab observation remains read-only unless a separately approved capability explicitly grants more.

OpenClaw is an initial runtime adapter, not permanent product coupling. Trusted backend and authorized human administrators alone manage identities, permissions and lifecycle; optional Hermes is explicitly configured and permissioned, never mandatory or an unrestricted manager.

## Collaboration

All agent messaging MUST traverse a **central message broker, distinct from the inference broker**. Authenticate the sender from credentials, never request fields; enforce conversation membership and authorized recipient visibility on reads and sends; persist messages with idempotent retries and immediate revocation. Define membership/history visibility explicitly, including what newly added members may see.

Enforce network policy against direct peer messaging, alternate channels and broker bypass. Chat shares explicit messages only: no implicit access to private files, tools, secrets, private memory, or chain-of-thought. Conversation membership does not grant runtime/tool authority. Shared results may contain approved summaries, not private reasoning traces.

## Shared inference and model management

- Centralize model registry and privileged model operations. Load the selected model **once** into one shared server for four independent agents, not one server/model copy per agent. Agents cannot launch servers or administer the registry.
- Each request contains only that agent's system instructions, context, relevant authorized memory/history and authorized tool definitions. Profiles may share the underlying model but vary generation parameters. Never share private contexts, sessions or credentials across agents.
- Agents select centrally registered model profiles; they do not launch model servers. Allow future routing, optional specialist models and explicitly configured providers without requiring them for normal single-model operation or silently falling back to cloud.
- Independently authenticate and authorize every requesting agent; enforce rate/resource budgets, cancellation/revocation and request metadata logs without exposing private prompts, memory or secrets. Workers must not reach raw inference or model-administration endpoints or modify their own inference policy.
- Configure concurrency and queue bounds; support backend continuous batching where actually available. Add interactive priority **and per-agent fairness**, per-agent limits, token/context budgets, CPU/GPU telemetry, deadlines, real cancellation, overload handling and conservative benchmarking before increasing parallelism. A disconnected request or changed job row is not proof remote execution stopped.
- Acceptance requires four real agents using one verified loaded model, observable scheduling, instruction/memory/history/permission isolation, and retained measurements. Loaded-state inventory alone is not current GPU/Vulkan proof.

## Security, containment and operator control

Trusted external monitors MUST observe runtime execution/shell/privilege/filesystem/escape/resource behavior; network egress, peer contact, unauthorized services/listeners, broker bypass and transfers; identity/credential/admin/policy changes; repeated denials, restricted reads, manipulation and evidence concealment. Combine deterministic rules, OS/VM telemetry, enforced networking and behavioral anomalies. AI may explain evidence but is never sole enforcement or an administrator.

| Severity | Required response |
|---|---|
| Information | Record evidence/event. |
| Warning | Alert and increase monitoring. |
| High | Block, revoke temporary access, cancel jobs and isolate. |
| Critical | For escape, theft, monitoring/audit tampering or peer compromise: isolate **and terminate the VM**. |

Containment MUST revoke broker and temporary credentials; block network, jobs and new jobs; stop runtime execution; preserve external evidence; create/update incident; notify the administrator. Read back every action's target state, report partial failures honestly, and forbid automatic restart until explicit admin recovery. Do not wait for successful evidence export before blocking an active compromise.

Preserve evidence before destruction/rebuild; take forensic snapshots where practical, but never delay emergency containment to obtain them. Keep configurable severity policy under trusted administrator authority and test partial-failure behavior.

Admin global emergency stop MUST stop all agent execution, cancel jobs, revoke credentials, block networks and durably latch creation/start/dispatch against restart races. Preserve management and security services so the administrator can investigate and recover.

Provide an all-agent security dashboard showing actual protection/monitor health, current and historical incidents, evidence, policy violations, network denials, permission/communication events and runtime terminations. Each incident needs UUID, timestamp, agent, severity, behavior, resource, evidence, attempted/verified actions, outcome and status; support investigation, acknowledgment and separately authorized recovery. Acknowledgment is not permission to resume.

Protect backend, enforcer, audit system, Machine Manager and runtimes separately: distinct service identities, internal API authorization, short-lived scoped credentials, secret segmentation, default-deny access, tamper-resistant external audit, configuration integrity, resource limits and secure admin recovery. Monitor the monitors; lost/stale required coverage MUST prevent execution or contain existing execution, never silently downgrade protection.

## Acceptance and current limitations

[SECURITY_ACCEPTANCE.md](SECURITY_ACCEPTANCE.md) defines the mandatory malicious-case matrix and normal collaboration/recovery gates. Every malicious case requires a real blocked attempt, detection, incident, containment and preserved evidence; unavailable privileged tests are **BLOCKED**, not simulated passes.

**Observed source state:** persistent platform/jobs, compute adapters, worker/profile checks, model broker and durable serial admission exist. In-progress chat code adds schema v4, individual/group messages, separate environment-reference agent chat credentials, membership checks/revocation and metadata security events. It does not establish hostile-runtime network containment, automatic model replies, complete incident response or production security. See [ARCHITECTURE.md](ARCHITECTURE.md) for exact boundaries.

**Current operational observations and test results:** see [deployment](DEPLOYMENT.md) and [product-update handoff](PRODUCT_UPDATE_2026-11-02.md). Read-only inspection found four registered workers with stale verified status, four original domains shut off and an additional stopped domain of unverified provenance. Four-agent real acceptance remains blocked; this document does not authorize starts/stops. A loaded `qwen3-1_7b` response with unavailable memory accounting / `size_vram: 0` is not current GPU proof. Baseline was 97 tests (96 passed, one skip); the source increment now has 106 discovered (105 passed, one optional skip). These are software/fixture results, not hostile-agent acceptance.
