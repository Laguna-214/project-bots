"""Durable, exact-payload human approval and one-shot execution receipts."""
import json
import time
import uuid

from .permissions import Permissions, POLICY_VERSION, canonical, digest, route
from .service import ConflictError, fields, identifier


class Approvals(Permissions):
    @staticmethod
    def revision(db, principal):
        # Bind configuration/policy, not volatile monitoring observations.
        configuration = {table: [json.loads(r[0]) for r in db.execute('SELECT data FROM ' + table + ' ORDER BY rowid')] for table in ('settings', 'machines', 'agents', 'workers')}
        configuration['containment'] = [(r['key'], {k: v for k, v in json.loads(r['data']).items() if k in ('stopped', 'contained', 'revoked')}) for r in db.execute('SELECT key,data FROM security_state ORDER BY key')]
        return digest(canonical({'version': POLICY_VERSION, 'principal_revision': principal['revision'], 'configuration': configuration}))

    @staticmethod
    def payload(method, path, payload):
        action, resource = route(method, path)
        if method != 'POST':
            raise ValueError('Only supported mutations need approval')
        if action.startswith('vm.'):
            allowed = {'operation_id', 'confirmation'}
            required = set(allowed)
            if action == 'vm.create':
                allowed.update(('template', 'cpus', 'ram_mib', 'disk_gib', 'ssh_key'))
                required = set(allowed)
            elif action in ('vm.snapshot-create', 'vm.snapshot-restore'):
                allowed.add('snapshot'); required.add('snapshot')
            elif action == 'vm.resources':
                allowed.update(('cpus', 'ram_mib', 'disk_gib'))
                required = set(allowed)
            fields(payload, allowed, required)
            if action == 'vm.resources':
                for name, low, high in (('cpus', 1, 8), ('ram_mib', 2048, 32768), ('disk_gib', 16, 256)):
                    if type(payload[name]) is not int or not low <= payload[name] <= high:
                        raise ValueError('Invalid resource bounds')
            if not identifier(payload['operation_id']):
                raise ValueError('Operation UUID required')
            expected = 'create' if action == 'vm.create' else action[3:] + ':' + path.split('/')[5]
            if payload['confirmation'] != expected:
                raise ValueError('Invalid intent')
        elif action == 'job.dispatch':
            fields(payload, ('confirmation',), ('confirmation',))
            if payload['confirmation'] != 'dispatch:' + path.split('/')[3]:
                raise ValueError('Invalid dispatch intent')
        else:
            fields(payload, ())
        canonical(payload)
        return action, resource

    def request(self, actor, data):
        fields(data, ('method', 'path', 'payload', 'expires_in'), ('method', 'path', 'payload'))
        action, resource = self.payload(data['method'], data['path'], data['payload'])
        ttl = data.get('expires_in', 300)
        if type(ttl) is not int or not 1 <= ttl <= 600:
            raise ValueError('Approval lifetime must be 1–600 seconds')
        with self.repository.transaction() as db:
            principal = self.authorize(actor, data['method'], data['path'], db)
            # Duplicate requests do not renew a pending/consumed authorization.
            policy_revision = self.revision(db, principal)
            if db.execute('SELECT 1 FROM integration_approvals WHERE actor=? AND json_extract(data,\'$.path\')=? AND json_extract(data,\'$.payload_hash\')=? AND (json_extract(data,\'$.status\')=\'consumed\' OR (json_extract(data,\'$.status\') IN (\'pending\',\'approved\') AND json_extract(data,\'$.expires_at\')>? AND json_extract(data,\'$.policy_revision\')=?))', (actor, data['path'], digest(canonical(data['payload'])), time.time(), policy_revision)).fetchone():
                raise ConflictError('Approval already requested; inspect original authorization')
            approval = {'id': str(uuid.uuid4()), 'actor': actor, 'actor_name': principal['name'], 'method': data['method'], 'path': data['path'], 'action': action, 'resource': resource, 'payload': data['payload'], 'canonical_payload': canonical(data['payload']), 'payload_hash': digest(canonical(data['payload'])), 'created_at': time.time(), 'expires_at': min(time.time() + ttl, principal['expires_at']), 'policy_revision': self.revision(db, principal), 'status': 'pending', 'decided_at': None, 'decided_by': None, 'operation_id': None}
            db.execute('INSERT INTO integration_approvals VALUES (?,?,?)', (approval['id'], actor, canonical(approval)))
            self.event(db, actor, 'approval_requested', approval['id'], 'pending')
        return approval

    @staticmethod
    def get(db, approval_id):
        if identifier(approval_id) is None:
            raise PermissionError('Approval required')
        row = db.execute('SELECT data FROM integration_approvals WHERE id=?', (approval_id,)).fetchone()
        if not row:
            raise PermissionError('Unknown approval')
        return json.loads(row[0])

    def decision(self, approval_id, decision, data, human=False):
        self.human(human)
        fields(data, ())
        if decision not in ('approve', 'reject'):
            raise ValueError('Unsupported decision')
        with self.repository.transaction() as db:
            approval = self.get(db, approval_id)
            if approval['status'] != 'pending' or approval['expires_at'] <= time.time():
                raise ConflictError('Approval is no longer pending/live')
            principal = self.authorize(approval['actor'], approval['method'], approval['path'], db)
            if decision == 'approve' and approval['policy_revision'] != self.revision(db, principal):
                raise ConflictError('Policy changed; request a fresh approval')
            approval.update(status='approved' if decision == 'approve' else 'rejected', decided_at=time.time(), decided_by='paired-browser-admin')
            db.execute('UPDATE integration_approvals SET data=? WHERE id=?', (canonical(approval), approval_id))
            self.event(db, approval['actor'], 'approval_' + decision, approval_id, approval['status'])
        return approval

    def listing(self, actor=None, human=False, operations=False):
        if not human and not actor:
            raise PermissionError('Forbidden')
        table = 'integration_operations' if operations else 'integration_approvals'
        key = 'operations' if operations else 'approvals'
        with self.repository.transaction() as db:
            if not human:
                self.active(db, actor)
            rows = db.execute('SELECT data FROM ' + table + (' WHERE actor=?' if not human else '') + ' ORDER BY rowid DESC LIMIT 200', () if human else (actor,))
            records = [json.loads(r[0]) for r in rows]
            if not operations:
                for record in records:
                    record['expired'] = record['expires_at'] <= time.time()
                    try:
                        principal = self.active(db, record['actor'])
                        record['invalidated'] = record['policy_revision'] != self.revision(db, principal)
                    except PermissionError:
                        record['invalidated'] = True
            return {key: records}

    def consume(self, actor, approval_id, method, path, payload):
        self.payload(method, path, payload)
        with self.repository.transaction() as db:
            principal = self.authorize(actor, method, path, db)
            approval = self.get(db, approval_id)
            if approval['actor'] != actor or approval['method'] != method or approval['path'] != path or approval['canonical_payload'] != canonical(payload) or approval['status'] != 'approved' or approval['expires_at'] <= time.time() or approval['policy_revision'] != self.revision(db, principal):
                raise PermissionError('No live exact human approval')
            operation_id = payload.get('operation_id', approval_id)
            if db.execute('SELECT 1 FROM integration_operations WHERE id=?', (operation_id,)).fetchone():
                raise ConflictError('Operation ID already used; inspect original receipt')
            approval.update(status='consumed', operation_id=operation_id, consumed_at=time.time())
            # Intent is uncertain BEFORE remote dispatch: crashes never make it retryable.
            operation = {'id': operation_id, 'actor': actor, 'approval_id': approval_id, 'action': approval['action'], 'resource': approval['resource'], 'path': path, 'payload_hash': approval['payload_hash'], 'status': 'uncertain', 'started_at': time.time(), 'finished_at': None}
            db.execute('UPDATE integration_approvals SET data=? WHERE id=?', (canonical(approval), approval_id))
            db.execute('INSERT INTO integration_operations VALUES (?,?,?,?)', (operation_id, approval_id, actor, canonical(operation)))
            self.event(db, actor, 'approval_consumed', approval_id, 'uncertain')
        return operation_id

    def finish(self, operation_id, succeeded):
        with self.repository.transaction() as db:
            row = db.execute('SELECT data FROM integration_operations WHERE id=?', (operation_id,)).fetchone()
            operation = json.loads(row[0])
            operation.update(status='succeeded' if succeeded else 'uncertain', finished_at=time.time())
            db.execute('UPDATE integration_operations SET data=? WHERE id=?', (canonical(operation), operation_id))
            self.event(db, operation['actor'], 'integration_operation', operation_id, operation['status'])
