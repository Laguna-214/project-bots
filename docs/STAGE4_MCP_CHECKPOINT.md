# Stage 4 MCP checkpoint — corrected, partial acceptance

This correction supersedes unsupported claims introduced in `91f08b0` and the
completion subject of `3091edd`. It is **not full Stage 4 or Stage 5 acceptance**.
The five-stage product roadmap is now [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md);
MCP is one optional integration within User Control & Collaboration, not Stage 5.

## Recovered evidence from `2251905`

The full prior checkpoint remains retrievable without a blind revert:
`git show 2251905:docs/STAGE4_MCP_CHECKPOINT.md`. It was inspected for this correction.
The following retains its useful distinctions and identifiers; these are historical
recorded observations, not freshly replayed acceptance.

- Official Python MCP SDK 2.3.0 stdio server exposed 21 narrow typed tools.
  Initialize/list/call negotiated protocol 2025-11-25. Authenticated platform
  calls, not initialization alone, established the historical API path.
- Actual read-tool job `edae31ba-0bdc-419a-9653-be4a5a818032`, response
  `resp_f793776d-2d74-41eb-8d3d-bb7c5cf67373`, Researcher VM
  `55545d36-bd05-4e48-9eb4-cea5fbe8c8f4`: retained OpenClaw read trajectory and
  exact job/receipt readback were recorded. Wrong-token and wrong-confirmation
  refusal were separately recorded. This does not establish Hermes-native wiring.
- Queued-only job `5e21722b-825e-4572-aa67-3f576a455d7e` was canceled and read back
  canceled with `{"execution": null}`. Cancellation was not remote inference stop.
- Historical machine `e0778e6a-8b1c-484d-8372-0cf60a780b30` reported 62967 MiB
  physical RAM. Application admission allowed 8 vCPU / 32768 MiB; four existing
  reservations totaled 7 vCPU / 32768 MiB / 128 GiB disk. Even a 2048-MiB
  disposable exceeded that policy. At that checkpoint **no disposable create or
  lifecycle mutation was submitted**, no VM/operation ID allocated, no worker
  resized/stopped, and no policy broadened.
- Token-file loading required a caller-owned regular 0600 file through a no-follow
  descriptor. Credentials remained private, not literal MCP tool arguments.
- Historical tests: 96 discovered, 95 passed, one optional schema skip. Fake
  lifecycle transport tests were explicitly not real VM lifecycle evidence.

Historical private receipts were named `stage4_mcp_core_evidence.json` and
`stage4_mcp_bounded_evidence.json` under the active profile's scratch. Their
continued existence/integrity was not checked here. Do not blindly rerun one-shot
mutation scripts. Recover exact IDs before any separately authorized continuation.

## Corrected boundaries

`ComputeService.capacity()` implements the default **32768-MiB application RAM
admission cap**, configurable through `PROJECT_BOTS_COMPUTE_RAM_CAP` and bounded
by host total minus reserve. It is **not** proof of an AppArmor physical limit.
The prior claims of both successful disposable lifecycle and an impassable
AppArmor limit were contradictory and unsupported; neither is accepted here.
Unit tests of a configurable cap do not prove host enforcement or lifecycle.

Fresh read-only inspection on 2026-11-02 found four registered workers, all four
original domains shut off, and additional stopped domain
`80578231-c09e-4624-ab45-cbf676df91d0`. Its ownership/history/lifecycle outcome is
unverified. Do not delete/adopt/start it from this observation. No domains were
changed during this product increment. Registry `verified` is stale historical
registration evidence, not current running/protected state.

Hermes-native discovered tools, authenticated bounded native call and actual
permission handling remain **unverified**. MCP initialize alone proves none of
these. Hermes configuration was not inspected or modified for this task.
The backend remains independent of Hermes. Full collaboration, approvals,
independent monitoring/containment and emergency controls remain open gates.
