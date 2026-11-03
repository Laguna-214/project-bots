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


def chat_request(repository, method, path, data, actor):
    """Narrow chat routing; non-admin callers never reach legacy admin routes."""
    from urllib.parse import urlsplit, parse_qs
    from .chat import ChatService
    target = urlsplit(path)
    parts = target.path.split('/')
    chat = ChatService(repository)
    is_messages = len(parts) == 5 and parts[1:3] == ['api', 'chats'] and parts[4] == 'messages'
    if actor != 'admin' and not ((method == 'GET' and target.path == '/api/chats') or is_messages):
        raise PermissionError('Forbidden')
    if target.path == '/api/chats' and not target.query:
        return (chat.list(actor), 200) if method == 'GET' else (chat.create(data), 201)
    if is_messages:
        query = parse_qs(target.query, keep_blank_values=True, strict_parsing=True)
        if query.keys() - {'after'} or any(len(v) != 1 for v in query.values()):
            raise ValueError('Invalid cursor')
        if method == 'GET':
            return chat.history(parts[3], int(query.get('after', ['0'])[0]), actor), 200
        if target.query:
            raise ValueError('Unexpected query')
        return chat.send(parts[3], data, actor), 201
    if len(parts) == 5 and parts[1:3] == ['api', 'chats'] and parts[4] == 'members' and method == 'POST' and not target.query:
        return chat.set_members(parts[3], data), 200
    if len(parts) == 5 and parts[1:3] == ['api', 'agents'] and parts[4] == 'chat-identity' and method == 'POST' and not target.query:
        return chat.configure_identity(parts[3], data), 200
    if len(parts) == 5 and parts[1:3] == ['api', 'agents'] and parts[4] == 'conversation' and not target.query:
        from .conversations import ConversationService
        conversations = ConversationService(repository)
        return (conversations.configuration(parts[3]), 200) if method == 'GET' else (conversations.configure(parts[3], data), 200)
    if target.path == '/api/conversations/jobs' and method == 'GET':
        from .conversations import ConversationService
        query = parse_qs(target.query, keep_blank_values=True, strict_parsing=True)
        if query.keys() - {'chat_id'} or any(len(v) != 1 for v in query.values()):
            raise ValueError('Invalid job filter')
        return ConversationService(repository).jobs(query.get('chat_id', [None])[0]), 200
    if len(parts) == 6 and parts[1:4] == ['api', 'conversations', 'jobs'] and parts[5] == 'cancel' and method == 'POST' and not target.query:
        from .conversations import ConversationService
        if data != {}:
            raise ValueError('Empty cancellation required')
        return ConversationService(repository).cancel(parts[4]), 200
    if path == '/api/security/events' and method == 'GET':
        return chat.events(), 200
    if parts[1:3] == ['api', 'chats']:
        raise LookupError('Unknown chat route')
    return None


def security_request(service, method, path, data):
    from .security import SecurityService
    security = SecurityService(service.repository, service.compute_request)
    parts = path.split('/')
    if method == 'GET' and path == '/api/security/status':
        return security.status(), 200
    if path == '/api/security/incidents':
        return (security.incidents(), 200) if method == 'GET' else (security.report(data), 201)
    if method == 'POST' and path == '/api/security/emergency-stop':
        return security.emergency_stop(data), 200
    if method == 'POST' and path == '/api/security/recover':
        return security.recover(data), 200
    if len(parts) == 5 and parts[3] == 'incidents' and method == 'GET':
        return security.incident(parts[4]), 200
    if len(parts) == 6 and parts[3] == 'incidents' and method == 'POST':
        if parts[5] == 'acknowledge':
            return security.acknowledge(parts[4], data), 200
        if parts[5] == 'recover':
            return security.recover(data, parts[4]), 200
    raise LookupError('Unknown security route')


