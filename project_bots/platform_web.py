"""Authenticated platform HTTP adapter, including explicit Stage 2 compute routes."""
from http.server import ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import secrets

from .compute import ComputeUnavailable
from .repository import SQLiteRepository
from .service import ConflictError, PlatformService
from .web import make_handler


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


def make_platform_handler(code, service, ttl_seconds=600):
    base = make_handler(code, ttl_seconds)

    class Handler(base):
        def machine_authorized(self):
            # Machine credentials cannot bypass browser Origin/CSRF checks.
            if not self.allowed_host() or any(key in self.headers for key in ('Origin', 'Sec-Fetch-Site', 'X-Setup-Origin')):
                return False
            reference = service.get_settings()['machine_api_env']
            secret = os.environ.get(reference, '')
            supplied = self.headers.get('Authorization', '')
            return len(secret) >= 32 and hmac.compare_digest(supplied.encode(), ('Bearer ' + secret).encode())

        def do_GET(self):
            if not self.allowed_host():
                self.json_response(403, {'error': 'Forbidden'})
            elif self.path == '/':
                self.respond(200, Path(__file__).with_name('dashboard.html').read_bytes(), 'text/html; charset=utf-8')
            elif self.path == '/dashboard.js':
                self.respond(200, Path(__file__).with_name('dashboard.js').read_bytes(), 'text/javascript; charset=utf-8')
            elif self.path == '/api/session':
                super().do_GET()
            elif not (self.authorized() or self.machine_authorized()):
                self.json_response(403, {'error': 'Forbidden'})
            else:
                self.dispatch('GET')

        def do_POST(self):
            if self.path == '/api/pair':
                super().do_POST()
            elif not (self.authorized_write() or self.machine_authorized()):
                self.json_response(403, {'error': 'Forbidden'})
            else:
                self.dispatch('POST')

        def dispatch(self, method):
            try:
                data = None
                if method == 'POST':
                    length = int(self.headers.get('Content-Length', '0'))
                    if self.headers.get('Content-Type') != 'application/json' or not 0 < length <= 65536:
                        raise ValueError('Expected JSON under 64 KiB')
                    data = json.loads(self.rfile.read(length), object_pairs_hook=unique_object)
                    if not isinstance(data, dict):
                        raise ValueError('Expected JSON object')
                parts = self.path.split('/')
                if self.path in ('/api/machines', '/api/agents', '/api/jobs'):
                    collection = parts[2]
                    if method == 'GET':
                        result, status = service.list(collection), 200
                    else:
                        create = {'machines': service.create_machine, 'agents': service.create_agent, 'jobs': service.create_job}[collection]
                        result, status = create(data), 201
                elif 5 <= len(parts) <= 7 and parts[1:3] == ['api', 'machines']:
                    result, status = service.compute_request(parts[3], method, '/'.join(parts[4:]), data), 200
                elif len(parts) == 5 and parts[1:3] == ['api', 'agents'] and parts[4] == 'worker':
                    from .service import identifier
                    identifier(parts[3])
                    result = service.repository.worker(parts[3]) if method == 'GET' else service.register_worker(parts[3], data)
                    status = 200
                elif self.path == '/api/workers' and method == 'GET':
                    result, status = service.list('workers'), 200
                elif self.path in ('/api/models', '/api/models/loaded') and method == 'GET':
                    result, status = service.model_request('loaded' if self.path.endswith('/loaded') else 'tags'), 200
                elif len(parts) == 4 and parts[1:3] == ['api', 'models'] and method == 'POST':
                    result, status = service.model_request(parts[3], data), 200
                elif len(parts) == 5 and parts[1:3] == ['api', 'jobs'] and parts[4] == 'execution' and method == 'GET':
                    result, status = service.repository.execution(parts[3]), 200
                elif len(parts) == 5 and parts[1:3] == ['api', 'jobs'] and parts[4] == 'dispatch' and method == 'POST':
                    result, status = service.dispatch_job(parts[3], data), 200
                elif self.path == '/api/settings':
                    result = service.get_settings() if method == 'GET' else service.save_settings(data)
                    status = 200
                elif len(parts) == 4 and parts[1:3] == ['api', 'jobs'] and method == 'GET':
                    result, status = service.get_job(parts[3]), 200
                elif len(parts) == 5 and parts[1:3] == ['api', 'jobs'] and method == 'POST':
                    result, status = service.job_action(parts[3], parts[4], data), 200
                else:
                    self.json_response(404, {'error': 'Not found'})
                    return
                self.json_response(status, result)
            except ComputeUnavailable:
                self.json_response(503, {'error': 'Compute unavailable or outcome uncertain; inspect operation before retrying'})
            except ConflictError as exc:
                self.json_response(409, {'error': str(exc)})
            except LookupError:
                self.json_response(404, {'error': 'Not found'})
            except (ValueError, UnicodeDecodeError, RecursionError):
                # Never echo submitted values (which could contain credentials).
                self.json_response(400, {'error': 'Invalid request'})

    return Handler


def serve(host='127.0.0.1', port=8032):
    path = os.environ.get('PROJECT_BOTS_DB', str(Path.home() / '.local/share/project-bots/platform.db'))
    service = PlatformService(SQLiteRepository(path))
    code = f'{secrets.randbelow(100_000_000):08d}'
    with ThreadingHTTPServer((host, port), make_platform_handler(code, service)) as server:
        print(f'Workforce listening on http://{host}:{server.server_port}', flush=True)
        print('Platform pairing code (expires in 10 minutes): ' + code, flush=True)
        print('One use; five incorrect attempts lock pairing until restart. Trusted LAN or SSH tunnel only.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
