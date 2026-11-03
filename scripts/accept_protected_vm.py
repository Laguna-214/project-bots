#!/usr/bin/env python3
"""Opt-in PAUSED emulator/cgroup acceptance, NOT guest packet or S01-S15 acceptance.
Install this reviewed file root-owned at /opt/project-bots-protected/accept_protected_vm.py.
Run /usr/bin/python3 -I /opt/project-bots-protected/accept_protected_vm.py --confirm ...
No nested guest vCPU is resumed. No deletion or automatic recovery occurs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import uuid

LAB = '2f3ce848-c083-4674-8659-e2d9f0d37638'
VM = 'a3ec8c2c-a7a0-4164-a357-f006175d189e'
CONFIRM = 'PAUSED NESTED VM ONLY ' + VM + ' IN LAB ' + LAB


def prerequisites(confirmation):
    if confirmation != CONFIRM:
        raise ValueError('Exact scoped administrator confirmation required')
    if os.geteuid() != 0 or Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower() != LAB:
        raise PermissionError('Only administrator inside the already-approved disposable outer lab')
    source = Path(__file__).absolute()
    if source != Path('/opt/project-bots-protected/accept_protected_vm.py'):
        raise PermissionError('Install reviewed source at fixed root-owned location first')
    for node in [*source.parents, source]:
        info = node.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise PermissionError('Untrusted script/source ancestor')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm', required=True)
    args = parser.parse_args()
    prerequisites(args.confirm)
    # Validate installed project tree before the first project import.
    for file in [Path('/opt/project-bots-protected/project_bots'),
                 *Path('/opt/project-bots-protected/project_bots').rglob('*')]:
        info = file.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise PermissionError('Untrusted installed dependency tree')
    sys.dont_write_bytecode = True
    sys.path.insert(0, '/opt/project-bots-protected')
    from project_bots.protected_compute import ProtectedAuthority, KernelBoundary, ConflictError
    authority = ProtectedAuthority()
    if set(authority.bindings) != {VM}:
        raise ValueError('Lab harness requires ONLY its fixed nested fixture binding')
    b = authority.binding(VM)
    evidence = authority.root / ('paused-acceptance-' + str(uuid.uuid4()))
    evidence.mkdir(mode=0o700)
    report = {'lab': LAB, 'vm_id': VM, 'scope': 'paused emulator + kernel attachment + tree stop',
              'guest_execution': 'NOT RUN', 'packet_effect': 'NOT RUN', 'S01-S15': 'NOT RUN'}
    try:
        kernel = KernelBoundary(b)
        report['network_before'] = kernel.inspect()
        report['prepare'] = authority.prepare_paused(VM)
        report['members'] = kernel.members()
        report['paused_state'] = authority.detail(VM)
        if report['paused_state']['state'] != 'paused':
            raise RuntimeError('Guest is not observed paused')
        report['network_after'] = kernel.inspect()
        report['definition_sha256'] = hashlib.sha256(authority.virsh('dumpxml', VM, '--inactive').encode()).hexdigest()
    finally:
        # On ANY partial launch the durable intent/fence persists. Stop exact target;
        # leave definition/disk/logs/evidence, and never act on an outer/original VM.
        op = str(uuid.uuid4())
        report['stop_operation_id'] = op
        try:
            report['stop'] = authority.action(VM, 'force-stop', {'operation_id': op, 'confirmation': 'force-stop:' + VM})
            reconstructed = ProtectedAuthority()
            try:
                reconstructed.action(VM, 'start', {'operation_id': str(uuid.uuid4()), 'confirmation': 'start:' + VM})
            except ConflictError:
                report['durable_start_fence'] = 'denied after authority reconstruction'
            else:
                raise RuntimeError('Durable start fence failed')
            report['empty_after'] = KernelBoundary(b).empty()
            if not report['empty_after']:
                raise RuntimeError('VM subtree still populated')
        finally:
            (evidence / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'evidence': str(evidence), 'scope': report['scope'], 'guest_execution': 'NOT RUN'}))


if __name__ == '__main__':
    main()
