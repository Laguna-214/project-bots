# Passt follow-up diagnosis — 2026-11-02

**Stage 2 remains blocked. No application networking fix or full acceptance is claimed.** This investigation made no privileged changes, disabled no confinement, created no VM, and left no probe process or SSH tunnel running.

## Proven immediate failure

On compute `10.0.50.56`, the unchanged installed `/usr/bin/passt` (`0.0~git20260120.386b5f5-1`) was launched as `pbcompute`, under its normal AppArmor confinement. Unprivileged `strace` of our own child succeeded. Both supported modes failed at socket acceptance:

```text
accept4(6, NULL, NULL, 0) = -1 EACCES (Permission denied)
getsockopt(-1, SOL_SOCKET, SO_PEERCRED, ...) = -1 EBADF
setsockopt(-1, SOL_SOCKET, SO_RCVBUF, ...) = -1 EBADF
setsockopt(-1, SOL_SOCKET, SO_SNDBUF, ...) = -1 EBADF
epoll_ctl(3, EPOLL_CTL_ADD, -1, ...) = -1 EBADF
```

The epoll error is **secondary to denied accept**, not proof of an epoll implementation defect. Upstream `tap.c` at installed revision `386b5f5`, lines 1437–1450, assigns `accept4()` directly to `c->fd_tap` and calls `tap_start_connection()` without checking failure. That function registers this invalid descriptor. The event-driven socket is consequently not serviced, including disconnect notification; `--one-off` does not rescue it.

Protocol-valid probes:

- Stream mode: sent a 300-byte Ethernet/IPv4/UDP DHCPDISCOVER with BOOTP magic cookie, client MAC, broadcast flag and DHCP message type, preceded by QEMU stream's four-byte big-endian frame length. No response.
- Vhost-user mode: enabled `--vhost-user` and sent the valid initial `VHOST_USER_GET_FEATURES` header (request 1, version flags 1, size 0; three little-endian uint32s). No response. This tests initial control-plane negotiation, **not** a full shared-memory/vhost-user datapath.
- Both traces show the same `accept4 EACCES` before any packet/protocol processing. Both backend pcaps contain only the 24-byte pcap header, zero captured packets. Thus there is no DHCP offer or DNS traffic to inspect on this backend path; an independent DNS failure has not been established.
- Both processes were explicitly terminated and reaped. One earlier strace-wrapper probe left its child alive; that exact child was identified and terminated, then the harness was corrected to clean up its process group. Final process inspection found no passt/QEMU workload.

Private evidence: profile `private/stage2-passt-protocol-diagnostic.log`. Reproducible probe: profile `cache/scratch/passt_protocol_probe.py`, copied to compute `/home/pbcompute/passt_protocol_probe.py`; compute logs/pcaps/traces are under private `/home/pbcompute/passt-stage2-diagnostic/`. No token/private key is in these files. Run `python3 /home/pbcompute/passt_protocol_probe.py strace-dhcp` or `strace-vhost` as pbcompute. These are diagnostics, not shipped application commands.

## Separate confirmed shutdown policy issue

Kernel journal read access through existing `projectbots` account established these actual denials for the original managed VM:

- 07:42:52: profile `passt`, PID 45096, `sendmsg` denied for disconnected `run/systemd/journal/dev-log`.
- 07:46:12: profile `libvirtd`, PID 44270, `signal send term` denied, peer `passt`.
- 07:46:12: profile `passt`, `signal receive term` denied, peer `libvirtd`.

The reciprocal signal denial explains libvirt's failure to terminate the orphan. **It does not explain `accept4 EACCES`.** The newly reproduced accept failures did not generate matching entries in the accessible kernel or general journal; no auditd log directory exists. A missing denial record is not evidence that AppArmor allowed the call.

## Package/source/documentation comparison

