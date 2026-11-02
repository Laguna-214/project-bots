"""Stage 2 software contracts; mocked commands are NOT real libvirt tests."""
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class ComputeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / 'ubuntu.qcow2'; self.image.write_bytes(b'trusted-image')
        import hashlib
        self.catalog = self.root / 'catalog.json'
        self.catalog.write_text(json.dumps({'ubuntu-desktop': {'image': str(self.image), 'sha256': hashlib.sha256(self.image.read_bytes()).hexdigest()}}))
        self.catalog.chmod(0o600); self.image.chmod(0o600)
        self.calls = []; self.domains = {}; self.states = {}
        def run(argv):
            self.calls.append(argv)
            self.assertIsInstance(argv, list)
            if argv[:2] == ['qemu-img', 'info']:
                return json.dumps({'format': 'qcow2', 'virtual-size': 8 * 1024**3})
            if argv[:2] == ['qemu-img', 'convert']:
                Path(argv[-1]).write_bytes(b'private-disk')
            if argv[0] == 'cloud-localds':
                Path(argv[-3]).write_bytes(b'seed')
            if argv[:3] == ['virsh', '--connect', 'qemu:///session']:
                command = argv[3]
                if command == 'define':
                    from xml.etree import ElementTree as ET
                    xml = Path(argv[4]).read_text(); vm_id = ET.fromstring(xml).findtext('uuid')
                    self.domains[vm_id] = xml; self.states[vm_id] = 'shut off'
                if command == 'dumpxml':
                    return self.domains[argv[4]]
                if command == 'domstate':
                    return self.states[argv[4]]
                if command in ('start', 'reboot', 'resume'):
                    self.states[argv[4]] = 'running'
                if command == 'shutdown':
                    self.states[argv[4]] = 'shut off'
                if command == 'suspend':
                    self.states[argv[4]] = 'paused'
                if command == 'undefine':
                    del self.domains[argv[4]]
            return ''
        self.runner = run

    def backend(self):
        from project_bots.compute import ComputeService
        backend = ComputeService(self.root / 'state', self.catalog, runner=self.runner)
        backend.capacity = lambda: {'cpus': 8, 'ram_mib': 32768, 'disk_gib': 512}
        return backend

    def provision(self, backend=None, **changes):
        data = {'template': 'ubuntu-desktop', 'cpus': 2, 'ram_mib': 4096, 'disk_gib': 24,
                'ssh_key': 'ssh-ed25519 ' + __import__('base64').b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20' + b'x' * 32).decode(),
                'confirmation': 'create', 'operation_id': str(__import__('uuid').uuid4())}
        data.update(changes)
        return (backend or self.backend()).create(data)

    def test_provision_trusted_template_private_disk_fixed_cloud_init_and_owned_xml(self):
        from xml.etree import ElementTree as ET
        backend = self.backend(); vm = self.provision(backend)
        self.assertEqual(backend.detail(vm['id'])['state'], 'shut off')
        self.assertEqual(len(backend.list()), 1)
        xml = ET.fromstring(self.domains[vm['id']])
        self.assertEqual(xml.findtext('name'), 'pb-' + vm['id'])
        self.assertEqual(xml.find('devices/graphics').get('listen'), '127.0.0.1')
        self.assertIsNone(xml.find('devices/hostdev'))
        disk = Path(xml.find('devices/disk/source').get('file'))
        self.assertNotEqual(disk, self.image)
        self.assertEqual(disk.parent.stat().st_mode & 0o777, 0o700)
        cloud = json.loads((disk.parent / 'user-data').read_text().split('\n', 1)[1])
        self.assertEqual(cloud['packages'], ['ubuntu-desktop-minimal', 'openssh-server', 'qemu-guest-agent'])
        self.assertTrue(cloud['ssh_pwauth'] is False)
        self.assertNotIn('runcmd', cloud)
        self.assertEqual(cloud['users'][0]['sudo'], [])
        self.assertEqual(self.backend().detail(vm['id'])['id'], vm['id'])
        self.assertTrue(all('qemu:///session' in c for c in self.calls if c[0] == 'virsh'))


    def test_lifecycle_requires_confirmation_and_ownership_with_offline_edits_snapshots(self):
        from project_bots.service import ConflictError
        backend = self.backend(); vm = self.provision(backend); vm_id = vm['id']
        def action(name, **extra):
            return backend.action(vm_id, name, {'operation_id': str(__import__('uuid').uuid4()), 'confirmation': name + ':' + vm_id, **extra})
        with self.assertRaises(ValueError):
            backend.action(vm_id, 'start', {'operation_id': str(__import__('uuid').uuid4())})
        self.assertEqual(action('start')['state'], 'running')
        self.assertEqual(action('pause')['state'], 'paused')
        self.assertEqual(action('resume')['state'], 'running')
        self.assertEqual(action('restart')['state'], 'running')
        with self.assertRaises(ConflictError):
            action('resources', cpus=3, ram_mib=6144, disk_gib=32)
        with self.assertRaises(ConflictError):
            action('snapshot-create', snapshot='clean')
        with self.assertRaises(ConflictError):
            action('delete')
        self.assertEqual(action('shutdown')['state'], 'shut off')
        updated = action('resources', cpus=3, ram_mib=6144, disk_gib=32)
        self.assertEqual((updated['cpus'], updated['ram_mib'], updated['disk_gib']), (3, 6144, 32))
        action('snapshot-create', snapshot='clean')
        self.assertEqual(backend.detail(vm_id)['snapshots'], ['clean'])
        action('snapshot-restore', snapshot='clean')
        self.assertTrue(any(c[:3] == ['qemu-img', 'snapshot', '-a'] for c in self.calls))
        original = self.domains[vm_id]
        self.domains[vm_id] = original.replace(backend.owner, str(__import__('uuid').uuid4()))
        before = len(self.calls)
        with self.assertRaises(ConflictError):
            action('delete')
        self.assertFalse(any(c[0] == 'qemu-img' or 'undefine' in c for c in self.calls[before:]))
        self.domains[vm_id] = original
        self.assertEqual(action('delete')['phase'], 'deleted')
        self.assertEqual(backend.list(), [])
        self.assertFalse((backend.root / vm_id).exists())


    def test_durable_idempotency_and_timeout_never_replays_host_mutation(self):
        from project_bots.compute import ComputeUnavailable
        from project_bots.service import ConflictError
        backend = self.backend(); op = str(__import__('uuid').uuid4())
        vm = self.provision(backend, operation_id=op)
        count = len(self.calls)
        replay = self.provision(backend, operation_id=op)
        self.assertEqual(vm, replay); self.assertEqual(len(self.calls), count)
        with self.assertRaises(ConflictError):
            self.provision(backend, operation_id=op, cpus=3)
        self.assertEqual(self.backend().operation(op)['status'], 'succeeded')
        action_op = str(__import__('uuid').uuid4())
        data = {'operation_id': action_op, 'confirmation': 'start:' + vm['id']}
        original = backend.run
        def fail(argv):
            if 'start' in argv:
                raise ComputeUnavailable('timeout')
            return original(argv)
        backend.run = fail
        with self.assertRaises(ComputeUnavailable):
            backend.action(vm['id'], 'start', data)
        self.assertEqual(self.backend().operation(action_op)['status'], 'unknown')
        self.assertEqual(backend.detail(vm['id'])['state'], 'shut off')
        backend.run = original; before = len(self.calls)
        with self.assertRaises(ConflictError):
            backend.action(vm['id'], 'start', data)
        with self.assertRaises(ConflictError):
            backend.action(vm['id'], 'start', {**data, 'operation_id': str(__import__('uuid').uuid4())})
        self.assertEqual(len(self.calls), before)


    def test_policy_rejects_untrusted_templates_paths_unsafe_fields_and_disk_tampering(self):
        from project_bots.service import ConflictError
        backend = self.backend()
        for changes in ({'cpus': True}, {'cpus': 9}, {'ram_mib': 1024}, {'disk_gib': 999}, {'command': 'touch /bad'},
                        {'xml': '<domain/>'}, {'template': '../../etc/passwd'}, {'confirmation': True},
                        {'ssh_key': 'ssh-ed25519 aaaa\nruncmd: evil'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.provision(backend, **changes)
        self.assertEqual(self.calls, [])
        self.image.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.provision(backend)
        self.image.write_bytes(b'trusted-image')
        backend = self.backend(); vm = self.provision(backend)
        disk = backend.root / vm['id'] / 'disk.qcow2'
        disk.unlink(); disk.symlink_to(self.image)
        with self.assertRaises(ConflictError):
            backend.action(vm['id'], 'delete', {'confirmation': 'delete:' + vm['id'], 'operation_id': str(__import__('uuid').uuid4())})
        self.assertTrue(self.image.exists())

    def test_health_console_and_capacity_policy(self):
        backend = self.backend(); health = backend.health()
        self.assertEqual(health['libvirt_uri'], 'qemu:///session')
        self.assertIsInstance(health['cpu_count'], int)
        self.assertIn('memory_available_mib', health)
        self.assertIn('storage_free_gib', health)
        self.assertIn('templates', health)
        vm = self.provision(backend)
        console = backend.detail(vm['id'])['console']
        self.assertEqual(console['listen'], '127.0.0.1')
        self.assertEqual(console['ssh_user'], 'bot')
        from xml.etree import ElementTree as ET
        xml = ET.fromstring(self.domains[vm['id']])
        forward = xml.find('devices/interface/portForward')
        self.assertEqual(forward.get('address'), '127.0.0.1')
        self.assertEqual(forward.find('range').get('to'), '22')
        self.assertGreaterEqual(console['ssh_port'], 22000)
        with self.assertRaises(ValueError):
            backend.reserve({'cpus': 8, 'ram_mib': 32768, 'disk_gib': 24}, capacity={'cpus': 8, 'ram_mib': 32768, 'disk_gib': 100})


    def test_catalog_permissions_and_snapshot_disk_format_are_enforced(self):
        from project_bots.service import ConflictError
        self.catalog.chmod(0o666)
        with self.assertRaises(ValueError): self.backend()
        self.catalog.chmod(0o600)
        backend = self.backend(); vm = self.provision(backend)
        old = backend.run
        def unsafe(argv):
            if argv[:2] == ['qemu-img', 'info'] and str(backend.root) in argv[-1]:
                return json.dumps({'format': 'raw', 'virtual-size': 1024})
            return old(argv)
        backend.run = unsafe
        with self.assertRaises(ConflictError):
            backend.action(vm['id'], 'snapshot-create', {'snapshot': 'bad', 'confirmation': 'snapshot-create:' + vm['id'], 'operation_id': str(__import__('uuid').uuid4())})
        self.assertFalse(any(c[:2] == ['qemu-img', 'snapshot'] for c in self.calls))

    def test_host_commands_timeout_and_errors_are_redacted(self):
        from project_bots.compute import run_command, ComputeUnavailable
        from unittest.mock import patch
        import subprocess
        for error in (subprocess.TimeoutExpired(['virsh'], 120, stderr='secret'), subprocess.CalledProcessError(1, ['virsh'], stderr='secret')):
            with patch('project_bots.compute.subprocess.run', side_effect=error) as run:
                with self.assertRaises(ComputeUnavailable) as result:
                    run_command(['virsh', '--connect', 'qemu:///session', 'version'])
                self.assertNotIn('secret', str(result.exception))
                self.assertEqual(run.call_args.kwargs['timeout'], 120)
                self.assertNotIn('shell', run.call_args.kwargs)


    def test_low_memory_start_and_invalid_offline_operations_fail_closed(self):
        from project_bots.service import ConflictError
        backend = self.backend(); vm = self.provision(backend)
        def action(verb, **extra):
            return backend.action(vm['id'], verb, {'operation_id': str(__import__('uuid').uuid4()), 'confirmation': verb + ':' + vm['id'], **extra})
        before = len(self.calls)
        backend.host_resources = lambda: {'memory_available_mib': 1024, 'storage_free_gib': 100}
        with self.assertRaises(ConflictError): action('start')
        for verb, extra in [('resources', {'cpus': 2, 'ram_mib': 4096, 'disk_gib': 16}), ('snapshot-create', {'snapshot': '--bad'}), ('snapshot-restore', {'snapshot': 'missing'}), ('destroy', {})]:
            with self.subTest(verb=verb), self.assertRaises((ValueError, ConflictError)):
                action(verb, **extra)
        self.assertFalse(any('start' in c or 'destroy' in c or c[:2] == ['qemu-img', 'resize'] for c in self.calls[before:]))

    def test_failed_provision_retains_inspectable_intent_without_automatic_cleanup(self):
        from project_bots.compute import ComputeUnavailable
        backend = self.backend(); original = backend.run; op = str(__import__('uuid').uuid4())
        def fail(argv):
            if argv[0] == 'cloud-localds': raise ComputeUnavailable('failure')
            return original(argv)
        backend.run = fail
        with self.assertRaises(ComputeUnavailable): self.provision(backend, operation_id=op)
        self.assertEqual(backend.operation(op)['status'], 'unknown')
        def absent(argv):
            if 'dumpxml' in argv: raise ComputeUnavailable('domain absent')
            return original(argv)
        backend.run = absent
        self.assertEqual(backend.detail(op)['state'], 'unavailable')
        self.assertEqual(backend.list()[0]['phase'], 'provisioning')
        self.assertTrue((backend.root / op / 'disk.qcow2').is_file())


    def test_post_mutation_observation_failure_is_uncertain_not_rejected(self):
        from project_bots.compute import ComputeUnavailable
        backend = self.backend(); original = backend.run; op = str(__import__('uuid').uuid4())
        def unobservable(argv):
            if 'dumpxml' in argv: raise ComputeUnavailable('observation timeout')
            return original(argv)
        backend.run = unobservable
        with self.assertRaises(ComputeUnavailable): self.provision(backend, operation_id=op)
        self.assertEqual(backend.operation(op)['status'], 'unknown')
        self.assertIn(op, self.domains)


    def test_concurrent_duplicate_creates_have_only_one_host_mutation(self):
        from concurrent.futures import ThreadPoolExecutor
        from project_bots.service import ConflictError
        backend = self.backend(); operation = str(__import__('uuid').uuid4())
        def create(_):
            try: return self.provision(backend, operation_id=operation)['id']
            except ConflictError: return 'busy'
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(create, range(8)))
        self.assertTrue(all(v in (operation, 'busy') for v in outcomes))
        self.assertIn(operation, outcomes)
        self.assertEqual(len(self.domains), 1)
        self.assertEqual(sum(c[:2] == ['qemu-img', 'convert'] for c in self.calls), 1)


    def test_service_owner_is_a_singleton_and_define_requests_schema_validation(self):
        import sqlite3
        backend = self.backend()
        with self.assertRaises(sqlite3.IntegrityError):
            with backend.db() as db:
                db.execute('INSERT INTO config(owner) VALUES (?)', (str(__import__('uuid').uuid4()),))
        self.provision(backend)
        self.assertTrue(all(c[-1] == '--validate' for c in self.calls if len(c) > 3 and c[0] == 'virsh' and c[3] == 'define'))


class MachineHTTPTests(unittest.TestCase):
    def test_local_fake_http_adapter_vm_routes_and_redacted_failures(self):
        from project_bots import machine_http
        from project_bots.machine_client import MachineClient
        from project_bots.compute import ComputeUnavailable
        token = secrets.token_urlsafe(32)
        class Fake:
            def health(self): return {'backend': 'fake', 'templates': []}
            def list(self): return [{'id': 'fake-vm'}]
            def create(self, data): return {'received': data}
            def detail(self, vm_id): return {'id': vm_id}
            def action(self, vm_id, action, data): return {'id': vm_id, 'action': action, 'received': data}
            def operation(self, op_id): return {'id': op_id, 'status': 'succeeded'}
        with ThreadingHTTPServer(('127.0.0.1', 0), machine_http.make_handler(Fake(), token)) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
            try:
                client = MachineClient(f'http://127.0.0.1:{server.server_port}', token)
                self.assertEqual(client.request('GET', '/v1/vms'), [{'id': 'fake-vm'}])
                self.assertEqual(client.request('POST', '/v1/vms', {'confirmation': 'create'})['received'], {'confirmation': 'create'})
                self.assertEqual(client.request('POST', '/v1/vms/fake-vm/start', {'confirmation': 'start:fake-vm'})['action'], 'start')
                self.assertEqual(client.request('GET', '/v1/operations/fake-op')['status'], 'succeeded')
                self.assertEqual(client.request('GET', '/v1/vms/fake-vm')['id'], 'fake-vm')
                with self.assertRaises(ValueError):
                    MachineClient('http://192.0.2.1:9443', token)
                with self.assertRaises(ValueError):
                    MachineClient('https://host:9443@evil.example', token)
                with self.assertRaises(ComputeUnavailable) as error:
                    MachineClient(client.endpoint, secrets.token_urlsafe(32)).request('GET', '/v1/health')
                self.assertNotIn(token, str(error.exception))
                request = Request(client.endpoint + '/v1/vms', data=b'{"x":1,"x":2}', headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
                with self.assertRaises(HTTPError) as error:
                    urlopen(request)
                self.assertEqual(error.exception.code, 400); error.exception.close()
            finally:
                server.shutdown(); worker.join()

    def test_machine_cli_launches_loopback_and_refuses_unsafe_bind_before_host_commands(self):
        import subprocess
        import time
        import socket
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); catalog = root / 'catalog.json'; catalog.write_text('{}')
            catalog.chmod(0o600)
            env = {**os.environ, 'TEST_COMPUTE_TOKEN': secrets.token_urlsafe(32)}
            base = [__import__('sys').executable, '-m', 'project_bots.cli', 'machine-service', '--catalog', str(catalog), '--state-dir', str(root / 'state'), '--token-env', 'TEST_COMPUTE_TOKEN']
            rejected = subprocess.run(base + ['--host', '0.0.0.0'], env=env, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('TLS', rejected.stderr)
            self.assertNotIn(env['TEST_COMPUTE_TOKEN'], rejected.stderr)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            process = subprocess.Popen(base + ['--port', str(port)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                for _ in range(100):
                    try:
                        with urlopen(Request(f'http://127.0.0.1:{port}/v1/vms', headers={'Authorization': 'Bearer ' + env['TEST_COMPUTE_TOKEN']}), timeout=.2) as response:
                            self.assertEqual(json.load(response), [])
                        break
                    except OSError:
                        if process.poll() is not None:
                            self.fail(process.communicate()[1].decode())
                        time.sleep(.02)
                else:
                    self.fail('Machine CLI did not listen')
            finally:
                process.terminate(); process.communicate(timeout=5)

    def test_platform_routes_use_registry_env_credentials_and_require_exact_confirmation(self):
        from project_bots.machine_http import make_handler
        from project_bots.platform_web import make_platform_handler
        from project_bots.repository import SQLiteRepository
        from project_bots.service import PlatformService
        from unittest.mock import patch
        import uuid
        class Fake:
            def health(self): return {'backend': 'fake', 'templates': ['ubuntu-desktop']}
            def list(self): return []
            def create(self, data): return {'id': data['operation_id'], 'state': 'shut off'}
            def detail(self, vm_id): return {'id': vm_id, 'state': 'shut off'}
            def action(self, vm_id, action, data): return {'id': vm_id, 'action': action}
            def operation(self, op_id): return {'id': op_id}
        token = secrets.token_urlsafe(32); admin = secrets.token_urlsafe(32)
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'COMPUTE_TEST_SECRET': token, 'PROJECT_BOTS_API_TOKEN': admin}):
            service = PlatformService(SQLiteRepository(Path(temp) / 'private' / 'platform.db'))
            with ThreadingHTTPServer(('127.0.0.1', 0), make_handler(Fake(), token)) as compute:
                thread = threading.Thread(target=compute.serve_forever, daemon=True); thread.start()
                machine = service.create_machine({'name': 'fake only', 'endpoint': f'http://127.0.0.1:{compute.server_port}', 'credential_env': 'COMPUTE_TEST_SECRET'})
                with ThreadingHTTPServer(('127.0.0.1', 0), make_platform_handler('12345678', service)) as platform:
                    other = threading.Thread(target=platform.serve_forever, daemon=True); other.start()
                    root = f'http://127.0.0.1:{platform.server_port}/api/machines/{machine["id"]}'
                    def call(path, data=None, authorized=True):
                        headers = {'Content-Type': 'application/json'}
                        if authorized: headers['Authorization'] = 'Bearer ' + admin
                        with urlopen(Request(root + path, data=None if data is None else json.dumps(data).encode(), headers=headers)) as response:
                            return json.load(response)
                    try:
                        self.assertEqual(call('/health')['backend'], 'fake')
                        self.assertEqual(call('/vms'), [])
                        op = str(uuid.uuid4())
                        self.assertEqual(call('/vms', {'operation_id': op, 'confirmation': 'create'})['id'], op)
                        self.assertEqual(call('/vms/' + op)['state'], 'shut off')
                        self.assertEqual(call('/vms/' + op + '/start', {'operation_id': str(uuid.uuid4()), 'confirmation': 'start:' + op})['action'], 'start')
                        self.assertEqual(call('/operations/' + op)['id'], op)
                        for path, data, auth, status in [('/vms', None, False, 403), ('/vms', {'operation_id': str(uuid.uuid4())}, True, 400), ('/vms/' + op + '/delete', {'confirmation': 'start:' + op, 'operation_id': str(uuid.uuid4())}, True, 400)]:
                            with self.assertRaises(HTTPError) as error: call(path, data, auth)
                            self.assertEqual(error.exception.code, status); error.exception.close()
                    finally:
                        platform.shutdown(); other.join(); compute.shutdown(); thread.join()

    def test_dashboard_exposes_narrow_vm_forms_without_command_or_secret_inputs(self):
        from html.parser import HTMLParser
        class Forms(HTMLParser):
            def __init__(self): super().__init__(); self.ids = set(); self.names = set()
            def handle_starttag(self, tag, attrs):
                self.ids.update(v for k, v in attrs if k == 'id')
                self.names.update(v for k, v in attrs if k == 'name')
        parsed = Forms(); parsed.feed(Path('project_bots/dashboard.html').read_text())
        self.assertTrue({'vm-create-form', 'vm-action-form', 'compute-machine', 'compute-output', 'operation-form'} <= parsed.ids)
        self.assertTrue({'template', 'cpus', 'ram_mib', 'disk_gib', 'ssh_key', 'operation_id', 'snapshot'} <= parsed.names)
        self.assertFalse({'command', 'xml', 'password', 'token', 'image_path'} & parsed.names)

    @unittest.skipUnless(__import__('shutil').which('openssl'), 'openssl required for ephemeral TLS test certificate')
    def test_tls_client_verifies_certificate_chain_and_hostname(self):
        from project_bots.machine_client import MachineClient
        from project_bots.compute import ComputeUnavailable
        from project_bots.machine_http import make_handler
        import ssl
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); cert = root / 'cert.pem'; key = root / 'key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(key), '-out', str(cert), '-days', '1', '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'], check=True, capture_output=True)
            token = secrets.token_urlsafe(32)
            class Fake:
                def list(self): return []
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(cert, key)
            with ThreadingHTTPServer(('127.0.0.1', 0), make_handler(Fake(), token)) as server:
                server.socket = context.wrap_socket(server.socket, server_side=True)
                thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
                try:
                    endpoint = f'https://localhost:{server.server_port}'
                    self.assertEqual(MachineClient(endpoint, token, str(cert)).request('GET', '/v1/vms'), [])
                    with self.assertRaises(ComputeUnavailable):
                        MachineClient(endpoint, token).request('GET', '/v1/vms')
                    with self.assertRaises(ComputeUnavailable):
                        MachineClient(f'https://127.0.0.1:{server.server_port}', token, str(cert)).request('GET', '/v1/vms')
                finally:
                    server.shutdown(); thread.join()

    def test_real_acceptance_script_requires_opt_in_before_reading_keys_or_network(self):
        import subprocess
        result = subprocess.run([__import__('sys').executable, 'scripts/accept_machine.py', '--endpoint', 'http://127.0.0.1:1', '--ssh-key-file', '/nonexistent'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('confirm-real-host-mutation', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_opt_in_acceptance_flow_with_fake_client_is_not_real_libvirt(self):
        import importlib.util
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('accept_machine', 'scripts/accept_machine.py')
        script = importlib.util.module_from_spec(spec); spec.loader.exec_module(script)
        calls = []; observed = {'state': 'shut off'}
        class Fake:
            def __init__(self, *args): pass
            def request(self, method, path, data=None):
                calls.append((method, path, data))
                if path == '/v1/health': return {'backend': 'FAKE ONLY'}
                if path == '/v1/vms' and method == 'POST':
                    observed['id'] = data['operation_id']; return dict(observed)
                if path == '/v1/vms': return []
                if method == 'POST':
                    verb = path.split('/')[-1]
                    if verb == 'start': observed['state'] = 'running'
                    if verb == 'shutdown': observed['state'] = 'shut off'
                    if verb == 'delete': observed['phase'] = 'deleted'
                return dict(observed)
        with tempfile.TemporaryDirectory() as temp:
            key = Path(temp) / 'key.pub'; key.write_text('ssh-ed25519 FAKE-TEST-PUBLIC-KEY')
            with patch.object(script, 'MachineClient', Fake), patch.object(script.time, 'sleep'), patch('builtins.print'):
                self.assertEqual(script.main(['--endpoint', 'http://127.0.0.1:1', '--ssh-key-file', str(key), '--confirm-real-host-mutation', script.APPROVAL]), 0)
        mutations = [c for c in calls if c[0] == 'POST']
        self.assertEqual(len(mutations), 4)
        self.assertEqual([c[1].split('/')[-1] for c in mutations], ['vms', 'start', 'shutdown', 'delete'])
        self.assertTrue(all(c[2]['confirmation'] for c in mutations))

    def test_missing_admin_ca_is_a_redacted_service_error(self):
        from project_bots.machine_client import MachineClient
        from project_bots.compute import ComputeUnavailable
        with self.assertRaises(ComputeUnavailable) as error:
            MachineClient('https://localhost:9443', secrets.token_urlsafe(32), '/unavailable-private-ca-file')
        self.assertNotIn('/unavailable-private-ca-file', str(error.exception))

    def test_authenticated_health_and_transport_policy(self):
        from project_bots import machine_http
        token = secrets.token_urlsafe(32)
        class Backend:
            def health(self):
                return {'backend': 'fake', 'cpu_count': 4}
        with self.assertRaises(ValueError):
            machine_http.validate_listener('0.0.0.0', token, None, None)
        with self.assertRaises(ValueError):
            machine_http.validate_listener('127.0.0.1', 'weak', None, None)
        machine_http.validate_listener('127.0.0.1', token, None, None)
        with ThreadingHTTPServer(('127.0.0.1', 0), machine_http.make_handler(Backend(), token)) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
            url = f'http://127.0.0.1:{server.server_port}/v1/health'
            try:
                with self.assertRaises(HTTPError) as error:
                    urlopen(url)
                self.assertEqual(error.exception.code, 403)
                error.exception.close()
                request = Request(url, headers={'Authorization': 'Bearer ' + token})
                self.assertEqual(json.load(urlopen(request))['backend'], 'fake')
                request.add_header('Origin', 'http://evil.example')
                with self.assertRaises(HTTPError) as error:
                    urlopen(request)
                error.exception.close()
            finally:
                server.shutdown(); worker.join()
