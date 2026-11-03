"""Shared-client static contracts; no production browser or VM mutation."""
from contextlib import closing
from http.server import ThreadingHTTPServer
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from project_bots.platform_web import make_platform_handler
from project_bots.repository import SQLiteRepository
from project_bots.service import PlatformService


class SharedClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        repo = SQLiteRepository(Path(self.temp.name) / 'private' / 'db')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_platform_handler('01234567', PlatformService(repo)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)

    def get(self, path):
        with closing(http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)) as conn:
            conn.request('GET', path)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode()

    def test_manifest_and_network_only_service_worker(self):
        status, headers, body = self.get('/manifest.webmanifest')
        self.assertEqual(status, 200, body)
        manifest = json.loads(body)
        self.assertEqual(manifest['start_url'], '/')
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual(manifest['scope'], '/')
        self.assertTrue(manifest['icons'])
        status, headers, body = self.get('/client-sw.js')
        self.assertEqual(status, 200, body)
        self.assertIn('fetch', body)
        self.assertIn('no-store', body)
        self.assertNotIn('caches.', body)
        self.assertNotIn('IndexedDB', body)
        self.assertNotIn('Authorization', body)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        status, headers, body = self.get('/')
        self.assertIn('manifest-src', headers['Content-Security-Policy'])
        self.assertIn('worker-src', headers['Content-Security-Policy'])
        self.assertIn('/manifest.webmanifest', body)
        self.assertIn('/client.js', body)
        self.assertIn('mobile-primary', body)


if __name__ == '__main__':
    unittest.main()
