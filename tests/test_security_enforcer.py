"""Independent enforcer with real disposable subprocess and HTTP readbacks.

The fixture Machine Manager terminates only its own child; no live VM is touched.
This proves process/API reconciliation, NOT host/network isolation.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from project_bots.repository import SQLiteRepository
from project_bots.service import PlatformService, ConflictError
from project_bots.security import SecurityService, check_agent_execution, enforce_once
from security_fixtures import fixture_security

ROOT = Path(__file__).resolve().parents[1]


class EnforcerProcessTests(unittest.TestCase):
    def test_independent_process_terminates_fixture_and_restart_never_starts_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = SQLiteRepository(Path(tmp) / 'private/state.db')
            platform = PlatformService(repo)
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
            self.addCleanup(lambda: child.poll() is None and (child.terminate(), child.wait(timeout=5)))
            vm_id = str(uuid.uuid4())
            requests = []
            token = 'machine-fixture-' + '0123456789abcdef' * 3
            class Manager(BaseHTTPRequestHandler):
                def log_message(self, *_):
                    pass
                def do_GET(self):
                    requests.append(('GET', self.path))
                    self.send_response(200); self.end_headers()
                    self.wfile.write(json.dumps({'id': vm_id, 'state': 'running' if child.poll() is None else 'shut off'}).encode())
                def do_POST(self):
                    requests.append(('POST', self.path))
                    body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    valid = (self.path == '/v1/vms/' + vm_id + '/force-stop' and self.headers.get('Authorization') == 'Bearer ' + token and body['confirmation'] == 'force-stop:' + vm_id)
                    self.send_response(200 if valid else 403); self.end_headers()
                    if valid:
                        child.kill(); child.wait(timeout=5)
                    self.wfile.write(b'{}')
            server = ThreadingHTTPServer(('127.0.0.1', 0), Manager)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
            machine = platform.create_machine({'name': 'fixture', 'endpoint': 'http://127.0.0.1:' + str(server.server_port), 'credential_env': 'FIXTURE_COMPUTE'})
            aid = platform.create_agent({'name': 'fixture child', 'role': 'r', 'machine_id': machine['id']})['id']
            worker = repo.save_worker({'agent_id': aid, 'vm_id': vm_id, 'credential_env': 'FIXTURE_WORKER', 'profile': {}})
            fixture_security(repo)
            job = platform.create_job({'title': 'fixture running', 'input': 'x', 'agent_id': aid})
            repo.begin_execution(job['id'], worker)
            # Record stop without an available compute client: partial and still running.
            sec = SecurityService(repo)
            with patch.dict(os.environ, {'FIXTURE_WORKER': 'worker-old-' + 'a' * 40}):
                sec.emergency_stop({'reason': 'fixture process termination'})
            self.assertIsNone(child.poll())
            env = dict(os.environ, FIXTURE_COMPUTE=token, FIXTURE_WORKER='worker-old-' + 'a' * 40)
            command = [sys.executable, '-m', 'project_bots.security', '--db', str(repo.path), '--once']
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIsNotNone(child.poll(), (requests, sec.incidents(), result.stdout, result.stderr))
            self.assertEqual(repo.execution(job['id'])['status'], 'terminated')
            incident = sec.incidents()['incidents'][0]
            self.assertTrue(any(a['action'] == 'runtime_shutdown' and a['status'] == 'verified' for a in incident['actions']))
            self.assertEqual(incident['outcome'], 'partial')  # network and forced destroy absent
            again = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(sum(method == 'POST' for method, _ in requests), 1)
            with self.assertRaises(ConflictError):
                platform.compute_request(machine['id'], 'POST', 'vms/' + vm_id + '/start', {'confirmation': 'start:' + vm_id, 'operation_id': str(uuid.uuid4())})
            self.assertTrue(sec.status()['global_stop'])
            self.assertIsNotNone(child.poll(), (requests, sec.incidents(), result.stdout, result.stderr))
            sec.acknowledge(incident['id'], {'note': 'fixture reviewed'})
            fixture_security(repo)
            with patch.dict(os.environ, {'FIXTURE_WORKER': 'worker-old-' + 'a' * 40}):
                with self.assertRaises(ConflictError):
                    sec.recover({'note': 'boolean assertion is not rotation', 'credential_rotated': True}, incident['id'])
            with patch.dict(os.environ, {'FIXTURE_WORKER': 'worker-new-' + '0123456789abcdef' * 3}):
                recovered = sec.recover({'note': 'fixture telemetry and rotation verified', 'credential_rotated': True}, incident['id'])
                self.assertEqual(recovered['status'], 'recovered')
                self.assertTrue(sec.status()['global_stop'])
                enforce_once(repo, platform.compute_request)
                self.assertFalse(sec.status()['agents'][0]['contained'])
                sec.recover({'note': 'explicit global recovery'})
                check_agent_execution(repo, aid)
                self.assertIsNotNone(child.poll())  # recovery does not start anything
            with patch.dict(os.environ, {'FIXTURE_WORKER': 'worker-old-' + 'a' * 40}):
                with self.assertRaises(ConflictError):
                    check_agent_execution(repo, aid)
