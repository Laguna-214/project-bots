"""Opt-in root system-libvirt authority. Never imported as root from a worker checkout.

Installation is offline/admin-only. No provisioning, recovery, XML, PID or command
input is accepted over the control protocol. See PROTECTED_VM_ENFORCEMENT.md.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import hashlib
import ipaddress
import json
import os
import socket
import sqlite3
import stat
import struct
import subprocess
import uuid
from xml.etree import ElementTree as ET

from .compute import ComputeUnavailable, NS
from .service import ConflictError


def canonical(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError('Canonical UUID required')
    return value


def trusted(path, directory=False):
    """Check EVERY component, including source/config ancestors; root-owned only."""
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute trusted path required')
    for node in [*reversed(path.parents), path]:
        info = node.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Root ownership, no symlinks or group/other writes required')
    if directory != path.is_dir() or not directory and not path.is_file():
        raise ValueError('Wrong trusted object type')
    return path


@dataclass(frozen=True)
class Binding:
    vm_id: str
    owner: str
    uid: int
    gid: int
    broker_ipv4: str
    broker_port: int

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise ValueError('Exact static binding required')
        canonical(value['vm_id']); canonical(value['owner'])
        for key in ('uid', 'gid'):
            if type(value[key]) is not int or not 60000 <= value[key] <= 64999:
                raise ValueError('Dedicated administrator-provisioned identity required')
        address = ipaddress.IPv4Address(value['broker_ipv4'])
        if address.is_loopback or address.is_unspecified or address.is_multicast or address.is_link_local:
            raise ValueError('Explicit unicast non-loopback broker required')
        if type(value['broker_port']) is not int or not 1024 <= value['broker_port'] <= 65535:
            raise ValueError('Unprivileged exact broker TCP port required')
        return cls(**value)

    @property
    def unit(self):
        return 'pb' + self.vm_id.replace('-', '') + '.slice'

    @property
    def cgroup(self):
        return Path('/sys/fs/cgroup') / self.unit

    @property
    def pin(self):
        return Path('/sys/fs/bpf/project-bots') / self.vm_id


def network_source(binding):
    """No maps/configurable policy; compile once per immutable binding, x86 LE."""
    address = int.from_bytes(ipaddress.IPv4Address(binding.broker_ipv4).packed, 'little')
    port = int.from_bytes(binding.broker_port.to_bytes(2, 'big'), 'little')
    return '''#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
struct ip4 { unsigned char vihl, tos; unsigned short len, id, frag;
 unsigned char ttl, proto; unsigned short sum; unsigned int src, dst; };
struct ports { unsigned short src, dst; };
static __always_inline int check(struct __sk_buff *skb, int incoming) {
 struct ip4 ip; struct ports p;
 if (bpf_skb_load_bytes(skb, 0, &ip, sizeof(ip))) return 0;
 /* Only IPv4 without options/fragments, TCP. IPv6 and every other protocol deny. */
 if (ip.vihl != 0x45 || ip.proto != 6 || (ip.frag & 0xff3f)) return 0;
 if (bpf_skb_load_bytes(skb, 20, &p, sizeof(p))) return 0;
 return incoming ? (ip.src == BROKER && p.src == PORT) :
                   (ip.dst == BROKER && p.dst == PORT);
}
SEC("cgroup_skb/egress") int egress(struct __sk_buff *skb) { return check(skb, 0); }
SEC("cgroup_skb/ingress") int ingress(struct __sk_buff *skb) { return check(skb, 1); }
char LICENSE[] SEC("license") = "GPL";
'''.replace('BROKER', f'0x{address:08x}').replace('PORT', hex(port))


def run(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, check=True, timeout=20,
                              env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'}).stdout
    except (OSError, subprocess.SubprocessError):
        raise ComputeUnavailable('Protected host action/readback unavailable; retain operation ID') from None


def validate_xml(text, b):
    """Supplement pinned inactive XML hash; no external net backend or host device."""
    root = ET.fromstring(text)
    if (root.tag != 'domain' or root.get('type') not in ('kvm', 'qemu') or
            root.findtext('uuid') != b.vm_id or root.findtext('name') != 'pb-' + b.vm_id or
            root.findtext('metadata/{' + NS + '}owner') != b.owner or
            root.findtext('resource/partition') != '/' + b.unit[:-6]):
        raise ConflictError('Protected domain owner/partition mismatch')
    dac = root.find("seclabel[@model='dac']")
    if dac is None or dac.get('type') != 'static' or dac.findtext('label') != '+' + str(b.uid) + ':+' + str(b.gid):
        raise ConflictError('Dedicated DAC identity required')
    interfaces = root.findall('devices/interface')
    if len(interfaces) != 1 or interfaces[0].get('type') != 'user' or interfaces[0].find('backend') is not None:
        raise ConflictError('Only in-process QEMU user networking is permitted')
    if any(n.tag.split('}')[-1] in {'commandline', 'hostdev', 'filesystem', 'redirdev', 'graphics', 'portForward', 'vsock'} for n in root.iter()):
        raise ConflictError('External backend, shared device or alternate control path prohibited')
    return root


class KernelBoundary:
    def __init__(self, binding, runner=run):
        self.b = binding
        self.run = runner

    def inspect(self):
        b = self.b
        trusted(b.cgroup, directory=True)
        trusted(b.pin, directory=True)
        # The administrator records immutable program tags, not caller-supplied IDs.
        config = trusted(Path('/etc/project-bots/protected') / b.vm_id / 'programs.json')
        expected = json.loads(config.read_text())
        attached = json.loads(self.run(['/usr/sbin/bpftool', '-j', 'cgroup', 'show', str(b.cgroup), 'effective']))
        for hook in ('ingress', 'egress'):
            pinned = json.loads(self.run(['/usr/sbin/bpftool', '-j', 'prog', 'show', 'pinned', str(b.pin / hook)]))
            if isinstance(pinned, list):
                pinned = pinned[0]
            matches = [p for p in attached if p.get('attach_type') in (hook, 'cgroup_inet_' + hook) and p.get('id') == pinned.get('id')]
            if (pinned.get('tag') != expected[hook] or pinned.get('type') != 'cgroup_skb' or not matches):
                raise ComputeUnavailable('Kernel packet fence missing or replaced')
        return {'status': 'enforced', 'vm_id': b.vm_id, 'runtime_kind': 'libvirt-vm',
                'blocked': False, 'policy': 'broker-only-tcp-ipv4; all IPv6 denied',
                'cgroup': str(b.cgroup), 'source': 'effective cgroup BPF + root-pinned program tags'}

    def empty(self):
        return 'populated 0' in (self.b.cgroup / 'cgroup.events').read_text().splitlines()

    def kill(self):
        # Kernel kills the subtree atomically, not a collected/possibly reused PID list.
        (self.b.cgroup / 'cgroup.kill').write_text('1')
        import time
        for _ in range(100):
            if self.empty():
                return
            time.sleep(.05)
        raise ComputeUnavailable('Whole VM subtree is not confirmed empty')

    def members(self):
        """Root-owned descendants, same dedicated uid/gid, no network helper escape."""
        b = self.b
        paths = [b.cgroup, *b.cgroup.rglob('*')]
        pids = set()
        for path in paths:
            if path.is_dir():
                info = path.stat()
                if info.st_uid != 0 or info.st_mode & 0o022:
                    raise ComputeUnavailable('VM cgroup delegated or writable')
                pids.update(int(x) for x in (path / 'cgroup.procs').read_text().split())
        if not pids:
            raise ComputeUnavailable('No VM cgroup members')
        qemu = 0
        for pid in pids:
            status = Path('/proc', str(pid), 'status').read_text()
            values = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
            if ({int(x) for x in values['Uid'].split()} != {b.uid} or
                    {int(x) for x in values['Gid'].split()} != {b.gid} or
                    int(values['CapEff'].strip(), 16) != 0 or
                    values.get('NoNewPrivs', '').strip() != '1' or
                    values.get('Seccomp', '').strip() != '2'):
                raise ComputeUnavailable('VM process identity/sandbox mismatch')
            command = Path('/proc', str(pid), 'cmdline').read_bytes().split(b'\0')
            exe = os.readlink('/proc/' + str(pid) + '/exe')
            if exe == '/usr/bin/qemu-system-x86_64' and b.vm_id.encode() in command:
                qemu += 1
            else:
                # Threads are not cgroup.procs entries. No passt/slirp helper process.
                raise ComputeUnavailable('Unexpected VM process/backend')
            label = Path('/proc', str(pid), 'attr/current').read_text().strip()
            if label != 'libvirt-' + b.vm_id + ' (enforce)':
                raise ComputeUnavailable('Enforcing exact libvirt AppArmor profile absent')
        if qemu != 1:
            raise ComputeUnavailable('Exact emulator identity missing')
        # Also reject this reserved UID anywhere outside the protected subtree.
        for entry in Path('/proc').iterdir():
            if entry.name.isdigit():
                try:
                    if entry.stat().st_uid == b.uid and int(entry.name) not in pids:
                        raise ComputeUnavailable('Reserved VM UID escaped cgroup')
                except FileNotFoundError:
                    pass
        return sorted(pids)


class ProtectedAuthority:
    """Backend accepted by machine_http.make_handler; offline-configured VMs only."""
    def __init__(self, config='/etc/project-bots/protected', state='/var/lib/project-bots-protected', runner=run):
        self.config = trusted(config, directory=True)
        self.root = trusted(state, directory=True)
        self.run = runner
        self.bindings = {}
        for directory in self.config.iterdir():
            canonical(directory.name)
            value = Binding.parse(json.loads(trusted(directory / 'binding.json').read_text()))
            if value.vm_id != directory.name or any(value.uid == b.uid or value.gid == b.gid for b in self.bindings.values()):
                raise ValueError('Binding/identity collision')
            self.bindings[value.vm_id] = value
        dbpath = self.root / 'authority.db'
        if dbpath.exists():
            trusted(dbpath)
        with self.db() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS fences(vm TEXT PRIMARY KEY, op TEXT NOT NULL);'
                             'CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, digest TEXT, data TEXT);')
        os.chmod(dbpath, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.root / 'authority.db', timeout=20)
        try:
            db.execute('PRAGMA synchronous=FULL')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def prepare_paused(self, vm_id):
        import fcntl
        with (self.root / 'authority.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return self._prepare_paused(vm_id)

    def _prepare_paused(self, vm_id):
        """Offline administrator/lab seam only; never exposed on the socket.

        Guest vCPUs remain paused. This is NOT authorization to resume without
        mandatory monitoring. Unknown launch/verification latches the target.
        """
        b, state = self.observe(vm_id)
        with self.db() as db:
            if db.execute('SELECT 1 FROM fences WHERE vm=?', (vm_id,)).fetchone():
                raise ConflictError('Durable fence set')
        kernel = KernelBoundary(b, self.run)
        kernel.inspect()
        if state != 'shut off' or not kernel.empty():
            raise ConflictError('Fresh stopped empty boundary required')
        op = str(uuid.uuid4())
        record = {'id': op, 'owner': b.owner, 'vm_id': vm_id, 'action': 'prepare-paused',
                  'status': 'requested_unverified'}
        with self.db() as db:
            # This offline, single-use acceptance seam intentionally never clears
            # its durable fence, including success. No online resume authority.
            db.execute('INSERT INTO fences VALUES(?,?)', (vm_id, op))
            db.execute('INSERT INTO operations VALUES(?,?,?)', (op, '', json.dumps(record)))
        try:
            self.virsh('start', vm_id, '--paused')
            kernel.members()
            kernel.inspect()
            record['status'] = 'succeeded'
        except Exception:
            record['status'] = 'unknown'
            kernel.kill()
            raise
        finally:
            with self.db() as db:
                db.execute('UPDATE operations SET data=? WHERE id=?', (json.dumps(record), op))
        return record

    def binding(self, vm_id):
        canonical(vm_id)
        if vm_id not in self.bindings:
            raise LookupError('Unregistered protected VM')
        return self.bindings[vm_id]

    def virsh(self, *args):
        return self.run(['/usr/bin/virsh', '--connect', 'qemu:///system', *args])

    def observe(self, vm_id):
        b = self.binding(vm_id)
        text = self.virsh('dumpxml', vm_id, '--inactive')
        validate_xml(text, b)
        digest = trusted(self.config / vm_id / 'domain.sha256').read_text().strip()
        if hashlib.sha256(text.encode()).hexdigest() != digest:
            raise ConflictError('Offline-pinned domain definition changed')
        state = self.virsh('domstate', vm_id).strip()
        if state not in ('shut off', 'running', 'paused', 'crashed'):
            raise ComputeUnavailable('Unverifiable VM state')
        return b, state

    def detail(self, vm_id):
        b, state = self.observe(vm_id)
        with self.db() as db:
            fence = db.execute('SELECT op FROM fences WHERE vm=?', (vm_id,)).fetchone()
        return {'id': vm_id, 'owner': b.owner, 'state': state, 'phase': 'defined',
                'protected_backend': True, 'security_contained': bool(fence),
                'coverage': 'network/launch only; runtime/identity/audit/watchdog not supplied'}

    def list(self):
        return [self.detail(key) for key in self.bindings]

    def health(self):
        return {'backend': 'protected-system-libvirt', 'libvirt_uri': 'qemu:///system',
                'protected': False, 'reason': 'Full security monitoring gates are not implemented'}

    def create(self, data):
        raise ConflictError('Offline reviewed administrator provisioning only')

    def operation(self, operation_id):
        canonical(operation_id)
        with self.db() as db:
            row = db.execute('SELECT data FROM operations WHERE id=?', (operation_id,)).fetchone()
        if not row:
            raise LookupError('Operation not found')
        return json.loads(row[0])

    def network_status(self, vm_id):
        b, state = self.observe(vm_id)
        kernel = KernelBoundary(b, self.run)
        result = kernel.inspect()
        if state in ('running', 'paused'):
            kernel.members()
        with self.db() as db:
            fenced = db.execute('SELECT 1 FROM fences WHERE vm=?', (vm_id,)).fetchone()
        # A stopped, empty fenced subtree has no possible traffic, no false drop-all claim.
        result['blocked'] = bool(fenced and kernel.empty() and state in ('shut off', 'crashed'))
        return result

    def action(self, vm_id, action, data):
        import fcntl
        b = self.binding(vm_id)
        if action not in ('start', 'resume', 'shutdown', 'force-stop', 'network-block'):
            raise ValueError('Protected mutation not supported')
        if not isinstance(data, dict) or set(data) != {'operation_id', 'confirmation'}:
            raise ValueError('Exact operation/confirmation required')
        op = canonical(data['operation_id'])
        if data['confirmation'] != action + ':' + vm_id:
            raise ValueError('Exact intent required')
        digest = hashlib.sha256(json.dumps([vm_id, b.owner, action, data], sort_keys=True).encode()).hexdigest()
        with (self.root / 'authority.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.db() as db:
                old = db.execute('SELECT digest, data FROM operations WHERE id=?', (op,)).fetchone()
                if old:
                    if old[0] != digest or json.loads(old[1])['status'] != 'succeeded':
                        raise ConflictError('Operation uncertain or conflicting')
                    return json.loads(old[1])['result']
                if action in ('start', 'resume'):
                    if db.execute('SELECT 1 FROM fences WHERE vm=?', (vm_id,)).fetchone():
                        raise ConflictError('Durable stop fence; offline recovery only')
                    # All previous unfinished mutations prevent launch after daemon restart.
                    for row in db.execute('SELECT data FROM operations'):
                        prior = json.loads(row[0])
                        if prior['vm_id'] == vm_id and prior['status'] != 'succeeded':
                            raise ConflictError('Uncertain prior mutation')
                record = {'id': op, 'owner': b.owner, 'vm_id': vm_id, 'action': action, 'status': 'requested_unverified'}
                db.execute('INSERT INTO operations VALUES(?,?,?)', (op, digest, json.dumps(record)))
                if action in ('force-stop', 'network-block'):
                    db.execute('INSERT OR IGNORE INTO fences VALUES(?,?)', (vm_id, op))
            try:
                if action not in ('force-stop', 'network-block'):
                    self.observe(vm_id)
                kernel = KernelBoundary(b, self.run)
                if action in ('force-stop', 'network-block'):
                    # Committed intent/fence and the static binding suffice to attempt
                    # containment; libvirt/XML and packet readback are not prerequisites.
                    # Later reconciliation failures still leave the operation unknown.
                    trusted(b.cgroup, directory=True)
                    kernel.kill()
                    _, after_kill = self.observe(vm_id)
                    if after_kill not in ('shut off', 'crashed'):
                        self.virsh('destroy', vm_id)
                    _, stopped = self.observe(vm_id)
                    if stopped not in ('shut off', 'crashed') or not kernel.empty():
                        raise ComputeUnavailable('VM termination unverified')
                elif action == 'shutdown':
                    self.virsh('shutdown', vm_id)
                else:
                    # No externally protected runtime/identity/audit/watchdog exists yet.
                    # An optional callback or administrator healthy flag must not bypass it.
                    raise ConflictError('Launch blocked: independent mandatory monitoring coverage is not installed')
                record.update(status='succeeded', result=self.detail(vm_id))
            except Exception:
                record['status'] = 'unknown'
                raise
            finally:
                with self.db() as db:
                    db.execute('UPDATE operations SET data=? WHERE id=?', (json.dumps(record), op))
            return record['result']


def domain_xml(b, software_emulation=False):
    """Fixed 512 MiB / 1 CPU standalone nested-lab shape, no caller XML/paths."""
    root = ET.Element('domain', type='qemu' if software_emulation else 'kvm')
    def add(parent, tag, value=None, **attributes):
        node = ET.SubElement(parent, tag, attributes)
        if value is not None:
            node.text = str(value)
        return node
    add(root, 'name', 'pb-' + b.vm_id); add(root, 'uuid', b.vm_id)
    add(add(root, 'metadata'), '{' + NS + '}owner', b.owner)
    add(root, 'memory', 524288, unit='KiB'); add(root, 'vcpu', 1)
    add(add(root, 'resource'), 'partition', '/' + b.unit[:-6])
    add(add(root, 'os'), 'type', 'hvm', arch='x86_64', machine='pc')
    add(root, 'on_poweroff', 'destroy'); add(root, 'on_reboot', 'destroy'); add(root, 'on_crash', 'destroy')
    label = add(root, 'seclabel', type='static', model='dac', relabel='yes')
    add(label, 'label', '+' + str(b.uid) + ':+' + str(b.gid))
    devices = add(root, 'devices')
    add(devices, 'emulator', '/usr/bin/qemu-system-x86_64')
    disk = add(devices, 'disk', type='file', device='disk')
    add(disk, 'driver', name='qemu', type='qcow2')
    add(disk, 'source', file='/var/lib/project-bots-protected/' + b.vm_id + '/disk.qcow2')
    add(disk, 'target', dev='vda', bus='virtio')
    interface = add(devices, 'interface', type='user')
    add(interface, 'model', type='virtio')
    serial = add(devices, 'serial', type='file')
    add(serial, 'source', path='/var/lib/project-bots-protected/' + b.vm_id + '/serial.log')
    add(serial, 'target', port='0')
    add(devices, 'memballoon', model='none')
    return ET.tostring(root, encoding='unicode')


def dispatch_request(authority, request):
    allowed = {'health': 0, 'list': 0, 'detail': 1, 'operation': 1, 'network_status': 1, 'action': 3}
    if not isinstance(request, dict) or set(request) != {'method', 'args'}:
        raise ValueError('Exact protocol required')
    method, args = request['method'], request['args']
    if not isinstance(method, str) or method not in allowed or not isinstance(args, list) or len(args) != allowed[method]:
        raise ValueError('Unknown method or invalid arguments')
    return getattr(authority, method)(*args)


def serve_authority():
    """Root-owned systemd unit only; SO_PEERCRED authorizes a fixed compute UID."""
    from .machine_http import unique_object
    if os.geteuid() != 0:
        raise PermissionError('Root protected authority required')
    trusted(Path(__file__))
    config = json.loads(trusted('/etc/project-bots/protected-control.json').read_text())
    if set(config) != {'compute_uid', 'compute_gid'} or any(type(v) is not int or v <= 0 for v in config.values()):
        raise ValueError('Exact non-root control identity required')
    authority = ProtectedAuthority()
    if any(b.uid == config['compute_uid'] or b.gid == config['compute_gid'] for b in authority.bindings.values()):
        raise ValueError('Control and VM identities must be distinct')
    directory = trusted('/run/project-bots-protected', directory=True)
    path = directory / 'control.sock'
    if path.exists():
        if not stat.S_ISSOCK(path.lstat().st_mode) or path.lstat().st_uid != 0:
            raise ValueError('Untrusted existing socket')
        path.unlink()
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(path)); os.chown(path, 0, config['compute_gid']); path.chmod(0o660)
        listener.listen(8)
        while True:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(5)
                uid = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
                try:
                    if uid != config['compute_uid']:
                        raise PermissionError('Unauthorized peer')
                    with connection.makefile('rb') as source:
                        data = source.readline(16385)
                    if len(data) > 16384 or not data.endswith(b'\n'):
                        raise ValueError('Bounded single JSON request required')
                    result = dispatch_request(authority, json.loads(data, object_pairs_hook=unique_object))
                    response = {'result': result}
                except (ValueError, TypeError, LookupError, PermissionError, ConflictError, ComputeUnavailable, OSError):
                    response = {'error': 'Protected request rejected or outcome uncertain; inspect original operation'}
                try:
                    connection.sendall(json.dumps(response).encode() + b'\n')
                except OSError:
                    pass


class ProtectedClient:
    """Same compute interface, fixed root Unix socket; no sudo or inherited authority."""
    def __init__(self, path='/run/project-bots-protected/control.sock'):
        self.path = path

    def request(self, method, *args):
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(30)
            sock.connect(self.path)
            uid = struct.unpack('3i', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
            if uid != 0:
                raise ComputeUnavailable('Protected authority peer is not root')
            sock.sendall(json.dumps({'method': method, 'args': args}).encode() + b'\n')
            with sock.makefile('rb') as source:
                body = source.readline(65537)
            if len(body) > 65536 or not body.endswith(b'\n'):
                raise ComputeUnavailable('Invalid protected authority response')
            response = json.loads(body)
            if 'error' in response:
                raise ComputeUnavailable(response['error'])
            return response['result']

    def health(self): return self.request('health')
    def list(self): return self.request('list')
    def detail(self, vm_id): return self.request('detail', vm_id)
    def operation(self, operation_id): return self.request('operation', operation_id)
    def network_status(self, vm_id): return self.request('network_status', vm_id)
    def action(self, vm_id, action, data): return self.request('action', vm_id, action, data)
    def create(self, data): raise ConflictError('Offline administrator provisioning only')
