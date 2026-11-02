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
            SQLiteRepository(parent / 'platform.db')
        self.assertEqual(parent.stat().st_mode & 0o777, 0o755)
        self.assertFalse((parent / 'platform.db').exists())

    def test_settings_are_separate_local_only_and_store_references(self):
        from project_bots.repository import SQLiteRepository
        from project_bots.service import PlatformService
        service = PlatformService(SQLiteRepository(self.path))
        settings = service.get_settings()
        self.assertEqual(settings['inference_endpoint'], 'http://127.0.0.1:11434')
        self.assertFalse(settings['cloud_fallback'])
        settings['inference_endpoint'] = 'http://10.0.50.30:11434'
        settings['machine_api_env'] = 'PB_MACHINE_TOKEN'
        service.save_settings(settings)
        self.assertEqual(PlatformService(SQLiteRepository(self.path)).get_settings(), settings)
        for bad in [dict(settings, cloud_fallback=True), dict(settings, token='secret'), dict(settings, machine_api_env='secret-value')]:
            with self.assertRaises(ValueError):
                service.save_settings(bad)

    def test_job_transitions_are_validated_and_claims_are_atomic(self):
        from project_bots.repository import SQLiteRepository
        from project_bots.service import PlatformService, ConflictError
        service = PlatformService(SQLiteRepository(self.path))
        agent = service.create_agent({'name': 'A', 'role': 'planner'})
        other = service.create_agent({'name': 'B', 'role': 'planner'})
        job = service.create_job({'title': 'J', 'input': 'I', 'agent_id': agent['id']})
        with self.assertRaises(ConflictError):
            service.job_action(job['id'], 'complete', {'result': 'premature'})
        with self.assertRaises(ConflictError):
            service.job_action(job['id'], 'claim', {'agent_id': other['id']})
        def claim(_):
            try:
                return PlatformService(SQLiteRepository(self.path)).job_action(job['id'], 'claim', {'agent_id': agent['id']})['status']
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
        service = PlatformService(SQLiteRepository(self.path))
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
        again = PlatformService(SQLiteRepository(self.path))
        self.assertEqual(again.get_job(job['id']), job)
        self.assertEqual(again.list('jobs'), [job])
        self.assertEqual(service.list('agents')[0]['status'], 'registered')

    def test_agent_registration_validates_fields_and_foreign_keys(self):
        from project_bots.repository import SQLiteRepository
        from project_bots.service import PlatformService
        service = PlatformService(SQLiteRepository(self.path))
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
        service = PlatformService(SQLiteRepository(self.path))
        machine = service.create_machine({'name': 'Compute', 'endpoint': 'https://compute.lan:9443', 'credential_env': 'COMPUTE_TOKEN'})
        self.assertEqual(machine['status'], 'unverified')
        self.assertEqual(machine['endpoint'], 'https://compute.lan:9443')
        import uuid
        self.assertEqual(str(uuid.UUID(machine['id'])), machine['id'])
        again = PlatformService(SQLiteRepository(self.path))
        self.assertEqual(again.list('machines'), [machine])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)
        import sqlite3
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 3)

    def test_stage_one_database_migrates_without_losing_registry_and_jobs(self):
        import sqlite3
        from project_bots.repository import SQLiteRepository
        from project_bots.service import PlatformService
        service = PlatformService(SQLiteRepository(self.path))
        machine = service.create_machine({'name': 'Existing', 'endpoint': 'https://compute.lan:9443'})
        agent = service.create_agent({'name': 'Existing worker', 'role': 'analyst', 'machine_id': machine['id']})
        job = service.create_job({'title': 'Existing job', 'input': 'Keep me', 'agent_id': agent['id']})
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE inference_admission')
            db.execute('DROP TABLE executions')
            db.execute('DROP TABLE workers')
            db.execute('PRAGMA user_version = 1')
            db.commit()
        migrated = PlatformService(SQLiteRepository(self.path))
        self.assertEqual(migrated.list('machines'), [machine])
        self.assertEqual(migrated.list('agents'), [agent])
        self.assertEqual(migrated.list('jobs'), [job])
        self.assertEqual(migrated.list('workers'), [])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 3)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertEqual(PlatformService(SQLiteRepository(self.path)).list('jobs'), [job])
