"""SQLite persistence boundary. SQL and transaction handling stay out of services."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3


class SQLiteRepository:
    def __init__(self, path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Do not change permissions of an existing user-selected directory.
        if self.path.parent.stat().st_mode & 0o077:
            raise ValueError('Database must use a private directory (mode 0700)')
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.fchmod(fd, 0o600)
        os.close(fd)
        with self.transaction() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > 1:
                raise ValueError('Database schema is newer than this program')
            if version == 0:
                db.execute('CREATE TABLE machines (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
                db.execute('CREATE TABLE agents (id TEXT PRIMARY KEY, machine_id TEXT REFERENCES machines(id), data TEXT NOT NULL)')
                db.execute('CREATE TABLE jobs (id TEXT PRIMARY KEY, agent_id TEXT REFERENCES agents(id), data TEXT NOT NULL)')
                db.execute('CREATE TABLE settings (id INTEGER PRIMARY KEY CHECK(id = 1), data TEXT NOT NULL)')
                db.execute('PRAGMA user_version = 1')

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def insert_machine(self, machine):
        with self.transaction() as db:
            db.execute('INSERT INTO machines (id, data) VALUES (?, ?)', (machine['id'], json.dumps(machine)))
        return machine

    def insert_agent(self, agent):
        try:
            with self.transaction() as db:
                db.execute('INSERT INTO agents (id, machine_id, data) VALUES (?, ?, ?)', (agent['id'], agent['machine_id'], json.dumps(agent)))
        except sqlite3.IntegrityError:
            raise ValueError('Unknown assigned machine') from None
        return agent

    def get_settings(self):
        with self.transaction() as db:
            row = db.execute('SELECT data FROM settings WHERE id = 1').fetchone()
            return json.loads(row['data']) if row else None

    def save_settings(self, settings):
        with self.transaction() as db:
            db.execute('INSERT INTO settings(id, data) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET data = excluded.data', (json.dumps(settings),))
        return settings

    def insert_job(self, job):
        try:
            with self.transaction() as db:
                db.execute('INSERT INTO jobs (id, agent_id, data) VALUES (?, ?, ?)', (job['id'], job['agent_id'], json.dumps(job)))
        except sqlite3.IntegrityError:
            raise ValueError('Unknown assigned agent') from None
        return job

    def get_job(self, job_id):
        with self.transaction() as db:
            return self._job(db, job_id)

    @staticmethod
    def _job(db, job_id):
        row = db.execute('SELECT data FROM jobs WHERE id = ?', (job_id,)).fetchone()
        if row is None:
            raise LookupError('Job not found')
        return json.loads(row['data'])

    def mutate_job(self, job_id, change):
        # Validation and mutation happen under one write transaction; no read/claim race.
        try:
            with self.transaction() as db:
                job = change(self._job(db, job_id))
                db.execute('UPDATE jobs SET agent_id = ?, data = ? WHERE id = ?', (job['agent_id'], json.dumps(job), job_id))
                return job
        except sqlite3.IntegrityError:
            raise ValueError('Unknown assigned agent') from None

    def list(self, collection):
        queries = {'machines': 'SELECT data FROM machines ORDER BY rowid', 'agents': 'SELECT data FROM agents ORDER BY rowid', 'jobs': 'SELECT data FROM jobs ORDER BY rowid'}
        if collection not in queries:
            raise ValueError('Unknown collection')
        with self.transaction() as db:
            return [json.loads(row['data']) for row in db.execute(queries[collection])]
