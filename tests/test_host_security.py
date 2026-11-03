"""Host enforcement contracts; privileged integration runs only in disposable netns."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import unittest
import uuid

import test_machine as machine_tests


class ForceStopTests(unittest.TestCase):
    setUp = machine_tests.ComputeTests.setUp
    backend = machine_tests.ComputeTests.backend
    provision = machine_tests.ComputeTests.provision
    def test_health_exposes_read_only_utilization_not_security_coverage(self):
        backend = self.backend()
        health = backend.health()
        self.assertIn('utilization', health)
        self.assertIn(health['utilization']['cpu']['status'], ('available', 'unavailable'))
        self.assertIn('not proof', health['utilization']['notice'])
        self.assertNotIn('protected', health['utilization'])

    def test_force_stop_retains_storage_and_definition_and_stable_operation(self):
        backend = self.backend(); vm = self.provision(backend); vid = vm['id']
        self.states[vid] = 'running'
        original = backend.run
        def run(argv):
            if argv[3:4] == ['destroy']:
                self.states[vid] = 'shut off'
            return original(argv)
        backend.run = run
        data = {'confirmation': 'force-stop:' + vid, 'operation_id': str(uuid.uuid4())}
        result = backend.action(vid, 'force-stop', data)
        self.assertEqual(result['state'], 'shut off')
        self.assertEqual(backend.operation(data['operation_id'])['status'], 'succeeded')
        backend.action(vid, 'force-stop', data)
        self.assertEqual(sum('destroy' in c for c in self.calls), 1)
        self.assertIn(vid, self.domains)
        self.assertTrue((backend.root / vid / 'disk.qcow2').is_file())
        self.assertFalse(any('undefine' in c for c in self.calls))
        # A fresh operation against a stopped owned VM is an observed no-op.
        backend.action(vid, 'force-stop', {**data, 'operation_id': str(uuid.uuid4())})
        self.assertEqual(sum('destroy' in c for c in self.calls), 1)

    def test_force_stop_latches_before_uncertain_destroy_and_blocks_direct_restart(self):
        from project_bots.compute import ComputeUnavailable
        from project_bots.service import ConflictError
        backend = self.backend(); vm = self.provision(backend); vid = vm['id']
        self.states[vid] = 'running'
        original = backend.run
        def run(argv):
            if argv[3:4] == ['destroy']:
                raise ComputeUnavailable('lost acknowledgement')
            return original(argv)
        backend.run = run
        operation_id = str(uuid.uuid4())
        with self.assertRaises(ComputeUnavailable):
            backend.action(vid, 'force-stop', {'confirmation': 'force-stop:' + vid, 'operation_id': operation_id})
        self.assertEqual(backend.operation(operation_id)['status'], 'unknown')
        # Independent stop observation is NOT recovery authority.
        self.states[vid] = 'shut off'
        fresh = self.backend()
        with self.assertRaises(ConflictError):
            fresh.action(vid, 'start', {'confirmation': 'start:' + vid, 'operation_id': str(uuid.uuid4())})
        self.assertTrue(fresh.record(vid)['security_contained'])
        self.assertFalse(any(c[3:4] == ['start'] for c in self.calls))

    def test_successful_force_stop_blocks_direct_start_after_manager_restart(self):
        from project_bots.service import ConflictError
        backend = self.backend(); vm = self.provision(backend); vid = vm['id']
        backend.action(vid, 'force-stop', {'confirmation': 'force-stop:' + vid, 'operation_id': str(uuid.uuid4())})
        fresh = self.backend()
        with self.assertRaises(ConflictError):
            fresh.action(vid, 'start', {'confirmation': 'start:' + vid, 'operation_id': str(uuid.uuid4())})
        self.assertTrue(fresh.record(vid)['security_contained'])

    def test_subprocess_binding_cannot_be_presented_as_vm_network_proof(self):
        from project_bots.compute import ComputeUnavailable
        backend = self.backend(); vm = self.provision(backend)
        class LeaderOnlyGuard:
            def inspect(self, _):
                return {'blocked': True, 'status': 'enforced', 'runtime_kind': 'subprocess'}
        backend.network_guard = LeaderOnlyGuard()
        with self.assertRaises(ComputeUnavailable):
            backend.network_status(vm['id'])

    def test_force_stop_rejects_ownership_mismatch_before_destroy(self):
        from project_bots.service import ConflictError
        backend = self.backend(); vm = self.provision(backend); vid = vm['id']
        self.states[vid] = 'running'
        self.domains[vid] = self.domains[vid].replace(backend.owner, str(uuid.uuid4()))
        with self.assertRaises(ConflictError):
            backend.action(vid, 'force-stop', {'confirmation': 'force-stop:' + vid, 'operation_id': str(uuid.uuid4())})
        self.assertFalse(any('destroy' in c for c in self.calls))


class NamespaceTests(unittest.TestCase):
    def test_host_namespace_is_refused(self):
        from project_bots.host_security import NamespaceFirewall
        fd = os.open('/proc/self/ns/net', os.O_RDONLY)
        self.addCleanup(os.close, fd)
        if os.environ.get('PB_DISPOSABLE_NETNS_TEST') == '1':
            fd = os.open('/proc/1/ns/net', os.O_RDONLY)
            self.addCleanup(os.close, fd)
        with self.assertRaises((ValueError, PermissionError)):
            NamespaceFirewall(fd)

    @unittest.skipUnless(os.environ.get('PB_DISPOSABLE_NETNS_TEST') == '1', 'requires explicitly isolated root network namespace')
    def test_real_default_deny_packet_counters_and_tamper_detection(self):
        from project_bots.host_security import NamespaceFirewall
        self.assertEqual(os.geteuid(), 0)
        self.assertNotEqual(os.stat('/proc/self/ns/net').st_ino, os.stat('/proc/1/ns/net').st_ino)
        subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True)
        fd = os.open('/proc/self/ns/net', os.O_RDONLY)
        self.addCleanup(os.close, fd)
        firewall = NamespaceFirewall(fd)
        self.addCleanup(firewall.close)
        self.addCleanup(lambda: subprocess.run(['nft', 'delete', 'table', 'inet', 'project_bots_guard'], capture_output=True))
        with socket.socket() as server:
            server.bind(('127.0.0.1', 0)); server.listen()
            address = server.getsockname()
            with socket.create_connection(address, timeout=.3):
                conn, _ = server.accept(); conn.close()
            before = firewall.block()
            self.assertTrue(before['blocked'])
            with self.assertRaises((TimeoutError, OSError)):
                socket.create_connection(address, timeout=.2)
            after = firewall.inspect()
            self.assertTrue(after['blocked'])
            self.assertGreater(after['dropped_packets'], 0)
            print('REAL_NETNS_EVIDENCE ' + json.dumps(after), flush=True)
            subprocess.run(['nft', 'delete', 'table', 'inet', 'project_bots_guard'], check=True)
            self.assertFalse(firewall.inspect()['blocked'])
            # Reconcile tampering back to default deny, never automatically allow.
            self.assertTrue(firewall.block()['blocked'])

    @unittest.skipUnless(os.environ.get('PB_DISPOSABLE_NETNS_TEST') == '1', 'requires explicitly isolated root network namespace')
    def test_real_independent_monitor_contains_after_kernel_rule_loss(self):
        from http.server import ThreadingHTTPServer
        import threading
        from project_bots.host_security import NamespaceFirewall, BoundNamespaceRuntime
        from project_bots.machine_http import make_handler
        from project_bots.repository import SQLiteRepository
        from project_bots.service import PlatformService
        from project_bots.security import SecurityService
        from security_fixtures import fixture_security
        subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True)
        # A nested namespace contains ONLY the nobody child. The trusted HTTP
        # manager/enforcer stay outside it and remain reachable during deny-all.
        child = subprocess.Popen(['unshare', '--net', '--', sys.executable, '-c', 'import os,signal,time; os.setgroups([]); os.setgid(65534); os.setuid(65534); signal.signal(signal.SIGTERM,signal.SIG_IGN); print("ready",flush=True); time.sleep(120)'], stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: child.poll() is None and (child.kill(), child.wait()))
        self.addCleanup(child.stdout.close)
        self.assertEqual(child.stdout.readline().strip(), 'ready')
        fd = os.open('/proc/' + str(child.pid) + '/ns/net', os.O_RDONLY); self.addCleanup(os.close, fd)
        firewall = NamespaceFirewall(fd); self.addCleanup(firewall.close)
        firewall.block()
        vid = str(uuid.uuid4())
        binding = BoundNamespaceRuntime(vid, child, firewall)
        self.addCleanup(binding.close)
        token = 'isolated-machine-fixture-' + '0123456789abcdef' * 3
        # Management stays in the outer disposable namespace. Only the child
        # namespace rules are tampered with; outer loopback remains reachable.
        with tempfile.TemporaryDirectory() as tmp:
            repo = SQLiteRepository(Path(tmp) / 'private/state.db')
            platform = PlatformService(repo); fixture_security(repo)
            requests = []
            class FixtureManager:
                def detail(self, target):
                    if target != vid: raise LookupError()
                    return {'id': vid, 'state': 'running' if child.poll() is None else 'shut off'}
                def network_status(self, target):
                    return {'vm_id': target, **binding.inspect(target)}
                def action(self, target, action, data):
                    requests.append({'action': action, 'operation_id': data['operation_id']})
                    if data['confirmation'] != action + ':' + vid: raise ValueError()
                    if action == 'network-block':
                        return binding.block(target)
                    if action == 'force-stop': return binding.force_stop(target)
                    raise ValueError()
            # Exact pinned nested target, not the outer management namespace.
            firewall._run(['delete', 'table', 'inet', 'project_bots_guard'])
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(FixtureManager(), token))
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
            machine = platform.create_machine({'name': 'isolated namespace fixture', 'endpoint': 'http://127.0.0.1:' + str(server.server_port), 'credential_env': 'PB_LAB_MACHINE'})
            aid = platform.create_agent({'name': 'disposable subprocess not VM', 'role': 'fixture', 'machine_id': machine['id']})['id']
            repo.save_worker({'agent_id': aid, 'vm_id': vid, 'profile': {}})
            command = [sys.executable, '-m', 'project_bots.security', '--db', str(repo.path), '--host-monitor', '--once']
            result = subprocess.run(command, env={**os.environ, 'PB_LAB_MACHINE': token}, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(child.returncode if child.poll() is not None else None, -signal.SIGKILL)
            incident = SecurityService(repo).incidents()['incidents'][0]
            self.assertEqual(incident['source'], 'trusted_host_network_monitor')
            self.assertEqual(incident['severity'], 'critical')
            self.assertEqual(incident['outcome'], 'partial')
            self.assertTrue(any(a['action'] == 'forced_vm_termination' and a['status'] == 'verified' for a in incident['actions']))
            self.assertTrue(incident['evidence'])
            self.assertTrue(incident['action_history'])
            self.assertTrue(firewall.inspect()['blocked'])
            self.assertTrue(any(a['action'] == 'network_isolation' and a['status'] == 'verified' for a in incident['actions']))
            second = subprocess.run(command, env={**os.environ, 'PB_LAB_MACHINE': token}, capture_output=True, text=True, timeout=15)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(sum(r['action'] == 'force-stop' for r in requests), 1)
            print('REAL_INDEPENDENT_MONITOR_EVIDENCE ' + json.dumps({'incident_id': incident['id'], 'source': incident['source'], 'severity': incident['severity'], 'child_returncode': child.returncode, 'outcome': incident['outcome'], 'actions': [a['action'] + ':' + a['status'] for a in incident['actions']]}), flush=True)

    def test_nondumpable_same_uid_child_cannot_impersonate_separate_identity(self):
        from project_bots.host_security import BoundNamespaceRuntime
        child = subprocess.Popen([sys.executable, '-c', 'import ctypes,time; assert ctypes.CDLL(None).prctl(4,0,0,0,0)==0; print("ready",flush=True); time.sleep(120)'], stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: child.poll() is None and (child.kill(), child.wait()))
        self.addCleanup(child.stdout.close)
        self.assertEqual(child.stdout.readline().strip(), 'ready')
        class BoundaryContractFixture:
            inode = os.stat('/proc/self/ns/net').st_ino
            def inspect(self): return {'blocked': True}
        with self.assertRaisesRegex(ValueError, 'UID'):
            BoundNamespaceRuntime(str(uuid.uuid4()), child, BoundaryContractFixture())

    def test_real_owned_process_force_stop_ignores_sigterm_and_preserves_evidence(self):
        from project_bots.host_security import OwnedProcess
        child = subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print("ready",flush=True); time.sleep(120)'], stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: child.poll() is None and (child.kill(), child.wait()))
        self.addCleanup(child.stdout.close)
        self.assertEqual(child.stdout.readline().strip(), 'ready')
        owned = OwnedProcess(child)
        child.terminate()
        self.assertIsNone(child.poll())
        result = owned.force_stop()
        self.assertTrue(result['terminated'])
        self.assertEqual(child.returncode, -signal.SIGKILL)
        self.assertTrue(owned.force_stop()['terminated'])
        print('REAL_PROCESS_EVIDENCE ' + json.dumps(result), flush=True)
