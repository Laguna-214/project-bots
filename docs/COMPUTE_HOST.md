# Ubuntu Desktop compute host: administrator setup and acceptance

**Stage 2 authorized runtime gates complete 2026-11-02; parent review/publication pending.** Authorized compute is `10.0.50.56` (`pbcompute`, UID 1001), separate from management EliteDesk `10.0.50.10`. Earlier real acceptance proved full lifecycle/offline resources/snapshots and negative-operation safety after the administrator's enforcing-AppArmor repair. Final disposable VM `ddeb8488-6c06-4e38-918c-e1f187415b6b`, created and controlled through the platform, proved the fixed new-instance cloud-init provisioning: post-reboot NetworkManager networking/DNS/key-only SSH, cloud-init done without errors, active display-manager/agent and visually inspected Ubuntu greeter, system `running` with zero failed units and **4.916-second startup**. Stale networkd wait-online is disabled; NM's own online wait remains enabled. First boot installs Desktop; reboot is required for the verified Desktop runtime. Graceful shutdown/delete left no VM, directory, QEMU/passt or VM listener. Host GPU remains amdgpu; no sudo/host security changes. No logged-in bot graphical session or Stage 3 acceptance. See [exact acceptance evidence, caveats and operation IDs](STAGE2_ACCEPTANCE.md).

Compute user service remains enabled/active on `127.0.0.1:9443`. Management now has enabled/active, reconnecting user units `project-bots-stage2-tunnel.service` and `project-bots-stage2-platform.service`, with loopback tunnel `http://127.0.0.1:19443` and platform `http://127.0.0.1:8032/`. Real authenticated platform calls used machine `e0778e6a-8b1c-484d-8372-0cf60a780b30`; health/lifecycle/operation reads and empty final VM list passed. No existing platform was running; this instance uses separate acceptance DB `/home/server1/.local/share/project-bots-stage2-acceptance/platform.db`, not an existing production deployment. Private credentials stay in management profile private env files. The remaining sections describe operating procedures, not additional completed checks. `10.0.50.30` remains an example, not a discovered address.

Target: existing Ubuntu Desktop gaming PC (i7-12700K, 64 GB, RX 6800), retaining normal desktop use and host GPU access for later shared Ollama. **No Proxmox, GPU passthrough, root-shell API, raw libvirt TCP/LAN socket or Ollama changes.** Stage 2 implements VM management only. No workers/inference are started. An Ubuntu **24.04-era libvirt 10/QEMU/passt** stack is the intended starting point: XML uses libvirt's supported user-mode passt backend and loopback port forwarding (not portable to older libvirt). Exact installed versions/driver support must be checked on the actual host.

## 1. Prerequisites and privilege boundary

An administrator must first review BIOS VT-x/VT-d settings, `/dev/kvm` read/write access, Ubuntu version, free RAM/disk, existing libvirt domains and Ollama/desktop resource use. Review all changes before installing OS packages. Typical Ubuntu package prerequisites are `qemu-kvm`, `qemu-utils`, `libvirt-daemon`, `libvirt-clients`, `cloud-image-utils`, `passt` and optionally `virt-viewer`/`libxml2-utils`. Package names/driver splits vary: verify the QEMU libvirt driver for that Ubuntu release. This repository intentionally does not run apt, create users, modify groups/firewall, install systemd units or enable host services.

Use a **dedicated unprivileged Unix identity**, private home and private compute state directory. Grant only `/dev/kvm` access as required (typically the `kvm` device group), not sudo or a generic privileged libvirt group. The service always uses **`qemu:///session`** for that identity; it cannot select `qemu:///system`. Validate as that exact identity:

```sh
virsh --connect qemu:///session version
virsh --connect qemu:///session list --all
qemu-img --version
cloud-localds --help
passt --version
```