- Installed/candidate: passt `0.0~git20260120.386b5f5-1`, AppArmor `5.0.2-0ubuntu1~26.04.1`, libvirt QEMU driver `12.0.0-1ubuntu5.6`; running kernel `7.0.0-42-generic`. No newer passt candidate exists in the host's configured repositories. No package install/update was attempted.
- [Ubuntu bug 2165771](https://bugs.launchpad.net/ubuntu/+source/passt/+bug/2165771), **Confirmed**, describes qemu session guests not getting an address on Ubuntu 26.04.1 with the **exact installed passt version**. It suggests missing `attach_disconnected` as a cause. This is a strong match, not a validated repair on this host.
- [Ubuntu bug 2165739](https://bugs.launchpad.net/ubuntu/+source/passt/+bug/2165739) records that this package's standalone passt profile lacks local override inclusion. Actual installed file agrees; adding a file under `local/` alone would do nothing.
- [Installed-revision tap.c](https://passt.top/passt/plain/tap.c?id=386b5f5) supports the causal chain above. Its seccomp generator uses ALLOW or KILL_PROCESS, not an EACCES return action; the observed process survives. SSH parent has `Seccomp: 0`, `NoNewPrivs: 0`.
- [Current upstream standalone profile](https://passt.top/passt/plain/contrib/apparmor/usr.bin.passt) has `flags=(attach_disconnected)`; the installed one does not. Upstream added it on October 2 for a **newer namespace-detachment implementation**, so blindly transplanting that change is not proven correct for the January binary. AppArmor's manual warns that attach_disconnected can introduce path aliasing; it is not a recommendation to relax policy here.
- [Libvirt documentation](https://libvirt.org/formatdomain.html#vhost-user-connection-with-passt-backend): passt-backed `type='vhostuser'` supported since 11.1.0, source path/type/mode implied and must not be supplied, one queue. Existing `type='user'` maps to QEMU stream; original real QEMU log confirms this. Version support alone is not a reason to switch; both modes fail the prerequisite accept.
- [Cloud-init networking documentation](https://docs.cloud-init.io/en/latest/reference/network-config.html): absent datasource/system/kernel network configuration, cloud-init generates DHCP fallback on the first eligible interface. Separate network-config is not mandatory for this single-NIC cloud image. Application seed supplies no network-config and does not disable networking. Existing guest log confirms ens3 up, no IPv4, and package/DNS failures. The deleted guest's actual netplan/renderer files were not retained, so renderer correctness is **not** independently proved; changing renderer would not fix the reproduced host accept failure. After host repair, inspect netplan, networkd/NetworkManager and cloud-init on a new guest before claiming readiness.

## Administrator handoff (commands NOT executed)

There is no demonstrated safe application/XML-only repair. Do not disable AppArmor, switch to complain/unconfined, copy binaries, grant privileges, change GPUs or install cross-release packages.

Minimal read-only administrator collection on compute:

```sh
sudo aa-status
sudo cat /sys/module/apparmor/parameters/audit
sudo cat /sys/module/apparmor/parameters/mode
sudo journalctl -k --since '2026-11-02 07:40:00' --no-pager
```

If the administrator needs to expose quiet denials, the following **temporary audit-only diagnostic** retains enforcement and restores the previous audit setting even on failure; review/authorize before use. It can be noisy for its few-second duration:

```sh
sudo sh -eu -c '
  parameter=/sys/module/apparmor/parameters/audit
  old=$(cat "$parameter")
  trap '\''printf "%s" "$old" > "$parameter"'\'' EXIT HUP INT TERM
  printf all > "$parameter"
  runuser -u pbcompute -- env HOME=/home/pbcompute python3 /home/pbcompute/passt_protocol_probe.py strace-dhcp
  journalctl -k --since "1 minute ago" --no-pager
'
```

Use resulting accept/path/peer denial and vendor review of bug 2165771 to determine a targeted enforcing-policy/package repair. No exact networking policy edit can honestly be prescribed as verified yet.

For the **separate, already proven signal issue**, the minimum policy permissions to review are `signal (send) set=(term) peer=passt,` in libvirtd and `signal (receive) set=(term) peer=libvirtd,` in standalone passt. Libvirtd includes `local/usr.sbin.libvirtd`; passt has no local hook. An administrator must back up/edit the appropriate policy, review syntax, and reload only affected profiles using `sudo apparmor_parser -r -T /etc/apparmor.d/usr.sbin.libvirtd /etc/apparmor.d/usr.bin.passt` after approving changes. These reciprocal, exact-peer TERM rules address teardown only, not networking. No such edit/reload was performed.

## Final checks and remaining acceptance

- Remote suite from the correct repository directory, with `PROJECT_BOTS_DOMAIN_RNG=/usr/share/libvirt/schemas/domain.rng`: **45 tests passed, no skips**. An initial invocation from the home directory failed relative-path/import assumptions; rerunning from the checkout resolved it without code changes.
- Authenticated direct-loopback API health succeeded; KVM accessible, libvirt backend. API `/v1/vms` returned `[]`; `virsh -c qemu:///session list --all` empty. Service remains active; only API listener `127.0.0.1:9443`, no VM SSH/SPICE listeners. No new tunnel was started.
- No new managed VM was created because the backend prerequisite already fails independently and no permitted repair is proven. No source/test changes were made by this follow-up; earlier uncommitted guest-agent fix is preserved.
- Full Stage 2 needs **actual guest SSH, successful cloud-init, Desktop/display-manager/agent and graphical readiness, restart with boot-ID change, full disposable lifecycle and live management integration**. Unit/schema tests and a listening passt port do not satisfy these gates.
