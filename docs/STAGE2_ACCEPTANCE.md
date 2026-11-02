# Stage 2 compute deployment evidence — 2026-11-02

## Final clean-boot acceptance: PASS — ready for parent review/Stage 2 closure

The final clean-boot gate is resolved in **new guests** by fixed, source-owned cloud-init provisioning. Combined with the retained full lifecycle/resource/snapshot evidence below, Stage 2's authorized runtime acceptance is complete. No Stage 3 implementation or deployment occurred. This verifies the locked key-only guest and graphical **greeter**, not a password-enabled bot desktop session.

### Root cause and narrow fix

Retained `stage2-repaired-network.log` showed ens3 connected through NetworkManager (`netplan-ens3`) but unmanaged by networkd, while the enabled `systemd-networkd-wait-online.service` failed. Its documented default timeout is 120 seconds; this was a stale renderer-specific dependency, not failed guest networking. The retained cloud configuration confirms package installation precedes `scripts_user` in cloud-final.

A regression test first failed because generated `runcmd` was missing, then passed with exactly these fixed argument lists after Desktop package installation:

```text
systemctl enable --now NetworkManager.service
systemctl disable --now systemd-networkd-wait-online.service
systemctl reset-failed systemd-networkd-wait-online.service
```

Only the obsolete renderer's wait is disabled/reset. NetworkManager's own wait-online remains enabled (180 ms observed); networkd itself and all security services/policies remain untouched. No blanket reset-failed, timeout reduction, arbitrary caller command/YAML, guest sudo, host root/package/AppArmor change or bot privilege/password change. This is a **new-instance seed fix**, not a retrofit of existing guests. References: [cloud-init runcmd](https://docs.cloud-init.io/en/latest/reference/modules.html#runcmd), [upstream list-command/final-stage semantics](https://github.com/canonical/cloud-init/blob/main/doc/module-docs/cc_runcmd/data.yaml), [networkd wait-online semantics/default timeout](https://www.freedesktop.org/software/systemd/man/latest/systemd-networkd-wait-online.service.html), [systemctl](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html).

### One new real disposable guest, entirely through the platform adapter

Existing machine registry `e0778e6a-8b1c-484d-8372-0cf60a780b30` was reused; initial managed/libvirt lists were empty. Intent was fsynced before each mutation; platform operation and fresh detail were read back. No direct-compute create/action bypass was used.

| Check | Exact evidence |
|---|---|
| Create / VM UUID | `ddeb8488-6c06-4e38-918c-e1f187415b6b`; 2 CPUs, 4096 MiB, 24 GiB; shut off |
| Start | `f5bb5731-dd76-489a-b781-9f2eb26a6c6f`; running |
| Initial cloud-init | done/extended done; `errors: []`, `recoverable_errors: {}`; system running, zero failed units; obsolete wait disabled |
| Initial-boot qualification | Desktop installation took 4 min 47.832 s total startup; display-manager was initially inactive and ens3 still used the server boot's networkd runtime. Installed Desktop becomes fully active on the explicitly tested reboot; no first-boot graphical readiness claim |
| Platform restart | `d1cc9655-4a11-4dc2-9a62-098e116dfccb`; boot ID `63a674ab-0350-4615-9ff5-45fbb228c0b8` → `dafa53b0-1578-4985-83f4-643a5b4879b0` |
| Clean reboot | SSH/readiness collected within **18.791 s of restart intent** (upper bound, not precise SSH-availability time); `systemd-analyze`: **2.142 s kernel + 2.774 s userspace = 4.916 s**, graphical.target 2.618 s userspace |
| System state | `running`; **0 failed units**; obsolete wait `disabled`, inactive, Result=success, start/exit monotonic timestamps 0 (not invoked this boot) |
| Network | NM ens3 connected `netplan-ens3`; IPv4 `10.0.50.56/24` via passt, gateway `10.0.50.1`, successful DNS; SSH key-only bot uid1000 with no extra groups |
| Desktop / agent | display-manager, NetworkManager and qemu-guest-agent active; fixed package versions as in prior run; GDM seat0/tty1, Xorg, gnome-shell; actual screenshot visually inspected: Ubuntu username greeter; guest-ping returned `{}` |
| Security / isolation | guest apparmor active; host passt/libvirtd `(enforce)`; SPICE 5900, guest SSH 22000 and compute 9443 loopback-only; no domain hostdev; host RX6800 remained amdgpu |
| Graceful shutdown | `8b941a08-fd85-45ff-bd80-ebb30ed785e3`; fresh detail polled to shut off |
| Delete | `3bb63c43-6bf8-4847-ad5b-f7b719079ce5`; succeeded operation and deleted tombstone read back |

At **2026-11-02T13:41:51Z**, final platform list `[]`, libvirt list empty, disposable directory absent, no compute QEMU/passt process or VM SSH/SPICE listener remained. Authenticated health stayed available (59011 MiB available, 852 GiB free). Compute service and management platform/tunnel units remain enabled/active. Private tokens/keys were never printed. Initial guest host-key enrollment used a dedicated known-hosts file over the already host-key-verified SSH tunnel (`accept-new` once); all subsequent guest SSH used StrictHostKeyChecking=yes.

### Deployed code and tests

Remote prior dirty guest-agent channel/test changes were inspected, backed up under private compute state `stage2-clean-prepatch/`, and preserved in the copied complete files. No Git reset/pull/commit/push. Compute user unit runs `/usr/bin/python3 -m project_bots.cli machine-service` from `/home/pbcompute/project-bots`; it was restarted **before create**, PID 53805, and the actual generated seed was read back with the fixed migration. Local/remote SHA-256 match: compute.py `992033fea6c9b8be16e2257843806eaa6584d2e6e2922b015665a04e503c5719`; test_machine.py `b16f518a986b70b0495df3b5db8c890108783ca0c64b02b54bb0bc6764669425`. These are checkout-backed deployed units, not a newly installed CLI distribution; no `project-bots` command was present on either service identity's PATH.

- Management full discovery: **45 pass, no skips** with the actual compute host's libvirt 12 sibling RNG schemas copied (host unchanged) to profile scratch `stage2-clean-libvirt-schemas/`. Default discovery without the opt-in schema environment passed 44 and skipped 1 (45 discovered).
- Compute full discovery with `PROJECT_BOTS_DOMAIN_RNG=/usr/share/libvirt/schemas/domain.rng`: **45 pass, no skips**, actual installed libvirt 12 schema. An initial no-env run passed 44 and skipped schema, then the explicit schema-enabled full run passed all 45.
- Management Node syntax and dashboard confirmation contract pass; remote JS/test hashes matched exactly. Compute has **no Node executable**; no remote Node execution or host package installation is claimed. An attempted remote Node command failed before service restart; restart was then explicitly executed and verified before provisioning.
- TDD RED log and full local logs: profile `cache/scratch/stage2-clean-{red,local-tests,local-tests-rng,baseline}.log`; remote full RNG log: compute private state `stage2-clean-tests-rng.log`.

Private durable evidence: profile `private/stage2-clean-evidence.jsonl`, `stage2-clean-{first-boot,desktop,host-running,deployment,final-host}.log`, `stage2-clean-post-reboot.json`, `stage2-clean-greeter.png`, persisted new create intent/VM ID/known-hosts. Scratch operational helpers `stage2_clean.py` and `stage2_clean_guest.py` are not shipped product features. A first host confinement read used `pgrep -x passt` and missed `passt.avx2`; the corrected /proc read in deployment evidence independently confirms both enforcing profiles.

Limits remain explicit: no logged-in bot graphical session, interactive SPICE/performance benchmark, snapshot application-data roundtrip, crash-injection/ownership-tampering hardware rerun, browser pairing/UI visual review or production-platform migration. The earlier real offline resources/snapshot and negative-operation evidence below is retained rather than reasserted as repeated on this one-gate guest. Parent review/publication and Stage 3 are separate next steps.

## Prior run: real guest and management integration acceptance after administrator repair

**Requested runtime gates PASS; one guest clean-boot caveat remains OPEN.** DHCP, key-only guest SSH, successful cloud-init, Ubuntu Desktop packages, active display-manager/guest agent, visually observed graphical greeter, reboot boot-ID change, pause/resume, graceful shutdown/re-start, offline resources/snapshot restore and deletion all succeeded on the real host. Authenticated platform-to-compute integration is demonstrated and remains available. Do not read this as a completely clean guest boot: `systemd-networkd-wait-online.service` fails after Desktop switches networking to NetworkManager, adding approximately 120 seconds and leaving system state `degraded`. No fix or privileged guest command was applied. A logged-in graphical user session is not claimed: `bot` has a locked password, no sudo group and key-only SSH; GDM's greeter session is not a bot desktop session. No Stage 3 acceptance.

### Repair and hardware evidence

The administrator independently applied the approved repair (backup `/root/project-bots-apparmor-tzu5_ng3`). This run read back `profile passt /usr/bin/passt{,.avx2} flags=(attach_disconnected)`, exact-peer `signal (receive) set=(term) peer=libvirtd,` and local libvirtd `signal (send) set=(term) peer=passt,`. Running passt PID 51121 and libvirtd both reported `(enforce)`. No host root/package/policy change, security bypass or sudo execution was used. A guest `sudo -n -l` capability query was denied (password required); no elevated guest command ran. Management checkout `cf31e31`; compute remains `815f145` plus its preserved two-file guest-agent channel/test patch; no pull, overwrite, commit or push.

Actual host remains Ubuntu 26.04.1/kernel 7.0.0-42-generic, i7-12700K/20 logical CPUs, 62967 MiB RAM, libvirt 12/QEMU 10.2.1, passt 20260120. The previously signature/hash-verified official Ubuntu 24.04 template/catalog was reused unchanged. Final authenticated health: KVM accessible, `qemu:///session`, 59027 MiB available, 852 GiB free. RX 6800 `03:00.0` remained `amdgpu` before/after; domain XML had no hostdev. No GPU, host desktop or Ollama configuration was changed.

### Fresh disposable VM: `a14a9007-861a-436c-b962-6ab72b86823f`

Only this VM was created in the repaired run; initial managed/libvirt lists were empty. Real `MachineClient` create/start used the SSH tunnel. All subsequent successful lifecycle actions used the **authenticated platform HTTP adapter**, not just direct compute. Every mutation intent was fsynced to private evidence before submission and operation/detail read back.

| Check | Operation UUID / evidence |
|---|---|
| Create | `a14a9007-861a-436c-b962-6ab72b86823f`; 2 CPUs, 4096 MiB, 24 GiB; shut off |
| Start | `17a0a2c4-e201-45c8-b9e2-4a0cb21dc3ef`; running |
| Guest networking | DHCP `ens3` IPv4 `10.0.50.56/24`, gateway `10.0.50.1` (normal passt host-address presentation, not a separate LAN reservation); working DNS and package downloads |
| Cloud-init | `status: done`, `extended_status: done`, `errors: []`, `recoverable_errors: {}`; fixed NoCloud seed |
| Installed packages | ubuntu-desktop-minimal `1.539.2`, openssh-server `1:9.6p1-3ubuntu13.20`, qemu-guest-agent `1:8.2.2+ds-0ubuntu1.18`, gdm3 `46.2-1ubuntu1~24.04.9` |
| Reboot | `7124bb8b-5313-46d5-b113-7ff1a0a1ede3`; boot ID `b3a69b28-6ff3-4dc9-bf0f-cc664a824af6` → `3594a541-033a-4534-a2af-e8ce6bb9e27c`; SSH returned after network wait |
| Graphical/agent readiness | display-manager and qemu-guest-agent active; GDM/Xorg/gnome-shell greeter processes, `gdm` seat0 tty1 session; actual libvirt screenshot visually inspected, Ubuntu username greeter visible; read-only guest-ping returned `{}` |
| Pause / resume | `d9bc9aab-9b0c-4967-8871-5a75aa0b1482` / `d68a5a3f-a05c-4b35-8af8-6f55da0db71e`; paused / running detail |
| Live safety rejections | resources `8529d38a-c652-4cea-adf9-2df69909f53f`, snapshot `9bc28683-0b3b-44d1-83e8-f08f009194b4`, delete `57d8902c-55b6-49a7-9db3-043ad8272f3a`; all durable rejected, guest unchanged |
| Graceful shutdown | `4cb97b28-d299-4fb9-af0c-1a4c9e4294db`; polled shut off, no orphan passt or VM listeners |
| Offline resources | `30331004-9a94-4a6f-b482-ae06b35ab379`; 3 CPUs, 6144 MiB, 26 GiB |
| Shrink rejection | `42bd05a0-b42f-48df-8ebb-76bed13ad7bc`; durable rejected, disk stays 26 GiB |
| Offline snapshot / restore | `b837b3fa-4e82-4e0b-a060-5ba0cb949565` / `c588d1cf-413e-4234-ac3e-d9c95fb9efcc`; `acceptance-desktop`; succeeded; no application-data roundtrip asserted |
| Start after shutdown/restore | `8f4dd630-7cd1-4b2a-bcb6-f32826b58456`; SSH returns, boot ID `540c5485-8118-45a8-ae85-6d9b6af5060e`, nproc 3, memory 5925 MiB guest usable, cloud-init done, both services active |
| Final shutdown | `f1820505-1494-4a7c-9031-08c04904050b`; polled shut off |
| Delete | `3796a94b-e83b-4eb9-94fe-7354fc4ff19c`; succeeded operation + deleted tombstone read back through platform |

Compute service was restarted with the guest running: detail remained usable. Replaying the exact original create after restart returned its cached original result, while fresh detail still showed the same running, resized VM; no second VM was created. Management platform restart retained its registry record and compute access.

**Storage observation corrects a previous assumption:** the service only grows qcow2 offline, but this Ubuntu cloud image has stock `growpart` and `resizefs` modules. On the subsequent boot, the guest **automatically grew its partition/filesystem**: vda 25769803776 → 27917287424 bytes, vda1 24694996480 → 26842480128 bytes; root filesystem reported 25923289088 bytes afterward. No guest expansion command was sent by the service/operator. Do not promise that cloud-image filesystems remain unchanged after reboot; review image behavior separately.

### Durable management integration / handoff

No existing platform process, port 8032 listener, default platform DB, or project-bots user unit existed. Separate acceptance state was created; no user data was replaced. These **management-only user systemd units** are enabled/active and survive this tool/subagent session; there is **no tracked background tunnel handle to hand off**:

- `project-bots-stage2-tunnel.service`: `/usr/bin/ssh -N -T`, dedicated existing key/verified host key, IdentitiesOnly/BatchMode/StrictHostKeyChecking/ExitOnForwardFailure, server-alive and restart-on-failure. Binds only `127.0.0.1:19443` → compute `127.0.0.1:9443`, and `127.0.0.1:19222` → compute `127.0.0.1:22000` (now no guest listener).
- `project-bots-stage2-platform.service`: checkout CLI `serve`, `127.0.0.1:8032`, private **isolated acceptance DB** `/home/server1/.local/share/project-bots-stage2-acceptance/platform.db`. This is a working persistent integration instance, **not migration/publication of a pre-existing production platform**. Dashboard URL `http://127.0.0.1:8032/`; API requires the separate platform credential/pairing. No browser pairing/visual dashboard review was performed.
- Unit files: `/home/server1/.config/systemd/user/project-bots-stage2-{tunnel,platform}.service`. Private environment files: profile `private/gaming-compute.env` and newly generated `private/stage2-platform.env` (0600). Tokens were never printed or put in Git. No Hermes config changed.
- Machine UUID `e0778e6a-8b1c-484d-8372-0cf60a780b30`; credential reference `PROJECT_BOTS_COMPUTE_TOKEN`; endpoint `http://127.0.0.1:19443`. Registry remains intentionally `unverified`; explicit `/api/machines/<UUID>/health` returned real libvirt/KVM health and `/vms` tracked this VM then `[]`. Missing-auth platform and compute requests each returned **403**.
- Parent should independently read back the services and authenticated `http://127.0.0.1:8032/api/machines/e0778e6a-8b1c-484d-8372-0cf60a780b30/{health,vms}` and deleted VM/operation before reporting final deployment status. Securely load credentials from the private env file; do not print them.

### Final safety, tests and open gates

At `2026-11-02T13:28:43Z`, managed and libvirt lists were empty, disposable directory absent, no compute QEMU/passt process or SPICE/guest-SSH listener remained. While running the VM, compute API/SPICE/SSH bound exactly `127.0.0.1:9443`, `:5900`, `:22000`; external host administration SSH `:22` was pre-existing and unchanged. Dedicated compute service remains enabled/active. No unrelated VM existed or was touched.

Local suite: **44 pass + 1 optional schema skip** (45 discovered); remote full suite with installed libvirt 12 RNG: **45 pass, no skips**. Node syntax and dashboard confirmation contract pass. No application/test code changed in this rerun, so no new TDD cycle was necessary; existing remote edits were preserved. Final `git diff --check` passed; documented new-run UUIDs were programmatically matched to durable evidence/readiness logs, and private credential values were checked absent from the four changed documents.

Remaining limits: guest `systemd-networkd-wait-online` timeout/degraded state (networkctl shows ens3 unmanaged by networkd, nmcli shows connected `netplan-ens3`); no bot graphical login/password/autologin; no interactive SPICE/performance benchmark, real-domain ownership-tampering or crash/failure-injection rerun, snapshot application-data roundtrip, production-platform migration, or Stage 3/worker/Ollama acceptance. Functional guest and integration gates succeeded; **unqualified clean-boot/full-stage completion is not asserted** pending disposition of the wait-online issue.

Durable private evidence: profile `private/stage2-repaired-evidence.jsonl`, `stage2-repaired-{guest-readiness,desktop,post-reboot,network,restart-after-shutdown,cloud-config}.log`, `stage2-greeter.png`, persisted repaired create/VM/machine IDs and guest known-hosts. Operational helpers are profile `cache/scratch/stage2_real.py` and `stage2_platform.py`, not shipped CLI features. Initial guest package-query quoting failed (`Bad substitution`) after successful cloud-init; the corrected independent readback above verified the actual packages/services. No fabricated readiness output.

## Historical first deployment (before repair)

**Historical result: deployed, core VM lifecycle exercised, full acceptance BLOCKED.** A running QEMU domain is not a ready Ubuntu Desktop. Guest SSH, package installation and graphical readiness did not pass in that earlier run.

Follow-up: [protocol-valid passt diagnosis](STAGE2_PASST_DIAGNOSIS.md) establishes `accept4() = EACCES` before the secondary epoll `EBADF`, in both stream and vhost-user modes. Ubuntu bug 2165771 matches the exact installed version. AppArmor TERM denial separately explains the orphan. No privileged repair or full acceptance has been performed; the original observations below are historical.

## Deployment and trust

- Authorized management: EliteDesk `10.0.50.10`; actual compute: `10.0.50.56`, Ubuntu 26.04.1 LTS, kernel `7.0.0-42-generic`, i7-12700K/20 logical CPUs, 62967 MiB RAM; authenticated health after cleanup: 59115 MiB available, 852 GiB storage free.
- Dedicated identity `pbcompute`, UID 1001, groups `pbcompute`, `users`, `kvm`; no sudo. Session libvirt `qemu:///session`, libvirt 12.0.0, QEMU 10.2.1, passt `0.0~git20260120.386b5f5-1`.
- Public Git clone `/home/pbcompute/project-bots`, base `815f145975b91fae19697de68edcfc58a9929f74`. The uncommitted guest-agent channel fix and regression test were subsequently copied from the management checkout. No commit/push.
- Official image source: `https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img`, standalone qcow2, original virtual size 3758096384 bytes. Downloaded `SHA256SUMS` and `SHA256SUMS.gpg` from the same official directory.
- Publisher verification: `gpgv --keyring /usr/share/keyrings/ubuntu-cloudimage-keyring.gpg SHA256SUMS.gpg SHA256SUMS` returned **Good signature** from `UEC Image Automatic Signing Key <cdimage@ubuntu.com>`, fingerprint `D2EB44626FDDC30B513D5BB71A5D6C4C7DB87C81`, signature dated 2026-10-17. The preinstalled keyring belongs to package `ubuntu-keyring` (`2023.11.28.1build1`), confirmed by `dpkg-query -S`; no downloaded untrusted key was imported.
- Matching signed published SHA-256 and actual file verification: `04e8f2461a16a44e78a370284471f29616cdd9baf1893df25807b71f985b6c94`; `sha256sum -c` returned `noble-server-cloudimg-amd64.img: OK`.
- Template `/home/pbcompute/templates/ubuntu-24.04/noble-server-cloudimg-amd64.img`; catalog `/home/pbcompute/templates/catalog.json`, template ID `ubuntu-desktop`. Both mode 0600, private parent directories.

## Service / transport handoff

- User unit `/home/pbcompute/.config/systemd/user/project-bots-compute.service`; `systemctl --user is-enabled` = `enabled`, `is-active` = `active`. Latest observed main PID 46292. Linger was already enabled by the administrator.
- Executes `/usr/bin/python3 -m project_bots.cli machine-service` from the Git checkout, with explicit loopback `127.0.0.1:9443`, catalog above, state `/home/pbcompute/.local/share/project-bots-compute`, `XDG_RUNTIME_DIR=/run/user/1001`, UMask 0077, Restart=on-failure.
- Private compute environment file `/home/pbcompute/.config/project-bots-compute/compute.env` mode 0600. Secret was transferred directly by SCP to management profile `private/gaming-compute.env`; token never printed. It defines `PROJECT_BOTS_COMPUTE_TOKEN`. Platform registration/restarting the management server to inherit this credential is **not** claimed done.
- Management API endpoint `http://127.0.0.1:19443`, SSH-forwarded to compute `127.0.0.1:9443`. A second loopback forward `127.0.0.1:19222` targets compute `127.0.0.1:22000` for acceptance guest SSH (now no VM listener).
- Tunnel launched as tracked foreground SSH in background tool session **`proc_baaabe926e5c`, PID 3621382** on management. Parent must retain/manage it; it is not an installed reconnecting service. Uses the already verified host key, BatchMode/IdentitiesOnly, ExitOnForwardFailure, ServerAliveInterval 30 / CountMax 3. No public compute port opened.
- Unauthenticated health returned 403; authenticated health returned backend libvirt, KVM accessible true. Service was restarted after VM definition; detail and identical create replay still returned the same VM without new conversion.

## Real disposable VM and operations

Only managed VM **`9bc73046-7528-4d31-ba65-8b8e9029c5d1`** was created. Initial request: 2 vCPU, 4096 MiB, 24 GiB, generated dedicated ed25519 acceptance public key, fixed cloud-init. Requests used the real `MachineClient` through the SSH tunnel, not a fake backend; intent UUIDs were saved before each mutation. The stock acceptance script was not used because separate guest-readiness investigation was required before deletion.

| Check | Operation UUID / observed result |
|---|---|
| Create | `9bc73046-7528-4d31-ba65-8b8e9029c5d1`, defined / shut off |
| Start | `2bb5ba25-30a3-42da-bbe2-ca38afca0178`, running |
| Pause | `c254557f-9c08-43bf-9a18-d17063d790af`, paused |
| Resume | `da5ad16d-2a49-415d-895e-fee9932f0eec`, running |
| Graceful shutdown | `098992a2-700f-47b2-8100-f49de866e60e`, polled shut off; QEMU log reason=shutdown |
| Repeat start failure | `95d9f862-85f5-4e53-9d7c-9ea35c5a947f`, unknown; passt port 22000 held by orphan from first run; no QEMU launch |
| Offline resources | `d411c415-c121-4ce0-b2eb-117b5bca4939`, 3 vCPU / 6144 MiB / 26 GiB |
| Snapshot create | `49ceccec-65db-4e4d-8719-9c0fde38e3dc`, `acceptance-offline`; qemu-img listed internal snapshot ID 1 |
| Snapshot restore | `566e9665-464a-4e0b-8395-545fea530d56`, succeeded; no guest application-data roundtrip claimed |
| Redefine with agent fix | `fcfea917-2970-4a62-8a21-6f19b26a285e`, same resources, actual libvirt XML contains virtio agent channel |
| Shrink rejection | `82eef010-1c67-4674-b79f-2a995eeb6162`, rejected, resources remained 26 GiB |
| Delete | `de092b8b-d097-4876-bb58-4d929b48230d`, succeeded, deleted tombstone read back |

The pause UUID above is recorded exactly in the private evidence log; use that log as the source of truth for any further operation queries.

Isolation readback while running: SPICE `127.0.0.1:5900`, guest SSH forward `127.0.0.1:22000`, API `127.0.0.1:9443`. Domain XML had owner UUID `4344a339-274b-47eb-a015-ba7c146950a5`, exact private disk/seed paths and no hostdev. State directory mode 0700, generated files 0600. RX 6800 `03:00.0` remained bound to **amdgpu** before/after; no host GPU/desktop/Ollama settings were changed. No performance/desktop-interactivity benchmark is claimed.

Disk readback after offline growth: qemu-img virtual size **27917287424 bytes** (26 GiB), but root partition remained start 2099200/end 50331614 (23 GiB), unchanged from before growth. Read-only fdisk reported expected stale backup GPT location; no partition/filesystem repair or expansion was performed. Temporary sparse raw diagnostic copies were removed.

## Blocker: installed passt backend is not serving guest traffic

Guest SSH repeatedly timed out during banner exchange. After graceful shutdown, a **read-only** qcow2-to-sparse-raw conversion and `debugfs` reads (no mount/root/guest command) established:

- Guest kernel booted; cloud-init selected NoCloud seed and created locked non-sudo `bot` with the acceptance key.
- `ens3` was up with only IPv6 link-local, no IPv4 lease; network-online timed out.
- Package update/install failed with `Temporary failure resolving 'archive.ubuntu.com'` / `security.ubuntu.com`; cloud-final exited 1. Desktop and agent readiness did **not** succeed.
- Passt had selected real `wlo1`, DHCP address `10.0.50.56`, router/DNS `10.0.50.1`, but never serviced the QEMU socket; after shutdown PID 45096 stayed orphaned, holding port 22000. A repeat start failed `Address already in use`.
- Independent unprivileged foreground probe, **using the installed confined `/usr/bin/passt` unchanged**, reproduced `Failed to add fd to epoll: Bad file descriptor` after connecting a UNIX client. It did not exit after the client disconnected, despite `--one-off`. This reproduces a backend failure outside Project Bots. Exact kernel/AppArmor/package cause is **not yet established**.
- Kernel journal and `/proc/<passt>/fd`/syscall diagnostics are not readable by pbcompute; passt reports its normal `passt (enforce)` AppArmor profile. No policy disabled, binary copied to evade confinement, sudo, new privileged package or privileged escape was attempted.

Administrator **read-only** next diagnostics on compute (not executed here):

```sh
sudo journalctl -k --since '2026-11-02 07:40:00' --until '2026-11-02 08:00:00' --no-pager
sudo aa-status
apt-cache policy passt libvirt-daemon-driver-qemu qemu-system-x86
```

Review any kernel/AppArmor denials and the installed passt/package compatibility before proposing a targeted administrator repair. Do not blindly disable AppArmor, grant sudo to pbcompute or change GPU/network policy. Once repaired, rerun the confined socket probe and then a fresh explicitly authorized disposable VM acceptance. A successful backend probe alone still does not prove SSH/Desktop readiness.

Local failed-start reconciliation was performed only after stopping the service, checking exact UUID/owner/disk paths and confirmed shut-off domain, and backing SQLite up to `compute.db.pre-reconciliation-1793623777` within private state. The failed start record was changed unknown→rejected with a detailed reconciliation note; the original unknown is retained in the stopped backup. Only exact same-UID orphan PID 45096 with this VM's socket path was terminated. Service restarted, and ordinary owned offline API actions then cleaned up the disposable VM. No unrelated domains existed or were modified.

## Final verification and remaining gate

- Remote suite: **45/45 pass**, including actual installed libvirt 12 Relax NG schema. Local management suite: **44 pass / 1 optional schema skip**. Node syntax and dashboard confirmation contract pass; `git diff --check` passes.
- Separate software fix: regression first failed for missing `org.qemu.guest_agent.0` transport, then passed after adding fixed UNIX/virtio channel; actual domain redefine included it. This does not claim a working installed guest agent because package/network boot failed first.
- API tombstone and delete operation read back; managed list `[]`; `virsh list --all` empty; disposable VM directory absent. No QEMU/passt acceptance processes or SSH/SPICE VM listeners remain. API user service is enabled/active and authenticated health remains usable, but its VM networking dependency remains blocked.
- Guest login, `cloud-init status --wait` via `bot`, Desktop/display-manager/agent readiness, actual graphical greeter/session, restart boot-ID change and live resize/snapshot/delete negative tests remain **not passed** on hardware. No Stage 3/worker readiness claim.
- Private management evidence: profile `private/stage2-evidence.jsonl`, `stage2-cloud-init-output.log`, `stage2-passt-diagnostic.log`, dedicated acceptance key and persisted create intent. Scratch helper scripts are operational probes, not shipped CLI features. No private key or token belongs in Git/docs/output.