These are administrator-local checks, not exposed commands. Session libvirt still needs a working per-user daemon/runtime directory; depending on Ubuntu packaging this means user socket activation or libvirtd autostart. A headless service identity may require administrator-configured user manager/linger and an appropriate `XDG_RUNTIME_DIR`. Do not accidentally run the service as your desktop login: its session libvirt would then share ownership of your desktop VMs. No prewritten unit is automatically installed because runtime/driver layout must be verified on the actual host. After manual launch works, an administrator can create a **user** service with a fixed executable/arguments, `UMask=0077`, private token EnvironmentFile mode 0600, restart policy and resource limits; ensure its namespace/runtime still permits session libvirt sockets, passt, KVM and the private disks. Avoid blindly applying `PrivateDevices`/`NoNewPrivileges`/mount sandboxing that prevents the selected backend from functioning; test any hardening explicitly.

**Actual limitations:** the service Unix identity and local root remain trusted administrators. Session libvirt limits blast radius compared with system libvirt, but a compromise can still exercise that identity's KVM access and modify all of its files/VMs. Membership in common system `libvirt` administration groups may be effectively root-equivalent on some hosts: it is not a safe generic recommendation. The owner metadata/SQLite record/exact disk checks restrict the HTTP API; they do not defend against root or a malicious same-UID process copying metadata or racing direct virsh commands. Do not manually mutate the service's domains concurrently. No per-user RBAC, mTLS or strong independent approval service is supplied.

## 2. Trusted local Ubuntu catalog

Obtain a **standalone qcow2 Ubuntu cloud image** from an administrator-approved official source. Verify its signed published checksum independently. Catalog hashes only enforce the administrator's pin; they do not establish image publisher trust. Do not use a Desktop installer ISO as the template: this implementation customizes a cloud image with fixed Desktop packages at first boot.

Keep catalog/image paths absolute and canonical (no symlink components). Files must be owned by root or the dedicated service UID, not group/other writable; their immediate parent directories must not be group/other writable. Prefer root-owned read-only images/catalog under a dedicated reviewed directory, readable by the service. Ancestors must also be administered safely; do not place them beneath attacker-controlled directories. Restrict the service identity's writable storage to private VM state wherever practical. Set catalog mode 0644 or 0600, images 0644 or 0600 as appropriate; never permit group write. Example **catalog schema**, with real path/hash to be supplied locally:

```json
{
  "ubuntu-desktop": {
    "image": "/absolute/trusted/ubuntu-cloud.qcow2",
    "sha256": "<actual 64-character sha256 digest of the approved image>"
  }
}
```

The API never accepts image paths, catalogs, YAML, arbitrary XML, shell snippets or package names. Each VM gets a standalone conversion and fresh read-only cloud-init seed. Generated cloud-init has the fixed Desktop/SSH/guest-agent packages, non-sudo locked `bot` user, supplied ed25519 public key and a fixed three-command service migration after package installation: enable/start NetworkManager, disable/stop only systemd-networkd-wait-online, reset-failed only that stale unit. This leaves NetworkManager-wait-online and security services intact; it accepts no caller-supplied runcmd. New guests receive this seed; existing guests are not retrofitted. Network/package mirror access is needed for first-boot installation. After cloud-init completes, explicitly reboot and verify the Desktop/NM runtime and clean system state rather than assuming package installation started the display-manager. No guest password or arbitrary root command is accepted. The Desktop graphical greeter has no configured password/autologin: use SSH keys for login/administration; interactive graphical login setup would be a separately reviewed guest change, not an API feature. Installing the Desktop package set is not evidence a graphical session was successfully launched.

## 3. Launch and transport

Install Project Bots for that identity using the existing no-root installer after review. Provision a random secret securely in its inherited environment (do not print/log it, put it in history, or paste it into browser forms):

```sh
# Dedicated compute identity, private terminal; do not enable shell tracing.
export PROJECT_BOTS_COMPUTE_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
project-bots machine-service --catalog /absolute/trusted/catalog.json \
  --state-dir "$HOME/.local/share/project-bots-compute"
```

