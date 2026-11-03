"""Dedicated compute API. No browser authentication, CORS or command passthrough."""
import hmac
from http.server import BaseHTTPRequestHandler
import ipaddress
import json
from .compute import ComputeUnavailable
from .service import ConflictError


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


def loopback(host):
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == 'localhost'


def validate_listener(host, token, cert, key):
    if not isinstance(token, str) or len(token) < 32 or len(set(token)) < 16 or not token.isascii() or any(c.isspace() for c in token):
        raise ValueError('Set a high-entropy machine token of at least 32 characters')
    if bool(cert) != bool(key) or (not loopback(host) and not (cert and key)):
        raise ValueError('Non-loopback binds require TLS certificate and key')


def make_handler(backend, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def reply(self, status, value):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            supplied = self.headers.get('Authorization', '').encode()
            return not any(k in self.headers for k in ('Origin', 'Sec-Fetch-Site', 'X-Setup-Origin')) and hmac.compare_digest(supplied, ('Bearer ' + token).encode())

        def setup(self):
            super().setup()
            self.connection.settimeout(20)

        def do_GET(self):
            self.dispatch('GET')

        def do_POST(self):
            self.dispatch('POST')

        def dispatch(self, method):
            if not self.authorized():
                self.reply(403, {'error': 'Forbidden'})
                return
            try:
                data = None
                if method == 'POST':
                    length = int(self.headers.get('Content-Length', '0'))
                    if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type') != 'application/json' or not 0 < length <= 16384:
                        raise ValueError('Expected bounded JSON')
                    data = json.loads(self.rfile.read(length), object_pairs_hook=unique_object)
                    if not isinstance(data, dict):
                        raise ValueError('Expected JSON object')
                parts = self.path.split('/')
                if self.path == '/v1/health' and method == 'GET':
                    result = backend.health()
                elif self.path == '/v1/vms':
                    result = backend.list() if method == 'GET' else backend.create(data)
                elif len(parts) == 4 and parts[1:3] == ['v1', 'vms'] and method == 'GET':
                    result = backend.detail(parts[3])
                elif len(parts) == 5 and parts[1:3] == ['v1', 'vms'] and parts[4] == 'network' and method == 'GET':
                    result = backend.network_status(parts[3])
                elif len(parts) == 5 and parts[1:3] == ['v1', 'vms'] and method == 'POST':
                    result = backend.action(parts[3], parts[4], data)
                elif len(parts) == 4 and parts[1:3] == ['v1', 'operations'] and method == 'GET':
                    result = backend.operation(parts[3])
                else:
                    self.reply(404, {'error': 'Not found'}); return
                self.reply(200, result)
            except ConflictError:
                self.reply(409, {'error': 'Operation conflicts or requires local reconciliation'})
            except LookupError:
                self.reply(404, {'error': 'Not found'})
            except (ValueError, UnicodeError, RecursionError):
                self.reply(400, {'error': 'Invalid request'})
            except (ComputeUnavailable, OSError):
                self.reply(503, {'error': 'Host unavailable or outcome uncertain; inspect operation before retrying'})

    return Handler


def compute_backend(protected, state, catalog):
    if protected:
        from .protected_compute import ProtectedClient
        return ProtectedClient()
    from .compute import ComputeService
    return ComputeService(state, catalog)


def serve(host, port, state, catalog, token_env='PROJECT_BOTS_COMPUTE_TOKEN', cert=None, key=None,
          protected=False):
    import os
    import ssl
    from http.server import ThreadingHTTPServer
    from .service import env_reference
    token = os.environ.get(env_reference(token_env), '')
    validate_listener(host, token, cert, key)
    context = None
    if cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert, key)
    backend = compute_backend(protected, state, catalog)
    with ThreadingHTTPServer((host, port), make_handler(backend, token)) as server:
        if context:
            server.socket = context.wrap_socket(server.socket, server_side=True)
        print(f'Machine service listening on {"https" if context else "http"}://{host}:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
