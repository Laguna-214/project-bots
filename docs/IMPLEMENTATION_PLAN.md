# Implementation plan

Exactly **five development stages** follow. Names and ordering are fixed; hardening starts immediately, not only in the final stage. Historical repository stage labels do not rename these stages or prove completion. Work in small reviewed increments that preserve the functioning llama.cpp RX6800 Vulkan setup and four workers. Each gate needs source revision, test scope, actual output, evidence location and explicit limitations.

## Stage 1 — Core Application

**Deliver:** backend independent of clients/Hermes; durable machines/agents/jobs/settings and migrations; native application-owned individual/group chats/history, memberships and shared events; authenticated responsive web shell; basic authorization, validation, secret references, safe rendering, private persistence and audit foundations. Establish Chats/Agents/Activity navigation without pretending infrastructure registration creates an online agent. Application-owned chats are not a claim of native mobile/desktop apps.

**Gate:** isolated installation/restart/migration tests retain state; unauthorized API access and malformed input fail; browser host/origin/CSRF/session checks pass; atomic job claims and honest state transitions are demonstrated. Define principal/resource authorization and approval contracts before privileged expansion.

**Current evidence:** registry/jobs/settings, private SQLite, pairing/browser guards and installed fixture HTTP tests exist. Chat schema v4 and security state/incident schema v5 are source-tested working-tree code, not deployed to existing services. Not a claim that all core UX or fine-grained user authorization is complete.

## Stage 2 — Machine Manager

**Deliver:** separately authenticated Machine Manager with distinct service identity; trusted templates, owned VM inventory, one-runtime-per-VM allocation, resource admission, bounded lifecycle/offline snapshots, operation IDs, readback and uncertain-outcome reconciliation. Establish default-deny segmentation, external monitoring hooks and safe runtime start gates before hostile execution. Any lightweight container+sandbox alternative must disclose its weaker assurance.

**Gate:** unit/contract checks plus separately authorized disposable-only create/start/inspect/stop/offline-snapshot/restore/delete acceptance, preserving important workers and exact evidence/operation IDs. Deny unauthorized ownership changes, host access, privilege escalation and arbitrary commands/images/XML. Distinguish application admission limits from physical resources and OS enforcement.

**Current evidence:** compute routes and mocked command tests exist; [historical Stage 2 evidence](STAGE2_ACCEPTANCE.md) records real narrower lifecycle/boot gates, not the expanded security model. The later bounded MCP checkpoint did not submit additional disposable lifecycle mutations when policy admission blocked capacity. Expanded host/security gates remain unverified; this plan does not authorize new live actions.

## Stage 3 — AI Workers & Model Manager

**Deliver:** independent identities/workspaces/memory/history/secrets/tools/network/resources; explicit deployed identity/profile checks; role-based capabilities; centralized registry and model administration unavailable to agents. One selected model loaded once in shared llama.cpp; per-request agent-only instructions/context/relevant memory/authorized tools. Preserve local inference with no cloud/model fallback.

Implement bounded configurable scheduling with interactive priority, per-agent fairness/limits, token/context budgets, queue/backpressure, timeout, real cancellation and CPU/GPU telemetry; benchmark conservatively before enabling backend continuous batching/parallelism. Integrate security health and durable stop/containment admission checks.

**Gate:** four real independent agents use one verified loaded server; record scheduling measurements and instruction/private-memory/history/permission isolation. Capture live RX6800 Vulkan evidence, model/server identity and resource telemetry. Validate overloaded/canceled/uncertain jobs without false success or leaked reservations; prove agents cannot launch model servers/administer registry.

**Current evidence:** worker presets/configuration, identity preflights, model broker and serial durable priority/FIFO admission exist. Shared broker fairness/aging, bounded budgets and cancellation/revocation of forwarding are source/HTTP-fixture tested; actual backend-stop proof is not provided. Four-agent live acceptance is **BLOCKED** in inherited context by stopped VMs; unavailable loaded memory/GPU accounting is not a substitute. Do not start them under this plan alone.

## Stage 4 — User Control & Collaboration

**Deliver:** individual/group chats and membership control; central authenticated persistent message broker distinct from inference; sender binding, recipient visibility, immediate revocation and network anti-bypass enforcement. No implicit private data/tools/secrets/chain-of-thought sharing. Implement agent name/role/model creation, activity, approvals, stop-one and durable emergency stop-all; retain management/security access. Security dashboard exposes actual all-agent protection health and incidents/evidence, not registration badges.

**Gate:** real authorized collaboration plus unauthorized sender/group/read/revocation tests; out-of-band peer/network attempts denied. Exercise human approvals, containment, stop-all creation/start latch across restarts/races and safe recovery. Responsive mobile workflows and desktop full-web behavior must be exercised. Optional MCP/native client integration requires actual discovery, authenticated call and permission semantics, not SDK initialization alone.

**Current evidence:** `chat.py` and platform tests implement an initial persistent broker with agent credentials, memberships, idempotency and metadata events. Durable incident/stop/recovery APIs and Security dashboard controls are now fixture-tested. Automatic replies/runtime delivery, packet containment, full human approvals, native notifications and protected monitoring remain incomplete. Historical MCP evidence is bounded; native apps are not delivered.

## Stage 5 — Final Product & Hardening

**Deliver:** finish cross-stage gaps and complete web, native mobile and desktop experiences; hardened independent backend/enforcer/audit/Machine Manager/runtime identities, short-lived credentials, secret/network segmentation, tamper resistance, configuration integrity, limits, monitor-monitor fail-safe and secure admin recovery. Finish external monitoring, deterministic severity/containment engine, readback/partial-failure reporting, incident investigation/history/acknowledgment and alerting, without deferring their basic prerequisites from earlier stages. Finalize reliability/recovery, tested backups/restore, installation/update/uninstall, documentation and release preparation. Verify accessibility/responsiveness; optional native desktop features remain scoped. Native apps do not exist yet.

**Gate:** every malicious case in [SECURITY_ACCEPTANCE.md](SECURITY_ACCEPTANCE.md) has a real blocked attempt, detection, incident, containment and preserved evidence; normal collaboration and recovery pass; monitor failures contain rather than downgrade. Re-run four-agent shared-model acceptance and non-destructive regression checks. Document remaining blocked/unrun gates and exact supported threat model. No production-security or completion claim while a mandatory gate is blocked, mocked-only or unverified.

**Current evidence:** this stage is **not complete**. Prior completion subjects/checkpoints and MCP initialize results do not meet product or hostile-agent acceptance.

## Execution and evidence rules

- Read actual source/dirty state first; preserve concurrent work and earlier bounded evidence. Baseline executed 97 tests, 96 passed and one optional skip; the combined continuation ran 150 tests, OK with one optional skip, plus all three Node interaction suites. See the product-update handoff for exact scope; none establishes full hostile-agent acceptance.
- Use disposable fixtures for contracts. Mocked commands/SDK fixtures prove contracts only, never VM containment or GPU behavior. No destructive live host/VM changes or security broadening without separate approval.
- Treat unavailable permissions/resources/telemetry as **BLOCKED**, not a simulated pass. Resolve capacity by authorized policy review, not by stopping/resizing important workers or guessing physical limits.
- Keep acceptance records with exact revision/config, targets, operation/job/incident IDs, observations, before/after readbacks and limitations. Never print secrets or private reasoning in public reports.
- Complete one bounded increment, test it and verify its actual behavior before expanding scope. No automatic recovery/retry on uncertain remote side effects. No Hermes configuration is required to implement the backend product.
