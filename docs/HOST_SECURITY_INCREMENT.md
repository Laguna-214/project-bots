# Host-security increment — 2026-11-03

## Latest administrator-lab update

The separately authorized disposable lab now passed all **5 NamespaceTests**,
including the two formerly skipped real nftables/rule-loss cases. Kernel readback,
actual reblocking and pidfd termination of an owned subprocess were exercised.
The fixture Machine Manager's VM-named action label is **not real VM termination**.
Production VM isolation/monitor/watchdog gates remain unaccepted. The old combined
schema failures below are historical; latest parent suite is **209 tests, OK with
3 default skips**, with XML and privileged cases separately exercised successfully.
Only the approved CPU-cap adjustment and new lab setup changed deployment state;
no original VM or host security policy was changed. Full evidence and limitations:
[resumed checkpoint](RESUME_CHECKPOINT_2026-11-03.md).

## Original checkpoint acceptance boundary

**Source hardening delivered; real VM security acceptance remains BLOCKED.** No
checkout code was deployed, no services were restarted, no host firewall/security
policy was changed, and no original or unknown VM was mutated. This document does
not change the five-stage product requirements or pass any of S01–S15 in
`SECURITY_ACCEPTANCE.md`.

## Implemented and reviewed

- Owner/UUID/name/storage-validated `force-stop` uses fixed session-libvirt
  `destroy UUID`, not shell/PID input. Definitions, disks and evidence survive.
  Critical incidents choose this path without waiting for graceful shutdown.
- Host containment is persisted **before** force-stop/network-block. Start,
  restart, resume, deletion, resource changes and snapshot mutations are denied
  while latched, including after Machine Manager reconstruction. Unknown external
  outcomes and original operation IDs remain retained; observing a stopped VM is
  not permission to restart it. No HTTP unlatch exists. Offline administrator
  reconciliation is required; backend incident recovery alone cannot clear this
  host latch. Direct same-UID `virsh` access is NOT fenced by this application latch.
- The trusted containment client exposes only fixed readback, shutdown,
  force-stop and network-block routes. There is no worker heartbeat, arbitrary
  command, PID registration, or administrator-supplied "healthy" HTTP route.
- `NamespaceFirewall` pins a non-host namespace descriptor. Atomic nftables inet
  default-drop input/output/forward rules cover IPv4/IPv6, including loopback;
  kernel JSON rule/counter readback, not submitted flags, determines its result.
  Rules persist without the reconciler. No allow/delete/unblock API is supplied.
- `BoundNamespaceRuntime` is a **single disposable subprocess binding**, not a VM
  or process-tree launcher. `OwnedProcess` uses the launcher's Popen handle,
  pidfd SIGKILL and waitpid. It does not terminate descendants, enforce cgroups,
  or prove hostile workload containment. ComputeService now rejects subprocess
  bindings or mismatched targets presented as VM network proof. An eventual VM
  adapter must return its exact `vm_id` and `runtime_kind: libvirt-vm` *after*
  independently proving complete emulator/network-backend membership; those
  labels alone are not evidence and there is no API for supplying them.
- Opt-in host polling detects missing rules, unavailable transport, wrong target,
  missing binding, invalid packet counters, counter regression and namespace
  replacement. Missing/unverifiable network enforcement is critical, rather than
  silently degrading into graceful-only monitor-loss handling. Increasing
  default-deny counters produces a deterministic high incident with retained
  counter evidence; cursors survive reconciler reconstruction. This detects
  denied traffic counts, **not packet attribution, payloads or the complete
  network behavior matrix**. Counter resets/boundary retirement need explicit
  offline reconciliation; they are never auto-accepted as a new healthy baseline.
- Containment intent, target and stable operation ID are committed before network
  or stop transport. Timeouts retain `requested_unverified`. Acknowledgment is
  labeled `acknowledged_not_effect_proof`; separate target/state readbacks decide
  action verification. Action history is preserved and outcome remains partial.
  Already-stopped critical targets still receive the idempotent host latch call.
- Enforcer health is unavailable while reconciliation is in progress and refreshed
  only after successful completion. A failed iteration cannot refresh health.
  No runtime/identity/audit health adapters are fabricated by the network monitor.

## Problems found in the interrupted increment

1. Direct Machine Manager start could restart a successfully force-stopped owned
   VM after backend containment; fixed with a durable host-side latch and tests.
2. Network transport/binding loss could avoid the critical monitor response;
   fixed with deterministic critical containment and retry/readback tests.
3. Dropped-packet counters were returned but ignored by detection; fixed with
   persistent counter correlation (still not full packet/event telemetry).
4. A timed-out action lost platform-side operation correlation; fixed by committing
   intent before transport and preserving unknown/acknowledged distinctions.
5. A subprocess network binding could be relabeled as VM proof by ComputeService;
   fixed by rejecting incompatible/mismatched adapter results.
