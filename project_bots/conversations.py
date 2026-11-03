"""Trusted, tool-free conversational orchestration; private data is never group context.

Tables are additive, initialized transactionally without changing the platform schema.
Reply jobs never recursively trigger replies. Uncertain dispatch is never retried.
"""
import json
import time
import uuid
from .service import ConflictError, fields, identifier, text


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS conversation_agents (agent_id TEXT PRIMARY KEY REFERENCES agents(id), data TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS conversation_jobs (id TEXT PRIMARY KEY, chat_id TEXT NOT NULL REFERENCES chats(id), agent_id TEXT NOT NULL REFERENCES agents(id), trigger_sequence INTEGER NOT NULL REFERENCES chat_messages(sequence), status TEXT NOT NULL, revision TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL, UNIQUE(agent_id,trigger_sequence))')


class ConversationService:
    def __init__(self, repository):
        self.repository = repository
        with repository.transaction() as db:
            initialize(db)

    def configure(self, agent_id, data):
        identifier(agent_id)
        fields(data, ('enabled','system_instructions','memory','tools','max_replies'), ('enabled','system_instructions','memory','tools','max_replies'))
        if type(data['enabled']) is not bool or data['tools'] != [] or type(data['max_replies']) is not int or not 1 <= data['max_replies'] <= 32:
            raise ValueError('Tool-free enrollment and a reply budget of 1..32 required')
        config = dict(data, system_instructions=text(data['system_instructions'], 8000, multiline=True), memory=text(data['memory'],8000,multiline=True) if data['memory'] else '', revision=str(uuid.uuid4()))
        with self.repository.transaction() as db:
            if not db.execute('SELECT 1 FROM agents WHERE id=?',(agent_id,)).fetchone():
                raise LookupError('Agent not found')
            db.execute('INSERT INTO conversation_agents VALUES (?,?) ON CONFLICT(agent_id) DO UPDATE SET data=excluded.data',(agent_id,json.dumps(config)))
            db.execute("UPDATE conversation_jobs SET status=CASE WHEN status='running' THEN 'cancelling' ELSE 'cancelled' END,updated_at=? WHERE agent_id=? AND status IN ('queued','running')",(time.time(),agent_id))
        return dict(config,agent_id=agent_id)

    def configuration(self, agent_id):
        with self.repository.transaction() as db:
            row=db.execute('SELECT data FROM conversation_agents WHERE agent_id=?',(agent_id,)).fetchone()
            if not row:
                raise LookupError('Conversation enrollment not found')
            return dict(json.loads(row[0]),agent_id=agent_id)

    @staticmethod
    def enqueue(db, message):
        initialize(db)
        # Only explicit human messages create a bounded fan-out. Peers can
        # collaborate via the broker but cannot autonomously generate a loop.
        if message['sender'] != 'admin':
            return
        for row in db.execute('SELECT c.agent_id,c.data FROM conversation_agents c JOIN chat_members m ON c.agent_id=m.agent_id JOIN chat_identities i ON i.agent_id=c.agent_id WHERE m.chat_id=? AND i.enabled=1',(message['chat_id'],)).fetchall():
            config=json.loads(row['data'])
            now = time.time()
            used=db.execute('SELECT count(*) FROM conversation_jobs WHERE agent_id=? AND chat_id=? AND created_at>=?',(row['agent_id'],message['chat_id'],now-60)).fetchone()[0]
            if config['enabled'] and used < config['max_replies']:
                # Admission budget is rolling, not a permanent lifetime lockout.
                # Canceled/blocked attempts still count; changing config does not refund them.
                db.execute("INSERT OR IGNORE INTO conversation_jobs VALUES (?,?,?,?,'queued',?,?,?)",(str(uuid.uuid4()),message['chat_id'],row['agent_id'],message['sequence'],config['revision'],now,now))

    def jobs(self, chat_id=None):
        with self.repository.transaction() as db:
            # Keep the newest history window plus every unresolved job. Return
            # chronological order: the dashboard reverses it for newest-first.
            return [dict(r) for r in db.execute('''
                WITH filtered AS (
                    SELECT rowid AS position, * FROM conversation_jobs
                    WHERE (? IS NULL OR chat_id=?)
                ), recent AS (
                    SELECT id FROM filtered ORDER BY created_at DESC, position DESC LIMIT 500
                )
                SELECT id,chat_id,agent_id,trigger_sequence,status,revision,created_at,updated_at
                FROM filtered WHERE id IN (SELECT id FROM recent)
                    OR status IN ('queued','running','cancelling','uncertain')
                ORDER BY created_at, position
            ''', (chat_id,chat_id))]

    def cancel(self, job_id):
        identifier(job_id)
        with self.repository.transaction() as db:
            row=db.execute('SELECT * FROM conversation_jobs WHERE id=?',(job_id,)).fetchone()
            if not row:
                raise LookupError('Reply job not found')
            if row['status'] in ('queued','running'):
                db.execute("UPDATE conversation_jobs SET status=CASE WHEN status='running' THEN 'cancelling' ELSE 'cancelled' END,updated_at=? WHERE id=?",(time.time(),job_id))
            return dict(db.execute('SELECT * FROM conversation_jobs WHERE id=?',(job_id,)).fetchone())