Default loopback HTTP port is 9443, separate from the management dashboard port 8032. TLS is optional **only on loopback**. Use an administrator-approved SSH account to forward management-loopback to compute-loopback; this account need not be the compute service identity:

```sh
# On management PC. Replace ACTUAL_COMPUTE_HOST; this is not host discovery.
ssh -N -o ExitOnForwardFailure=yes -L 19443:127.0.0.1:9443 ADMIN@ACTUAL_COMPUTE_HOST
```

Register endpoint `http://127.0.0.1:19443` in the management dashboard. Securely provision the **same compute token** in a named management-server environment variable, e.g. `GAMING_COMPUTE_TOKEN`, and register `credential_env: "GAMING_COMPUTE_TOKEN"`. Keep the platform API token separate. Restart management to inherit a changed secret. The SSH tunnel is not automatically managed/reconnected by this software. Plain loopback is accessible to other local users; keep hosts trusted.

For direct LAN transport:

```sh
project-bots machine-service --host ACTUAL_COMPUTE_BIND_IP --port 9443 \
  --catalog /absolute/trusted/catalog.json --state-dir "$HOME/.local/share/project-bots-compute" \
  --tls-cert /private/service-fullchain.pem --tls-key /private/service-key.pem
```

Use a hostname/IP covered by the certificate SAN, a trusted CA (or set management `PROJECT_BOTS_MACHINE_CA_FILE` to a private/admin-local CA bundle), and firewall to the actual management host only. Non-loopback plaintext startup is refused; the adapter also refuses remote HTTP and does not bypass TLS verification, follow redirects or inherit proxy environment variables. IPv4 listener support only. No raw libvirt LAN listener is needed/allowed.

## 4. Software checks (safe; no real VM mutation)

```sh
python3 -m unittest discover -s tests -v
node --check project_bots/dashboard.js  # optional existing Node
node tests/dashboard_vm.cjs             # fake DOM/HTTP, not visual or VM acceptance
# Optional installed libvirt schema validation, no daemon required:
PROJECT_BOTS_DOMAIN_RNG=/usr/share/libvirt/schemas/domain.rng \
  python3 -m unittest discover -s tests -p test_domain_schema.py -v
```

The schema test uses installed libxml2 through ctypes and administrator-supplied sibling RNG schemas. During development the actual generated XML was validated successfully against the **upstream libvirt v10.0.0 Relax NG schema** (nine schema files fetched into temporary scratch). This proves schema shape only, not successful QEMU startup, driver/passt support, boot, graphics, SSH or cloud-init. Unit tests use temporary files/mocked fixed command argv. Fake HTTP adapter tests use loopback HTTP servers and never create a real domain. TLS tests create a temporary certificate and verify trust/hostname rejection. Default unittest skips the optional schema when its path is absent. No real host acceptance runs during discovery.

## 5. Real host acceptance — repeatable procedure, explicit opt-in only

After the administrator approves one disposable VM and actual compute access:

1. Confirm actual listener/firewall/TLS or SSH tunnel; validate token rejection and authenticated health. Record OS, libvirt/QEMU/passt versions, resource headroom and template signature/hash. Health is not VM readiness.
2. Through the paired dashboard (or explicit API client), create one Ubuntu Desktop VM with an actual ed25519 **public key only**, 2 CPUs/4096 MiB/24 GiB and a fresh operation UUID. Confirm it is defined, shut off and visible after restarting the compute service. Verify namespace, owner metadata, isolated paths, permissions and generated XML locally. Keep that state/database to preserve ownership.
3. Start, poll detail to running, then verify actual listening sockets (`ss` as an administrator), SPICE and guest SSH forwards are loopback only. Forward the reported SSH port through an approved SSH transport and log in as `bot` using the private key **locally**. Verify `cloud-init status --wait`, the fixed package installation, `systemctl status display-manager`, and guest agent. `bot` has no sudo; cloud-init's privileged logs/admin remediation require an independently approved guest access method. No service guest-command API is available. Check host GPU/desktop/Ollama remains untouched and guest has no hostdev GPU. Record package installation/graphical readiness honestly, including limitations of key-only graphical login.
4. Confirm pause/resume/restart observations and graceful shutdown (may need boot complete and resume before ACPI). After initial Desktop installation, explicitly reboot, record a changed boot ID and startup timing, and verify NetworkManager connectivity, active display-manager/agent, cloud-init done and system running/zero failed units; the stale networkd waiter must be disabled and NM's waiter retained. Offline, test CPU/RAM edit and disk growth; record guest partition/filesystem sizes before and after reboot, accounting for stock cloud-image growpart/resizefs auto-expansion. Create/restore a qcow2 disk snapshot offline; live operations and shrinking must fail. Verify unowned/renamed/copied-name domains and modified disk paths cannot be mutated through the API. Do not modify unrelated domains for testing.
5. Offline-delete **only that verified-owned VM**, read back its tombstone/operation and confirm list, libvirt definition and private disks no longer contain it. Confirm duplicate successful operation IDs do not repeat host work. Repeat in a deliberate test window for interrupted conversion/start, service restart and local recovery; don't test failure injection on important domains.

