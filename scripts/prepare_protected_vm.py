#!/usr/bin/env python3
"""Generate review artifacts WITHOUT privileged actions, network or VM execution.

Run from the checkout with PYTHONPATH=.; never execute this checkout script as root.
The generated recipe is deliberately NOT an unattended production installer.
"""
import argparse
import json
import os
from pathlib import Path
from project_bots.protected_compute import Binding, domain_xml, network_source


def generate(binding, destination):
    b = Binding.parse(binding)
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    (destination / 'binding.json').write_text(json.dumps(binding, sort_keys=True, indent=2) + '\n')
    (destination / 'guard.c').write_text(network_source(b))
    (destination / 'domain.xml').write_text(domain_xml(b, software_emulation=True) + '\n')
    (destination / b.unit).write_text('[Unit]\nDescription=Project Bots exact protected VM ' + b.vm_id + '\n'
        '[Slice]\nDelegate=no\nCPUAccounting=yes\nCPUQuota=100%\nMemoryAccounting=yes\nMemoryMax=768M\nTasksMax=128\n')
    (destination / 'project-bots-protected.service').write_text('''[Unit]
Description=Project Bots root exact-UUID protected authority (review required)
After=libvirtd.service
[Service]
Type=simple
User=root
Group=root
UMask=0077
RuntimeDirectory=project-bots-protected
RuntimeDirectoryMode=0755
ExecStart=/usr/bin/python3 -I /opt/project-bots-protected/protected_authority_entry.py
NoNewPrivileges=yes
ProtectHome=yes
ProtectSystem=strict
ReadWritePaths=/var/lib/project-bots-protected /run/project-bots-protected /sys/fs/cgroup
RestrictAddressFamilies=AF_UNIX
Restart=on-failure
[Install]
WantedBy=multi-user.target
''')
    (destination / 'INSTALL-REVIEW.txt').write_text(f'''ADMINISTRATOR REVIEW REQUIRED; NOT EXECUTED
Target: only inside approved outer lab 2f3ce848-c083-4674-8659-e2d9f0d37638.
Nested disposable UUID: {b.vm_id}; owner {b.owner}; identity {b.uid}:{b.gid}.
Never use this on compute host or an original domain. Never import checkout as root.

1. Verify root-owned source snapshot digest approved by independent reviewer, and
   copy the complete project_bots package to /opt/project-bots-protected (root:root,
   directories 0755, files 0644, no symlinks, no writable ancestors). Inspect every
   imported module, not only protected_compute.py. No symlink back into checkout.
2. Signed Ubuntu archive input lock is REQUIRED before installing packages:
   qemu-system-x86 qemu-utils libvirt-daemon-system libvirt-clients libvirt-daemon-driver-qemu
   libslirp0 apparmor clang llvm libbpf-dev linux-libc-dev bpftool python3.
   Retain signed InRelease/index validation, exact versions and package SHA256s;
   simulate first; reject upgrades/removals outside approved list. No sandbox/LSM
   bypass. This generator does not invent an available-version or signature lock.
3. Assert reserved UID and GID {b.uid} and {b.gid} are ABSENT. Create a dedicated
   nologin/no-home/no-groups VM identity. Do not grant agents system libvirt access.
   Install binding.json root:root 0600 at /etc/project-bots/protected/{b.vm_id}/.
   Create /var/lib/project-bots-protected root:root 0700 and the UUID directory,
   with disk.qcow2 and serial.log accessible only to root and this VM UID as needed.
   Supply standalone <=2 GiB nested fixture disk, pinned SHA256 and verified Ubuntu
   cloud-image signed SHA256SUMS (installed Ubuntu keyring). No image exists here.
4. Copy {b.unit} to /etc/systemd/system, daemon-reload, start ONLY {b.unit}.
   Assert /sys/fs/cgroup/{b.unit} is root-owned/not delegated and populated 0.
   Its 768 MiB tree ceiling includes the 512 MiB QEMU guest; 1 CPU; 128 tasks.
5. Compile reviewed guard.c inside ROOT-OWNED staging (not this directory):
   clang -target bpfel -O2 -g -I/usr/include/x86_64-linux-gnu -c guard.c -o guard.o
   Require existing administrator-managed bpffs mount at /sys/fs/bpf; don't remount.
   Create root-only /sys/fs/bpf/project-bots/{b.vm_id}; fail if it exists.
   bpftool prog loadall guard.o /sys/fs/bpf/project-bots/{b.vm_id} type cgroup/skb
   bpftool cgroup attach /sys/fs/cgroup/{b.unit} cgroup_inet_ingress pinned /sys/fs/bpf/project-bots/{b.vm_id}/ingress multi
   bpftool cgroup attach /sys/fs/cgroup/{b.unit} cgroup_inet_egress pinned /sys/fs/bpf/project-bots/{b.vm_id}/egress multi
   Independently read back effective attachments, program IDs/tags and translated
   instruction dump; ensure both tags correspond to this compiled object. Store
   {{"ingress":"EXACT_TAG","egress":"EXACT_TAG"}} as root:root 0600 programs.json
   alongside binding.json. Never replace absent programs with a healthy assertion.
6. Review generated domain.xml and validate against installed libvirt schema.
   virsh --connect qemu:///system define ROOT_STAGED_DOMAIN_XML --validate
   virsh --connect qemu:///system autostart {b.vm_id} --disable
   Pin SHA256 of EXACT bytes from virsh dumpxml {b.vm_id} --inactive as domain.sha256.
   Verify dynamic AppArmor exact-domain profile, QEMU seccomp/NoNewPrivs and no caps;
   failure is BLOCKED, never disable sandbox to satisfy the readback.
7. Install authority service only after review. Create root:root 0600
   /etc/project-bots/protected-control.json with exact compute_uid/compute_gid.
   Compute identity is not the VM UID, root, or a libvirt-group member. Existing
   Machine Manager can opt in via machine_http.serve(..., protected=True) only on a
   separately installed service; existing default still uses session-libvirt.
8. Do NOT enable any unit, start any VM, or execute privileged harness until parent
   approval. The current production start/resume paths intentionally reject absent
   mandatory external monitoring. The lab harness only accepts paused launch and
   whole-tree kill; it NEVER resumes guest execution and cannot pass packet/S01-S15.

Rollback: keep definitions, disks, DB, serial and evidence. Stop exact nested VM
through authority after review, verify subtree empty. Do not auto-delete fences,
pins, units or evidence; no original/outer VM mutation is a rollback step.
''')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Unprivileged generation only; review before any administrator action')
    binding = json.loads(Path(args.binding).read_text())
    print(generate(binding, args.output))


if __name__ == '__main__':
    main()
