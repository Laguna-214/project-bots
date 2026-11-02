# Stage 4 MCP — bounded core checkpoint, not full acceptance

Stage 3's sandboxed four-guest browser gate passed **before** this work began;
see [STAGE3_BROWSER_ADMIN_GATE.md](STAGE3_BROWSER_ADMIN_GATE.md) for the exact
one-time guest-root authorization, package pins and offline controlled-page proof.
No host security changes, bot sudo or permanent guest-root API were introduced.

## Implemented and exercised

`project_bots/mcp_server.py` uses the **official Python MCP SDK 2.3.0**, stdio
transport and standard initialize/tools/list/tools/call. No custom pseudo-MCP,
HTTP listener, shell execution, guest commands, sampling or root capability.
Optional dependency is pinned in `requirements-mcp.txt`; the base platform stays
stdlib-only. The current managed Python environment already had SDK 2.3.0;
no dependency install or Hermes environment mutation was performed.

Seventeen explicitly typed tools delegate only to existing authenticated platform
routes:

- `list_workers`, `worker_health`, `list_agents`
- `create_job`, `assign_job`, `dispatch_job`, `get_job`, `get_job_execution`
- `list_machines`, `machine_health`, `list_vms`, `get_vm`, `get_operation`
- `create_vm`, `vm_action` (fixed lifecycle/offline snapshot enum)
- `list_models`, `loaded_models`

Structured output is explicit. Read/mutation annotations are explicit. There is
no generic URL/path/method/shell tool. Caller text cannot select an arbitrary
compute command, guest command, package, image URL or raw XML. `assign_job` assigns
an existing queued job to an existing agent; it does **not** change a live worker's
model. Model assignment/reconfiguration and model mutations are deliberately not
exposed in this checkpoint. No fake approval queue or invented API is advertised.

The adapter reuses the existing endpoint/TLS/token policy: HTTPS or explicit
loopback HTTP tunnel only; credentials are resolved by an operator-selected
environment-variable **reference**, never tool inputs. Redirects/proxies are
refused, reads bounded at 2 MiB and request timeout 330 seconds. VM commands retain
caller operation UUID and exact `<action>:<VM UUID>` or `create` intent. Dispatch
requires `dispatch:<job UUID>`. These strings are **not cryptographic human
approval**: the MCP host/operator must obtain actual permission. The existing
platform/compute admission, ownership, resource, conflict and offline checks are
still authoritative. Unknown outcomes require inspecting the **original** IDs,
not automatic retries or force-unlock. MCP cancellation is not remote inference
cancellation. Create-job has no idempotency key: inspect before retrying.

## Real end-to-end evidence

A fresh official-SDK stdio client negotiated **2025-11-25**, listed all 17 tools,
observed the four existing workers, authenticated worker health, model inventory,
loaded model, compute health and exact VM list. It then created and dispatched one
real Researcher read-tool job entirely through MCP → installed platform 8033 →
existing worker → GPU llama.cpp broker path:

- Job **`edae31ba-0bdc-419a-9653-be4a5a818032`**
- Response **`resp_f793776d-2d74-41eb-8d3d-bb7c5cf67373`**
- Preserved VM **`55545d36-bd05-4e48-9eb4-cea5fbe8c8f4`**
- Unprompted workspace challenge **`b4688a00-760c-4dcf-b429-ed6348877bb5`**

The result matched the file's challenge; retained actual OpenClaw audit contains
`tool.action.finished`, `read`, `succeeded` with that response run ID. Wrong
confirmation returned a real MCP tool error and the exact job remained queued
before the permitted dispatch. A separate fresh MCP process read back the exact
completed job **and receipt**; a separately authenticated wrong-token MCP process
was refused and did not expose the real token. This is actual MCP/core acceptance,
not a mocked tool response. It does not establish Hermes-native wiring.

Private evidence under the active project-bot scratch:
`stage4_mcp_core_evidence.json`, `stage4_mcp_core_accept.py` and
`stage4_mcp_readback_stderr.log`. The acceptance harness creates one job; do not
blindly rerun it. Existing exact job and receipt may be read without new dispatch.

Five new tests followed observed RED→GREEN slices. Tests use actual MCP stdio
initialize/list/call over a local fixture HTTP server plus in-process SDK contract
checks for job confirmation/receipt, job creation/assignment, fixed VM actions,
operation IDs and inventories. VM actions in those tests are **fake transport**,
not hardware lifecycle evidence. Full discovery: **91 tests, 90 passed, 1 optional
libvirt-schema skip**. Existing Node syntax/dashboard confirmation contracts and
`git diff --check` passed. No commit/push.

## Launch contract for parent/operator (not configured here)

Using an interpreter with `requirements-mcp.txt` installed in its own reviewed
venv, launch from the checkout (or supply its package on PYTHONPATH):

```sh
python -m project_bots.mcp_server \
  --endpoint http://127.0.0.1:8033 \
  --token-env PROJECT_BOTS_PLATFORM_TOKEN
```

Provide `PROJECT_BOTS_PLATFORM_TOKEN` through a private parent environment or
trusted private launcher; never put its value in chat, arguments, Git or tool
schemas. Optional trusted CA file reference is `PROJECT_BOTS_PLATFORM_CA_FILE`.
The current active profile's credential file is `private/stage3-platform.env`;
read it privately and map its stored value to the selected token reference.
Hermes filters stdio child environments; explicitly configure the narrowly needed
credential mechanism through its supported connection tooling, not raw YAML edits.

Official Hermes native-MCP docs were retrieved before planning wiring:
https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp .
They describe native stdio discovery, filtered child environments and connection
management. **No Hermes config, MCP connection, plugin or service was changed.**
Parent owns supported connection management and any user approval UI. Official SDK
reference: https://py.sdk.modelcontextprotocol.io/v2/ .

## Pause/checkpoint and exact next work

The user asked to work until 10% subscription remains, then pause until reset.
No reliable live provider quota/reset metadata is exposed to this child. No
percentage or reset time is inferred. Work is checkpointed promptly at this real
core gate; no blind scheduled resume or tight quota polling is installed.

Stage 4 is **partial**. After an explicit continuation/parent decision:

1. Review this dirty tree and remaining transport/error/input validation coverage;
   run `python3 -m unittest discover -s tests -q` with the pinned optional SDK.
2. Exercise `create_vm`, exact operation inspection, start, graceful shutdown,
   offline snapshot create/restore and delete through actual MCP against **one
   new managed disposable only** under the existing bounded Stage 4 authorization.
   No such disposable was created by this checkpoint. Retain every operation UUID,
   stop on uncertain outcome, and never stop/delete the four worker VMs. Read back
   empty disposable intent/domain/disk plus the unchanged four workers.
3. Parent wires this reviewed server into the active project-bot Hermes profile
   through supported native connection management, with private credentials and
   actual permission semantics; prove native discovered tools and a bounded real
   call. Do not hand-edit profile YAML or claim SDK testing proves Hermes wiring.
4. Close Stage 4 only after those gates. Stage 5/autonomous execution, additional
   model installation, broad root endpoints and unrelated changes remain stopped.

All four workers, current models and enabled inference/platform/tunnel services
are preserved. No root mechanism is deployed for future jobs. The future browser
bootstrap boundary is documented as explicit trusted-operator hash-pinned guest
packaging, not a client-requested package or command feature.
