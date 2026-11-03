"""Trusted control-plane security state. No claim of host/network isolation.

Only trusted service code may report coverage. There is deliberately no HTTP
heartbeat endpoint: an administrator's assertion is not monitor telemetry.
"""
from contextlib import contextmanager
import hashlib
import json
import os
import time
import uuid

from .service import ConflictError, fields, identifier, text

REQUIRED_COVERAGE = ('runtime', 'network', 'identity', 'audit', 'enforcer')


def migrate(db):
    db.execute('CREATE TABLE IF NOT EXISTS security_state (key TEXT PRIMARY KEY, data TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS security_incidents (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
    db.execute("INSERT OR IGNORE INTO security_state VALUES ('global', '{\"stopped\": false}')")


@contextmanager
def connection(repository, db=None):
    if db is not None:
        yield db
    else:
        with repository.transaction() as current:
            yield current


def _read(db, key, default=None):
    row = db.execute('SELECT data FROM security_state WHERE key=?', (key,)).fetchone()
    return json.loads(row[0]) if row else default


def _write(db, key, value):
    db.execute('INSERT INTO security_state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data', (key, json.dumps(value)))


def _credential_fingerprints(db, aid):
    """Private rotation evidence; never include values/digests in API responses."""
    refs = {}
    chat = db.execute('SELECT credential_env FROM chat_identities WHERE agent_id=?', (aid,)).fetchone()
    worker = db.execute('SELECT data FROM workers WHERE agent_id=?', (aid,)).fetchone()
    agent = db.execute('SELECT data FROM agents WHERE id=?', (aid,)).fetchone()
    if chat:
        refs['chat'] = chat[0]
    if worker:
        refs['gateway'] = json.loads(worker[0]).get('credential_env')
    if agent:
        refs['inference'] = json.loads(agent[0]).get('config', {}).get('credential_env')
    return {kind: hashlib.sha256(os.environ[ref].encode()).hexdigest() if os.environ.get(ref) else None for kind, ref in refs.items() if ref}


def _coverage(db):
    now = time.time()
    result = {}
    for name in REQUIRED_COVERAGE:
        item = _read(db, 'coverage:' + name, {})
        fresh = (item.get('healthy') is True and 0 <= now - item.get('observed_at', 0) <= item.get('ttl', 0))
        result[name] = dict(item, status='healthy' if fresh else ('stale' if item else 'unavailable'))
    return result


def check_global(repository, *, db=None, require_health=True):
    """Read-only admission. Missing, stale or failed trusted coverage denies work."""
    with connection(repository, db) as current:
        if _read(current, 'global', {'stopped': True})['stopped']:
            raise ConflictError('Global emergency stop is latched')
        if require_health and any(v['status'] != 'healthy' for v in _coverage(current).values()):
            raise ConflictError('Required trusted security coverage unavailable or stale')


def check_agent_execution(repository, agent_id, *, db=None):
    with connection(repository, db) as current:
        check_agent_capability(repository, agent_id, db=current)
        check_global(repository, db=current)


def check_agent_capability(repository, agent_id, *, db=None):
    """Revocation gate for messaging/queued work; does not require OS telemetry."""
    with connection(repository, db) as current:
        check_global(repository, db=current, require_health=False)
        if _read(current, 'agent:' + str(agent_id), {}).get('contained'):
            raise ConflictError('Agent is contained; explicit administrator recovery required')
        revoked = _read(current, 'revoked_fingerprints:' + str(agent_id), [])
        if any(value in revoked for value in _credential_fingerprints(current, agent_id).values() if value):
            raise ConflictError('Previously revoked credential is still configured')


class SecurityService:
    def __init__(self, repository, compute_request=None):
        self.repository = repository
        # Keep force-stop off the general platform lifecycle/UI allowlist. The
        # trusted reconciler uses a separate fixed containment-only transport.
        from .service import PlatformService
        if isinstance(getattr(compute_request, '__self__', None), PlatformService):
            from .machine_client import containment_request
            self.compute_request = lambda machine, method, route, data=None: containment_request(repository, machine, method, route, data)
        else:
            self.compute_request = compute_request

    def observe(self, coverage, *, healthy, source, ttl=30, observed_at=None):
        """Trusted adapter interface, not exposed to agents or public HTTP callers."""
        if coverage not in REQUIRED_COVERAGE or type(healthy) is not bool or not 0 < ttl <= 60:
            raise ValueError('Invalid coverage observation')
        source = text(source, 200)
        stamp = time.time() if observed_at is None else observed_at
        if not isinstance(stamp, (int, float)) or not 0 <= time.time() - stamp <= 60:
            raise ValueError('Observation must be current')
        with self.repository.transaction() as db:
            _write(db, 'coverage:' + coverage, {'healthy': healthy, 'source': source, 'observed_at': stamp, 'ttl': ttl})

    def status(self):
        with self.repository.transaction() as db:
            coverage = _coverage(db)
            stopped = _read(db, 'global', {'stopped': True})['stopped']
            agents = []
            for row in db.execute('SELECT id FROM agents ORDER BY rowid'):
                aid = row[0]
                agents.append(dict(_read(db, 'agent:' + aid, {'contained': False}), agent_id=aid))
            incidents = [json.loads(r[0]) for r in db.execute('SELECT data FROM security_incidents ORDER BY rowid DESC')]
        return {'global_stop': stopped, 'protected': not stopped and all(v['status'] == 'healthy' for v in coverage.values()), 'coverage': coverage, 'agents': agents, 'incidents': incidents,
                'limitations': ['Coverage must come from separately configured trusted adapters; none installed by default.', 'VM packet isolation needs an OS-verified VM network adapter; none installed by default. Owner-validated force-stop source exists but real-VM acceptance is unverified.', 'Audit evidence shares backend SQLite authority; not tamper-resistant external storage.']}

    def incidents(self):
        return {'incidents': self.status()['incidents']}

    def incident(self, incident_id):
        if identifier(incident_id) is None:
            raise ValueError('Incident UUID required')
        with self.repository.transaction() as db:
            row = db.execute('SELECT data FROM security_incidents WHERE id=?', (incident_id,)).fetchone()
            if row is None:
                raise LookupError('Incident not found')
            return json.loads(row[0])

    @staticmethod
    def _save_incident(db, incident):
        db.execute('INSERT INTO security_incidents VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data', (incident['id'], json.dumps(incident)))

    def report(self, data, *, source='administrator_report'):
        fields(data, ('agent_id', 'severity', 'behavior', 'resource', 'evidence'), ('agent_id', 'severity', 'behavior', 'resource', 'evidence'))
        aid = identifier(data['agent_id'])
        if aid is None or data['severity'] not in ('information', 'warning', 'high', 'critical'):
            raise ValueError('Invalid incident')
        incident = {'id': str(uuid.uuid4()), 'created_at': time.time(), 'agent_id': aid, 'severity': data['severity'],
                    'behavior': text(data['behavior']), 'resource': text(data['resource']), 'evidence': text(data['evidence'], 4000, multiline=True),
                    'source': source, 'status': 'open', 'actions': [], 'outcome': 'recorded', 'acknowledgments': []}
        with self.repository.transaction() as db:
            if not db.execute('SELECT 1 FROM agents WHERE id=?', (aid,)).fetchone():
                raise LookupError('Agent not found')
            self._save_incident(db, incident)
            if incident['severity'] in ('high', 'critical'):
                self._latch_agent(db, aid, incident['id'])
        if incident['severity'] in ('high', 'critical'):
            self.enforce(incident['id'])
        return self.incident(incident['id'])

    def _latch_agent(self, db, aid, incident_id):
        # Revoke before any external operation, even if evidence/action export fails.
        fingerprints = _credential_fingerprints(db, aid)
        _write(db, 'revoked_credentials:' + aid, fingerprints)
        prior = _read(db, 'revoked_fingerprints:' + aid, [])
        _write(db, 'revoked_fingerprints:' + aid, sorted(set(prior + [v for v in fingerprints.values() if v])))
        _write(db, 'agent:' + aid, {'contained': True, 'incident_id': incident_id, 'contained_at': time.time()})
        db.execute('UPDATE chat_identities SET enabled=0 WHERE agent_id=?', (aid,))
        for row in db.execute('SELECT id,data FROM jobs WHERE agent_id=?', (aid,)).fetchall():
            job = json.loads(row['data'])
            if job['status'] in ('queued', 'running'):
                job.update(status='canceled', message='Security containment; remote termination requires independent readback')
                db.execute('UPDATE jobs SET data=? WHERE id=?', (json.dumps(job), row['id']))
        # Active remote work remains uncertain until independently observed stopped.
        for row in db.execute('SELECT job_id,data FROM executions').fetchall():
            receipt = json.loads(row['data'])
            if receipt['agent_id'] == aid and receipt['status'] in ('running', 'uncertain'):
                receipt.update(status='uncertain', security_incident_id=incident_id)
                db.execute('UPDATE executions SET data=? WHERE job_id=?', (json.dumps(receipt), row['job_id']))

    def emergency_stop(self, data):
        fields(data, ('reason',), ('reason',))
        reason = text(data['reason'], 4000)
        with self.repository.transaction() as db:
            _write(db, 'global', {'stopped': True, 'reason': reason, 'stopped_at': time.time()})
            # Include unassigned queued jobs, not only agent jobs.
            for row in db.execute('SELECT id,data FROM jobs').fetchall():
                job = json.loads(row['data'])
                if job['status'] in ('queued', 'running'):
                    job.update(status='canceled', message='Global emergency stop')
                    db.execute('UPDATE jobs SET data=? WHERE id=?', (json.dumps(job), row['id']))
            db.execute("DELETE FROM inference_admission WHERE state='queued'")
            for row in db.execute('SELECT id FROM agents').fetchall():
                aid = row[0]
                incident = {'id': str(uuid.uuid4()), 'created_at': time.time(), 'agent_id': aid, 'severity': 'critical', 'behavior': 'global_emergency_stop', 'resource': aid,
                            'evidence': reason, 'source': 'administrator', 'status': 'open', 'actions': [], 'outcome': 'pending', 'acknowledgments': []}
                self._save_incident(db, incident)
                self._latch_agent(db, aid, incident['id'])
        for incident in self.status()['incidents']:
            if incident['status'] not in ('recovered',) and incident['severity'] in ('high', 'critical'):
                self.enforce(incident['id'])
        return self.status()

    def _record_enforcement_intent(self, incident_id, vm_id, action, operation_id, *, acknowledged=False):
        """Commit correlation before transport; a timeout never erases intent."""
        with self.repository.transaction() as db:
            incident = json.loads(db.execute('SELECT data FROM security_incidents WHERE id=?', (incident_id,)).fetchone()[0])
            intents = incident.setdefault('enforcement_intents', [])
            if not any(i['operation_id'] == operation_id for i in intents):
                intents.append({'vm_id': vm_id, 'action': action, 'operation_id': operation_id,
                                'requested_at': time.time(), 'outcome': 'requested_unverified'})
            if acknowledged:
                next(i for i in intents if i['operation_id'] == operation_id)['outcome'] = 'acknowledged_not_effect_proof'
            self._save_incident(db, incident)

    def enforce(self, incident_id):
        """Idempotent trusted reconciliation; only fixed Machine Manager operations."""
        incident = self.incident(incident_id)
        aid = incident['agent_id']
        with self.repository.transaction() as db:
            owner = _read(db, 'agent:' + aid, {})
            pending = db.execute("SELECT count(*) FROM jobs WHERE agent_id=? AND json_extract(data,'$.status') IN ('queued','running')", (aid,)).fetchone()[0]
        if not owner.get('contained') or owner.get('incident_id') != incident_id or incident['status'] == 'recovered':
            return incident
        actions: list[dict] = [{'action': 'capability_revocation', 'status': 'verified', 'readback': {'agent_id': aid, 'contained': owner['contained'], 'incident_id': owner['incident_id']}},
                   {'action': 'job_cancellation', 'status': 'verified' if pending == 0 else 'unverified', 'readback': {'pending_job_rows': pending, 'remote_execution': 'requires runtime readback'}},
                   {'action': 'network_isolation', 'status': 'unavailable', 'readback': 'No trusted network enforcement adapter configured'}]
        # Network isolation is attempted first but never delays runtime fencing
        # beyond the bounded transport timeout; failure does not suppress stop.
        try:
            worker = self.repository.worker(aid)
            agent = next(a for a in self.repository.list('agents') if a['id'] == aid)
            if self.compute_request is None or not agent['machine_id']:
                raise LookupError('No trusted network transport')
            route = 'vms/' + worker['vm_id']
            network = self.compute_request(agent['machine_id'], 'GET', route + '/network')
            if network.get('vm_id') != worker['vm_id'] or network.get('status') == 'unavailable':
                raise ValueError('No verified network binding')
            operation_id = str(uuid.uuid5(uuid.UUID(incident_id), 'network-block:' + worker['vm_id']))
            if network.get('blocked') is not True:
                self._record_enforcement_intent(incident_id, worker['vm_id'], 'network-block', operation_id)
                self.compute_request(agent['machine_id'], 'POST', route + '/network-block', {'confirmation': 'network-block:' + worker['vm_id'], 'operation_id': operation_id})
            network = self.compute_request(agent['machine_id'], 'GET', route + '/network')
            actions[2] = {'action': 'network_isolation', 'status': 'verified' if network.get('vm_id') == worker['vm_id'] and network.get('blocked') is True else 'unverified', 'readback': network, 'operation_id': operation_id}
        except Exception as exc:
            actions[2]['error_kind'] = type(exc).__name__
        try:
            worker = self.repository.worker(aid)
            agent = next(a for a in self.repository.list('agents') if a['id'] == aid)
            if self.compute_request is None or not agent['machine_id']:
                raise LookupError('No trusted compute adapter')
            route = 'vms/' + worker['vm_id']
            before = self.compute_request(agent['machine_id'], 'GET', route)
            if before.get('id') != worker['vm_id']:
                raise ValueError('Compute target mismatch')
            stop_action = 'force-stop' if incident['severity'] == 'critical' else 'shutdown'
            operation_id = str(uuid.uuid5(uuid.UUID(incident_id), stop_action + ':' + worker['vm_id']))
            acknowledged = any(i['operation_id'] == operation_id and i['outcome'] == 'acknowledged_not_effect_proof' for i in incident.get('enforcement_intents', []))
            if before.get('state') != 'shut off' or (stop_action == 'force-stop' and not before.get('security_contained') and not acknowledged):
                self._record_enforcement_intent(incident_id, worker['vm_id'], stop_action, operation_id)
                self.compute_request(agent['machine_id'], 'POST', route + '/' + stop_action, {'confirmation': stop_action + ':' + worker['vm_id'], 'operation_id': operation_id})
                self._record_enforcement_intent(incident_id, worker['vm_id'], stop_action, operation_id, acknowledged=True)
            after = self.compute_request(agent['machine_id'], 'GET', route)
            verified = after.get('id') == worker['vm_id'] and after.get('state') == 'shut off'
            actions.append({'action': 'runtime_shutdown', 'status': 'verified' if verified else 'unverified', 'readback': {'vm_id': worker['vm_id'], 'state': after.get('state'), 'method': stop_action, 'operation_id': operation_id}})
            if incident['severity'] == 'critical':
                actions.append({'action': 'forced_vm_termination', 'status': 'verified' if verified else 'unverified', 'readback': {'vm_id': worker['vm_id'], 'state': after.get('state'), 'operation_id': operation_id, 'method': stop_action, 'already_stopped': before.get('state') == 'shut off'}})
            if verified:
                with self.repository.transaction() as db:
                    for row in db.execute('SELECT job_id,data FROM executions').fetchall():
                        receipt = json.loads(row['data'])
                        if receipt['agent_id'] == aid and receipt['status'] in ('running', 'uncertain'):
                            receipt.update(status='terminated', terminated_at=time.time(), security_incident_id=incident_id)
                            db.execute('UPDATE executions SET data=? WHERE job_id=?', (json.dumps(receipt), row['job_id']))
        except Exception as exc:
            with self.repository.transaction() as db:
                configured = db.execute('SELECT 1 FROM workers WHERE agent_id=?', (aid,)).fetchone()
                receipt = db.execute("SELECT 1 FROM executions WHERE json_extract(data,'$.agent_id')=?", (aid,)).fetchone()
            if configured is None and receipt is None:
                actions.append({'action': 'runtime_shutdown', 'status': 'not_applicable', 'readback': 'Registry-only agent: no configured worker or execution receipt; no runtime termination claimed'})
            else:
                actions.append({'action': 'runtime_shutdown', 'status': 'unavailable', 'error_kind': type(exc).__name__, 'readback': 'Trusted Machine Manager shutdown/readback unavailable; no termination claim'})
        if incident['severity'] == 'critical' and not any(a['action'] == 'forced_vm_termination' for a in actions):
            actions.append({'action': 'forced_vm_termination', 'status': 'unavailable', 'readback': 'Trusted force-stop/readback unavailable; no termination claim'})
        with self.repository.transaction() as db:
            current = json.loads(db.execute('SELECT data FROM security_incidents WHERE id=?', (incident_id,)).fetchone()[0])
            if current.get('actions') != actions:
                current.setdefault('action_history', []).append({'observed_at': time.time(), 'actions': actions})
            current.update(actions=actions, outcome='partial', last_enforced_at=time.time())
            self._save_incident(db, current)
        return self.incident(incident_id)

    def acknowledge(self, incident_id, data):
        fields(data, ('note',), ('note',))
        note = text(data['note'], 4000)
        with self.repository.transaction() as db:
            row = db.execute('SELECT data FROM security_incidents WHERE id=?', (identifier(incident_id),)).fetchone()
            if not row:
                raise LookupError('Incident not found')
            incident = json.loads(row[0])
            incident['acknowledgments'].append({'at': time.time(), 'note': note, 'actor': 'admin'})
            if incident['status'] == 'open':
                incident['status'] = 'acknowledged'
            self._save_incident(db, incident)
        return self.incident(incident_id)

    def recover(self, data, incident_id=None):
        fields(data, ('note', 'credential_rotated') if incident_id else ('note',), ('note', 'credential_rotated') if incident_id else ('note',))
        note = text(data['note'], 4000)
        with self.repository.transaction() as db:
            if any(v['status'] != 'healthy' for v in _coverage(db).values()):
                raise ConflictError('Recovery requires fresh trusted coverage and policy verification')
            if incident_id is None:
                if any(json.loads(r[0]).get('contained') for r in db.execute("SELECT data FROM security_state WHERE key LIKE 'agent:%'")):
                    raise ConflictError('Recover contained agents individually first')
                _write(db, 'global', {'stopped': False, 'recovered_at': time.time(), 'note': note})
            else:
                if data['credential_rotated'] is not True:
                    raise ConflictError('Credential rotation required')
                row = db.execute('SELECT data FROM security_incidents WHERE id=?', (identifier(incident_id),)).fetchone()
                if not row:
                    raise LookupError('Incident not found')
                incident = json.loads(row[0])
                if not incident['acknowledgments']:
                    raise ConflictError('Investigate and acknowledge before recovery')
                if not any(a['action'] == 'runtime_shutdown' and a['status'] in ('verified', 'not_applicable') for a in incident['actions']):
                    raise ConflictError('Runtime stop must be independently verified')
                state = _read(db, 'agent:' + incident['agent_id'], {})
                if state.get('incident_id') != incident_id:
                    raise ConflictError('A newer containment incident owns the latch')
                old = _read(db, 'revoked_credentials:' + incident['agent_id'], {})
                current = _credential_fingerprints(db, incident['agent_id'])
                revoked = _read(db, 'revoked_fingerprints:' + incident['agent_id'], [])
                if any(not digest or not current.get(kind) or current[kind] == digest for kind, digest in old.items()) or any(v in revoked for v in current.values() if v):
                    raise ConflictError('Actual credential rotation cannot be verified; old credentials remain revoked')
                # Old chat identity remains disabled; recovery never enables credentials or starts runtime.
                _write(db, 'agent:' + incident['agent_id'], {'contained': False, 'recovered_at': time.time()})
                incident.update(status='recovered', recovery={'at': time.time(), 'note': note, 'actor': 'admin'})
                self._save_incident(db, incident)
        return self.incident(incident_id) if incident_id else self.status()


def poll_host_network(security):
    """Independent trusted Machine Manager kernel readbacks, never worker reports.

    Full runtime exec/filesystem/privilege/audit coverage is deliberately NOT
    claimed by this packet firewall monitor. Missing bindings deny admission.
    """
    workers = security.repository.list('workers')
    healthy = bool(workers)
    for worker in workers:
        aid = worker['agent_id']
        failure = None
        try:
            agent = next(a for a in security.repository.list('agents') if a['id'] == aid)
            if security.compute_request is None:
                raise LookupError('No trusted host transport')
            observed = security.compute_request(agent['machine_id'], 'GET', 'vms/' + worker['vm_id'] + '/network')
            bound = observed.get('vm_id') == worker['vm_id'] and observed.get('status') in ('bound', 'enforced')
            good = bound and observed.get('blocked') is True
            if good and 'dropped_packets' in observed:
                count = observed['dropped_packets']
                if type(count) is not int or count < 0:
                    raise ValueError('Invalid kernel packet counter')
                key = 'network_cursor:' + worker['vm_id']
                with security.repository.transaction() as db:
                    previous = _read(db, key, {'dropped_packets': 0, 'namespace_inode': observed.get('namespace_inode')})
                if count < previous['dropped_packets'] or observed.get('namespace_inode') != previous.get('namespace_inode'):
                    good = False  # Counter reset/boundary replacement needs review.
                elif count > previous['dropped_packets']:
                    security.report({'agent_id': aid, 'severity': 'high', 'behavior': 'host_network_denied_packets',
                                     'resource': worker['vm_id'], 'evidence': json.dumps({'previous': previous, 'current': observed}, sort_keys=True)[:4000]},
                                    source='trusted_host_network_monitor')
                if good:
                    with security.repository.transaction() as db:
                        _write(db, key, {'dropped_packets': count, 'namespace_inode': observed.get('namespace_inode')})
            if not good:
                failure = json.dumps(observed, sort_keys=True)[:4000]
        except Exception as exc:
            good = False
            # Retain type, not arbitrary exception text that could contain secrets.
            failure = 'Trusted network observation unavailable: ' + type(exc).__name__
        healthy = healthy and good
        if not good:
            current = security.status()
            owner = next((a for a in current['agents'] if a['agent_id'] == aid), {})
            active = next((i for i in current['incidents'] if i['id'] == owner.get('incident_id') and i['severity'] == 'critical' and i['status'] != 'recovered'), None)
            if active:
                security.enforce(active['id'])
            else:
                security.report({'agent_id': aid, 'severity': 'critical', 'behavior': 'host_network_enforcement_lost',
                                 'resource': worker['vm_id'], 'evidence': failure},
                                source='trusted_host_network_monitor')
    security.observe('network', healthy=healthy, source='independent Machine Manager kernel firewall and namespace readbacks', ttl=10)
    return healthy


def enforce_once(repository, compute_request=None, *, host_monitor=False):
    """Independent reconciler. Never starts a VM, executes shell, or accepts PIDs.

    Shared backend DB and service UID remain trusted; process independence alone
    does not protect against a same-UID attacker or replace external monitors.
    """
    if compute_request is None:
        from .service import PlatformService
        compute_request = PlatformService(repository).compute_request
    security = SecurityService(repository, compute_request)
    security.observe('enforcer', healthy=False, source='reconciliation in progress; completion not verified', ttl=10)
    if host_monitor:
        poll_host_network(security)
    state = security.status()
    # This invocation is the enforcer probe. Only successful completion below
    # refreshes health; in-progress/failed loops must not admit new execution.
    missing = [k for k, v in state['coverage'].items() if k != 'enforcer' and v['status'] != 'healthy']
    contained = {a['agent_id'] for a in state['agents'] if a['contained']}
    explicitly_recovered = {a['agent_id'] for a in state['agents'] if a.get('recovered_at') and not a['contained']}
    if missing or state['global_stop']:
        for worker in repository.list('workers'):
            if worker['agent_id'] not in contained and (missing or worker['agent_id'] not in explicitly_recovered):
                security.report({'agent_id': worker['agent_id'], 'severity': 'high', 'behavior': 'trusted_coverage_lost' if missing else 'global_stop_reconciliation',
                                 'resource': worker['vm_id'], 'evidence': 'Missing required coverage: ' + ','.join(missing) if missing else 'Durable global stop is latched'}, source='trusted_enforcer')
    for incident in security.incidents()['incidents']:
        if incident['severity'] in ('high', 'critical') and incident['status'] != 'recovered':
            # Do not reapply an older incident after a newer explicit recovery.
            with repository.transaction() as db:
                owner = _read(db, 'agent:' + incident['agent_id'], {})
            if owner.get('contained') and owner.get('incident_id') == incident['id']:
                security.enforce(incident['id'])
    security.observe('enforcer', healthy=True, source='independent reconciliation loop completed', ttl=10)
    return security.status()


def main():
    import argparse
    from .repository import SQLiteRepository
    parser = argparse.ArgumentParser(description='Trusted security reconciler; no host/network monitor is installed by this command')
    parser.add_argument('--db', required=True)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--host-monitor', action='store_true', help='Poll trusted OS-bound network adapters; missing coverage actively contains workers')
    parser.add_argument('--interval', type=float, default=2)
    args = parser.parse_args()
    if not 0.1 <= args.interval <= 5:
        parser.error('interval must be between 0.1 and 5 seconds')
    repository = SQLiteRepository(args.db)
    while True:
        try:
            state = enforce_once(repository, host_monitor=args.host_monitor)
            print(json.dumps({'global_stop': state['global_stop'], 'protected': state['protected'], 'incidents': len(state['incidents'])}), flush=True)
        except Exception:
            # A failed reconciliation must not refresh enforcer health.
            print('{"error":"reconciliation failed; execution remains fail-safe"}', flush=True)
            if args.once:
                raise SystemExit(1)
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
