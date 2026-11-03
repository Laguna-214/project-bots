"""Backend integration authorities. No caller-supplied human flag or token promotion.

Opaque credentials are hashed; grants are immutable exact method/path capabilities.
Human identity is established by the paired browser session in the HTTP adapter.
"""
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid

from .service import ConflictError, fields, identifier, text

POLICY_VERSION = 1
DEFAULT_GRANTS = [{'method': 'GET', 'path': path} for path in ('/api/agents', '/api/workers', '/api/roles')]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def migrate(db):
    db.execute('CREATE TABLE integration_principals (id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, data TEXT NOT NULL)')
    db.execute('CREATE TABLE integration_approvals (id TEXT PRIMARY KEY, actor TEXT NOT NULL REFERENCES integration_principals(id), data TEXT NOT NULL)')
    db.execute('CREATE TABLE integration_operations (id TEXT PRIMARY KEY, approval_id TEXT UNIQUE NOT NULL REFERENCES integration_approvals(id), actor TEXT NOT NULL, data TEXT NOT NULL)')


def route(method, path):
    """Finite supported API surface; never patterns/wildcards or arbitrary shell."""
    if not isinstance(path, str) or not isinstance(method, str):
        raise ValueError('Exact route required')
    parts = path.split('/')
    if method == 'GET' and path in ('/api/agents', '/api/workers', '/api/roles', '/api/machines', '/api/jobs', '/api/models', '/api/models/loaded'):
        return 'read', path
    if method == 'GET' and len(parts) in (4, 5, 6) and parts[1:3] == ['api', 'jobs']:
        if identifier(parts[3]) and (len(parts) == 4 or parts[4:] == ['execution']):
            return 'read', path
    if parts[1:3] == ['api', 'machines'] and len(parts) in (5, 6, 7):
        identifier(parts[3])
        if method == 'GET' and (parts[4:] in (['health'], ['vms']) or (len(parts) == 6 and parts[4] in ('vms', 'operations') and identifier(parts[5]))):
            return 'read', path
        if method == 'POST' and parts[4:] == ['vms']:
            return 'vm.create', '/api/machines/' + parts[3]
        if method == 'POST' and len(parts) == 7 and parts[4] == 'vms' and identifier(parts[5]) and parts[6] in ('start', 'shutdown', 'restart', 'pause', 'resume', 'delete', 'resources', 'snapshot-create', 'snapshot-restore'):
            return 'vm.' + parts[6], '/'.join(parts[:6])
    if method == 'POST' and len(parts) == 5 and parts[1:3] == ['api', 'jobs'] and identifier(parts[3]) and parts[4] in ('dispatch', 'cancel'):
        return 'job.' + parts[4], '/'.join(parts[:4])
    raise ValueError('Unsupported integration action')


