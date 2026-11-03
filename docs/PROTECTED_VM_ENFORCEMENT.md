# Protected VM enforcement — source increment, NOT accepted deployment

## Current outcome

Parent post-fix combined run: **227 tests, OK, 2 privileged skips** with real XML schema validation enabled (`protected-parent-postfix.log` in profile scratch). Critical force-stop/network-block now attempt the validated fixed cgroup kill before libvirt observation; a later reconciliation failure remains unknown. Final scoped independent source-publication re-review **passed** (`deleg_54a86c27`), including all 18 focused tests. This is source/fixture/XML verification only, not privileged VM/BPF/packet acceptance.

**The requested whole core gate is NOT COMPLETE.** This tree adds an executable,
opt-in system-libvirt authority and kernel cgroup packet-policy adapter, fixed
protected XML, offline review-artifact generation, and a real-lab **paused QEMU**
acceptance program. It does not invent external monitoring or enable guest
execution when that monitoring is absent. Production `start`/`resume` therefore
fail closed. There is no privileged or real nested-VM execution evidence yet.
The BPF source has not even been compiled/loaded in this environment: clang,
libbpf development headers and virsh are absent. Unit contracts are not evidence
that the verifier, libvirt, QEMU or AppArmor accepted this deployment.

The original five-stage roadmap, llama.cpp/RX6800 provider, original stopped VMs,
legacy session backend and all unrelated clients/inference features are unchanged.
No host policy, system service, package, VM, Git branch or GitHub state was changed.

## Why a separate system-libvirt backend

Session-libvirt and the worker-owning Machine Manager share authority. A worker
with that UID can bypass application fences and alter launch XML/files. Relabeling
a Popen/netns fixture as a VM does not fix that. This mode requires administrator-
provisioned **system libvirt**, root-owned launch/configuration and a unique,
non-login host UID/GID per protected VM. Workers and the non-root compute API must
not be libvirt-group members, possess libvirt credentials, own the QEMU UID, or
write cgroups, configuration, disks of other VMs, source or the helper service.
Nothing migrates existing definitions or grants a blanket sudo/capability endpoint.

The HTTP boundary selects `ProtectedClient` only through administrator-local
`machine_http.serve(..., protected=True)`. The normal CLI/default call remains
session-libvirt and explicitly has no installed VM network guard. Missing root
socket never falls back to session mode. No CLI migration switch was added.

## Implemented control/data boundaries

* `project_bots/protected_compute.py`: canonical exact UUID/static-owner bindings;
  no caller XML, path, shell, PID, executable or arbitrary root-command action.
  Root source validation checks every ownership/permission/symlink ancestor.
* `scripts/protected_authority_entry.py`: Python `-I`, fixed installed path,
  validates the complete root source tree **before importing project code**.
  Never point this at a checkout or load modules from a worker-writable venv.
* Root Unix service authenticates the exact compute UID with Linux SO_PEERCRED.
  Its root-owned directory prevents socket substitution; the client also verifies
  the server is root. Bounded JSON has a fixed method/arity allowlist. No worker
  health, recovery/unlatch, create/delete, arbitrary method or raw libvirt route.
  Existing authenticated Machine Manager HTTP handlers can use this interface.
* Root configuration fixes owner, VM UUID, dedicated UID/GID and a single broker
  IPv4/TCP port. Every mutation persists operation/owner/target/action intent before
  transport. Cross-process flock serializes operations; SQLite FULL synchronous
  commits preserve pending/unknown outcomes. Critical stop/network-block commit a
  root fence first, even when subsequent observation fails. No online recovery.
* Exact inactive XML bytes must match an administrator-pinned SHA256, plus semantic
  UUID/owner/partition/DAC/backend/device validation. Fixed generated XML has one
  in-process QEMU `user` interface: **no passt/external slirp, bridge, TAP, port
  forward, graphics listener, shared filesystem, hostdev, vsock or caller args**.
  System-libvirt retains QEMU/KVM; only the nested fixture may use `type=qemu` TCG.
  Trusted management uses libvirt's Unix control socket/root serial log, not guest
  routable management/admin endpoints.
* Dedicated top-level `pb<UUID-without-hyphens>.slice`, not the libvirt daemon's or
  management's cgroup. Root-only, Delegate=no, 768 MiB tree cap, 100% one-CPU quota,
  128 tasks. Fixed guest budget is **512 MiB / one vCPU**, <=2 GiB standalone disk.
