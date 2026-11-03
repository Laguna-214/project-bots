"""LAN configuration UI; short console code exchanges once for a strong session token."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import ipaddress
import json
from pathlib import Path
import secrets
import ssl
import threading
import time
from urllib.parse import urlsplit

from .cli import codex_status
from .config import PRESETS, load_config, save_config, validate_config

HTML = (Path(__file__).with_name('setup.html')).read_bytes()
SCRIPT = (Path(__file__).with_name('setup.js')).read_bytes()


def make_handler(code, ttl_seconds=600):
    csrf = secrets.token_urlsafe(32)
    pairing_code = code
    deadline = time.monotonic() + ttl_seconds
    session_token = None
    attempts = 0
    pair_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Never log URLs or headers (which may accidentally carry credentials).
            pass

        def respond(self, status, body, kind='application/json; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self'; manifest-src 'self'; worker-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def json_response(self, status, data):
            self.respond(status, json.dumps(data).encode())

        def allowed_host(self):
            host = self.headers.get('Host', '')
            try:
                parsed = urlsplit('http://' + host)
                addr = parsed.hostname
                if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or parsed.port != self.server.server_port:
                    return False
                if addr == 'localhost':
                    return True
                ip = ipaddress.ip_address(addr)
                return ip.is_private or ip.is_loopback
            except (ValueError, TypeError):
                return False

        def same_origin(self, require_origin=False):
            host = self.headers.get('Host', '')
            origin = ('https://' if isinstance(self.connection, ssl.SSLSocket) else 'http://') + host
            return (self.allowed_host() and
                    self.headers.get('X-Setup-Origin') == origin and
                    self.headers.get('Origin', None if require_origin else origin) == origin)

        def authorized(self):
            provided = self.headers.get('Authorization', '')
            return (self.same_origin() and session_token is not None and
                    hmac.compare_digest(provided.encode(), ('Bearer ' + session_token).encode()))

        def authorized_write(self):
            return (self.same_origin(require_origin=True) and self.authorized() and
                    hmac.compare_digest(self.headers.get('X-CSRF-Token', '').encode(), csrf.encode()))

        def do_GET(self):
            if not self.allowed_host():
                self.json_response(403, {'error': 'Forbidden'})
            elif self.path == '/':
                self.respond(200, HTML, 'text/html; charset=utf-8')
            elif self.path == '/setup.js':
                self.respond(200, SCRIPT, 'text/javascript; charset=utf-8')
            elif self.path in ('/api/session', '/api/config'):
                if not self.authorized():
                    self.json_response(403, {'error': 'Forbidden'})
                elif self.path == '/api/session':
                    status, ready = codex_status()
                    self.json_response(200, {'csrf': csrf, 'presets': {k: {'label': v[0], 'endpoint': v[1], 'api_key_env': v[2]} for k, v in PRESETS.items()}, 'codex': {'status': status, 'signed_in': ready}})
                else:
                    self.json_response(200, {'config': load_config()})
            else:
                self.json_response(404, {'error': 'Not found'})

        def do_POST(self):
            nonlocal pairing_code, session_token, attempts
            if self.path == '/api/pair':
                if not self.same_origin(require_origin=True):
                    self.json_response(403, {'error': 'Forbidden'})
                    return
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if self.headers.get('Content-Type') != 'application/json' or not 0 < length <= 128:
                        raise ValueError
                    submitted = json.loads(self.rfile.read(length))
                    candidate = submitted.get('code') if isinstance(submitted, dict) else None
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                    candidate = None
                with pair_lock:
                    if attempts >= 5:
                        self.json_response(429, {'error': 'Too many attempts. Restart setup for a new code.'})
                    elif pairing_code is None or time.monotonic() >= deadline:
                        self.json_response(403, {'error': 'Code expired or already used. Restart setup.'})
                    elif not isinstance(candidate, str) or not candidate.isascii() or not hmac.compare_digest(candidate.encode(), pairing_code.encode()):
                        attempts += 1
                        self.json_response(403, {'error': 'Invalid code'})
                    else:
                        pairing_code = None
                        session_token = secrets.token_urlsafe(32)
                        self.json_response(200, {'token': session_token})
                return
            if self.path != '/api/config':
                self.json_response(404, {'error': 'Not found'})
                return
            if not self.authorized_write():
                self.json_response(403, {'error': 'Forbidden'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if self.headers.get('Content-Type') != 'application/json' or not 0 < length <= 4096:
                    raise ValueError('Expected JSON under 4 KiB')
                data = json.loads(self.rfile.read(length))
                save_config(validate_config(data))
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.json_response(400, {'error': str(exc)})
                return
            self.json_response(200, {'saved': True})

    return Handler


def serve(host='0.0.0.0', port=8032):
    code = f'{secrets.randbelow(100_000_000):08d}'
    with ThreadingHTTPServer((host, port), make_handler(code)) as server:
        print(f'Setup listening on http://{host}:{server.server_port} (open using your server LAN IP)', flush=True)
        print('Setup pairing code (expires in 10 minutes): ' + code, flush=True)
        print('The code works once; five wrong attempts lock setup until restart.', flush=True)
        print('Only use on a trusted LAN. Never enter API keys in this page. Ctrl-C to stop.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
