"""Reviewed VM provisioning workflow; remote errors are never blindly retried."""
import uuid
import shlex


def guest_ssh(key, known, compute_key, compute_host, ssh_port, vm_id):
    proxy = shlex.join(['ssh', '-i', str(compute_key), '-o', 'IdentitiesOnly=yes', '-o',
                        'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-W',
                        '127.0.0.1:'+str(ssh_port), compute_host])
    return ['ssh', '-T', '-i', str(key), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile='+str(known),
            '-o', 'HostKeyAlias=pb-'+str(uuid.UUID(vm_id)), '-o', 'ProxyCommand='+proxy,
            '-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=20', '-o', 'ServerAliveCountMax=3']


def tunnel_unit(key, known, compute_key, compute_host, ssh_port, gateway_port, vm_id):
    command=guest_ssh(key,known,compute_key,compute_host,ssh_port,vm_id)
    command += ['-L',f'127.0.0.1:{gateway_port}:127.0.0.1:18789',
                '-L',f'127.0.0.1:{gateway_port+1}:127.0.0.1:18790',
                '-R','127.0.0.1:11434:127.0.0.1:21435','bot@127.0.0.1','sleep','infinity']
    # systemd's own quoting, not a shell command; %% protects literal specifiers.
    import json
    argv=' '.join(json.dumps(x).replace('%','%%') for x in command)
    return '[Unit]\nDescription=Project Bots isolated worker tunnel '+vm_id+'\nAfter=network-online.target\n[Service]\nExecStart='+argv+'\nRestart=always\nRestartSec=5\nUMask=0077\n[Install]\nWantedBy=default.target\n'



def ensure_vm(api, manifest, save, ssh_key):
    """Persist intent before supported API calls; resume only observed known VMs."""
    vm_id = str(uuid.UUID(manifest['vm_id']))
    existing = next((v for v in api('/vms') if v['id'] == vm_id), None)
    if existing is None:
        if manifest.get('phase'):
            raise RuntimeError('Prior provisioning intent needs operation inspection; refusing duplicate create')
        manifest['phase'] = 'create-intent'
        save()
        api('/vms', {'operation_id': vm_id, 'confirmation': 'create', 'template': 'ubuntu-desktop',
                     'cpus': 1, 'ram_mib': 8192, 'disk_gib': 32, 'ssh_key': ssh_key})
        existing = api('/vms/' + vm_id)
    if existing['state'] == 'shut off':
        if manifest.get('start_operation'):
            raise RuntimeError('Prior start intent needs operation inspection; refusing replay')
        manifest['start_operation'] = str(uuid.uuid4())
        save()
        api('/vms/' + vm_id + '/start', {'operation_id': manifest['start_operation'], 'confirmation': 'start:' + vm_id})
        existing = api('/vms/' + vm_id)
    if existing['state'] != 'running':
        raise RuntimeError('VM not running; inspect before continuing')
    manifest.update(phase='vm-running', ssh_port=existing['ssh_port'])
    save()
    return existing