6. Enforcer health was refreshed before a failing reconciliation; fixed.
7. The opt-in nested-namespace integration test deleted a table in the wrong
   (management) namespace and deliberately faked block failure. It now targets the
   pinned child namespace and exercises actual reblocking before pidfd termination.
   **The corrected privileged tests have not been executed here.**

## Real read-only host observations

SSH used the existing pinned key, BatchMode, IdentitiesOnly and strict host-key
checking, as `pbcompute@10.0.50.56`; no sudo/password attempts were made.

| Item | Management execution environment | Compute host |
|---|---|---|
| Identity | server1 UID/GID 1000 | pbcompute UID/GID 1001; groups users/render/kvm |
| Effective/ambient capabilities | no effective SYS_ADMIN/NET_ADMIN/SETUID/SETGID; ambient empty | effective and ambient empty |
| `unshare --net true` | Operation not permitted | Operation not permitted |
| `unshare --user --map-root-user --net true` | uid_map write: Operation not permitted | uid_map write: Operation not permitted |
| cgroup v2 root | not writable | not writable |
| Current cgroup | user-1000 user service, hermes-gateway.service | user-1001 session scope |
| Tools | nft/ip/unshare/nsenter installed; virsh not found in PATH | nft/ip/unshare/nsenter/virsh/bpftool installed; auditctl/ausearch not found |

Compute readback additionally showed `kernel.unprivileged_userns_clone=1` and
`kernel.apparmor_restrict_unprivileged_userns=1`. No sysctl/AppArmor exception,
security disabling, alternate user, or privileged group shortcut was attempted.
A permissive capability **bounding set is not effective capability permission**.
No delegated cgroup subtree was supplied; root not writable alone is not a claim
that an administrator could never delegate a dedicated subtree.

All five observed persistent domains remain **shut off**, autostart disabled,
managed-save absent; `dominfo` reports `Security model: none`:

- `4accba4d-24c9-4942-aec9-fd54de816319`
- `4c827ae7-02ab-40f8-8cc9-3af9c6340526`
- `55545d36-bd05-4e48-9eb4-cea5fbe8c8f4`
- `b4974b11-1c8a-409a-9f04-6401b9407ff1`
- **Unknown, preserve:** `80578231-c09e-4624-ab45-cbf676df91d0`

These observations do not prove AppArmor confinement, distinct VM host identities,
current guest protection, a watchdog, or network isolation. Existing passt
networking runs under session libvirt; there is **no installed VM netns adapter**.
The production Machine Manager constructor installs no network guard and therefore
returns unavailable. A binding for a subprocess UUID does not fix passt/QEMU.

## Verified tests and explicit skips

Baseline actually executed: `python -m unittest discover -s tests -v`, **181
 discovered, 178 passed, 3 skipped**, no failures. Baseline log:
`/home/server1/.hermes/profiles/project-bot/cache/scratch/host-security-baseline.log`.
The exact original skips were:

1. `test_domain_schema.DomainSchemaTests.test_generated_domain_validates_against_libvirt_schema`
   — optional libvirt schema path not supplied.
2. `test_host_security.NamespaceTests.test_real_default_deny_packet_counters_and_tamper_detection`
   — requires explicitly isolated root network namespace.
3. `test_host_security.NamespaceTests.test_real_independent_monitor_contains_after_kernel_rule_loss`
   — same isolated-root prerequisite.

The first skip was safely resolved: `/usr/share/libvirt/schemas` was copied
read-only from the compute host into profile scratch, then the generated XML
passed actual libxml2 Relax NG validation using `PROJECT_BOTS_DOMAIN_RNG`. This
is schema validation, **not VM boot or enforcement acceptance**.

The normal suite executes a real owned child that ignores SIGTERM, then proves
pidfd SIGKILL/waitpid termination with return code **-9**, idempotent readback and
retained evidence. The independent reconciler/HTTP test also terminates a real
owned child across reconciler restart, but uses a fixture Machine Manager and
SQLite authority. These are real process/API tests, **not hostile VM/network,
protected-watchdog or tamper-resistant-audit acceptance**.

Final focused run: **63 discovered, 61 passed, 2 privileged skips**, no failures
or warning lines. Log:
`/home/server1/.hermes/profiles/project-bot/cache/scratch/host-targeted-complete.log`.
This included host/security/Machine Manager/enforcer/HTTP tests and parent-owned
telemetry tests. `ComputeService.health()['utilization']` now integrates the
parent's read-only sensors without populating any security heartbeat.