* `network_source()` generates a map-free, immutable-to-agent cgroup_skb ingress
  and egress BPF program. It denies IPv6, UDP/ICMP/other protocols, fragments and
  IPv4 options; IPv4 TCP is permitted only toward the exact approved broker
  address/port, with reverse source tuple on ingress. No DNS, peer, host/admin or
  raw inference exception exists. Broker application authentication remains
  mandatory: this is a layer-3/4 allowlist, not message authorization or telemetry.
* Both programs attach `multi` to the **parent slice before QEMU creation**;
  inheritance covers libvirt's nested emulator cgroup and forked descendants.
  No host firewall/sysctl changes or agent network authority. External network
  backends are prohibited rather than assumed to share QEMU's process cgroup.
  QEMU must have no effective caps, NoNewPrivs, seccomp mode 2 and the exact
  enforcing dynamic libvirt AppArmor profile; otherwise even paused binding fails.
  This is important for AF_PACKET/raw-socket bypasses that cgroup_skb alone cannot
  be assumed to cover. No capability/sandbox exception is provided.
* `KernelBoundary.inspect()` queries **effective** kernel attachments and matches
  program IDs to root-only pinned programs and reviewed immutable tags. A label,
  optional monitor callback or supplied boolean cannot stand in for those checks.
  `members()` independently checks exact QEMU executable/UUID, UID/GID, process
  sandbox/profile, no unexpected helper process and no reserved-UID process outside
  the boundary. Unsupported layouts fail closed, not accepted by name alone.
* Offline `prepare_paused()` commits a permanent one-use fence/intent, starts
  libvirt with `--paused`, then checks emulator membership and kernel policy again.
  It **never resumes a guest**, is not exposed on the root socket, and retains the
  fence even on success. On uncertain launch/binding, kill the fenced subtree.
* `force-stop` and (conservatively) `network-block` use **cgroup.kill on the whole
  fixed tree**, verify populated=0, reconcile exact libvirt state, and preserve
  definitions/disks/logs/operations. There is no leader-PID kill claim. A fresh
  domain readback avoids redundant `destroy` after cgroup kill already stopped it.
  Network-block currently terminates the VM, not an independently live deny-all
  mode. Missing BPF readback must not prevent critical tree termination.

## Review/setup artifact (not deployed)

Generate locally as an ordinary user; example addresses are documentation-only,
not a ready broker endpoint:

```sh
# binding JSON has EXACTLY these keys; write it in private scratch first:
# {"vm_id":"a3ec8c2c-a7a0-4164-a357-f006175d189e",
#  "owner":"fd698b30-a01a-4ebc-a4bc-a8ddc01bf9c6",
#  "uid":62001,"gid":62001,"broker_ipv4":"192.0.2.10","broker_port":21435}
PYTHONPATH=. python scripts/prepare_protected_vm.py \
  --binding /PRIVATE_SCRATCH/binding.json --output /PRIVATE_SCRATCH/review-artifacts
```

This produces `binding.json`, `guard.c`, `domain.xml`, a bounded slice unit,
`project-bots-protected.service` and **INSTALL-REVIEW.txt** with exact compile,
load/attach, ownership, libvirt define/hash and source installation steps. It does
not install anything, contact a network, enable units or run privileged commands.
Install both standalone entry/harness scripts under the reviewed root snapshot,
as well as the complete reviewed Python package. No symlink into this checkout.
The generated service is a review candidate, not independently security-reviewed
or operationally accepted. Keep system libvirt/AppArmor/seccomp enforcing.

**Input trust remains a blocker**, not a made-up hash. Before installing anything,
parent/admin must retain signed Ubuntu InRelease/Packages validation and lock exact
versions plus package SHA256 for the named QEMU/libvirt/libslirp/AppArmor/compiler/
libbpf/bpftool/Python inputs. The fixture disk must have a fixed SHA256 validated
against an Ubuntu-signed SHA256SUMS using the installed Ubuntu keyring. Pin a
specific dated image, not a mutable `current` URL alone. No input lock/image or
package installation was produced/performed in this increment. Package simulation
must reject unapproved upgrades/removals. If any requirement needs a host policy
exception or a new outer VM, **stop**: neither is authorized.

## Exact bounded real-lab program

Only after parent code review, signed-input lock, approved administrator staging,
and explicitly approving this nested UUID, inside existing outer lab
`2f3ce848-c083-4674-8659-e2d9f0d37638` (1 vCPU / 2 GiB / 24 GiB):

```sh
/usr/bin/python3 -I /opt/project-bots-protected/accept_protected_vm.py \
  --confirm 'PAUSED NESTED VM ONLY a3ec8c2c-a7a0-4164-a357-f006175d189e IN LAB 2f3ce848-c083-4674-8659-e2d9f0d37638'
```

