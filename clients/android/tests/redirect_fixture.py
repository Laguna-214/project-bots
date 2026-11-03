#!/usr/bin/env python3
"""Loopback-only Chromium/Android redirect fixture; not an acceptance test.

Open http://127.0.0.1:18761/ (strict response CSP) and /unprotected
(no CSP) in separate fresh pages. /stats records synthetic fixture requests.
The forbidden origin is 127.0.0.1:18762. Never send real credentials here.
Stop with Ctrl-C. Requires an independent browser/device to exercise it.
"""
import http.server
import json
import threading
from typing import cast

hits = []


class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        port = cast(http.server.HTTPServer, self.server).server_port
        hits.append([port, self.path])
        if port == 18762:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'window.forbiddenScriptRan=true;')
            return
        if self.path == '/stats':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(json.dumps(hits).encode())
            return
        if self.path.startswith('/redirect-'):
            self.send_response(302)
            self.send_header('Location', 'http://127.0.0.1:18762/' + self.path[10:])
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Cache-Control', 'no-store')
        if self.path != '/unprotected':
            self.send_header('Content-Security-Policy',
                             "default-src 'self'; script-src 'self'; img-src 'self'; "
                             "connect-src 'self'; style-src 'self'; frame-src 'none'; "
                             "object-src 'none'; worker-src 'none'; base-uri 'none'; "
                             "form-action 'self'")
        self.end_headers()
        self.wfile.write(b'<script src="/redirect-script"></script>'
                        b'<img src="/redirect-image">'
                        b'<link rel="stylesheet" href="/redirect-style">')

    def log_message(self, format: str, *args: object):
        pass


if __name__ == '__main__':
    servers = [http.server.ThreadingHTTPServer(('127.0.0.1', p), Fixture)
               for p in (18761, 18762)]
    try:
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        print('Fixture ready: 18761 trusted, 18762 forbidden', flush=True)
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