Final concurrently edited combined tree: **206 discovered, 201 passed, 1 failure,
2 errors, 2 privileged skips**. Log:
`/home/server1/.hermes/profiles/project-bot/cache/scratch/host-security-combined-final.log`.
These failures are in the concurrently added approval/schema migration work,
outside this increment's file ownership: `permissions.migrate()` attempts to
recreate existing `integration_principals` in the v3/chat and stage-one migration
fixtures; the platform persistence test still expects schema version 5 rather
than the new version 6. The parent/approval owner must reconcile them before
claiming a passing whole tree. The earlier combined run also saw the approval
HTTP replay test fail (400 vs 403), which no longer failed in the final run.
`git diff --check` passed. New regression tests were exercised red before their
fixes; the same-UID/nondumpable child rejection is additional existing-boundary
coverage, not a newly demonstrated identity vulnerability.

## Opt-in administrator setup artifact — disposable acceptance only

This is a **reviewable setup recipe, not authorization or an installed service**.
Do not grant `pbcompute`, agents or the management process blanket sudo,
CAP_SYS_ADMIN, host nftables authority, cgroup-root write access or a shell
endpoint. Do not relax AppArmor/userns sysctls. Human administrator `projectbots`
must perform separately approved work locally; no password is supplied to agents.

First request approval for a **new dedicated disposable Linux lab**, preserving
all five domains above and existing llama.cpp/RX6800 Vulkan services. Use a
reviewed, root-owned source snapshot in that disposable lab; never run privileged
code from an unreviewed user-writable checkout. The packet test needs root in a
fresh network namespace with setns/unshare/netfilter capability. The nested-child
case additionally needs narrowly scoped UID/GID dropping, namespace observation
of that separate UID and pidfd signaling (SYS_ADMIN, NET_ADMIN, SETUID, SETGID,
SYS_PTRACE/KILL as required by that lab's kernel/LSM); no host firewall rule edits.
Have the administrator confirm namespace and LSM permissions without weakening
the existing host. Example invocation **inside that approved disposable lab**, from
its reviewed source root, with a private administrator-created scratch directory:

```sh
# Preconditions: administrator shell in dedicated lab, trusted source, private TMPDIR.
# unshare creates the throwaway boundary before any test can alter nftables.
PB_DISPOSABLE_NETNS_TEST=1 PYTHONPATH=tests:. \
  unshare --net -- python3 -m unittest test_host_security.NamespaceTests -v
```

`PB_DISPOSABLE_NETNS_TEST=1` alone is NOT isolation; never set it in the existing
host namespace. The tests assert non-host namespace identity and refuse PID 1's
network namespace. Rules apply only to disposable namespaces; their retirement
is rollback. Retain `REAL_NETNS_EVIDENCE` and
`REAL_INDEPENDENT_MONITOR_EVIDENCE`, exact lab identity, source snapshot hash and
privilege profile. This can accept packet/owned-process primitives only, not any
VM or S01–S15 chain. The recipe has not run with privileged prerequisites here.

## Precise remaining approvals and implementation prerequisites

1. Approve/provide the disposable lab and administrator-scoped namespace test above;
   no existing VM is an acceptable default target. Supply an explicit disposable VM
   UUID/owner/resource budget before any create/start/destroy lifecycle testing.
2. Implement/review a trusted **VM launcher + kernel-backed VM network adapter**
   that proves QEMU and every passt/network backend are in the intended boundary
   before guest execution, survives child forking and manager death, keeps trusted
   management reachable, and exposes only authenticated exact-UUID actions.
   Do not make this a root command/PID service. Default-deny-all primitives do not
   yet supply the approved broker-only collaboration policy or anti-bypass tests.
3. Administrator provision distinct protected identities, root-owned immutable-to-
   agent launch configuration, a delegated dedicated cgroup subtree (pids/memory/
   CPU plus complete runtime-tree kill/readback), LSM policy and hypervisor fencing.
   Same-UID session-libvirt APIs and a process-leader pidfd are insufficient.
4. Supply independently protected runtime exec/filesystem/privilege/escape/resource
   telemetry, identity/control-plane denial telemetry, external append-only audit
   storage and integrity/access verification, and a monitor-of-monitor watchdog.
   Current SQLite/UID authority is shared with the trusted backend and is not
   tamper-resistant. All five coverage categories must be fresh and independently
   verifiable; no observe-call fixtures or administrator health assertions.
5. Define/review offline host-latch/counter-boundary reconciliation and explicit
   authorized recovery, protected evidence retention, credential rotation and
   no-restart behavior. No generic online host unlatch was invented in this increment.
6. Execute **every S01–S15 chain** in that authorized lab with real attempted denial,
   external detection, incident, network containment, correct runtime/VM fencing,
   preserved inaccessible-to-agent evidence, and restart/recovery controls.
   All fifteen remain BLOCKED/UNVERIFIED, not partially passed by fixture counts.

Do not enable `project_bots.security --host-monitor` against the current live
registry as a health probe: unavailable adapters intentionally create critical
incidents and can force-stop owned workers. Activation, deployment, VM lifecycle,
policy installation and services require separately scoped approval.
