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
            if version > 6:
                raise ValueError('Database schema is newer than this program')
            if version == 0:
                db.execute('CREATE TABLE machines (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
                db.execute('CREATE TABLE agents (id TEXT PRIMARY KEY, machine_id TEXT REFERENCES machines(id), data TEXT NOT NULL)')
                db.execute('CREATE TABLE jobs (id TEXT PRIMARY KEY, agent_id TEXT REFERENCES agents(id), data TEXT NOT NULL)')
                db.execute('CREATE TABLE settings (id INTEGER PRIMARY KEY CHECK(id = 1), data TEXT NOT NULL)')
                db.execute('PRAGMA user_version = 1')
            if version < 2:
                db.execute('CREATE TABLE workers (agent_id TEXT PRIMARY KEY REFERENCES agents(id), vm_id TEXT NOT NULL UNIQUE, data TEXT NOT NULL)')
                db.execute('CREATE TABLE executions (job_id TEXT PRIMARY KEY REFERENCES jobs(id), data TEXT NOT NULL)')
                db.execute('PRAGMA user_version = 2')
            if version < 3:
                db.execute('CREATE TABLE inference_admission (sequence INTEGER PRIMARY KEY AUTOINCREMENT, ticket TEXT UNIQUE NOT NULL, priority INTEGER NOT NULL, memory_mib INTEGER NOT NULL, state TEXT NOT NULL, deadline REAL NOT NULL)')
                db.execute('PRAGMA user_version = 3')
            if version < 4:
                from .chat import migrate
                migrate(db)
                db.execute('PRAGMA user_version = 4')
            from .security import migrate
            migrate(db)
            if version < 6:
                from .permissions import migrate as migrate_permissions
                migrate_permissions(db)
                db.execute('PRAGMA user_version = 6')

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
                from .security import check_agent_capability
                check_agent_capability(self, job.get('agent_id'), db=db)
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
                if db.execute('SELECT 1 FROM executions WHERE job_id=?', (job_id,)).fetchone():
                    from .service import ConflictError
                    raise ConflictError('Dispatched jobs require execution reconciliation; active cancellation is not implemented')
                job = change(self._job(db, job_id))
                if job['status'] in ('queued', 'running'):
                    from .security import check_agent_execution, check_agent_capability
                    gate = check_agent_execution if job['status'] == 'running' else check_agent_capability
                    gate(self, job['agent_id'], db=db)
                db.execute('UPDATE jobs SET agent_id = ?, data = ? WHERE id = ?', (job['agent_id'], json.dumps(job), job_id))
                return job
        except sqlite3.IntegrityError:
            raise ValueError('Unknown assigned agent') from None

    def save_worker(self, worker):
        from .service import ConflictError
        try:
            with self.transaction() as db:
                from .security import check_agent_capability
                check_agent_capability(self, worker['agent_id'], db=db)
                if db.execute('SELECT 1 FROM executions WHERE json_extract(data,\'$.agent_id\') = ? AND json_extract(data,\'$.status\') IN (\'running\',\'uncertain\')', (worker['agent_id'],)).fetchone():
                    raise ConflictError('Worker has an unresolved execution')
                db.execute('INSERT INTO workers(agent_id, vm_id, data) VALUES(?,?,?) ON CONFLICT(agent_id) DO UPDATE SET vm_id=excluded.vm_id,data=excluded.data', (worker['agent_id'], worker['vm_id'], json.dumps(worker)))
        except sqlite3.IntegrityError:
            raise ValueError('Unknown agent or VM already assigned') from None
        return worker

    def worker(self, agent_id):
        with self.transaction() as db:
            row = db.execute('SELECT data FROM workers WHERE agent_id=?', (agent_id,)).fetchone()
            if row is None:
                raise LookupError('Worker not configured')
            return json.loads(row[0])

    def execution(self, job_id):
        with self.transaction() as db:
            row = db.execute('SELECT data FROM executions WHERE job_id=?', (job_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def assert_worker_idle(self, agent_id):
        from .service import ConflictError
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM executions WHERE json_extract(data,'$.agent_id')=? AND json_extract(data,'$.status') IN ('running','uncertain')", (agent_id,)).fetchone():
                raise ConflictError('Worker is busy or needs reconciliation')

    def begin_execution(self, job_id, worker):
        import time
        from .service import ConflictError
        with self.transaction() as db:
            from .security import check_agent_execution
            check_agent_execution(self, worker['agent_id'], db=db)
            job = self._job(db, job_id)
            if job['status'] != 'queued' or job['agent_id'] != worker['agent_id'] or db.execute('SELECT 1 FROM executions WHERE job_id=?', (job_id,)).fetchone():
                raise ConflictError('Job cannot be dispatched again')
            if db.execute('SELECT 1 FROM executions WHERE json_extract(data,\'$.agent_id\')=? AND json_extract(data,\'$.status\') IN (\'running\',\'uncertain\')', (worker['agent_id'],)).fetchone():
                raise ConflictError('Worker is busy or needs reconciliation')
            row = db.execute('SELECT data FROM workers WHERE agent_id=?', (worker['agent_id'],)).fetchone()
            if row is None or json.loads(row[0]) != worker:
                raise ConflictError('Worker configuration changed')
            receipt = {'job_id':job_id, 'agent_id':worker['agent_id'], 'status':'running', 'started_at':time.time(), 'worker':worker}
            db.execute('INSERT INTO executions VALUES (?,?)', (job_id,json.dumps(receipt)))
            job['status'] = 'running'
            db.execute('UPDATE jobs SET data=? WHERE id=?', (json.dumps(job),job_id))
            return job

    def finish_execution(self, job_id, status, result=None, response_id=None):
        import time
        with self.transaction() as db:
            job = self._job(db,job_id)
            receipt = json.loads(db.execute('SELECT data FROM executions WHERE job_id=?',(job_id,)).fetchone()[0])
            if receipt.get('security_incident_id'):
                return job
            receipt.update(status=status, finished_at=time.time(), response_id=response_id)
            job.update(status='succeeded' if status=='succeeded' else 'failed', result=result if status=='succeeded' else None,
                       error=None if status=='succeeded' else ('Gateway outcome uncertain; no automatic retry' if status=='uncertain' else 'Gateway did not complete the job'), progress=100 if status=='succeeded' else 0)
            db.execute('UPDATE executions SET data=? WHERE job_id=?',(json.dumps(receipt),job_id))
            db.execute('UPDATE jobs SET data=? WHERE id=?',(json.dumps(job),job_id))
            return job

    def admission_enqueue(self, ticket, memory_mib, priority, deadline, queue_limit):
        import time
        with self.transaction() as db:
            from .security import check_global
            check_global(self, db=db, require_health=False)
            db.execute("DELETE FROM inference_admission WHERE state='queued' AND deadline<=?", (time.time(),))
            if db.execute("SELECT count(*) FROM inference_admission WHERE state='queued'").fetchone()[0] >= queue_limit:
                raise ValueError('Inference queue exceeded')
            db.execute("INSERT INTO inference_admission(ticket,priority,memory_mib,state,deadline) VALUES(?,?,?,'queued',?)", (ticket, priority, memory_mib, deadline))

    def admission_acquire(self, ticket, memory_mib, concurrency):
        import time
        with self.transaction() as db:
            from .security import check_global
            check_global(self, db=db, require_health=False)
            db.execute("DELETE FROM inference_admission WHERE state='queued' AND deadline<=?", (time.time(),))
            first = db.execute("SELECT ticket,memory_mib FROM inference_admission WHERE state='queued' ORDER BY priority,sequence LIMIT 1").fetchone()
            active, reserved = db.execute("SELECT count(*),coalesce(sum(memory_mib),0) FROM inference_admission WHERE state IN ('active','uncertain')").fetchone()
            if first and first['ticket'] == ticket and active < concurrency and reserved + first['memory_mib'] <= memory_mib:
                db.execute("UPDATE inference_admission SET state='active' WHERE ticket=?", (ticket,))
                return True
            return False

    def admission_release(self, ticket, uncertain=False):
        with self.transaction() as db:
            if uncertain:
                db.execute("UPDATE inference_admission SET state='uncertain' WHERE ticket=?", (ticket,))
            else:
                db.execute('DELETE FROM inference_admission WHERE ticket=?', (ticket,))

    def admission_pending(self):
        import time
        with self.transaction() as db:
            return db.execute("SELECT count(*) FROM inference_admission WHERE state='queued' AND deadline>?", (time.time(),)).fetchone()[0]

    def list(self, collection):
        queries = {'machines': 'SELECT data FROM machines ORDER BY rowid', 'agents': 'SELECT data FROM agents ORDER BY rowid', 'jobs': 'SELECT data FROM jobs ORDER BY rowid', 'workers': 'SELECT data FROM workers ORDER BY rowid'}
        if collection not in queries:
            raise ValueError('Unknown collection')
        with self.transaction() as db:
            return [json.loads(row['data']) for row in db.execute(queries[collection])]
