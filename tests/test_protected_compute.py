"""Unprivileged contracts; fake libvirt/kernel transport is NOT VM acceptance."""
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from project_bots import protected_compute as pc

VM = 'a3ec8c2c-a7a0-4164-a357-f006175d189e'
OWNER = 'fd698b30-a01a-4ebc-a4bc-a8ddc01bf9c6'

class ProtectedTests(unittest.TestCase):
    def test_config_rejects_caller_paths_and_noncanonical_uuid(self):
        good = dict(vm_id=VM, owner=OWNER, uid=62001, gid=62001,
                    broker_ipv4='192.0.2.10', broker_port=21435)
        self.assertEqual(pc.Binding.parse(good).unit, 'pb' + VM.replace('-', '') + '.slice')
        for key, value in [('vm_id', VM.upper()), ('pid', 123), ('xml', '<domain/>'),
                           ('broker_ipv4', '127.0.0.1'), ('broker_port', True), ('uid', 0)]:
            bad = {**good, key: value}
            with self.assertRaises(ValueError):
                pc.Binding.parse(bad)

    def test_kernel_readback_accepts_modern_bpftool_names_but_rejects_wrong_id(self):
        from unittest.mock import patch
        b = pc.Binding.parse(dict(vm_id=VM, owner=OWNER, uid=62001, gid=62001,
                                 broker_ipv4='192.0.2.10', broker_port=21435))
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / 'programs.json'
            config.write_text(json.dumps({'ingress': 'abc', 'egress': 'def'}))
            programs = [{'id': 1, 'tag': 'abc', 'type': 'cgroup_skb'},
                        {'id': 2, 'tag': 'def', 'type': 'cgroup_skb'}]
            attached = [{'id': 1, 'attach_type': 'ingress'}, {'id': 2, 'attach_type': 'egress'}]
            def runner(args):
                if 'cgroup' in args:
                    return json.dumps(attached)
                return json.dumps(programs[0 if args[-1].endswith('ingress') else 1])
            with patch.object(pc, 'trusted', side_effect=lambda path, **kw: config if str(path).endswith('programs.json') else Path(path)):
                self.assertEqual(pc.KernelBoundary(b, runner).inspect()['status'], 'enforced')
                attached[0]['id'] = 99
                with self.assertRaises(pc.ComputeUnavailable):
                    pc.KernelBoundary(b, runner).inspect()

    def test_real_unprivileged_unix_peer_cannot_impersonate_root_authority(self):
        import os
        import socket
        import threading
        if os.geteuid() == 0:
            self.skipTest('requires actual unprivileged peer')
        with tempfile.TemporaryDirectory() as temporary:
            path = str(Path(temporary) / 'control.sock')
            with socket.socket(socket.AF_UNIX) as listener:
                listener.bind(path); listener.listen(1)
                received = []
                def respond():
                    connection, _ = listener.accept()
                    with connection:
                        received.append(connection.recv(1024))
                thread = threading.Thread(target=respond)
                thread.start()
                with self.assertRaisesRegex(pc.ComputeUnavailable, 'not root'):
                    pc.ProtectedClient(path).health()
                thread.join(timeout=3)
                self.assertFalse(thread.is_alive())
                self.assertEqual(received, [b''])

    def test_untrusted_checkout_and_symlink_config_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'binding.json'
            path.write_text('{}')
            with self.assertRaises(ValueError):
                pc.trusted(path)
            link = Path(temporary) / 'link.json'
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                pc.trusted(link)

    def test_generated_review_artifacts_do_not_execute_or_enable_units(self):
        import runpy
        generator = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/prepare_protected_vm.py'))
        binding = dict(vm_id=VM, owner=OWNER, uid=62001, gid=62001,
                       broker_ipv4='192.0.2.10', broker_port=21435)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'review'
            generator['generate'](binding, output)
            self.assertEqual(json.loads((output / 'binding.json').read_text()), binding)
            self.assertIn('Delegate=no', (output / pc.Binding.parse(binding).unit).read_text())
            self.assertIn('python3 -I /opt/', (output / 'project-bots-protected.service').read_text())
            self.assertIn('NOT EXECUTED', (output / 'INSTALL-REVIEW.txt').read_text())
            pc.validate_xml((output / 'domain.xml').read_text(), pc.Binding.parse(binding))

    def test_network_program_has_no_default_pass_and_is_bound_to_tcp_broker(self):
        binding = pc.Binding.parse(dict(vm_id=VM, owner=OWNER, uid=62001, gid=62001,
                                       broker_ipv4='192.0.2.10', broker_port=21435))
        source = pc.network_source(binding)
        self.assertIn('SEC("cgroup_skb/egress")', source)
        self.assertIn('SEC("cgroup_skb/ingress")', source)
        self.assertIn('bpf_skb_load_bytes', source)
        self.assertIn('0x0a0200c0', source)  # network bytes, little-endian target
        self.assertIn('return 0;', source)
        self.assertNotIn('return 1;', source)

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.b = pc.Binding.parse(dict(vm_id=VM, owner=OWNER, uid=62001, gid=62001,
                                       broker_ipv4='192.0.2.10', broker_port=21435))
        self.authority = pc.ProtectedAuthority.__new__(pc.ProtectedAuthority)
        self.authority.root = Path(self.temp.name)
        self.authority.run = lambda argv: ''
        self.authority.bindings = {VM: self.b}
        with self.authority.db() as db:
            db.executescript('CREATE TABLE fences(vm TEXT PRIMARY KEY, op TEXT);'
                             'CREATE TABLE operations(id TEXT PRIMARY KEY,digest TEXT,data TEXT);')

    def test_xml_generated_is_fixed_identity_inprocess_network_no_host_shares(self):
        xml = pc.domain_xml(self.b, software_emulation=True)
        root = pc.validate_xml(xml, self.b)
        self.assertEqual(root.findtext('memory'), '524288')
        self.assertEqual(root.findtext('vcpu'), '1')
        self.assertEqual(root.find('devices/interface').attrib, {'type': 'user'})
        for bad in [xml.replace('type="user"', 'type="bridge"'),
                    xml.replace('<model type="virtio"', '<backend type="passt"/><model type="virtio"'),
                    xml.replace('</devices>', '<hostdev/></devices>'),
                    xml.replace('+' + str(self.b.uid), '+0')]:
            with self.assertRaises(pc.ConflictError):
                pc.validate_xml(bad, self.b)

    def test_prepared_launch_is_paused_until_members_and_network_verified(self):
        from unittest.mock import Mock, patch
        a = self.authority
        a.observe = Mock(return_value=(self.b, 'shut off'))
        a.virsh = Mock()
        events = []
        with patch.object(pc, 'KernelBoundary') as boundary:
            k = boundary.return_value
            k.empty.return_value = True
            k.inspect.side_effect = lambda: events.append('kernel')
            k.members.side_effect = lambda: events.append('members')
            a.virsh.side_effect = lambda *args: events.append(args)
            a.prepare_paused(VM)
        self.assertEqual(events, ['kernel', ('start', VM, '--paused'), 'members', 'kernel'])
        self.assertNotIn(('resume', VM), events)

    def test_missing_kernel_fence_never_calls_libvirt_start(self):
        from unittest.mock import Mock, patch
        a = self.authority
        a.observe = Mock(return_value=(self.b, 'shut off'))
        a.virsh = Mock()
        with patch.object(pc, 'KernelBoundary') as boundary:
            boundary.return_value.inspect.side_effect = pc.ComputeUnavailable('missing')
            with self.assertRaises(pc.ComputeUnavailable):
                a.prepare_paused(VM)
        a.virsh.assert_not_called()

    def test_kernel_kill_already_stopped_vm_does_not_destroy_again(self):
        from unittest.mock import Mock, patch
        a = self.authority
        a.observe = Mock(side_effect=[(self.b, 'shut off'), (self.b, 'shut off'),
                                     (self.b, 'shut off')])
        a.virsh = Mock()
        with patch.object(pc, 'KernelBoundary') as boundary, patch.object(pc, 'trusted'):
            boundary.return_value.empty.return_value = True
            a.action(VM, 'force-stop', {'operation_id': str(uuid.uuid4()), 'confirmation': 'force-stop:' + VM})
        a.virsh.assert_not_called()

    def test_critical_kill_precedes_failed_observation_with_committed_intent_and_fence(self):
        from unittest.mock import Mock, patch
        a = self.authority
        for action in ('force-stop', 'network-block'):
            with self.subTest(action=action):
                op = str(uuid.uuid4())
                events = []
                def validate(path, directory=False):
                    self.assertEqual(path, self.b.cgroup)
                    self.assertEqual(str(path), '/sys/fs/cgroup/pb' + VM.replace('-', '') + '.slice')
                    self.assertTrue(directory)
                    events.append('trusted-fixed-cgroup')
                def kill():
                    # Separate DB connections read only committed durable state.
                    self.assertEqual(a.operation(op)['status'], 'requested_unverified')
                    self.assertEqual(a.operation(op)['vm_id'], VM)
                    self.assertEqual(a.operation(op)['owner'], OWNER)
                    self.assertEqual(a.operation(op)['action'], action)
                    with a.db() as db:
                        self.assertIsNotNone(db.execute('SELECT op FROM fences WHERE vm=?', (VM,)).fetchone())
                    events.append('kill')
                def observe(vm_id):
                    self.assertEqual(vm_id, VM)
                    events.append('observe')
                    raise pc.ComputeUnavailable('libvirt/XML unavailable')
                a.observe = Mock(side_effect=observe)
                a.virsh = Mock()
                with patch.object(pc, 'KernelBoundary') as boundary, patch.object(pc, 'trusted', side_effect=validate):
                    boundary.return_value.kill.side_effect = kill
                    with self.assertRaisesRegex(pc.ComputeUnavailable, 'libvirt/XML unavailable'):
                        a.action(VM, action, {'operation_id': op, 'confirmation': action + ':' + VM})
                    boundary.assert_called_once_with(self.b, a.run)
                    boundary.return_value.kill.assert_called_once_with()
                self.assertEqual(events, ['trusted-fixed-cgroup', 'kill', 'observe'])
                self.assertEqual(a.operation(op)['status'], 'unknown')
                a.virsh.assert_not_called()

    def test_critical_stop_rejects_untrusted_cgroup_before_kill_or_observation(self):
        from unittest.mock import Mock, patch
        a = self.authority
        a.observe = Mock(return_value=(self.b, 'running'))
        for action in ('force-stop', 'network-block'):
            with self.subTest(action=action):
                op = str(uuid.uuid4())
                with patch.object(pc, 'KernelBoundary') as boundary, patch.object(pc, 'trusted', side_effect=ValueError('untrusted')) as validate:
                    with self.assertRaisesRegex(ValueError, 'untrusted'):
                        a.action(VM, action, {'operation_id': op, 'confirmation': action + ':' + VM})
                    validate.assert_called_once_with(self.b.cgroup, directory=True)
                    boundary.return_value.kill.assert_not_called()
                a.observe.assert_not_called()
                self.assertEqual(a.operation(op)['status'], 'unknown')

    def test_critical_stop_rejects_wrong_or_caller_selected_targets(self):
        from unittest.mock import Mock, patch
        a = self.authority
        a.observe = Mock()
        for action in ('force-stop', 'network-block'):
            for vm_id, extra, confirmation in [
                    (str(uuid.uuid4()), {}, None),
                    (VM.upper(), {}, None),
                    (VM, {'cgroup': '/sys/fs/cgroup/system.slice'}, None),
                    (VM, {'pid': 1}, None),
                    (VM, {}, action + ':' + str(uuid.uuid4()))]:
                with self.subTest(action=action, vm_id=vm_id, extra=extra, confirmation=confirmation):
                    op = str(uuid.uuid4())
                    data = {'operation_id': op, 'confirmation': confirmation or action + ':' + vm_id, **extra}
                    with patch.object(pc, 'KernelBoundary') as boundary, patch.object(pc, 'trusted') as validate:
                        with self.assertRaises((ValueError, LookupError)):
                            a.action(vm_id, action, data)
                        boundary.assert_not_called()
                        validate.assert_not_called()
                    with self.assertRaises(LookupError):
                        a.operation(op)
        a.observe.assert_not_called()
        with a.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM fences').fetchone()[0], 0)

    def test_stop_intent_fences_restart_even_when_observation_fails(self):
        from unittest.mock import Mock, patch
        a = self.authority
        op = str(uuid.uuid4())
        a.observe = Mock(side_effect=pc.ComputeUnavailable('lost'))
        with patch.object(pc, 'KernelBoundary'), patch.object(pc, 'trusted'):
            with self.assertRaises(pc.ComputeUnavailable):
                a.action(VM, 'force-stop', {'operation_id': op, 'confirmation': 'force-stop:' + VM})
        self.assertEqual(a.operation(op)['status'], 'unknown')
        # Reconstructed authority shares only durable state, not a cached flag.
        other = pc.ProtectedAuthority.__new__(pc.ProtectedAuthority)
        other.root = a.root; other.bindings = {VM: self.b}
        with self.assertRaises(pc.ConflictError):
            other.action(VM, 'start', {'operation_id': str(uuid.uuid4()), 'confirmation': 'start:' + VM})

    def test_start_cannot_use_a_permissive_monitor_callback(self):
        from unittest.mock import Mock
        a = self.authority
        a.observe = Mock(return_value=(self.b, 'shut off'))
        a.run = Mock()
        a.monitor = lambda: True
        with self.assertRaisesRegex(pc.ConflictError, 'monitoring'):
            a.action(VM, 'start', {'operation_id': str(uuid.uuid4()), 'confirmation': 'start:' + VM})
        a.run.assert_not_called()

    def test_machine_service_protected_mode_never_constructs_session_backend(self):
        from project_bots import machine_http
        from unittest.mock import patch
        with patch('project_bots.compute.ComputeService', side_effect=AssertionError('legacy used')):
            backend = machine_http.compute_backend(True, '/ignored', '/ignored')
            self.assertIsInstance(backend, pc.ProtectedClient)

    def test_protocol_rejects_commands_pids_xml_and_unknown_method(self):
        for req in [{'method': 'virsh', 'args': ['destroy', VM]},
                    {'method': 'action', 'args': [VM, 'start', {'pid': 1}]},
                    {'method': 'detail', 'args': [VM], 'xml': '<domain/>'}]:
            with self.assertRaises((ValueError, pc.ConflictError)):
                pc.dispatch_request(self.authority, req)

if __name__ == '__main__':
    unittest.main()
