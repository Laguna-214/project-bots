"""Persistent shared-message broker. No runtime execution or private-memory access."""
import json
import sqlite3
import time
import uuid
import os
import hmac
from contextlib import contextmanager
from .service import ConflictError, fields, identifier, text, env_reference


def migrate(db):
    db.execute('CREATE TABLE chats (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
    db.execute('CREATE TABLE chat_members (chat_id TEXT REFERENCES chats(id), agent_id TEXT REFERENCES agents(id), PRIMARY KEY(chat_id,agent_id))')
    db.execute('CREATE TABLE chat_messages (sequence INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL REFERENCES chats(id), sender TEXT NOT NULL, client_id TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL, UNIQUE(chat_id,sender,client_id))')
    db.execute('CREATE INDEX chat_history ON chat_messages(chat_id,sequence)')
    db.execute('CREATE TABLE chat_identities (agent_id TEXT PRIMARY KEY REFERENCES agents(id), credential_env TEXT NOT NULL UNIQUE, enabled INTEGER NOT NULL CHECK(enabled IN (0,1)))')
    db.execute('CREATE TABLE security_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, created_at REAL NOT NULL, agent_id TEXT, behavior TEXT NOT NULL, resource TEXT NOT NULL, outcome TEXT NOT NULL)')


class ChatService:
    def __init__(self, repository):
        self.repository = repository

    @staticmethod
    def event(db, actor, behavior, resource, outcome):
        db.execute('INSERT INTO security_events(id,created_at,agent_id,behavior,resource,outcome) VALUES (?,?,?,?,?,?)', (str(uuid.uuid4()), time.time(), actor, behavior, resource, outcome))

    def protected_references(self, admin_reference=None):
        settings = self.repository.get_settings() or {}
        references = {admin_reference or settings.get('machine_api_env', 'PROJECT_BOTS_API_TOKEN'), 'PROJECT_BOTS_COMPUTE_TOKEN', 'PROJECT_BOTS_INFERENCE_ADMIN_TOKEN', 'PROJECT_BOTS_LLAMA_BACKEND_TOKEN'}
        if os.environ.get('PROJECT_BOTS_LLAMA_TOKEN_ENV'):
            references.add(env_reference(os.environ['PROJECT_BOTS_LLAMA_TOKEN_ENV']))
        references.update(w['credential_env'] for w in self.repository.list('workers'))
        references.update(a.get('config', {}).get('credential_env') for a in self.repository.list('agents') if a.get('config', {}).get('credential_env'))
        references.update(m['credential_env'] for m in self.repository.list('machines') if m['credential_env'])
        return references

    def configure_identity(self, agent_id, data):
        if identifier(agent_id) is None:
            raise ValueError('Agent UUID required')
        fields(data, ('credential_env', 'enabled'), ('credential_env', 'enabled'))
        reference = env_reference(data['credential_env'])
        protected_refs = self.protected_references()
        value = os.environ.get(reference, '')
        if reference in protected_refs or (value and any(value == os.environ.get(r, '') for r in protected_refs)):
            raise ConflictError('Chat credentials must be separate from control-plane credentials')
        if type(data['enabled']) is not bool:
            raise ValueError('Enabled must be boolean')
        try:
            with self.repository.transaction() as db:
                db.execute('INSERT INTO chat_identities VALUES (?,?,?) ON CONFLICT(agent_id) DO UPDATE SET credential_env=excluded.credential_env,enabled=excluded.enabled', (agent_id, reference, int(data['enabled'])))
                self.event(db, agent_id, 'chat_identity_changed', agent_id, 'enabled' if data['enabled'] else 'revoked')
                from .conversations import initialize
                initialize(db)
                db.execute("UPDATE conversation_jobs SET status=CASE WHEN status='running' THEN 'cancelling' ELSE 'cancelled' END,updated_at=? WHERE agent_id=? AND status IN ('queued','running')", (time.time(), agent_id))
        except sqlite3.IntegrityError:
            raise ConflictError('Unknown agent or credential reference already assigned') from None
        return {'agent_id': agent_id, 'credential_env': reference, 'enabled': data['enabled']}

    def authenticate(self, supplied, admin_reference):
        # Reject reused token VALUES too, including Gateway/platform authority.
        with self.repository.transaction() as db:
            identities = db.execute('SELECT * FROM chat_identities').fetchall()
        secrets = [(r['agent_id'], os.environ.get(r['credential_env'], ''), bool(r['enabled'])) for r in identities]
        protected = [os.environ.get(r, '') for r in self.protected_references(admin_reference)]
        matches = [item for item in secrets if len(item[1]) >= 32 and hmac.compare_digest(supplied.encode(), ('Bearer ' + item[1]).encode())]
        if len(matches) != 1 or not matches[0][2] or matches[0][1] in protected:
            return None
        from .security import check_agent_capability
        try:
            check_agent_capability(self.repository, matches[0][0])
        except ConflictError:
            return None
        return matches[0][0]

    def is_chat_credential(self, supplied):
        with self.repository.transaction() as db:
            refs = [r[0] for r in db.execute('SELECT credential_env FROM chat_identities')]
        return any(os.environ.get(r) and hmac.compare_digest(supplied.encode(), ('Bearer ' + os.environ[r]).encode()) for r in refs)

    @contextmanager
    def access(self, chat_id, actor):
        # Membership/identity check and message write share the same transaction.
        denied = False
        with self.repository.transaction() as db:
            revoked = False
            if actor != 'admin':
                from .security import check_agent_capability
                try:
                    check_agent_capability(self.repository, actor, db=db)
                except ConflictError:
                    revoked = True
            if actor != 'admin' and (revoked or not db.execute('SELECT 1 FROM chat_members m JOIN chat_identities i ON i.agent_id=m.agent_id WHERE m.chat_id=? AND m.agent_id=? AND i.enabled=1', (chat_id, actor)).fetchone()):
                self.event(db, actor, 'message_access_denied', chat_id, 'blocked')
                denied = True
            else:
                self.require_chat(db, chat_id)
                yield db
        if denied:
            raise PermissionError('Forbidden')

    def set_members(self, chat_id, data):
        fields(data, ('agent_ids',), ('agent_ids',))
        try:
            with self.repository.transaction() as db:
                chat = self.require_chat(db, chat_id)
                members = self.members(data['agent_ids'], chat['kind'])
                db.execute('DELETE FROM chat_members WHERE chat_id=?', (chat_id,))
                db.executemany('INSERT INTO chat_members VALUES (?,?)', [(chat_id, a) for a in members])
                self.event(db, None, 'chat_membership_changed', chat_id, 'updated')
                from .conversations import initialize
                initialize(db)
                db.execute("UPDATE conversation_jobs SET status=CASE WHEN status='running' THEN 'cancelling' ELSE 'cancelled' END,updated_at=? WHERE chat_id=? AND status IN ('queued','running')", (time.time(), chat_id))
        except sqlite3.IntegrityError:
            raise ValueError('Unknown agent') from None
        return dict(chat, agent_ids=members)

    def events(self):
        with self.repository.transaction() as db:
            return {'events': [dict(r) for r in db.execute('SELECT * FROM security_events ORDER BY sequence DESC LIMIT 100')]}

    @staticmethod
    def members(value, kind):
        if not isinstance(value, list) or not 1 <= len(value) <= 32 or not all(isinstance(v, str) for v in value) or len(set(value)) != len(value):
            raise ValueError('Expected distinct members')
        if kind == 'individual' and len(value) != 1:
            raise ValueError('Individual chat requires one agent')
        if any(identifier(item) is None for item in value):
            raise ValueError('Expected agent UUIDs')
        return value

    def create(self, data):
        fields(data, ('title', 'kind', 'agent_ids'), ('title', 'kind', 'agent_ids'))
        if data['kind'] not in ('individual', 'group'):
            raise ValueError('Invalid chat kind')
        members = self.members(data['agent_ids'], data['kind'])
        chat = {'id': str(uuid.uuid4()), 'title': text(data['title']), 'kind': data['kind'], 'created_at': time.time()}
        try:
            with self.repository.transaction() as db:
                db.execute('INSERT INTO chats VALUES (?,?)', (chat['id'], json.dumps(chat)))
                db.executemany('INSERT INTO chat_members VALUES (?,?)', [(chat['id'], a) for a in members])
        except sqlite3.IntegrityError:
            raise ValueError('Unknown agent') from None
        return dict(chat, agent_ids=members)

    def list(self, actor='admin'):
        with self.repository.transaction() as db:
            if actor != 'admin':
                from .security import check_agent_capability
                try:
                    check_agent_capability(self.repository, actor, db=db)
                except ConflictError:
                    raise PermissionError('Forbidden') from None
            rows = db.execute('SELECT data,id FROM chats WHERE ?=\'admin\' OR id IN (SELECT m.chat_id FROM chat_members m JOIN chat_identities i ON i.agent_id=m.agent_id WHERE m.agent_id=? AND i.enabled=1) ORDER BY rowid DESC LIMIT 100', (actor, actor))
            return [dict(json.loads(r[0]), agent_ids=[m[0] for m in db.execute('SELECT agent_id FROM chat_members WHERE chat_id=? ORDER BY rowid', (r[1],))]) for r in rows]

    @staticmethod
    def require_chat(db, chat_id):
        if identifier(chat_id) is None:
            raise ValueError('Chat UUID required')
        row = db.execute('SELECT data FROM chats WHERE id=?', (chat_id,)).fetchone()
        if row is None:
            raise LookupError('Chat not found')
        return json.loads(row[0])

    def send(self, chat_id, data, actor='admin'):
        fields(data, ('client_id', 'content'), ('client_id', 'content'))
        if identifier(data['client_id']) is None:
            raise ValueError('Client UUID required')
        content = text(data['content'], 16000, multiline=True)
        with self.access(chat_id, actor) as db:
            old = db.execute('SELECT * FROM chat_messages WHERE chat_id=? AND sender=? AND client_id=?', (chat_id, actor, data['client_id'])).fetchone()
            if old:
                if old['content'] != content:
                    raise ConflictError('Message ID reused with different content')
                return dict(old)
            cursor = db.execute('INSERT INTO chat_messages(chat_id,sender,client_id,content,created_at) VALUES (?,?,?,?,?)', (chat_id, actor, data['client_id'], content, time.time()))
            message = dict(db.execute('SELECT * FROM chat_messages WHERE sequence=?', (cursor.lastrowid,)).fetchone())
            from .conversations import ConversationService
            ConversationService.enqueue(db, message)
            return message

    def history(self, chat_id, after=0, actor='admin'):
        if type(after) is not int or not 0 <= after <= 9223372036854775807:
            raise ValueError('Invalid history cursor')
        with self.access(chat_id, actor) as db:
            rows = db.execute('SELECT * FROM chat_messages WHERE chat_id=? AND sequence>? ORDER BY sequence LIMIT 101', (chat_id, after)).fetchall()
            page = [dict(row) for row in rows[:100]]
            return {'messages': page, 'has_more': len(rows) > 100, 'next_after': page[-1]['sequence'] if page else after}
