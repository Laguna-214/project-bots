"""Constrained session-libvirt boundary. Only this module constructs host commands."""
import base64
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import uuid
from xml.etree import ElementTree as ET

from .service import fields, identifier, ConflictError

NS = 'urn:project-bots:managed:v1'
ET.register_namespace('pb', NS)


class ComputeUnavailable(Exception):
    """Redacted host failure; an operation may have taken effect."""


def run_command(argv):
    try:
        return subprocess.run(argv, check=True, capture_output=True, text=True, timeout=120,
                              env={**os.environ, 'LC_ALL': 'C'}).stdout
    except (OSError, subprocess.SubprocessError):
        raise ComputeUnavailable('Host command failed or timed out; inspect before retrying') from None


class ComputeService:
    def __init__(self, state, catalog, runner=run_command, network_guard=None):
        # Installed only by a trusted host launcher with independently verified
        # runtime/netns bindings; never configured through the HTTP API.
        self.network_guard = network_guard
        self.root = Path(state).expanduser().absolute()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.is_symlink() or self.root.stat().st_mode & 0o077:
            raise ValueError('Compute state requires a private, non-symlink directory')
        self.catalog = Path(catalog).absolute()
        self.trusted_file(self.catalog)
        self.run = runner
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO config(id, owner) VALUES (1, ?)', (str(uuid.uuid4()),))
            self.owner = db.execute('SELECT owner FROM config').fetchone()[0]
            db.execute('CREATE TABLE IF NOT EXISTS vms (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, target TEXT NOT NULL, digest TEXT NOT NULL, data TEXT NOT NULL)')

    @contextmanager
    def db(self):
        path = self.root / 'compute.db'
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600); os.close(fd)
        db = sqlite3.connect(path, timeout=10)
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback(); raise
        finally:
            db.close()

    @staticmethod
    def trusted_file(path):
        if path.resolve() != path or not path.is_file() or path.stat().st_uid not in (0, os.getuid()) or path.stat().st_mode & 0o022 or path.parent.stat().st_mode & 0o022:
            raise ValueError('Catalog/images require trusted owner and no group/other write or symlinks')

    def host_resources(self):
        import shutil
        memory = {}
        for line in Path('/proc/meminfo').read_text().splitlines():
            name, value = line.split(':', 1)
            memory[name] = int(value.split()[0]) // 1024
        return {'cpu_count': os.cpu_count() or 1, 'memory_total_mib': memory['MemTotal'],
                'memory_available_mib': memory['MemAvailable'],
                'storage_free_gib': shutil.disk_usage(self.root).free // 1024**3}

    def capacity(self):
        host = self.host_resources()
        cap = os.environ.get('PROJECT_BOTS_COMPUTE_RAM_CAP', '')
        try:
            ram_cap = int(cap)
            if ram_cap < 2048:
                raise ValueError
        except ValueError:
            ram_cap = 32768
        try:
            cpu_cap = int(os.environ.get('PROJECT_BOTS_COMPUTE_CPU_CAP', '8'))
            if cpu_cap < 1:
                raise ValueError
        except ValueError:
            cpu_cap = 8
        return {'cpus': min(cpu_cap, max(0, host['cpu_count'] - 2)),
                'ram_mib': min(ram_cap, max(0, host['memory_total_mib'] - 8192)),
                'disk_gib': max(0, host['storage_free_gib'] - 10)}

    def reserve(self, requested, capacity=None, exclude=None):
        capacity = capacity or self.capacity()
        with self.db() as db:
            records = [json.loads(row[0]) for row in db.execute('SELECT data FROM vms')]
        active = [v for v in records if v['phase'] != 'deleted' and v['id'] != exclude]
        # CPU/RAM are reserved even when off. Sparse disks reserve their full logical size.
        for key in ('cpus', 'ram_mib', 'disk_gib'):
            if requested[key] + sum(v[key] for v in active) > capacity[key]:
                raise ValueError('Host resource reservation policy exceeded')

    def health(self):
        from .telemetry import collect_metrics
        self.virsh('version')
        return {'backend': 'libvirt', 'libvirt_uri': 'qemu:///session', **self.host_resources(),
                'kvm_accessible': os.access('/dev/kvm', os.R_OK | os.W_OK),
                'templates': sorted(json.loads(self.catalog.read_text())), 'policy': self.capacity(),
                'network': 'session user-mode passt; loopback SSH forwarding', 'gpu_passthrough': False,
                'utilization': collect_metrics()}

    def virsh(self, *args):
        return self.run(['virsh', '--connect', 'qemu:///session', *args])

    def save(self, vm):
        with self.db() as db:
            db.execute('INSERT INTO vms VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',
                       (vm['id'], json.dumps(vm)))

    def record(self, vm_id):
        if identifier(vm_id) is None:
            raise ValueError('VM UUID required')
        with self.db() as db:
            row = db.execute('SELECT data FROM vms WHERE id=?', (vm_id,)).fetchone()
        if not row:
            raise LookupError('VM not found')
        return json.loads(row[0])

    def operation(self, operation_id):
        if identifier(operation_id) is None:
            raise ValueError('Operation UUID required')
        with self.db() as db:
            row = db.execute('SELECT data FROM operations WHERE id=?', (operation_id,)).fetchone()
        if not row:
            raise LookupError('Operation not found')
        return json.loads(row[0])

    def execute(self, target, action, data, callback):
        import time
        if not isinstance(data, dict) or identifier(data.get('operation_id')) is None:
            raise ValueError('Operation UUID required')
        op_id = data['operation_id']
        digest = hashlib.sha256(json.dumps([target, action, data], sort_keys=True).encode()).hexdigest()
        # Serialize across HTTP threads AND processes without keeping SQL open over commands.
        fd = os.open(self.root / 'mutation.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as lock:
            if self._locked(lock) is False:
                raise ConflictError('Compute host busy; retry same operation ID')
            with self.db() as db:
                row = db.execute('SELECT digest, data FROM operations WHERE id=?', (op_id,)).fetchone()
                if row:
                    previous = json.loads(row[1])
                    if row[0] != digest or previous['status'] != 'succeeded':
                        raise ConflictError('Operation conflicts, is incomplete, or needs local reconciliation')
                    return previous['result']
                for other in db.execute('SELECT data FROM operations WHERE target=?', (target,)):
                    if action != 'force-stop' and json.loads(other[0])['status'] in ('running', 'unknown'):
                        raise ConflictError('Uncertain prior operation requires local reconciliation')
                operation = {'id': op_id, 'target': target, 'action': action, 'status': 'running', 'started_at': time.time()}
                db.execute('INSERT INTO operations VALUES (?, ?, ?, ?)', (op_id, target, digest, json.dumps(operation)))
            try:
                self._mutation_started = False
                result = callback()
                operation.update(status='succeeded', result=result)
            except (ValueError, LookupError, ConflictError):
                if self._mutation_started:
                    operation.update(status='unknown', error='Mutation started; local reconciliation required')
                    raise ComputeUnavailable('Host outcome uncertain; inspect operation and VM') from None
                operation.update(status='rejected', error='Request rejected')
                raise
            except Exception:
                operation.update(status='unknown', error='Host outcome uncertain; inspect VM and reconcile locally')
                raise ComputeUnavailable('Host outcome uncertain; inspect operation and VM before retrying') from None
            finally:
                operation['finished_at'] = time.time()
                with self.db() as db:
                    db.execute('UPDATE operations SET data=? WHERE id=?', (json.dumps(operation), op_id))
            return result

    @staticmethod
    def _locked(lock):
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    def create(self, data):
        target = data.get('operation_id') if isinstance(data, dict) else None
        return self.execute(target, 'create', data, lambda: self._create(data))

    def _create(self, data):
        fields(data, ('template', 'cpus', 'ram_mib', 'disk_gib', 'ssh_key', 'confirmation', 'operation_id'),
               ('template', 'cpus', 'ram_mib', 'disk_gib', 'ssh_key', 'confirmation', 'operation_id'))
        if data['confirmation'] != 'create':
            raise ValueError('Explicit create confirmation required')
        for key, low, high in [('cpus', 1, 8), ('ram_mib', 2048, 32768), ('disk_gib', 16, 256)]:
            if type(data[key]) is not int or not low <= data[key] <= high:
                raise ValueError('Resource outside policy')
        key = data['ssh_key']
        if not isinstance(key, str) or len(key) > 512 or not key.startswith('ssh-ed25519 ') or len(key.split()) != 2:
            raise ValueError('Only ed25519 public keys accepted')
        try:
            raw = base64.b64decode(key.split()[1], validate=True)
            if len(raw) != 51 or raw[:19] != b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20':
                raise ValueError
        except Exception:
            raise ValueError('Invalid ed25519 public key') from None
        self.trusted_file(self.catalog)
        catalog = json.loads(self.catalog.read_text())
        if not isinstance(data['template'], str) or data['template'] not in catalog:
            raise ValueError('Unknown template')
        template = catalog[data['template']]
        image = Path(template['image'])
        self.trusted_file(image)
        if not image.is_absolute() or image.resolve() != image or not image.is_file():
            raise ValueError('Unsafe template path')
        with image.open('rb') as source:
            hasher = hashlib.sha256()
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                hasher.update(chunk)
            digest = hasher.hexdigest()
        if digest != template['sha256']:
            raise ValueError('Template hash mismatch')
        info = json.loads(self.run(['qemu-img', 'info', '--output=json', str(image)]))
        if info['format'] != 'qcow2' or info.get('backing-filename') or info['virtual-size'] > data['disk_gib'] * 1024**3:
            raise ValueError('Template must be standalone qcow2 within requested size')
        self.reserve(data)
        with self.db() as db:
            ports = {json.loads(row[0]).get('ssh_port') for row in db.execute('SELECT data FROM vms') if json.loads(row[0])['phase'] != 'deleted'}
        ssh_port = next((p for p in range(22000, 22100) if p not in ports), None)
        if ssh_port is None:
            raise ValueError('SSH port reservation exhausted')
        vm_id = data['operation_id']; directory = self.root / vm_id
        directory.mkdir(mode=0o700)
        vm = {'id': vm_id, 'template': data['template'], 'cpus': data['cpus'], 'ram_mib': data['ram_mib'],
              'disk_gib': data['disk_gib'], 'ssh_port': ssh_port, 'desired': 'shut off', 'phase': 'provisioning'}
        self.save(vm)
        self._mutation_started = True
        disk = directory / 'disk.qcow2'
        self.run(['qemu-img', 'convert', '-f', 'qcow2', '-O', 'qcow2', str(image), str(disk)])
        disk.chmod(0o600)
        self.run(['qemu-img', 'resize', '-f', 'qcow2', str(disk), str(data['disk_gib']) + 'G'])
        cloud = {'users': [{'name': 'bot', 'lock_passwd': True, 'sudo': [], 'ssh_authorized_keys': [key]}],
                 'disable_root': True, 'ssh_pwauth': False,
                 'packages': ['ubuntu-desktop-minimal', 'openssh-server', 'qemu-guest-agent'], 'package_update': True,
                 # Desktop's netplan renderer is NetworkManager, not networkd. Run after
                 # package installation; retire only the obsolete renderer's online wait.
                 'runcmd': [['systemctl', 'enable', '--now', 'NetworkManager.service'],
                            ['systemctl', 'disable', '--now', 'systemd-networkd-wait-online.service'],
                            ['systemctl', 'reset-failed', 'systemd-networkd-wait-online.service']]}
        (directory / 'user-data').write_text('#cloud-config\n' + json.dumps(cloud))
        (directory / 'meta-data').write_text(json.dumps({'instance-id': vm_id, 'local-hostname': 'pb-' + vm_id[:8]}))
        self.run(['cloud-localds', str(directory / 'seed.iso'), str(directory / 'user-data'), str(directory / 'meta-data')])
        (directory / 'domain.xml').write_text(self.xml(vm))
        self.virsh('define', str(directory / 'domain.xml'), '--validate')
        vm['phase'] = 'defined'; self.save(vm)
        return self.verified_result(vm_id)

    def verified_result(self, vm_id):
        result = self.detail(vm_id)
        if result['state'] == 'unavailable':
            raise ComputeUnavailable('Mutation cannot be observed; inspect operation before retrying')
        return result

    def xml(self, vm):
        root = ET.Element('domain', type='kvm')
        def add(parent, tag, value=None, **attrs):
            node = ET.SubElement(parent, tag, attrs)
            if value is not None:
                node.text = str(value)
            return node
        add(root, 'name', 'pb-' + vm['id']); add(root, 'uuid', vm['id'])
        add(add(root, 'metadata'), '{' + NS + '}owner', self.owner)
        add(root, 'memory', vm['ram_mib'], unit='MiB'); add(root, 'vcpu', vm['cpus'])
        add(add(root, 'os'), 'type', 'hvm', arch='x86_64')
        add(root, 'features').append(ET.Element('acpi'))
        add(root, 'cpu', mode='host-model')
        devices = add(root, 'devices')
        for name, device, target, bus in [('disk.qcow2', 'disk', 'vda', 'virtio'), ('seed.iso', 'cdrom', 'sda', 'sata')]:
            disk = add(devices, 'disk', type='file', device=device)
            add(disk, 'driver', name='qemu', type='qcow2' if device == 'disk' else 'raw')
            add(disk, 'source', file=str(self.root / vm['id'] / name)); add(disk, 'target', dev=target, bus=bus)
            if device == 'cdrom':
                add(disk, 'readonly')
        interface = add(devices, 'interface', type='user')
        add(interface, 'model', type='virtio'); add(interface, 'backend', type='passt')
        add(add(interface, 'portForward', proto='tcp', address='127.0.0.1'), 'range', start=str(vm['ssh_port']), to='22')
        add(add(devices, 'channel', type='unix'), 'target', type='virtio', name='org.qemu.guest_agent.0')
        add(devices, 'graphics', type='spice', autoport='yes', listen='127.0.0.1')
        add(add(devices, 'video'), 'model', type='vga')
        return ET.tostring(root, encoding='unicode')

    def detail(self, vm_id):
        vm = self.record(vm_id)
        if vm.get('phase') == 'deleted':
            return {**vm, 'state': 'deleted'}
        try:
            xml = ET.fromstring(self.virsh('dumpxml', vm_id))
        except ComputeUnavailable:
            return {**vm, 'state': 'unavailable', 'error': 'Domain observation failed; do not infer absent or retry mutations'}
        sources = [n.get('file') for n in xml.findall('devices/disk/source')]
        expected = [str(self.root / vm_id / n) for n in ('disk.qcow2', 'seed.iso')]
        if xml.findtext('uuid') != vm_id or xml.findtext('name') != 'pb-' + vm_id or xml.findtext('metadata/{' + NS + '}owner') != self.owner or sources != expected:
            raise ConflictError('VM ownership mismatch')
        directory = self.root / vm_id
        if directory.resolve() != directory or any((directory / name).is_symlink() or not (directory / name).is_file() for name in ('disk.qcow2', 'seed.iso')):
            raise ConflictError('VM storage ownership mismatch')
        graphics = xml.find('devices/graphics')
        if graphics is None or graphics.get('listen') != '127.0.0.1' or xml.find('devices/hostdev') is not None:
            raise ConflictError('VM isolation policy mismatch')
        console = {'type': 'spice', 'listen': '127.0.0.1', 'port': graphics.get('port'),
                   'ssh_user': 'bot', 'ssh_port': vm['ssh_port'], 'requires_tunnel': True}
        return {**vm, 'state': self.virsh('domstate', vm_id).strip(), 'console': console}

    def list(self):
        with self.db() as db:
            ids = [row[0] for row in db.execute('SELECT id FROM vms')]
        return [vm for vm_id in ids if (vm := self.detail(vm_id))['phase'] != 'deleted']

    def network_status(self, vm_id):
        detail = self.detail(vm_id)  # same UUID/owner/storage checks as lifecycle
        if detail['state'] in ('unavailable', 'deleted'):
            raise ComputeUnavailable('Cannot verify network target ownership')
        if self.network_guard is None:
            return {'vm_id': vm_id, 'blocked': False, 'status': 'unavailable',
                    'source': 'No OS-verified runtime/network namespace binding installed'}
        result = self.network_guard.inspect(vm_id)
        if result.get('runtime_kind') != 'libvirt-vm' or result.get('vm_id') != vm_id:
            raise ComputeUnavailable('Network adapter has no verified libvirt VM binding')
        return result

    def action(self, vm_id, action, data):
        if identifier(vm_id) is None:
            raise ValueError('VM UUID required')
        return self.execute(vm_id, action, data, lambda: self._action(vm_id, action, data))

    def _action(self, vm_id, action, data):
        import re
        allowed = {'start', 'shutdown', 'restart', 'pause', 'resume', 'delete', 'resources', 'snapshot-create', 'snapshot-restore', 'force-stop', 'network-block'}
        if action not in allowed:
            raise ValueError('Unsupported action')
        extra = ('cpus', 'ram_mib', 'disk_gib') if action == 'resources' else ('snapshot',) if action.startswith('snapshot-') else ()
        fields(data, ('confirmation', 'operation_id', *extra), ('confirmation', 'operation_id', *extra))
        if data['confirmation'] != action + ':' + vm_id:
            raise ValueError('Explicit per-action VM confirmation required')
        vm = self.detail(vm_id)
        state = vm.pop('state'); vm.pop('console', None)
        if vm['phase'] != 'defined':
            raise ConflictError('VM is not in defined phase')
        if vm.get('security_contained') and action not in ('force-stop', 'network-block', 'shutdown'):
            raise ConflictError('Host containment latched; offline administrator reconciliation required')
        if action in ('force-stop', 'network-block'):
            # Persist before touching the external system. A timeout, service
            # restart, or later stopped observation cannot silently permit start.
            # There is intentionally no HTTP unlatch/admin-assertion endpoint.
            vm.update(security_contained=True, containment_operation_id=data['operation_id'], desired='shut off')
            self.save(vm)
        if action in ('delete', 'resources', 'snapshot-create', 'snapshot-restore') and state != 'shut off':
            raise ConflictError('VM must be shut off')
        directory = self.root / vm_id; disk = directory / 'disk.qcow2'
        if action == 'network-block':
            if self.network_guard is None or state == 'unavailable':
                raise ConflictError('No verified host network adapter/target')
            self._mutation_started = True
            self.network_guard.block(vm_id)
            result = self.network_status(vm_id)
            if result.get('blocked') is not True:
                raise ComputeUnavailable('Network enforcement could not be verified')
            return result
        if action == 'force-stop':
            # libvirt destroy stops execution only: retain domain, disks and evidence.
            # Never infer absence from a failed observation.
            if state not in ('running', 'paused', 'in shutdown', 'blocked', 'pmsuspended', 'shut off', 'crashed'):
                raise ConflictError('VM state cannot be safely force-stopped')
            if state not in ('shut off', 'crashed'):
                self._mutation_started = True
                self.virsh('destroy', vm_id)
            vm['desired'] = 'shut off'
        elif action == 'resources':
            for name, low, high in [('cpus', 1, 8), ('ram_mib', 2048, 32768), ('disk_gib', vm['disk_gib'], 256)]:
                if type(data[name]) is not int or not low <= data[name] <= high:
                    raise ValueError('Invalid resource bounds; disks cannot shrink')
            self.reserve(data, exclude=vm_id)
            if vm.get('snapshots') and data['disk_gib'] != vm['disk_gib']:
                raise ConflictError('Disk growth requires no snapshots')
            self._mutation_started = True
            if data['disk_gib'] > vm['disk_gib']:
                self.run(['qemu-img', 'resize', '-f', 'qcow2', str(disk), str(data['disk_gib']) + 'G'])
            vm.update({name: data[name] for name in extra})
            (directory / 'domain.xml').write_text(self.xml(vm))
            self.virsh('define', str(directory / 'domain.xml'), '--validate')
        elif action.startswith('snapshot-'):
            info = json.loads(self.run(['qemu-img', 'info', '--output=json', str(disk)]))
            if info.get('format') != 'qcow2' or info.get('backing-filename'):
                raise ConflictError('Offline snapshots require a standalone qcow2 disk')
            name = data['snapshot']
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', name):
                raise ValueError('Invalid snapshot name')
            snapshots = vm.setdefault('snapshots', [])
            if (action == 'snapshot-create' and name in snapshots) or (action == 'snapshot-restore' and name not in snapshots):
                raise ConflictError('Snapshot does not allow this action')
            self._mutation_started = True
            self.run(['qemu-img', 'snapshot', '-c' if action == 'snapshot-create' else '-a', name, str(disk)])
            if action == 'snapshot-create':
                snapshots.append(name)
        elif action == 'delete':
            self._mutation_started = True
            self.virsh('undefine', vm_id)
            for name in ('disk.qcow2', 'seed.iso', 'domain.xml', 'user-data', 'meta-data'):
                (directory / name).unlink()
            directory.rmdir()
            vm['phase'] = 'deleted'; vm['desired'] = 'deleted'
        else:
            expected = {'start': ('shut off',), 'shutdown': ('running', 'paused'), 'restart': ('running',), 'pause': ('running',), 'resume': ('paused',)}
            if state not in expected[action]:
                raise ConflictError('VM state does not allow action')
            if action == 'start' and self.host_resources()['memory_available_mib'] < vm['ram_mib'] + 4096:
                raise ConflictError('Insufficient available host RAM; preserve desktop and Ollama headroom')
            self._mutation_started = True
            self.virsh({'restart': 'reboot', 'pause': 'suspend'}.get(action, action), vm_id)
            vm['desired'] = {'shutdown': 'shut off', 'pause': 'paused'}.get(action, 'running')
        self.save(vm)
        return self.verified_result(vm_id)
