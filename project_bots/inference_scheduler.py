"""Shared admission layered on the existing durable backend reservations.

Never expire active/uncertain work. SQLite is the coordination authority; all
broker processes sharing a backend must use this same admission database.
"""
from contextlib import contextmanager
import time
import uuid
import math


class Overloaded(ValueError):
    pass


class Revoked(PermissionError):
    pass


class SharedScheduler:
    def __init__(self, gate, *, queue_timeout: float=30, per_agent_queue=2,
                 per_agent_active=1, requests_per_minute=60,
                 tokens_per_minute=131072, starvation_seconds: float=5):
        self.gate = gate
        self.repository = gate.repository
        self.queue_timeout = queue_timeout
        self.per_agent_queue = per_agent_queue
        self.per_agent_active = per_agent_active
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.starvation_seconds = starvation_seconds
        if any(type(x) is not int or x < 1 for x in (gate.memory_mib, gate.concurrency, gate.queue_limit, per_agent_queue, per_agent_active, requests_per_minute, tokens_per_minute)) or not 0 < queue_timeout <= 300 or not math.isfinite(starvation_seconds) or starvation_seconds <= 0:
            raise ValueError('Invalid scheduler limits')
        with self.repository.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS broker_requests (ticket TEXT PRIMARY KEY, agent TEXT NOT NULL, created REAL NOT NULL, cancelled INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS broker_usage (ticket TEXT PRIMARY KEY, agent TEXT NOT NULL, created REAL NOT NULL, tokens INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS broker_turns (agent TEXT PRIMARY KEY, dispatched REAL NOT NULL)')

    def cancel(self, agent, ticket):
        with self.repository.transaction() as db:
            return bool(db.execute('UPDATE broker_requests SET cancelled=1 WHERE ticket=? AND agent=?', (ticket, agent)).rowcount)

    def check(self, agent, ticket, check=None):
        if check is not None:
            try:
                allowed = check()
            except Exception as exc:
                raise Revoked('Admission authority unavailable') from exc
            if allowed is not True:
                raise Revoked('Admission revoked')
        with self.repository.transaction() as db:
            row = db.execute('SELECT cancelled FROM broker_requests WHERE ticket=? AND agent=?', (ticket, agent)).fetchone()
            if row is None or row[0]:
                raise Revoked('Request cancelled')

    @contextmanager
    def slot(self, agent, memory_mib, priority, tokens, *, request_id=None, check=None):
        gate = self.gate
        if type(memory_mib) is not int or not 0 < memory_mib <= gate.memory_mib or type(priority) is not int or not 0 <= priority <= 100 or type(tokens) is not int or tokens < 1:
            raise ValueError('Invalid request reservation')
        ticket = request_id or str(uuid.uuid4())
        now = time.time()
        with self.repository.transaction() as db:
            db.execute("DELETE FROM inference_admission WHERE state='queued' AND deadline<=?", (now,))
            db.execute('DELETE FROM broker_requests WHERE ticket NOT IN (SELECT ticket FROM inference_admission)')
            db.execute('DELETE FROM broker_usage WHERE created<=?', (now-60,))
            count, used = db.execute('SELECT count(*),coalesce(sum(tokens),0) FROM broker_usage WHERE agent=?', (agent,)).fetchone()
            queued = db.execute("SELECT count(*) FROM inference_admission WHERE state='queued'").fetchone()[0]
            own = db.execute("SELECT count(*) FROM inference_admission i JOIN broker_requests r USING(ticket) WHERE r.agent=? AND i.state='queued'", (agent,)).fetchone()[0]
            if count >= self.requests_per_minute or used+tokens > self.tokens_per_minute or queued >= gate.queue_limit or own >= self.per_agent_queue:
                raise Overloaded('Inference queue or agent budget exceeded')
            if db.execute('SELECT 1 FROM broker_requests WHERE ticket=?', (ticket,)).fetchone():
                raise Overloaded('Request identifier already in use')
            db.execute("INSERT INTO inference_admission(ticket,priority,memory_mib,state,deadline) VALUES(?,?,?,'queued',?)", (ticket, priority, memory_mib, now+self.queue_timeout))
            db.execute('INSERT INTO broker_requests(ticket,agent,created) VALUES(?,?,?)', (ticket, agent, now))
            db.execute('INSERT INTO broker_usage VALUES(?,?,?,?)', (str(uuid.uuid4()), agent, now, tokens))
        class Lease:
            uncertain = False
            def retain(self):
                self.uncertain = True
        lease = Lease()
        deadline = time.monotonic() + self.queue_timeout
        try:
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Inference queue deadline exceeded')
                self.check(agent, ticket, check)
                now = time.time()
                with self.repository.transaction() as db:
                    active, reserved = db.execute("SELECT count(*),coalesce(sum(memory_mib),0) FROM inference_admission WHERE state IN ('active','uncertain')").fetchone()
                    candidates = db.execute("""SELECT i.ticket,i.priority,i.memory_mib,r.agent,r.created,coalesce(t.dispatched,0) AS turn
                        FROM inference_admission i JOIN broker_requests r USING(ticket)
                        LEFT JOIN broker_turns t ON t.agent=r.agent
                        WHERE i.state='queued' AND i.deadline>? AND r.cancelled=0
                        AND (SELECT count(*) FROM inference_admission a JOIN broker_requests b USING(ticket)
                             WHERE b.agent=r.agent AND a.state IN ('active','uncertain')) < ?""", (now, self.per_agent_active)).fetchall()
                    # Oldest aged request wins absolutely; otherwise least-recently
                    # served agent wins, with trusted profile priority breaking ties.
                    eligible = [r for r in candidates if reserved+r['memory_mib'] <= gate.memory_mib]
                    aged = [r for r in eligible if now-r['created'] >= self.starvation_seconds]
                    first = min(aged, key=lambda r:r['created']) if aged else min(eligible, key=lambda r:(r['turn'],r['priority'],r['created']), default=None)
                    if active < gate.concurrency and first is not None and first['ticket'] == ticket:
                        db.execute("UPDATE inference_admission SET state='active' WHERE ticket=?", (ticket,))
                        db.execute('INSERT INTO broker_turns VALUES(?,?) ON CONFLICT(agent) DO UPDATE SET dispatched=excluded.dispatched', (agent, now))
                        break
                time.sleep(.01)
            yield lease
        finally:
            self.repository.admission_release(ticket, lease.uncertain)
            if not lease.uncertain:
                with self.repository.transaction() as db:
                    db.execute('DELETE FROM broker_requests WHERE ticket=?', (ticket,))