class Permissions:
    def __init__(self, repository):
        self.repository = repository

    @staticmethod
    def human(human):
        if human is not True:
            raise PermissionError('Paired human browser required')

    @staticmethod
    def event(db, actor, behavior, resource, outcome):
        from .chat import ChatService
        ChatService.event(db, actor, behavior, resource, outcome)

    def issue(self, data, human=False):
        self.human(human)
        fields(data, ('name', 'expires_in', 'grants'), ('name',))
        name = text(data['name'], 120)
        ttl = data.get('expires_in', 3600)
        if type(ttl) is not int or not 1 <= ttl <= 86400:
            raise ValueError('Token lifetime must be 1–86400 seconds')
        grants = data.get('grants', DEFAULT_GRANTS)
        if not isinstance(grants, list) or not 1 <= len(grants) <= 64:
            raise ValueError('Expected explicit capabilities')
        for grant in grants:
            fields(grant, ('method', 'path'), ('method', 'path'))
            route(grant['method'], grant['path'])
        if len(set(map(canonical, grants))) != len(grants):
            raise ValueError('Duplicate grants')
        token = secrets.token_urlsafe(48)
        principal = {'id': str(uuid.uuid4()), 'name': name, 'grants': grants, 'created_at': time.time(), 'expires_at': time.time() + ttl, 'revoked_at': None, 'revision': 1}
        with self.repository.transaction() as db:
            db.execute('INSERT INTO integration_principals VALUES (?,?,?)', (principal['id'], digest(token), canonical(principal)))
            self.event(db, principal['id'], 'integration_issued', principal['id'], 'issued')
        return dict(principal, token=token)

    @staticmethod
    def active(db, actor):
        row = db.execute('SELECT data FROM integration_principals WHERE id=?', (actor,)).fetchone()
        if not row:
            raise PermissionError('Forbidden')
        principal = json.loads(row[0])
        if principal['revoked_at'] is not None or principal['expires_at'] <= time.time():
            raise PermissionError('Forbidden')
        return principal

    def is_credential(self, supplied):
        if not supplied.startswith('Bearer '):
            return False
        with self.repository.transaction() as db:
            return db.execute('SELECT 1 FROM integration_principals WHERE token_hash=?', (digest(supplied[7:]),)).fetchone() is not None

    def authenticate(self, supplied):
        if not supplied.startswith('Bearer '):
            return None
        with self.repository.transaction() as db:
            row = db.execute('SELECT id FROM integration_principals WHERE token_hash=?', (digest(supplied[7:]),)).fetchone()
            if not row:
                return None
            try:
                return self.active(db, row[0])['id']
            except PermissionError:
                return None

    def principals(self, human=False):
        self.human(human)
        with self.repository.transaction() as db:
            return {'integrations': [json.loads(r[0]) for r in db.execute('SELECT data FROM integration_principals ORDER BY rowid DESC')]}

    def revoke(self, actor, data, human=False):
        self.human(human)
        fields(data, ())
        with self.repository.transaction() as db:
            row = db.execute('SELECT data FROM integration_principals WHERE id=?', (actor,)).fetchone()
            if not row:
                raise LookupError('Unknown integration')
            principal = json.loads(row[0])
            principal.update(revoked_at=time.time(), revision=principal['revision'] + 1)
            db.execute('UPDATE integration_principals SET data=? WHERE id=?', (canonical(principal), actor))
            self.event(db, actor, 'integration_revoked', actor, 'revoked')
        return principal

    def authorize(self, actor, method, path, db=None):
        if db is None:
            with self.repository.transaction() as connection:
                return self.authorize(actor, method, path, connection)
        principal = self.active(db, actor)
        if {'method': method, 'path': path} not in principal['grants']:
            raise PermissionError('Forbidden')
        route(method, path)
        return principal

    def lower_credential(self, supplied):
        """Never promote worker/inference credentials to the explicit owner key."""
        from .chat import ChatService
        chat = ChatService(self.repository)
        if self.is_credential(supplied) or chat.is_chat_credential(supplied):
            return True
        owner = (self.repository.get_settings() or {}).get('machine_api_env', 'PROJECT_BOTS_API_TOKEN')
        references = chat.protected_references() - {owner}
        references.update({'PROJECT_BOTS_COMPUTE_TOKEN', 'PROJECT_BOTS_INFERENCE_ADMIN_TOKEN', 'PROJECT_BOTS_LLAMA_BACKEND_TOKEN'})
        if os.environ.get('PROJECT_BOTS_LLAMA_TOKEN_ENV'):
            references.add(os.environ['PROJECT_BOTS_LLAMA_TOKEN_ENV'])
        # Set subtraction must not erase a same-reference lower-authority binding.
        references.update(w['credential_env'] for w in self.repository.list('workers'))
        references.update(a.get('config', {}).get('credential_env') for a in self.repository.list('agents') if a.get('config', {}).get('credential_env'))
        references.update(m['credential_env'] for m in self.repository.list('machines') if m.get('credential_env'))
        return any(os.environ.get(ref) and hmac.compare_digest(supplied.encode(), ('Bearer ' + os.environ[ref]).encode()) for ref in references)
