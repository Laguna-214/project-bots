import http.client
from http.server import ThreadingHTTPServer
import json
import threading
import unittest

from project_bots.web import make_handler


class PairingSecurityTests(unittest.TestCase):
    def run_server(self, code='00000042', ttl_seconds=600):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(code, ttl_seconds))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def pair(self, server, code):
        port = server.server_port
        origin = f'http://127.0.0.1:{port}'
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
        conn.request('POST', '/api/pair', body=json.dumps({'code': code}), headers={'Origin': origin, 'X-Setup-Origin': origin, 'Content-Type': 'application/json'})
        response = conn.getresponse()
        status, body = response.status, json.loads(response.read())
        conn.close()
        return status, body

    def test_five_wrong_codes_lock_even_correct_code_until_restart(self):
        server, thread = self.run_server()
        try:
            for _ in range(5):
                self.assertEqual(self.pair(server, '99999999')[0], 403)
            self.assertEqual(self.pair(server, '00000042')[0], 429)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_expired_code_is_rejected(self):
        server, thread = self.run_server(ttl_seconds=0)
        try:
            self.assertEqual(self.pair(server, '00000042')[0], 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_leading_zero_code_pairs_once(self):
        server, thread = self.run_server()
        try:
            status, body = self.pair(server, '00000042')
            self.assertEqual(status, 200)
            self.assertGreaterEqual(len(body['token']), 32)
            self.assertEqual(self.pair(server, '00000042')[0], 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
