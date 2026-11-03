"""Installed HTTPS/pairing flow with an ephemeral trusted certificate."""
from contextlib import closing
import http.client
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('openssl'), 'openssl required for disposable TLS fixture')
class HTTPSClientTests(unittest.TestCase):
    def test_installed_https_keeps_origin_csrf_and_certificate_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            cert, key = home / 'cert.pem', home / 'key.pem'
            result = subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                '-keyout', str(key), '-out', str(cert), '-days', '1', '-subj', '/CN=localhost',
                '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'], capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0)
            key.chmod(0o600)
            env = dict(os.environ, HOME=str(home), PROJECT_BOTS_DB=str(home / 'private' / 'db'))
            install = subprocess.run(['sh', str(ROOT / 'install.sh')], env=env, cwd=ROOT,
                                     capture_output=True, text=True, timeout=15)
            self.assertEqual(install.returncode, 0, install.stderr)
            process = subprocess.Popen([str(home / '.local/bin/project-bots'), 'serve', '--port', '0',
                '--tls-cert', str(cert), '--tls-key', str(key)], env=env, cwd=home,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                assert process.stdout is not None
                line = process.stdout.readline()
                if not line:
                    _, error = process.communicate(timeout=5)
                    self.fail('HTTPS command failed to start: ' + error)
                self.assertIn('https://127.0.0.1:', line)
                port = int(line.strip().split(':')[-1])
                code = process.stdout.readline().strip().split()[-1]
                self.assertRegex(code, r'^\d{8}$')
                context = ssl.create_default_context(cafile=str(cert))
                origin = 'https://127.0.0.1:' + str(port)
                def request(method, path, data=None, headers=None):
                    with closing(http.client.HTTPSConnection('127.0.0.1', port, context=context, timeout=5)) as conn:
                        conn.request(method, path, json.dumps(data) if data is not None else None,
                                     headers or {})
                        response = conn.getresponse()
                        return response.status, response.read().decode()
                self.assertEqual(request('GET', '/')[0], 200)
                bad = {'Origin':origin.replace('https:', 'http:'), 'X-Setup-Origin':origin,
                       'Content-Type':'application/json'}
                self.assertEqual(request('POST', '/api/pair', {'code':code}, bad)[0], 403)
                good = dict(bad, Origin=origin)
                status, body = request('POST', '/api/pair', {'code':code}, good)
                self.assertEqual(status, 200, body)
                token = json.loads(body)['token']
                status, body = request('GET', '/api/session', headers={'Authorization':'Bearer '+token,
                                       'X-Setup-Origin':origin})
                self.assertEqual(status, 200, body)
                csrf = json.loads(body)['csrf']
                good.update(Authorization='Bearer '+token)
                self.assertEqual(request('POST', '/api/agents', {'name':'TLS agent','role':'research'}, good)[0], 403)
                good['X-CSRF-Token'] = csrf
                self.assertEqual(request('POST', '/api/agents', {'name':'TLS agent','role':'research'}, good)[0], 201)
                with self.assertRaises(ssl.SSLCertVerificationError):
                    with closing(http.client.HTTPSConnection('127.0.0.1', port, timeout=5)) as conn:
                        conn.request('GET', '/')
                        conn.getresponse()
            finally:
                if process.poll() is None:
                    process.terminate()
                process.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
