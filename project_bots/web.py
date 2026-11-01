"""LAN configuration UI; bootstrap token stays in process memory."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import ipaddress
import json
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from .cli import codex_status
from .config import PRESETS, load_config, save_config, validate_config

HTML = (Path(__file__).with_name('setup.html')).read_bytes()
SCRIPT = (Path(__file__).with_name('setup.js')).read_bytes()


def make_handler(token):
    csrf = secrets.token_urlsafe(32)

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
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'")
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

        def authorized(self):
            host = self.headers.get('Host', '')
            return (self.allowed_host() and
                    self.headers.get('X-Setup-Origin') == 'http://' + host and
                    self.headers.get('Origin', 'http://' + host) == 'http://' + host and
                    hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token))

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
            if self.path != '/api/config':
                self.json_response(404, {'error': 'Not found'})
                return
            if not self.authorized() or not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), csrf):
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
    token = secrets.token_urlsafe(32)
    with ThreadingHTTPServer((host, port), make_handler(token)) as server:
        print(f'Setup listening on http://{host}:{server.server_port} (open using your server LAN IP)', flush=True)
        print('Bootstrap access token (this run only): ' + token, flush=True)
        print('Only use on a trusted LAN. Never enter API keys in this page. Ctrl-C to stop.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
