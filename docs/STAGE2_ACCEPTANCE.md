# Stage 2 compute deployment evidence — 2026-11-02

**Result: deployed, core VM lifecycle exercised, full acceptance BLOCKED.** A running QEMU domain is not a ready Ubuntu Desktop. Guest SSH, package installation and graphical readiness did not pass.

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
