"""Application security contracts; not hostile VM/network acceptance."""
import tempfile
import unittest
from pathlib import Path
from project_bots.repository import SQLiteRepository
from project_bots.service import PlatformService, ConflictError


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = SQLiteRepository(Path(self.temp.name) / 'private/state.db')
        self.service = PlatformService(self.repo)
        self.agent = self.service.create_agent({'name': 'A', 'role': 'r'})['id']

    def test_stop_is_durable_and_blocks_direct_repository_job_bypass(self):
        from project_bots.security import SecurityService
        security = SecurityService(self.repo)
        stopped = security.emergency_stop({'reason': 'fixture stop'})
        self.assertTrue(stopped['global_stop'])
        fresh = PlatformService(SQLiteRepository(self.repo.path))
        self.assertTrue(SecurityService(fresh.repository).status()['global_stop'])
        with self.assertRaises(ConflictError):
            fresh.create_job({'title': 'blocked', 'input': 'x'})
        with self.assertRaises(ConflictError):
            fresh.repository.insert_job({'id': 'bypass', 'agent_id': None})
        self.assertEqual(fresh.list('agents')[0]['id'], self.agent)
        self.assertFalse(stopped['protected'])

    def test_registry_only_agents_can_recover_after_verified_no_runtime(self):
        from project_bots.security import SecurityService
        sec = self.healthy_fixture()
        state = sec.emergency_stop({'reason': 'registry-only fixture'})
        incident = state['incidents'][0]
        sec.acknowledge(incident['id'], {'note': 'no configured runtime verified'})
        sec.recover({'note': 'fixture coverage restored', 'credential_rotated': True}, incident['id'])
        self.assertTrue(sec.status()['global_stop'])
        sec.recover({'note': 'explicit global recovery'})
        self.assertFalse(sec.status()['global_stop'])
        self.service.create_job({'title': 'queued again', 'input': 'safe queue'})

    def healthy_fixture(self):
        from project_bots.security import SecurityService, REQUIRED_COVERAGE
        security = SecurityService(self.repo)
        for name in REQUIRED_COVERAGE:
            security.observe(name, healthy=True, source='isolated test fixture')
        return security

    def test_execution_is_fail_safe_and_queue_registry_remain_available(self):
        from project_bots.security import check_agent_execution, SecurityService
        self.service.create_job({'title': 'queue only', 'input': 'x', 'agent_id': self.agent})
        with self.assertRaises(ConflictError):
            check_agent_execution(self.repo, self.agent)
        security = self.healthy_fixture()
        check_agent_execution(self.repo, self.agent)
        security.observe('network', healthy=False, source='fixture telemetry failure')
        with self.assertRaises(ConflictError):
            check_agent_execution(self.repo, self.agent)
        self.assertFalse(SecurityService(self.repo).status()['protected'])

    def test_stale_coverage_blocks_execution_after_repository_restart(self):
        import time
        from project_bots.security import SecurityService, check_agent_execution
        sec = self.healthy_fixture()
        sec.observe('audit', healthy=True, source='expired fixture', ttl=30, observed_at=time.time()-31)
        fresh = SQLiteRepository(self.repo.path)
        self.assertEqual(SecurityService(fresh).status()['coverage']['audit']['status'], 'stale')
        with self.assertRaises(ConflictError):
            check_agent_execution(fresh, self.agent)

    def test_information_and_warning_do_not_contain_unrelated_agents(self):
        from project_bots.security import SecurityService
        sec = SecurityService(self.repo)
        for severity in ('information', 'warning'):
            incident = sec.report({'agent_id': self.agent, 'severity': severity, 'behavior': 'fixture', 'resource': 'fixture', 'evidence': 'fixture'})
            self.assertEqual(incident['outcome'], 'recorded')
        self.assertFalse(sec.status()['agents'][0]['contained'])

    def test_raw_gateway_cannot_bypass_trusted_admission(self):
        from project_bots.workers import gateway_run
        with self.assertRaises(ConflictError):
            gateway_run({'endpoint': 'http://127.0.0.1:1'}, {'input': 'blocked'})

    def test_contained_chat_list_cannot_bypass_http_authentication(self):
        from project_bots.chat import ChatService
        from project_bots.security import SecurityService
        chat = ChatService(self.repo)
        chat.create({'title': 'fixture', 'kind': 'individual', 'agent_ids': [self.agent]})
        chat.configure_identity(self.agent, {'credential_env': 'FIXTURE_CHAT', 'enabled': True})
        SecurityService(self.repo).emergency_stop({'reason': 'fixture'})
        chat.configure_identity(self.agent, {'credential_env': 'FIXTURE_CHAT', 'enabled': True})
        with self.assertRaises(PermissionError):
            chat.list(self.agent)

    def test_containment_cancels_and_revokes_chat_but_ack_does_not_resume(self):
        from project_bots.security import SecurityService, check_agent_execution
        from project_bots.chat import ChatService
        import uuid
        chat = ChatService(self.repo)
        chat.configure_identity(self.agent, {'credential_env': 'FIXTURE_CHAT', 'enabled': True})
        group = chat.create({'title': 'g', 'kind': 'individual', 'agent_ids': [self.agent]})
        job = self.service.create_job({'title': 'queued', 'input': 'x', 'agent_id': self.agent})
        sec = SecurityService(self.repo)
        incident = sec.report({'agent_id': self.agent, 'severity': 'critical', 'behavior': 'fixture canary', 'resource': 'fixture', 'evidence': 'synthetic fixture report, not live detection'})
        self.assertEqual(self.repo.get_job(job['id'])['status'], 'canceled')
        self.assertEqual(incident['outcome'], 'partial')
        self.assertTrue(any(a['status'] == 'unavailable' for a in incident['actions']))
        sec.acknowledge(incident['id'], {'note': 'investigated'})
        with self.assertRaises(ConflictError):
            check_agent_execution(self.repo, self.agent)
        with self.assertRaises(PermissionError):
            chat.send(group['id'], {'client_id': str(uuid.uuid4()), 'content': 'blocked'}, self.agent)
        # Re-enabling the credential cannot bypass a contained latch.
        chat.configure_identity(self.agent, {'credential_env': 'FIXTURE_CHAT', 'enabled': True})
        with self.assertRaises(PermissionError):
            chat.send(group['id'], {'client_id': str(uuid.uuid4()), 'content': 'bypass'}, self.agent)
        with self.assertRaises(ConflictError):
            sec.recover({'note': 'not safe', 'credential_rotated': True}, incident['id'])

    def test_stop_blocks_compute_start_and_worker_registration_bypass(self):
        import uuid
        from project_bots.security import SecurityService
        SecurityService(self.repo).emergency_stop({'reason': 'test'})
        with self.assertRaises(ConflictError):
            self.service.compute_request(str(uuid.uuid4()), 'POST', 'vms', {'confirmation': 'create', 'operation_id': str(uuid.uuid4())})
        with self.assertRaises(ConflictError):
            self.repo.save_worker({'agent_id': self.agent, 'vm_id': str(uuid.uuid4()), 'profile': {}})

    def test_stop_racing_authorized_start_reconciles_owned_runtime(self):
        import os
        import uuid
        from unittest.mock import patch
        from project_bots.security import SecurityService
        self.healthy_fixture()
        machine = self.service.create_machine({'name': 'fixture', 'endpoint': 'http://127.0.0.1:19443', 'credential_env': 'FIXTURE_COMPUTE'})
        agent = self.service.create_agent({'name': 'raced', 'role': 'r', 'machine_id': machine['id']})['id']
        vm = str(uuid.uuid4())
        self.repo.save_worker({'agent_id': agent, 'vm_id': vm, 'profile': {}})
        state = {'running': False}
        def request(method, path, data=None):
            if path.endswith('/start'):
                SecurityService(self.repo).emergency_stop({'reason': 'during in-flight start'})
                state['running'] = True
                return {'id': vm, 'state': 'running'}
            if path.endswith(('/shutdown', '/force-stop')):
                state['running'] = False
                return {}
            return {'id': vm, 'state': 'running' if state['running'] else 'shut off'}
        with patch.dict(os.environ, {'FIXTURE_COMPUTE': 'fixture-token-' + '0123456789abcdef'*3}), patch('project_bots.machine_client.MachineClient.request', side_effect=request):
            with self.assertRaises(ConflictError):
                self.service.compute_request(machine['id'], 'POST', 'vms/' + vm + '/start', {'confirmation': 'start:' + vm, 'operation_id': str(uuid.uuid4())})
        self.assertFalse(state['running'])

    def test_late_remote_completion_cannot_undo_containment(self):
        import uuid
        from project_bots.security import SecurityService
        self.healthy_fixture()
        worker = self.repo.save_worker({'agent_id': self.agent, 'vm_id': str(uuid.uuid4()), 'profile': {}})
        job = self.service.create_job({'title': 'running', 'input': 'x', 'agent_id': self.agent})
        self.repo.begin_execution(job['id'], worker)
        SecurityService(self.repo).emergency_stop({'reason': 'while running'})
        result = self.repo.finish_execution(job['id'], 'succeeded', 'late')
        self.assertEqual(result['status'], 'canceled')
        self.assertIsNone(result['result'])
        self.assertEqual(self.repo.execution(job['id'])['status'], 'uncertain')

    def test_enforcer_monitor_loss_contains_without_self_reported_health(self):
        import uuid
        from project_bots.security import SecurityService, enforce_once
        self.repo.save_worker({'agent_id': self.agent, 'vm_id': str(uuid.uuid4()), 'profile': {}})
        sec = SecurityService(self.repo)
        enforce_once(self.repo)
        state = sec.status()
        self.assertTrue(state['agents'][0]['contained'])
        self.assertEqual(state['coverage']['enforcer']['status'], 'healthy')
        self.assertEqual(state['coverage']['network']['status'], 'unavailable')
        self.assertFalse(state['protected'])
        count = len(state['incidents'])
        enforce_once(self.repo)
        self.assertEqual(len(sec.status()['incidents']), count)