def make_platform_handler(code, service, ttl_seconds=600):
    base = make_handler(code, ttl_seconds)
    from .permissions import Permissions
    permissions = Permissions(service.repository)
    from .approvals import Approvals
    approvals = Approvals(service.repository)

    class Handler(base):
        def integration_actor(self):
            if not self.allowed_host() or any(k in self.headers for k in ('Origin', 'Sec-Fetch-Site', 'X-Setup-Origin')):
                return None
            return permissions.authenticate(self.headers.get('Authorization', ''))

        def chat_actor(self):
            from .chat import ChatService
            if not self.allowed_host() or any(k in self.headers for k in ('Origin', 'Sec-Fetch-Site', 'X-Setup-Origin')):
                return None
            return ChatService(service.repository).authenticate(self.headers.get('Authorization', ''), service.get_settings()['machine_api_env'])

        def machine_authorized(self):
            # Machine credentials cannot bypass browser Origin/CSRF checks.
            if not self.allowed_host() or any(key in self.headers for key in ('Origin', 'Sec-Fetch-Site', 'X-Setup-Origin')):
                return False
            reference = service.get_settings()['machine_api_env']
            secret = os.environ.get(reference, '')
            supplied = self.headers.get('Authorization', '')
            # A changed environment/settings must not promote a chat credential.
            from .chat import ChatService
            if permissions.lower_credential(supplied):
                return False
            return len(secret) >= 32 and hmac.compare_digest(supplied.encode(), ('Bearer ' + secret).encode())

        def do_GET(self):
            if not self.allowed_host():
                self.json_response(403, {'error': 'Forbidden'})
            elif self.path == '/':
                self.respond(200, Path(__file__).with_name('dashboard.html').read_bytes(), 'text/html; charset=utf-8')
            elif self.path in ('/manifest.webmanifest', '/client.js', '/client-sw.js', '/client-icon.svg', '/conversations.js', '/approvals.js'):
                kind = {'/manifest.webmanifest':'application/manifest+json', '/client.js':'text/javascript; charset=utf-8', '/client-sw.js':'text/javascript; charset=utf-8', '/client-icon.svg':'image/svg+xml', '/conversations.js':'text/javascript; charset=utf-8', '/approvals.js':'text/javascript; charset=utf-8'}[self.path]
                self.respond(200, Path(__file__).with_name(self.path[1:]).read_bytes(), kind)
            elif self.path == '/dashboard.js':
                self.respond(200, Path(__file__).with_name('dashboard.js').read_bytes(), 'text/javascript; charset=utf-8')
            elif self.path == '/security.js':
                self.respond(200, Path(__file__).with_name('security.js').read_bytes(), 'text/javascript; charset=utf-8')
            elif self.path == '/chat.js':
                self.respond(200, Path(__file__).with_name('chat.js').read_bytes(), 'text/javascript; charset=utf-8')
            elif self.path == '/api/session':
                super().do_GET()
            elif self.authorized() or self.machine_authorized():
                self.dispatch('GET', human=self.authorized())
            else:
                integration = self.integration_actor()
                if integration:
                    self.dispatch('GET', integration, integration=True)
                    return
                actor = self.chat_actor()
                if actor:
                    self.dispatch('GET', actor)
                else:
                    self.json_response(403, {'error': 'Forbidden'})

        def do_POST(self):
            if self.path == '/api/pair':
                super().do_POST()
            elif self.authorized_write() or self.machine_authorized():
                self.dispatch('POST', human=self.authorized_write())
            else:
                integration = self.integration_actor()
                if integration:
                    self.dispatch('POST', integration, integration=True)
                    return
                actor = self.chat_actor()
                if actor:
                    self.dispatch('POST', actor)
                else:
                    self.json_response(403, {'error': 'Forbidden'})

        def dispatch(self, method, actor='admin', human=False, integration=False):
            operation_id = None
            succeeded = False
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
                if parts[1:3] in (['api', 'approvals'], ['api', 'integration-operations']):
                    if self.path in ('/api/approvals', '/api/integration-operations') and method == 'GET':
                        result = approvals.listing(actor if integration else None, human, self.path.endswith('integration-operations'))
                        self.json_response(200, result)
                        return
                    if self.path == '/api/approvals' and method == 'POST':
                        if not integration:
                            raise PermissionError('Integration requester required')
                        self.json_response(201, approvals.request(actor, data))
                        return
                    if len(parts) == 5 and method == 'POST' and parts[2] == 'approvals':
                        self.json_response(200, approvals.decision(parts[3], parts[4], data, human))
                        return
                    raise LookupError('Unknown approval route')
                if parts[1:3] == ['api', 'integrations']:
                    if self.path == '/api/integrations':
                        result = permissions.principals(human) if method == 'GET' else permissions.issue(data, human)
                        self.json_response(200 if method == 'GET' else 201, result)
                        return
                    if len(parts) == 5 and parts[4] == 'revoke' and method == 'POST':
                        self.json_response(200, permissions.revoke(parts[3], data, human))
                        return
                    raise LookupError('Unknown integration route')
                if integration:
                    permissions.authorize(actor, method, self.path)
                    if method == 'POST':
                        operation_id = approvals.consume(actor, self.headers.get('X-Approval-ID'), method, self.path, data)
                chat_result = None if integration else chat_request(service.repository, method, self.path, data, actor)
                if chat_result is not None:
                    result, status = chat_result
                elif parts[1:3] == ['api', 'security']:
                    result, status = security_request(service, method, self.path, data)
                elif self.path in ('/api/machines', '/api/agents', '/api/jobs'):
                    collection = parts[2]
                    if method == 'GET':
                        result, status = service.list(collection), 200
                    else:
                        create = {'machines': service.create_machine, 'agents': service.create_agent, 'jobs': service.create_job}[collection]
                        result, status = create(data), 201
                elif 5 <= len(parts) <= 7 and parts[1:3] == ['api', 'machines']:
                    result, status = service.compute_request(parts[3], method, '/'.join(parts[4:]), data), 200
                elif len(parts) == 6 and parts[1:3] == ['api', 'agents'] and parts[4:] == ['worker', 'health'] and method == 'GET':
                    from .service import identifier
                    identifier(parts[3])
                    result, status = service.check_worker_identity(service.repository.worker(parts[3])), 200
                elif len(parts) == 5 and parts[1:3] == ['api', 'agents'] and parts[4] == 'worker':
                    from .service import identifier
                    identifier(parts[3])
                    result = service.repository.worker(parts[3]) if method == 'GET' else service.register_worker(parts[3], data)
                    status = 200
                elif self.path == '/api/roles' and method == 'GET':
                    from .workers import role_presets
                    result, status = role_presets(), 200
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
                succeeded = True
                self.json_response(status, result)
            except PermissionError:
                self.json_response(403, {'error': 'Forbidden'})
            except TimeoutError:
                self.json_response(503, {'error': 'Inference admission deadline exceeded before dispatch; job remains queued'})
            except ComputeUnavailable:
                self.json_response(503, {'error': 'Compute unavailable or outcome uncertain; inspect operation before retrying'})
            except ConflictError as exc:
                self.json_response(409, {'error': str(exc)})
            except LookupError:
                self.json_response(404, {'error': 'Not found'})
            except (ValueError, UnicodeDecodeError, RecursionError):
                # Never echo submitted values (which could contain credentials).
                self.json_response(400, {'error': 'Invalid request'})
            finally:
                if operation_id:
                    approvals.finish(operation_id, succeeded)

    return Handler


def serve(host='127.0.0.1', port=8032, tls_cert=None, tls_key=None):
    import ssl
    if bool(tls_cert) != bool(tls_key):
        raise ValueError('HTTPS requires both certificate and private key')
    context = None
    if tls_cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(tls_cert, tls_key)
    path = os.environ.get('PROJECT_BOTS_DB', str(Path.home() / '.local/share/project-bots/platform.db'))
    service = PlatformService(SQLiteRepository(path))
    code = f'{secrets.randbelow(100_000_000):08d}'
    with ThreadingHTTPServer((host, port), make_platform_handler(code, service)) as server:
        if context is not None:
            server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = 'https' if context is not None else 'http'
        print(f'Workforce listening on {scheme}://{host}:{server.server_port}', flush=True)
        print('Platform pairing code (expires in 10 minutes): ' + code, flush=True)
        print('One use; five incorrect attempts lock pairing until restart. Trusted LAN or SSH tunnel only.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