The harness checks root, fixed root-owned source location and the outer lab DMI
UUID; refuses extra bindings; verifies preexisting effective BPF, starts only its
fixed nested fixture **paused**, checks real process/cgroup/AppArmor/network
readbacks, force-stops in finally, reconstructs authority and verifies durable
start refusal. Root-only JSON evidence is retained under protected state; definitions,
disks and logs survive. It never resumes vCPUs, deletes evidence, clears fences,
acts on original domains or creates another outer VM. Review failures remain
failures. The harness is **NOT RUN**, and may uncover unsupported libvirt/LSM/BPF
behavior. Its outcome cannot prove actual denied packets or malicious guest probes.

## Remaining mandatory work / precise stop point

1. Independently review all new root code, service and generated artifacts before
   any privilege. Resolve actual package/input lock, root system-libvirt identity,
   libslirp availability, cgroup resource-partition inheritance, BPF verifier/load,
   pinned-tag layout and enforcing LSM/sandbox readback inside the approved lab.
2. This adapter cannot honestly resume a protected guest yet: **independently
   protected runtime, identity/control, audit and monitor-of-monitor coverage is
   absent**. No root healthy-file/callback/HTTP assertion was substituted. Production
   `start`/`resume` deliberately return ConflictError. A paused QEMU is a real
   hypervisor setup test but not a working agent or completed launch gate.
3. Implement the actual protected coverage/readback contract and monitored release
   of paused vCPUs. A new online "monitor healthy" assertion is not the fix. Extend
   operation/reconciliation tests before allowing resume; preserve durable fences.
   The existing namespace monitor also expects `blocked: true` (deny-all), not an
   active broker-only policy. This adapter deliberately returns `blocked: false`
   while broker-only enforcement is active. Do not point that reconciler at a
   future running protected VM until its policy-aware telemetry/readback contract
   is implemented; it would correctly regard the current result as insufficient.
4. Run an actual bounded guest attempted-traffic matrix with independent positive
   broker control and negative IPv4/IPv6, peer/admin/raw-inference, listener/raw
   socket/alternate-backend attempts; observe packet effects externally. Add
   independently retained counters/events, active loss containment and timing
   evidence. Current program has no packet-denial telemetry/counters. Programs
   persisting after helper death is not an independently verified watchdog.
5. Exercise real complete-tree stop, source/config access denial from the reserved
   identities, unauthorized root socket/libvirt access, daemon restart/races and
   manager loss. Then separately implement/accept recovery, credential rotation,
   protected external evidence and **every S01–S15 chain**. None passes here.

## Verification scope

Baseline: `python -m unittest discover -s tests -q`: **209 tests, OK, 3 skips**.
New focused checks use actual SQLite persistence, actual unprivileged Unix peer
credentials and trusted-path refusal, generated artifacts/XML, plus explicitly
mocked privileged libvirt/kernel transport. New XML also passes real libxml2
RelaxNG validation against retained installed-libvirt sibling schemas, both KVM
and software-emulated shapes. No fake transport output is VM/kernel effect proof.
The earlier combined run with `PROJECT_BOTS_DOMAIN_RNG` pointing to the retained
`stage2-clean-libvirt-schemas/domain.rng` reported **224 tests, OK, 2 privileged
skips**, 86.066 seconds, zero warning lines. Log:
`/home/server1/.hermes/profiles/project-bot/cache/scratch/protected-vm-full-suite-final.log`.
That run and its **15 passing focused tests predate critical-stop fix cycle 1**;
these results do not establish acceptance of the changed tree.

Fix cycle 1 removes libvirt/XML observation as a prerequisite for critical kill:
after committing intent/fence, validate the fixed root-owned cgroup path and
attempt whole-subtree kill, then reconcile libvirt and read back effects. Later
observation failure preserves an `unknown` operation, not a successful stop claim.
New unprivileged tests cover both critical actions, committed intent/fence before
kill, trusted fixed-target validation before kill, and rejection of unregistered,
noncanonical, wrong-confirmation or caller-selected path/PID targets. The ordering
regression was observed RED before the source change and GREEN afterwards.

Post-fix focused command:
```sh
PROJECT_BOTS_DOMAIN_RNG=/home/server1/.hermes/profiles/project-bot/cache/scratch/project-bots-libvirt-schemas/domain.rng \
  python3 -m unittest discover -s tests -p 'test_protected*.py' -v
```
Result: **18 tests, all passed**, 0.574 seconds (the original 15 plus 3 new test
methods). Compilation of the changed source/test and whitespace checks passed.
These counts are separate runs, not additive unique-test totals. No privileged
kernel/VM acceptance was run; fresh independent review and parent combined-tree
verification remain required. No commit/push.
