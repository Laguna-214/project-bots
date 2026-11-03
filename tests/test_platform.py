from security_fixtures import fixture_repository, fixture_security
"""Stage 1 repository and installed HTTP acceptance tests."""
import concurrent.futures
from contextlib import closing
import http.client
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


class InstalledPlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.env = dict(os.environ, HOME=str(self.home), PROJECT_BOTS_DB=str(self.home / 'data/platform.db'), PROJECT_BOTS_API_TOKEN='test-only-' + 'a' * 40)
        install = subprocess.run(['sh', str(ROOT / 'install.sh')], cwd=ROOT, env=self.env, capture_output=True, text=True)
        self.assertEqual(install.returncode, 0, install.stderr)
        self.process = None
        self.addCleanup(self.stop)
        self.start()

    def start(self):
        fixture_repository(self.env['PROJECT_BOTS_DB'])
        exe = self.home / '.local/bin/project-bots'
        self.process = subprocess.Popen([str(exe), 'serve', '--port', '0'], cwd=self.home, env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert self.process.stdout is not None
        line = self.process.stdout.readline()
        if not line:
            _, error = self.process.communicate(timeout=5)
            self.fail('Installed serve command did not start: ' + error)
        self.port = int(line.split(':')[-1].split()[0])
        self.origin = f'http://127.0.0.1:{self.port}'
        self.code = self.process.stdout.readline().strip().split()[-1]
        self.assertRegex(self.code, r'^\d{8}$')
        self.token = ''
        self.csrf = ''

    def stop(self):
        if self.process is not None:
            self.process.terminate()
            out, err = self.process.communicate(timeout=5)
            self.assertNotIn(self.env['PROJECT_BOTS_API_TOKEN'], out + err)
            self.process = None

    def request(self, method, path, data=None, status=200, headers=None, authenticated=True) -> Any:
        hdr = {'Origin': self.origin, 'X-Setup-Origin': self.origin, 'Content-Type': 'application/json'}
        if authenticated and self.token:
            hdr['Authorization'] = 'Bearer ' + self.token
        if self.csrf:
            hdr['X-CSRF-Token'] = self.csrf
        if headers is not None:
            hdr = headers
        body = json.dumps(data) if data is not None else None
        with closing(http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)) as conn:
            conn.request(method, path, body, hdr)
            response = conn.getresponse()
            raw = response.read().decode()
            self.assertEqual(response.status, status, raw)
            self.assertNotIn(self.env['PROJECT_BOTS_API_TOKEN'], raw)
            return json.loads(raw) if response.getheader('Content-Type', '').startswith('application/json') else raw

    def pair(self):
        self.token = self.request('POST', '/api/pair', {'code': self.code})['token']
        self.csrf = self.request('GET', '/api/session')['csrf']

    def test_persistent_individual_group_chats_and_idempotent_messages(self):
        import uuid
        self.pair()
        agent = self.request('POST', '/api/agents', {'name': 'Researcher', 'role': 'research'}, 201)
        other = self.request('POST', '/api/agents', {'name': 'Programmer', 'role': 'code'}, 201)
        single = self.request('POST', '/api/chats', {'title': 'Private discussion', 'kind': 'individual', 'agent_ids': [agent['id']]}, 201)
        group = self.request('POST', '/api/chats', {'title': 'Team', 'kind': 'group', 'agent_ids': [agent['id'], other['id']]}, 201)
        path = '/api/chats/' + group['id'] + '/messages'
        payload = {'client_id': str(uuid.uuid4()), 'content': '<script>not executable</script>\nHello team'}
        sent = self.request('POST', path, payload, 201)
        self.assertEqual(sent['sender'], 'admin')
        self.assertEqual(self.request('POST', path, payload, 201), sent)
        self.request('POST', path, dict(payload, content='conflicting retry'), 409)
        self.request('POST', path, dict(payload, sender=agent['id']), 400)
        self.request('POST', '/api/chats', {'title': 'Invalid', 'kind': 'individual', 'agent_ids': [agent['id'], other['id']]}, 400)
        self.stop()
        self.start()
        self.pair()
        self.assertEqual({c['id'] for c in self.request('GET', '/api/chats')}, {single['id'], group['id']})
        self.assertEqual(self.request('GET', path)['messages'], [sent])
        self.assertEqual(self.request('GET', path + '?after=' + str(sent['sequence']))['messages'], [])
        self.assertEqual(self.request('GET', '/api/agents'), [agent, other])
        self.assertEqual(self.request('GET', '/api/jobs'), [])

    def test_chat_broker_agent_identity_membership_and_immediate_revocation(self):
        import uuid
        self.stop()
        self.env.update(CHAT_A_TOKEN='chat-a-fixture-' + '1234567890abcdef' * 3, CHAT_B_TOKEN='chat-b-fixture-' + 'abcdef1234567890' * 3)
        self.start()
        self.pair()
        a = self.request('POST', '/api/agents', {'name': 'A', 'role': 'research'}, 201)['id']
        b = self.request('POST', '/api/agents', {'name': 'B', 'role': 'code'}, 201)['id']
        for agent_id, reference in ((a, 'CHAT_A_TOKEN'), (b, 'CHAT_B_TOKEN')):
            self.request('POST', '/api/agents/' + agent_id + '/chat-identity', {'credential_env': reference, 'enabled': True})
        self.request('POST', '/api/agents/' + b + '/chat-identity', {'credential_env': 'CHAT_A_TOKEN', 'enabled': True}, 409)
        chat = self.request('POST', '/api/chats', {'title': 'A only', 'kind': 'group', 'agent_ids': [a]}, 201)
        path = '/api/chats/' + chat['id'] + '/messages'
        ah = {'Authorization': 'Bearer ' + self.env['CHAT_A_TOKEN'], 'Content-Type': 'application/json'}
        bh = dict(ah, Authorization='Bearer ' + self.env['CHAT_B_TOKEN'])
        payload = {'client_id': str(uuid.uuid4()), 'content': 'A shared report'}
        sent = self.request('POST', path, payload, 201, headers=ah)
        self.assertEqual(sent['sender'], a)
        self.request('POST', path, dict(payload, sender=b), 400, headers=ah)
        self.request('POST', path, dict(payload, content='b attempt'), 403, headers=bh)
        self.request('GET', path, status=403, headers=bh)
        self.assertEqual(self.request('GET', '/api/chats', headers=bh), [])
        self.request('GET', '/api/jobs', status=403, headers=ah)
        self.request('POST', '/api/chats', {'title': 'Escalate'}, 403, headers=ah)
        self.request('POST', '/api/chats/' + chat['id'] + '/members', {'agent_ids': [a, b]}, 403, headers=ah)
        self.request('POST', '/api/chats/' + chat['id'] + '/members', {'agent_ids': [a, b]})
        self.assertEqual(self.request('GET', path, headers=bh)['messages'], [sent])
        reply = self.request('POST', path, {'client_id': str(uuid.uuid4()), 'content': 'B collaborative reply'}, 201, headers=bh)
        self.assertEqual(reply['sender'], b)
        self.assertEqual(self.request('GET', path, headers=ah)['messages'], [sent, reply])
        self.request('POST', '/api/chats/' + chat['id'] + '/members', {'agent_ids': [b]})
        self.request('GET', path, status=403, headers=ah)
        self.request('POST', path, {'client_id': str(uuid.uuid4()), 'content': 'revoked'}, 403, headers=ah)
        self.request('POST', '/api/agents/' + b + '/chat-identity', {'credential_env': 'CHAT_B_TOKEN', 'enabled': False})
        self.request('GET', path, status=403, headers=bh)
        events = self.request('GET', '/api/security/events')['events']
        self.assertTrue(any(e['behavior'] == 'message_access_denied' and e['agent_id'] == a for e in events))
        self.assertTrue(any(e['behavior'] == 'chat_membership_changed' for e in events))
        self.assertNotIn('A shared report', json.dumps(events))
        self.assertEqual(self.request('GET', path)['messages'], [sent, reply])

    def test_chat_rejects_ambiguous_tokens_and_malformed_membership(self):
        self.stop()
        shared = 'test-ambiguous-' + '1234567890abcdef' * 3
        self.env.update(CHAT_A_TOKEN=shared, CHAT_B_TOKEN=shared)
        self.start()
        self.pair()
        a = self.request('POST', '/api/agents', {'name': 'A', 'role': 'r'}, 201)['id']
        b = self.request('POST', '/api/agents', {'name': 'B', 'role': 'r'}, 201)['id']
        for agent_id, reference in ((a, 'CHAT_A_TOKEN'), (b, 'CHAT_B_TOKEN')):
            self.request('POST', '/api/agents/' + agent_id + '/chat-identity', {'credential_env': reference, 'enabled': True})
        headers = {'Authorization': 'Bearer ' + shared}
        self.request('GET', '/api/chats', status=403, headers=headers)
        self.request('GET', '/api/agents', status=403, headers=headers)
        self.request('POST', '/api/agents/' + a + '/chat-identity', {'credential_env': 'PROJECT_BOTS_API_TOKEN', 'enabled': True}, 409)
        for members in ([None], [[]], ['bad'], [a, a], []):
            self.request('POST', '/api/chats', {'title': 'Bad members', 'kind': 'group', 'agent_ids': members}, 400)
        self.assertEqual(self.request('GET', '/api/chats'), [])

    def test_http_concurrent_claims_have_one_winner_and_size_limits(self):
        self.pair()
        agent = self.request('POST', '/api/agents', {'name': 'A', 'role': 'manual'}, 201)
        job = self.request('POST', '/api/jobs', {'title': 'Race', 'input': 'No worker'}, 201)
        path = '/api/jobs/' + job['id']
        def claim(_):
            with closing(http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)) as conn:
                conn.request('POST', path + '/claim', json.dumps({'agent_id': agent['id']}), {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.env['PROJECT_BOTS_API_TOKEN']})
                response = conn.getresponse()
                status = response.status
                response.read()
                return status
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(claim, range(8)))
        self.assertEqual(statuses.count(200), 1)
        self.assertEqual(statuses.count(409), 7)
        self.request('POST', path + '/cancel', {})
        self.request('POST', path + '/complete', {'result': 'late'}, 409)
        self.request('POST', '/api/jobs', {'title': 'Too large', 'input': 'x' * 65536}, 400)
        self.request('POST', '/api/jobs', {'title': 'Unknown agent', 'input': 'x', 'agent_id': '00000000-0000-0000-0000-000000000000'}, 400)
        self.request('GET', '/api/jobs/00000000-0000-0000-0000-000000000000', status=404)
        self.request('GET', '/api/jobs/bad-id', status=400)
        self.env['PROJECT_BOTS_API_TOKEN'] = 'too-short'
        self.stop()
        self.start()
        self.request('GET', '/api/jobs', status=403, headers={'Authorization': 'Bearer too-short'})

    def test_unicode_and_multiline_payloads_are_handled_without_crashing(self):
        # Invalid Unicode credentials must be rejected, not disconnect the handler.
        self.request('POST', '/api/pair', {'code': 'é' * 8}, 403)
        self.pair()
        headers = {'Origin': self.origin, 'X-Setup-Origin': self.origin, 'Authorization': 'Bearer é', 'X-CSRF-Token': self.csrf, 'Content-Type': 'application/json'}
        self.request('GET', '/api/jobs', status=403, headers=headers)
        self.request('POST', '/api/jobs', {'title': 'x', 'input': 'x'}, 403, headers=dict(headers, Authorization='Bearer ' + self.token, **{'X-CSRF-Token': 'é'}))
        job = self.request('POST', '/api/jobs', {'title': 'Multiline', 'input': 'First line\nSecond line\tvalue'}, 201)
        self.assertIn('\n', job['input'])
        agent = self.request('POST', '/api/agents', {'name': 'A', 'role': 'R', 'config': {'instructions': 'First\nSecond'}}, 201)
        path = '/api/jobs/' + job['id']
        self.request('POST', path + '/claim', {'agent_id': agent['id']})
        for message in [False, 0, None, [], {}]:
            self.request('POST', path + '/progress', {'progress': 1, 'message': message}, 400)
        self.request('POST', path + '/complete', {'result': 'Line1\nLine2'})
        self.request('POST', path + '/cancel', {}, 409)
        for payload in ['{', '{"title":NaN}', '[1]', '{"title":"a","title":"b","input":"c"}']:
            with closing(http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)) as conn:
                conn.request('POST', '/api/jobs', payload, {'Origin': self.origin, 'X-Setup-Origin': self.origin, 'Authorization': 'Bearer ' + self.token, 'X-CSRF-Token': self.csrf, 'Content-Type': 'application/json'})
                response = conn.getresponse()
                self.assertEqual(response.status, 400, response.read())
                response.read()

    def test_dashboard_has_accessible_forms_and_safe_client_rendering(self):
        from html.parser import HTMLParser
        class Forms(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = set()
            def handle_starttag(self, tag, attrs):
                self.ids.update(value for key, value in attrs if key == 'id')
        html = self.request('GET', '/')
        parsed = Forms()
        parsed.feed(html)
        self.assertTrue({'pair-form', 'machine-form', 'agent-form', 'job-form', 'settings-form', 'jobs', 'inspect', 'message', 'system-status'} <= parsed.ids)
        script = self.request('GET', '/dashboard.js')
        self.assertNotIn('innerHTML', script)
        self.assertNotIn('localStorage', script)
        self.assertIn('textContent', script)
        self.assertIn('/cancel', script)
        self.assertIn('/assign', script)
        self.assertIn('sessionStorage.setItem', script)
        self.assertNotIn('registered (no worker)', script)
        self.assertNotIn('No worker runtime, inference', html)
        self.assertNotIn('Cancel this job? No worker will be signaled in Stage 1.', script)
        self.assertTrue({'worker-form', 'dispatch-form', 'execution-form', 'model-form', 'worker-output', 'model-output'} <= parsed.ids)
        self.assertIn('width=device-width', html)
        self.assertTrue({'chats', 'chat-create-form', 'chat-message-form', 'chat-members', 'chat-history', 'security-events'} <= parsed.ids)
        chat_script = self.request('GET', '/chat.js')
        self.assertIn('textContent', chat_script)
        self.assertNotIn('innerHTML', chat_script)
        self.assertIn('client_id', chat_script)
        self.assertIn('/members', chat_script)
        security_script = self.request('GET', '/security.js')
        self.assertTrue({'security-status', 'security-stop-all', 'security-restore', 'security-health', 'security-agents', 'security-incidents', 'security-evidence'} <= parsed.ids)
        self.assertIn('/api/security/emergency-stop', security_script)
        self.assertIn('securityRefresh', script)
        self.assertNotIn('innerHTML', security_script)
        conversation_script = self.request('GET', '/conversations.js')
        self.assertIn('/api/conversations/jobs', conversation_script)
        self.assertTrue({'conversation-form', 'conversation-agent', 'conversation-jobs'} <= parsed.ids)
        self.assertIn('conversations.js', html)
        approvals_script = self.request('GET', '/approvals.js')
        self.assertIn('/api/approvals/', approvals_script)
        self.assertNotIn('innerHTML', approvals_script)
        self.assertTrue({'approvals-list', 'integration-form', 'integration-token', 'integration-operations'} <= parsed.ids)

    def test_machine_api_settings_and_browser_guards(self):
        machine_headers = {'Authorization': 'Bearer ' + self.env['PROJECT_BOTS_API_TOKEN'], 'Content-Type': 'application/json'}
        self.assertEqual(self.request('GET', '/api/agents', headers=machine_headers), [])
        agent = self.request('POST', '/api/agents', {'name': 'API Agent', 'role': 'manual'}, 201, headers=machine_headers)
        job = self.request('POST', '/api/jobs', {'title': 'API Job', 'input': 'Manual data'}, 201, headers=machine_headers)
        path = '/api/jobs/' + job['id']
        self.request('POST', path + '/claim', {'agent_id': agent['id']}, headers=machine_headers)
        self.request('POST', path + '/fail', {'error': 'External client failure'}, headers=machine_headers)
        self.request('POST', path + '/cancel', {}, 409, headers=machine_headers)
        self.request('GET', '/api/jobs', status=403, headers=dict(machine_headers, Origin='http://evil.test'))
        self.request('GET', '/api/jobs', status=403, headers=dict(machine_headers, **{'Sec-Fetch-Site': 'cross-site'}))
        self.request('GET', '/api/jobs', status=403, headers=dict(machine_headers, Host='evil.test'))
        self.request('GET', '/api/jobs', status=403, headers={'Authorization': 'Bearer ' + self.code})
        self.pair()
        self.request('POST', '/api/pair', {'code': self.code}, 403)
        no_csrf = {'Origin': self.origin, 'X-Setup-Origin': self.origin, 'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'}
        self.request('POST', '/api/jobs', {'title': 'No CSRF', 'input': 'x'}, 403, headers=no_csrf)
        for bad in [None, [], {'name': 'x', 'role': 'x', 'api_key': self.env['PROJECT_BOTS_API_TOKEN']}]:
            self.request('POST', '/api/agents', bad, 400)
        settings = self.request('GET', '/api/settings')
        settings['inference_endpoint'] = 'http://10.0.50.30:11434'
        self.assertEqual(self.request('POST', '/api/settings', settings), settings)
        self.request('POST', '/api/settings', dict(settings, cloud_fallback=True), 400)
        self.request('GET', '/api/config', status=404)
        # Reusing the same browser bearer after a refresh is supported by sessionStorage.
        self.assertIn('sessionStorage', self.request('GET', '/dashboard.js', authenticated=False))
        self.assertEqual(self.request('GET', '/api/session')['csrf'], self.csrf)
        self.stop()
        self.start()
        self.pair()
        self.assertEqual(self.request('GET', '/api/settings'), settings)

    def test_installed_dashboard_persists_registration_and_jobs_across_restart(self):
        html = self.request('GET', '/')
        self.assertIn('Workforce', html)
        self.assertIn('dashboard.js', html)
        self.request('GET', '/api/agents', status=403)
        self.pair()
        machine = self.request('POST', '/api/machines', {'name': 'Compute example', 'endpoint': 'http://10.0.50.30:9443'}, 201)
        agent = self.request('POST', '/api/agents', {'name': 'Research', 'role': 'researcher', 'machine_id': machine['id']}, 201)
        job = self.request('POST', '/api/jobs', {'title': 'First job', 'input': 'Plan work'}, 201)
        path = '/api/jobs/' + job['id']
        self.request('POST', path + '/assign', {'agent_id': agent['id']})
        self.request('POST', path + '/claim', {'agent_id': agent['id']})
        self.request('POST', path + '/progress', {'progress': 60, 'message': 'Recorded manually'})
        completed = self.request('POST', path + '/complete', {'result': 'Manual result, no inference'})
        self.assertEqual(completed['status'], 'succeeded')
        old_token = self.token
        self.stop()
        self.start()
        self.token = old_token
        self.request('GET', '/api/jobs', status=403)
        self.token = ''
        self.pair()
        self.assertEqual(self.request('GET', path), completed)
        self.assertEqual(self.request('GET', '/api/agents'), [agent])
        self.assertEqual(self.request('GET', '/api/machines'), [machine])
        self.assertFalse((self.home / '.config/project-bots/config.json').exists())


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'private' / 'platform.db'

    def test_existing_public_database_parent_is_not_chmodded(self):
        from project_bots.repository import SQLiteRepository
        parent = Path(self.temp.name) / 'shared'
        parent.mkdir(mode=0o755)
        parent.chmod(0o755)
        with self.assertRaisesRegex(ValueError, 'private directory'):
            fixture_repository(parent / 'platform.db')
        self.assertEqual(parent.stat().st_mode & 0o777, 0o755)
        self.assertFalse((parent / 'platform.db').exists())

    def test_settings_are_separate_local_only_and_store_references(self):
        from project_bots.repository import SQLiteRepository
        from project_bots.service import PlatformService
        service = PlatformService(fixture_repository(self.path))
        settings = service.get_settings()
        self.assertEqual(settings['inference_endpoint'], 'http://127.0.0.1:11434')
        self.assertFalse(settings['cloud_fallback'])
        settings['inference_endpoint'] = 'http://10.0.50.30:11434'
        settings['machine_api_env'] = 'PB_MACHINE_TOKEN'
        service.save_settings(settings)
        self.assertEqual(PlatformService(fixture_repository(self.path)).get_settings(), settings)
        for bad in [dict(settings, cloud_fallback=True), dict(settings, token='secret'), dict(settings, machine_api_env='secret-value')]:
            with self.assertRaises(ValueError):
                service.save_settings(bad)

    def test_job_transitions_are_validated_and_claims_are_atomic(self):
        from project_bots.repository import SQLiteRepository
        from project_bots.service import PlatformService, ConflictError
        service = PlatformService(fixture_repository(self.path))
        agent = service.create_agent({'name': 'A', 'role': 'planner'})
        other = service.create_agent({'name': 'B', 'role': 'planner'})
        job = service.create_job({'title': 'J', 'input': 'I', 'agent_id': agent['id']})
        with self.assertRaises(ConflictError):
            service.job_action(job['id'], 'complete', {'result': 'premature'})
        with self.assertRaises(ConflictError):
            service.job_action(job['id'], 'claim', {'agent_id': other['id']})
        def claim(_):
            try:
                return PlatformService(fixture_repository(self.path)).job_action(job['id'], 'claim', {'agent_id': agent['id']})['status']
            except ConflictError:
                return 'conflict'
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(claim, range(8)))
        self.assertEqual(outcomes.count('running'), 1)
        self.assertEqual(outcomes.count('conflict'), 7)
        for value in [True, '5', -1, 101, 5.5, None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                service.job_action(job['id'], 'progress', {'progress': value})
        service.job_action(job['id'], 'progress', {'progress': 50})
        with self.assertRaises(ConflictError):
            service.job_action(job['id'], 'progress', {'progress': 49})
        service.job_action(job['id'], 'fail', {'error': 'Client reported failure'})
        for action, data in [('claim', {'agent_id': agent['id']}), ('assign', {'agent_id': other['id']}), ('cancel', {}), ('complete', {'result': 'x'}), ('fail', {'error': 'x'}), ('progress', {'progress': 90})]:
            with self.subTest(action=action), self.assertRaises(ConflictError):
                service.job_action(job['id'], action, data)
        for running in (False, True):
            canceled = service.create_job({'title': 'C', 'input': 'I'})
            if running:
                service.job_action(canceled['id'], 'claim', {'agent_id': agent['id']})
            self.assertEqual(service.job_action(canceled['id'], 'cancel', {})['status'], 'canceled')
            with self.assertRaises(ConflictError):
                service.job_action(canceled['id'], 'claim', {'agent_id': agent['id']})
        for data in [{'title': 'x', 'input': 3}, {'title': 'x', 'input': 'x' * 16001}, {'title': 'x', 'input': 'x', 'agent_id': 'bad'}, {'title': 'x', 'input': 'x', 'agent_id': '00000000-0000-0000-0000-000000000000'}]:
            with self.subTest(data=str(data)[:80]), self.assertRaises(ValueError):
                service.create_job(data)
        with self.assertRaises(LookupError):
            service.get_job('00000000-0000-0000-0000-000000000000')

    def test_job_assignment_claim_progress_and_result_survive_restart(self):
        from project_bots.repository import SQLiteRepository
        from project_bots.service import PlatformService
        service = PlatformService(fixture_repository(self.path))
        agent = service.create_agent({'name': 'Planner', 'role': 'planner'})
        job = service.create_job({'title': 'Plan', 'input': 'Draft a plan'})
        self.assertEqual(job['status'], 'queued')
        job = service.job_action(job['id'], 'assign', {'agent_id': agent['id']})
        self.assertEqual(job['agent_id'], agent['id'])
        job = service.job_action(job['id'], 'claim', {'agent_id': agent['id']})
        self.assertEqual(job['status'], 'running')
        job = service.job_action(job['id'], 'progress', {'progress': 40, 'message': 'Drafting'})
        self.assertEqual(job['progress'], 40)
        job = service.job_action(job['id'], 'complete', {'result': 'The plan'})
        self.assertEqual(job['status'], 'succeeded')
        self.assertEqual(job['progress'], 100)
        again = PlatformService(fixture_repository(self.path))
        self.assertEqual(again.get_job(job['id']), job)
        self.assertEqual(again.list('jobs'), [job])
        self.assertEqual(service.list('agents')[0]['status'], 'registered')

    def test_agent_registration_validates_fields_and_foreign_keys(self):
        from project_bots.repository import SQLiteRepository
        from project_bots.service import PlatformService
        service = PlatformService(fixture_repository(self.path))
        machine = service.create_machine({'name': 'Compute', 'endpoint': 'http://10.0.50.30:9443'})
        agent = service.create_agent({'name': 'Research', 'role': 'researcher', 'config': {'model': 'local-model'}, 'machine_id': machine['id']})
        self.assertEqual(agent['status'], 'registered')
        self.assertEqual(service.list('agents'), [agent])
        for data in [None, [], {'name': ''}, {'name': 'x', 'endpoint': 'http://user:secret@host'}, {'name': 'x', 'endpoint': 'file:///etc/passwd'}, {'name': 'x', 'endpoint': 'http://bad host'}, {'name': 'x', 'endpoint': 'https://host/?token=secret'}, {'name': 'x', 'endpoint': 'https://host', 'api_key': 'secret'}, {'name': 'x', 'endpoint': 'https://host', 'credential_env': 'bad-name'}, {'name': 'x' * 201, 'endpoint': 'https://host'}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                service.create_machine(data)
        for data in [{'name': 'x', 'role': 'x', 'machine_id': 'missing'}, {'name': 'x', 'role': 'x', 'config': []}, {'name': 'x', 'role': 'x', 'status': 'running'}, {'name': 'x', 'role': 'x', 'config': {'api_key': 'secret'}}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                service.create_agent(data)
        import sqlite3
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('PRAGMA foreign_keys=ON')
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('INSERT INTO agents(id, machine_id, data) VALUES (?, ?, ?)', ('bad', 'missing', '{}'))

    def test_machine_registration_persists_with_private_migrated_database(self):
        from project_bots.repository import SQLiteRepository
        from project_bots.service import PlatformService
        service = PlatformService(fixture_repository(self.path))
        machine = service.create_machine({'name': 'Compute', 'endpoint': 'https://compute.lan:9443', 'credential_env': 'COMPUTE_TOKEN'})
        self.assertEqual(machine['status'], 'unverified')
        self.assertEqual(machine['endpoint'], 'https://compute.lan:9443')
        import uuid
        self.assertEqual(str(uuid.UUID(machine['id'])), machine['id'])
        again = PlatformService(fixture_repository(self.path))
        self.assertEqual(again.list('machines'), [machine])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)
        import sqlite3
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 6)

    def test_stage_one_database_migrates_without_losing_registry_and_jobs(self):
        import sqlite3
        from project_bots.repository import SQLiteRepository
        from project_bots.service import PlatformService
        service = PlatformService(fixture_repository(self.path))
        machine = service.create_machine({'name': 'Existing', 'endpoint': 'https://compute.lan:9443'})
        agent = service.create_agent({'name': 'Existing worker', 'role': 'analyst', 'machine_id': machine['id']})
        job = service.create_job({'title': 'Existing job', 'input': 'Keep me', 'agent_id': agent['id']})
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('integration_operations', 'integration_approvals', 'integration_principals', 'chat_messages', 'chat_members', 'chats', 'chat_identities', 'security_events'):
                db.execute('DROP TABLE ' + table)
            db.execute('DROP TABLE inference_admission')
            db.execute('DROP TABLE executions')
            db.execute('DROP TABLE workers')
            db.execute('PRAGMA user_version = 1')
            db.commit()
        migrated = PlatformService(fixture_repository(self.path))
        self.assertEqual(migrated.list('machines'), [machine])
        self.assertEqual(migrated.list('agents'), [agent])
        self.assertEqual(migrated.list('jobs'), [job])
        self.assertEqual(migrated.list('workers'), [])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 6)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertEqual(PlatformService(fixture_repository(self.path)).list('jobs'), [job])
