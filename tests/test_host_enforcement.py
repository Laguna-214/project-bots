"""Deterministic severity/operation/readback contracts, not real VM acceptance."""
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from project_bots.repository import SQLiteRepository
from project_bots.service import PlatformService
from project_bots.security import SecurityService
from security_fixtures import fixture_security


class CriticalTests(unittest.TestCase):
    def test_network_monitor_transport_loss_is_critical_and_forces_stop(self):
        from project_bots.security import poll_host_network
        stopped = []
        def request(machine, method, route, data=None):
            if route.endswith('/network'):
                raise OSError('trusted monitor transport lost')
            if route.endswith('/force-stop'):
                stopped.append(True)
            return {'id': self.vid, 'state': 'shut off' if stopped else 'running'}
        sec = SecurityService(self.repo, request)
        poll_host_network(sec)
        incidents = sec.incidents()['incidents']
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]['severity'], 'critical')
        self.assertTrue(stopped)
        self.assertNotEqual(sec.status()['coverage']['network']['status'], 'healthy')
        poll_host_network(sec)
        self.assertEqual(len(sec.incidents()['incidents']), 1)

    def test_timed_out_stop_retains_durable_intent_before_transport(self):
        intents = []
        def request(machine, method, route, data=None):
            if method == 'POST':
                incident = SecurityService(self.repo).incidents()['incidents'][0]
                intents.extend(incident.get('enforcement_intents', []))
                raise TimeoutError('lost stop acknowledgement')
            return {'id': self.vid, 'state': 'running'}
        sec = SecurityService(self.repo, request)
        incident = sec.report({'agent_id': self.aid, 'severity': 'critical', 'behavior': 'test', 'resource': self.vid, 'evidence': 'fixture'})
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0]['operation_id'], str(uuid.uuid5(uuid.UUID(incident['id']), 'force-stop:' + self.vid)))
        self.assertEqual(sec.incident(incident['id'])['enforcement_intents'], intents)
        self.assertEqual(intents[0]['vm_id'], self.vid)
        self.assertFalse(any(a['action'] == 'forced_vm_termination' and a['status'] == 'verified' for a in incident['actions']))

    def test_kernel_drop_counters_create_incident_without_agent_report(self):
        from project_bots.security import poll_host_network
        def request(machine, method, route, data=None):
            if route.endswith('/network'):
                return {'vm_id': self.vid, 'blocked': True, 'status': 'enforced', 'namespace_inode': 101,
                        'dropped_packets': 3, 'source': 'FIXTURE kernel counters'}
            return {'id': self.vid, 'state': 'shut off'}
        sec = SecurityService(self.repo, request)
        self.assertTrue(poll_host_network(sec))
        incidents = sec.incidents()['incidents']
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]['behavior'], 'host_network_denied_packets')
        self.assertEqual(incidents[0]['source'], 'trusted_host_network_monitor')
        self.assertIn('dropped_packets', incidents[0]['evidence'])
        poll_host_network(SecurityService(self.repo, request))
        self.assertEqual(len(sec.incidents()['incidents']), 1)

    def test_network_monitor_failure_never_becomes_healthy(self):
        from project_bots.security import poll_host_network
        sec = SecurityService(self.repo, lambda *_: (_ for _ in ()).throw(OSError('fixture telemetry lost')))
        poll_host_network(sec)
        self.assertNotEqual(sec.status()['coverage']['network']['status'], 'healthy')

    def test_network_tamper_is_deterministically_critical(self):
        from project_bots.security import poll_host_network
        stopped = []
        def request(machine, method, route, data=None):
            if route.endswith('/network'):
                return {'vm_id': self.vid, 'blocked': False, 'status': 'bound', 'source': 'FIXTURE kernel readback'}
            if route.endswith('/force-stop'): stopped.append(True)
            return {'id': self.vid, 'state': 'shut off' if stopped else 'running'}
        sec = SecurityService(self.repo, request)
        poll_host_network(sec)
        incident = sec.incidents()['incidents'][0]
        self.assertEqual(incident['severity'], 'critical')
        self.assertEqual(incident['source'], 'trusted_host_network_monitor')
        self.assertTrue(stopped)
        self.assertNotEqual(sec.status()['coverage']['network']['status'], 'healthy')

    def test_network_status_is_readback_and_not_a_submitted_flag(self):
        backend = __import__('test_machine').ComputeTests(methodName='test_health_console_and_capacity_policy')
        backend.setUp(); self.addCleanup(backend.doCleanups)
        compute = backend.backend(); vm = backend.provision(compute)
        status = compute.network_status(vm['id'])
        self.assertFalse(status['blocked'])
        self.assertEqual(status['status'], 'unavailable')

    def test_network_block_and_readback_precede_force_stop(self):
        calls = []; state = {'stopped': False, 'blocked': False}
        def request(machine, method, route, data=None):
            calls.append((method, route))
            if route.endswith('/network-block'):
                state['blocked'] = True
            if route.endswith('/network'):
                return {'vm_id': self.vid, 'blocked': state['blocked'], 'namespace_inode': 123, 'source': 'FIXTURE ONLY'}
            if route.endswith('/force-stop'):
                state['stopped'] = True
            return {'id': self.vid, 'state': 'shut off' if state['stopped'] else 'running'}
        sec = SecurityService(self.repo, request)
        incident = sec.report({'agent_id': self.aid, 'severity': 'critical', 'behavior': 'test', 'resource': self.vid, 'evidence': 'fixture'})
        network = next(a for a in incident['actions'] if a['action'] == 'network_isolation')
        self.assertEqual(network['status'], 'verified')
        self.assertLess(calls.index(('POST', 'vms/' + self.vid + '/network-block')), calls.index(('POST', 'vms/' + self.vid + '/force-stop')))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.repo = SQLiteRepository(Path(self.tmp.name) / 'private/state.db')
        platform = PlatformService(self.repo); fixture_security(self.repo)
        self.machine = platform.create_machine({'name': 'fixture', 'endpoint': 'http://127.0.0.1:19443', 'credential_env': 'FIXTURE_COMPUTE'})
        self.aid = platform.create_agent({'name': 'fixture', 'role': 'r', 'machine_id': self.machine['id']})['id']
        self.vid = str(uuid.uuid4())
        self.repo.save_worker({'agent_id': self.aid, 'vm_id': self.vid, 'profile': {}})

    def test_critical_never_waits_for_graceful_shutdown_and_operation_is_stable(self):
        calls = []; state = {'state': 'running'}
        def request(machine, method, route, data=None):
            calls.append((method, route, data))
            if route.endswith('/force-stop'): state['state'] = 'shut off'
            return {'id': self.vid, **state}
        sec = SecurityService(self.repo, request)
        incident = sec.report({'agent_id': self.aid, 'severity': 'critical', 'behavior': 'test', 'resource': self.vid, 'evidence': 'fixture'})
        posts = [c for c in calls if c[0] == 'POST']
        self.assertEqual(len(posts), 1)
        self.assertTrue(posts[0][1].endswith('/force-stop'))
        self.assertEqual(posts[0][2]['operation_id'], str(uuid.uuid5(uuid.UUID(incident['id']), 'force-stop:' + self.vid)))
        self.assertTrue(any(a['action'] == 'forced_vm_termination' and a['status'] == 'verified' for a in incident['actions']))
        sec.enforce(incident['id'])
        self.assertEqual(len([c for c in calls if c[0] == 'POST']), 1)

    def test_critical_failed_readback_never_claims_termination_or_retries_new_id(self):
        ids = []
        def request(machine, method, route, data=None):
            if method == 'POST': ids.append(data['operation_id'])
            return {'id': self.vid, 'state': 'running'}
        sec = SecurityService(self.repo, request)
        incident = sec.report({'agent_id': self.aid, 'severity': 'critical', 'behavior': 'test', 'resource': self.vid, 'evidence': 'fixture'})
        sec.enforce(incident['id'])
        self.assertEqual(len(set(ids)), 1)
        self.assertFalse(any(a['action'] == 'forced_vm_termination' and a['status'] == 'verified' for a in sec.incident(incident['id'])['actions']))

    def test_critical_already_stopped_still_latches_host_without_repeated_mutation(self):
        calls = []
        def request(machine, method, route, data=None):
            if method == 'POST': calls.append(route)
            return {'id': self.vid, 'state': 'shut off'}
        sec = SecurityService(self.repo, request)
        incident = sec.report({'agent_id': self.aid, 'severity': 'critical', 'behavior': 'test', 'resource': self.vid, 'evidence': 'fixture'})
        sec.enforce(incident['id'])
        self.assertEqual(calls, ['vms/' + self.vid + '/force-stop'])

    def test_failed_reconciliation_does_not_refresh_enforcer_health(self):
        from unittest.mock import patch
        from project_bots.security import enforce_once
        sec = SecurityService(self.repo)
        sec.report({'agent_id': self.aid, 'severity': 'critical', 'behavior': 'test', 'resource': self.vid, 'evidence': 'fixture'})
        with patch.object(SecurityService, 'enforce', side_effect=OSError('fixture reconciliation failure')):
            with self.assertRaises(OSError):
                enforce_once(self.repo, lambda *_: {})
        self.assertNotEqual(sec.status()['coverage']['enforcer']['status'], 'healthy')

    def test_high_uses_graceful_shutdown(self):
        posts = []
        def request(machine, method, route, data=None):
            if method == 'POST': posts.append(route)
            return {'id': self.vid, 'state': 'running'}
        sec = SecurityService(self.repo, request)
        sec.report({'agent_id': self.aid, 'severity': 'high', 'behavior': 'test', 'resource': self.vid, 'evidence': 'fixture'})
        self.assertEqual(posts, ['vms/' + self.vid + '/shutdown'])