A core lifecycle script is available in the checkout. It does **not** run automatically and stops on uncertainty without force/automatic cleanup:

```sh
# Token already provisioned; key file contains only a public key without comment.
python3 scripts/accept_machine.py --endpoint http://127.0.0.1:19443 \
  --ssh-key-file /local/admin/acceptance-ed25519.pub \
  --confirm-real-host-mutation 'CREATE START SHUTDOWN DELETE DISPOSABLE VM'
# Direct TLS can add --ca-file /admin/ca.pem; --token-env is configurable.
```

The script performs real create/start/detail/graceful-shutdown/delete **only after that explicit opt-in** and prints VM/operation IDs. It waits briefly for boot; it does not prove Desktop packages finished or guest SSH works. A timeout is NOT a reason to rerun with a new create ID. Inspect the printed operation first. The exact script flow is separately exercised with a fake client; that is not real libvirt acceptance.

## Recovery, rollback and storage caveats

Admission limits reserve resources even while VMs are off/partial; snapshot growth, guest writes and concurrent host workloads can still exhaust storage/memory. Default host headroom is conservative, not a performance guarantee. Snapshot retention/deletion and OS-level service quotas are not implemented. Disk snapshots capture only disk, not RAM/settings, and only offline standalone qcow2 is accepted. The service itself does not issue guest filesystem expansion commands, but stock cloud-image `growpart`/`resizefs` **can automatically expand the guest partition/filesystem at the next boot**, as observed in actual acceptance. Do not assume an offline unchanged partition will stay unchanged after reboot; review image modules before growth. Service power operations are graceful/asynchronous and never `destroy`/`reset`.

Commands have 120-second timeouts; management HTTP waits 15 seconds, so a conversion can continue after a caller timeout. Keep the UUID/payload, query operation/detail, and retry **the same successful payload/ID** only to retrieve its cached result. `running` after crash and `unknown` outcomes block later mutations of that target. There is no automatic reconciliation/force-unlock API. Stop the compute service, back up SQLite/state and inspect the domain/disk/operation under the dedicated identity; verify UUID, metadata owner and exact paths before any administrator-local repair. Preserve partial disks until actual outcome is understood. Do not erase the owner database or invent a new one to regain access; name prefix alone never grants ownership. A reviewed local DB/state repair or restoration from a consistent stopped backup is currently required; an automated recovery CLI is not supplied.

For software rollback, stop the compute service before replacing its installed package, preserve catalog/private DB/disks, and review schema compatibility. Stop/delete intended managed VMs first if fully removing the deployment; deleting files/uninstalling the CLI does not stop domains. The existing installer/update/uninstaller remains unchanged and preserves compute data/domains. No root packages, system users, OS services, SSH tunnels or firewall rules are automatically undone. Those are administrator-managed prerequisites. **Stage 2 hardware acceptance must be recorded separately before moving to workers.**
