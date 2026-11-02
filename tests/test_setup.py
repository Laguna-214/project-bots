import contextlib
import io
import json
import http.client
import threading
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ConfigTests(unittest.TestCase):
    def test_presets_validate_and_save_private_atomically(self):
        from project_bots.config import PRESETS, save_config, load_config, validate_config
        self.assertTrue({'openai', 'anthropic', 'google', 'xai', 'openrouter', 'deepseek', 'mistral', 'groq', 'together', 'fireworks', 'ollama', 'lmstudio', 'codex', 'custom'} <= PRESETS.keys())
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'nested' / 'config.json'
            config = validate_config({'provider': 'custom', 'endpoint': 'https://api.example.com/v1', 'model': 'vendor/model', 'api_key_env': 'MY_API_KEY'})
            save_config(config, path)
            self.assertEqual(load_config(path), config)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(path.parent.glob('*.tmp')), [])
            with self.assertRaises(ValueError):
                validate_config({'provider': 'custom', 'endpoint': 'http://public.example/v1', 'model': 'ok'})
            with self.assertRaises(ValueError):
                validate_config({'provider': 'openai', 'model': 'bad model', 'api_key_env': 'INVALID-NAME'})
            with self.assertRaises(ValueError):
                validate_config({'provider': 'madeup', 'model': 'ok'})
            with self.assertRaises(ValueError):
                validate_config({'provider': 'custom', 'endpoint': 'https://user:pass@example.com', 'model': 'ok'})


class CliTests(unittest.TestCase):
    def test_local_wizard_and_codex_missing(self):
        from project_bots.cli import main
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'PROJECT_BOTS_CONFIG': str(Path(d) / 'config.json'), 'PATH': d}):
            with patch('builtins.input', side_effect=['ollama', 'llama3', '', '']), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['setup', 'local']), 0)
            self.assertIn('Saved', out.getvalue())
            self.assertEqual(json.loads((Path(d) / 'config.json').read_text())['provider'], 'ollama')
            with contextlib.redirect_stdout(io.StringIO()) as status:
                self.assertNotEqual(main(['codex', 'status']), 0)
            self.assertIn('not installed', status.getvalue())

    def test_installer_from_fresh_clone_runs_cli(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, HOME=d)
            p = subprocess.run(['sh', str(ROOT / 'install.sh')], cwd=ROOT, env=env, text=True, capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            exe = Path(d) / '.local/bin/project-bots'
            self.assertTrue(exe.is_file())
            p = subprocess.run([str(exe), '--help'], cwd=d, env=env, text=True, capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn('setup web', p.stdout)
            web = subprocess.Popen([str(exe), 'setup', 'web', '--host', '127.0.0.1', '--port', '0'], cwd=d, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                listening = web.stdout.readline()
                token_line = web.stdout.readline()
                self.assertRegex(token_line, r'^Setup pairing code \(expires in 10 minutes\): [0-9]{8}\n$')
                port = int(listening.split(':')[-1].split()[0])
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
                conn.request('GET', '/')
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn('Set up your provider', response.read().decode())
                conn.close()
            finally:
                web.terminate()
                web.communicate(timeout=5)


class WebTests(unittest.TestCase):
    def test_setup_http_requires_token_origin_host_and_csrf_without_keys(self):
        from project_bots.web import make_handler
        from project_bots.config import load_config
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'PROJECT_BOTS_CONFIG': str(Path(d) / 'config.json')}):
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler('12345678'))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            port = server.server_port
            origin = f'http://127.0.0.1:{port}'
            def request(method, path, headers=None, body=None):
                conn = http.client.HTTPConnection('127.0.0.1', port)
                conn.request(method, path, body=body, headers=headers or {})
                resp = conn.getresponse()
                result = resp.status, dict(resp.getheaders()), resp.read().decode()
                conn.close()
                return result
            try:
                status, hdr, html = request('GET', '/')
                self.assertEqual(status, 200)
                self.assertNotIn('12345678', html)
                self.assertNotIn('id="api_key"', html.lower())
                self.assertIn('Content-Security-Policy', hdr)
                self.assertIn('<script src="/setup.js"></script>', html)
                self.assertIn('8-digit', html)
                status, _, script = request('GET', '/setup.js')
                self.assertEqual(status, 200)
                self.assertIn("api('/api/pair'", script)
                self.assertEqual(request('GET', '/api/session')[0], 403)
                pairing_headers = {'Origin': origin, 'X-Setup-Origin': origin, 'Content-Type': 'application/json'}
                pair_body = json.dumps({'code': '12345678'})
                self.assertEqual(request('POST', '/api/pair', {'Content-Type': 'application/json'}, pair_body)[0], 403)
                self.assertEqual(request('POST', '/api/pair', dict(pairing_headers, Host='evil.test'), pair_body)[0], 403)
                self.assertEqual(request('POST', '/api/pair', pairing_headers, json.dumps({'code': '00000000'}))[0], 403)
                status, _, body = request('POST', '/api/pair', pairing_headers, pair_body)
                self.assertEqual(status, 200)
                session_token = json.loads(body)['token']
                self.assertGreaterEqual(len(session_token), 32)
                self.assertNotEqual(session_token, '12345678')
                self.assertEqual(request('POST', '/api/pair', pairing_headers, pair_body)[0], 403)
                auth = {'Authorization': 'Bearer ' + session_token, 'Origin': origin, 'X-Setup-Origin': origin}
                self.assertEqual(request('GET', '/api/session', {'Authorization': 'Bearer 12345678', 'Origin': origin, 'X-Setup-Origin': origin})[0], 403)
                self.assertEqual(request('GET', '/api/session', {'Authorization': 'Bearer ' + session_token, 'Origin': 'http://evil.test'})[0], 403)
                self.assertEqual(request('GET', '/api/session', dict(auth, Host='evil.test'))[0], 403)
                status, _, body = request('GET', '/api/session', auth)
                self.assertEqual(status, 200)
                csrf = json.loads(body)['csrf']
                self.assertIn('codex', json.loads(body))
                headers = dict(auth, **{'Content-Type': 'application/json', 'X-CSRF-Token': csrf})
                payload = json.dumps({'provider': 'ollama', 'model': 'llama3'}).encode()
                self.assertEqual(request('POST', '/api/config', auth, payload)[0], 403)
                self.assertEqual(request('POST', '/api/config', headers, json.dumps({'provider': 'openai', 'model': 'gpt-4', 'api_key': 'leak'}))[0], 400)
                self.assertEqual(request('POST', '/api/config', headers, payload)[0], 200)
                self.assertEqual(load_config()['model'], 'llama3')
                self.assertEqual(request('GET', '/api/config', auth)[0], 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
