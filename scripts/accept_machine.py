#!/usr/bin/env python3
"""OPT-IN destructive real-host acceptance. Never run by unittest discovery.

Creates ONE disposable VM, starts, inspects, gracefully shuts down and deletes
that same UUID. On uncertainty, stops without forced shutdown/cleanup. Keep the
printed operation IDs and reconcile locally. This does not prove Desktop/SSH
readiness: those require the separate manual checks in docs/COMPUTE_HOST.md.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from project_bots.machine_client import MachineClient
from project_bots.service import env_reference

APPROVAL = 'CREATE START SHUTDOWN DELETE DISPOSABLE VM'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--token-env', default='PROJECT_BOTS_COMPUTE_TOKEN')
    parser.add_argument('--ca-file')
    parser.add_argument('--ssh-key-file', required=True)
    parser.add_argument('--template', default='ubuntu-desktop')
    parser.add_argument('--confirm-real-host-mutation', required=True, choices=[APPROVAL])
    args = parser.parse_args(argv)
    client = MachineClient(args.endpoint, os.environ.get(env_reference(args.token_env), ''), args.ca_file)
    print(json.dumps({'health': client.request('GET', '/v1/health')}), flush=True)
    key = Path(args.ssh_key_file).read_text().strip()
    # Catalog IDs, never image paths. This explicit opt-in authorizes only these actions.
    op = str(uuid.uuid4())
    print(json.dumps({'create_operation': op, 'planned_vm_id': op}), flush=True)
    vm = client.request('POST', '/v1/vms', {'template': args.template, 'cpus': 2, 'ram_mib': 4096, 'disk_gib': 24,
                                         'ssh_key': key, 'operation_id': op, 'confirmation': 'create'})
    vm_id = vm['id']
    if vm_id != op:
        raise RuntimeError('Unexpected VM identity; stop and inspect manually')
    def action(verb):
        action_op = str(uuid.uuid4())
        print(json.dumps({'action': verb, 'operation_id': action_op, 'vm_id': vm_id}), flush=True)
        return client.request('POST', '/v1/vms/' + vm_id + '/' + verb,
                              {'confirmation': verb + ':' + vm_id, 'operation_id': action_op})
    def wait(state):
        for _ in range(150):
            detail = client.request('GET', '/v1/vms/' + vm_id)
            if detail['state'] == state:
                print(json.dumps({'observed': detail}), flush=True)
                return
            time.sleep(2)
        raise RuntimeError('VM did not reach expected state; no forced action or cleanup attempted')
    action('start'); wait('running')
    # Allow ACPI/guest boot before requesting graceful shutdown. Desktop install may
    # still be running: perform readiness checks separately before accepting Stage 2.
    time.sleep(60)
    action('shutdown'); wait('shut off')
    deleted = action('delete')
    if deleted['phase'] != 'deleted' or any(v['id'] == vm_id for v in client.request('GET', '/v1/vms')):
        raise RuntimeError('Deletion did not verify')
    print('Real libvirt core lifecycle verified for disposable VM ' + vm_id, flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        print('Acceptance stopped: outcome may be uncertain. Inspect printed operation/VM IDs; no automatic retry or destructive cleanup.', file=sys.stderr)
        sys.exit(1)
