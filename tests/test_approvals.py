"""Installed HTTP/SQLite authorization acceptance; VM fixture != real-host evidence."""
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import unittest
import uuid
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import test_platform as platform_tests


class ApprovalHTTPTests(unittest.TestCase):
    env: dict
    port: int
    setUp = platform_tests.InstalledPlatformTests.setUp
    start = platform_tests.InstalledPlatformTests.start
    stop = platform_tests.InstalledPlatformTests.stop
    request = platform_tests.InstalledPlatformTests.request
    pair = platform_tests.InstalledPlatformTests.pair

    def bearer(self, token):
        return {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}

    def issue(self, grants=None, expires_in=3600):
        data = {'name': 'Hermes fixture', 'expires_in': expires_in}
        if grants is not None:
            data['grants'] = grants
        return self.request('POST', '/api/integrations', data, 201)

    def test_browser_only_opaque_scoped_issuance_durable_revoke(self):
        self.pair()
        owner = self.bearer(self.env['PROJECT_BOTS_API_TOKEN'])
        self.request('POST', '/api/integrations', {'name': 'owner not human'}, 403, headers=owner)
        issued = self.issue()
        token = issued['token']
        self.assertGreaterEqual(len(token), 48)
        header = self.bearer(token)
        self.assertEqual(self.request('GET', '/api/workers', headers=header), [])
        self.request('GET', '/api/settings', status=403, headers=header)
        self.request('POST', '/api/agents', {'name': 'escalation', 'role': 'admin'}, 403, headers=header)
        self.request('POST', '/api/integrations', {'name': 'self'}, 403, headers=header)
        self.assertNotIn(token, json.dumps(self.request('GET', '/api/integrations')))
        with closing(sqlite3.connect(self.env['PROJECT_BOTS_DB'])) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 6)
            self.assertNotIn(token, '\n'.join(db.iterdump()))
        self.stop(); self.start(); self.pair()
        self.assertEqual(self.request('GET', '/api/workers', headers=header), [])
        self.request('POST', '/api/integrations/' + issued['id'] + '/revoke', {})
        self.request('GET', '/api/workers', status=403, headers=header)
        # A revoked integration token cannot become a legacy owner alias.
        self.stop(); self.env['PROJECT_BOTS_API_TOKEN'] = token; self.start(); self.pair()
        self.request('GET', '/api/settings', status=403, headers=header)

    def vm_fixture(self):
        observed = []
        state = {'state': 'running'}
        token = 'compute-fixture-0123456789abcdef-' * 3
        class Host(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                if self.headers.get('Authorization') != 'Bearer ' + token:
                    self.send_error(403); return
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                observed.append((self.path, data))
                state['state'] = 'paused'
                body = json.dumps({'operation_id': data['operation_id'], 'state': state['state'], 'fixture': True}).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Host)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        self.stop(); self.env['FIXTURE_COMPUTE_TOKEN'] = token; self.start(); self.pair()
        machine = self.request('POST', '/api/machines', {'name': 'labeled local fixture', 'endpoint': 'http://127.0.0.1:' + str(server.server_port), 'credential_env': 'FIXTURE_COMPUTE_TOKEN'}, 201)
        vm = str(uuid.uuid4())
        path = '/api/machines/' + machine['id'] + '/vms/' + vm + '/pause'
        payload = {'operation_id': str(uuid.uuid4()), 'confirmation': 'pause:' + vm}
        return path, payload, observed, state

    def test_bound_human_approval_consumed_once_on_real_fixture_mutation(self):
        path, payload, observed, state = self.vm_fixture()
        issued = self.issue([{'method': 'POST', 'path': path}])
        headers = self.bearer(issued['token'])
        self.request('POST', path, payload, 403, headers=headers)
        self.assertEqual(observed, [])
        approval = self.request('POST', '/api/approvals', {'method': 'POST', 'path': path, 'payload': payload, 'expires_in': 300}, 201, headers=headers)
        aid = approval['id']
        self.assertEqual(approval['actor'], issued['id'])
        self.assertEqual(approval['action'], 'vm.pause')
        self.request('POST', '/api/approvals/' + aid + '/approve', {}, 403, headers=headers)
        self.request('POST', '/api/approvals/' + aid + '/approve', {'human': True}, 403, headers=self.bearer(self.env['PROJECT_BOTS_API_TOKEN']))
        self.request('POST', '/api/approvals/' + aid + '/approve', {})
        approved = dict(headers, **{'X-Approval-ID': aid})
        self.request('POST', path, dict(payload, operation_id=str(uuid.uuid4())), 403, headers=approved)
        peer = self.issue([{'method': 'POST', 'path': path}])
        self.request('POST', path, payload, 403, headers=dict(self.bearer(peer['token']), **{'X-Approval-ID': aid}))
        self.assertEqual(observed, [])
        # Restart retains both the principal and the human's exact authorization.
        self.stop(); self.start(); self.pair()
        result = self.request('POST', path, payload, headers=approved)
        self.assertTrue(result['fixture'])
        self.assertEqual(state['state'], 'paused')
        self.assertEqual(observed, [('/v1/' + '/'.join(path.split('/')[4:]), payload)])
        self.request('POST', path, payload, 403, headers=approved)
        self.assertEqual(len(observed), 1)
        operations = self.request('GET', '/api/integration-operations', headers=headers)['operations']
        self.assertEqual(operations[0]['id'], payload['operation_id'])
        self.assertEqual(operations[0]['status'], 'succeeded')
        self.assertEqual(self.request('GET', '/api/approvals')['approvals'][0]['status'], 'consumed')

    def test_resources_proposal_human_approval_executes_real_compute_fixture_disk_growth(self):
        import test_machine as machine_tests
        from project_bots.machine_http import make_handler
        fixture = machine_tests.ComputeTests(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        backend = fixture.backend()
        vm = fixture.provision(backend)
        token = 'local-compute-fixture-' + '0123456789abcdef'*3
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(backend, token))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        self.stop(); self.env['RESOURCE_COMPUTE_FIXTURE'] = token; self.start(); self.pair()
        machine = self.request('POST', '/api/machines', {'name':'real compute local fixture',
            'endpoint':'http://127.0.0.1:'+str(server.server_port), 'credential_env':'RESOURCE_COMPUTE_FIXTURE'}, 201)
        path = '/api/machines/'+machine['id']+'/vms/'+vm['id']+'/resources'
        payload = {'operation_id':str(uuid.uuid4()), 'confirmation':'resources:'+vm['id'],
                   'cpus':3, 'ram_mib':6144, 'disk_gib':32}
        issued = self.issue([{'method':'POST','path':path}])
        headers = self.bearer(issued['token'])
        for key in ('cpus','ram_mib','disk_gib'):
            invalid = {k:v for k,v in payload.items() if k != key}
            self.request('POST', '/api/approvals', {'method':'POST','path':path,'payload':invalid},400,headers=headers)
        for key, value in (('cpus',True),('ram_mib',0),('disk_gib',-1)):
            self.request('POST', '/api/approvals', {'method':'POST','path':path,'payload':dict(payload,**{key:value})},400,headers=headers)
        self.assertEqual(self.request('GET','/api/approvals')['approvals'],[])
        approval = self.request('POST', '/api/approvals', {'method':'POST','path':path,'payload':payload},201,headers=headers)
        self.request('POST','/api/approvals/'+approval['id']+'/approve',{})
        approved = dict(headers, **{'X-Approval-ID':approval['id']})
        self.request('POST',path,dict(payload,disk_gib=-1),400,headers=approved)
        self.assertEqual(self.request('GET','/api/approvals')['approvals'][0]['status'],'approved')
        self.assertEqual(self.request('GET','/api/integration-operations',headers=headers)['operations'],[])
        result = self.request('POST',path,payload,headers=approved)
        self.assertEqual((result['cpus'],result['ram_mib'],result['disk_gib']),(3,6144,32))
        self.assertEqual(backend.detail(vm['id'])['disk_gib'],32)
        self.assertTrue(any(call[:2]==['qemu-img','resize'] and call[-1]=='32G' for call in fixture.calls))
        self.assertEqual(self.request('GET','/api/approvals')['approvals'][0]['status'],'consumed')
        self.assertEqual(self.request('GET','/api/integration-operations',headers=headers)['operations'][0]['status'],'succeeded')

    def test_expiry_rejection_revocation_policy_change_and_scope_are_fail_closed(self):
        path, payload, observed, state = self.vm_fixture()
        issued = self.issue([{'method': 'POST', 'path': path}])
        headers = self.bearer(issued['token'])
        def propose(ttl=300, body=None):
            return self.request('POST', '/api/approvals', {'method': 'POST', 'path': path, 'payload': body or payload, 'expires_in': ttl}, 201, headers=headers)
        self.request('POST', '/api/approvals', {'method': 'POST', 'path': '/api/settings', 'payload': {}}, 400, headers=headers)
        self.request('POST', '/api/approvals', {'method': 'POST', 'path': path.replace('/pause', '/delete'), 'payload': dict(payload, confirmation=payload['confirmation'].replace('pause:', 'delete:'))}, 403, headers=headers)
        self.request('POST', '/api/integrations', {'name': 'no wildcards', 'grants': [{'method': 'GET', 'path': '/api/*'}]}, 400)
        first = propose(1)
        self.request('POST', '/api/approvals/' + first['id'] + '/approve', {})
        time.sleep(1.05)
        self.request('POST', path, payload, 403, headers=dict(headers, **{'X-Approval-ID': first['id']}))
        # Expired requests may be re-proposed, but the old decision never revives.
        second = propose()
        self.request('POST', '/api/approvals/' + second['id'] + '/reject', {})
        self.request('POST', path, payload, 403, headers=dict(headers, **{'X-Approval-ID': second['id']}))
        third = propose()
        self.request('POST', '/api/approvals/' + third['id'] + '/approve', {})
        settings = self.request('GET', '/api/settings')
        self.request('POST', '/api/settings', dict(settings, inference_endpoint='http://127.0.0.1:11435'))
        self.request('POST', path, payload, 403, headers=dict(headers, **{'X-Approval-ID': third['id']}))
        self.assertTrue(self.request('GET', '/api/approvals')['approvals'][0]['invalidated'])
        self.request('POST', '/api/integrations/' + issued['id'] + '/revoke', {})
        self.request('POST', path, payload, 403, headers=dict(headers, **{'X-Approval-ID': third['id']}))
        self.assertEqual(observed, [])
        short = self.issue(expires_in=1)
        time.sleep(1.05)
        self.request('GET', '/api/workers', status=403, headers=self.bearer(short['token']))

    def test_concurrent_consumption_and_uncertain_outcome_survive_restart(self):
        import concurrent.futures
        path, payload, observed, state = self.vm_fixture()
        issued = self.issue([{'method': 'POST', 'path': path}])
        headers = self.bearer(issued['token'])
        approval = self.request('POST', '/api/approvals', {'method': 'POST', 'path': path, 'payload': payload}, 201, headers=headers)
        self.request('POST', '/api/approvals/' + approval['id'] + '/approve', {})
        approved = dict(headers, **{'X-Approval-ID': approval['id']})
        import http.client
        def run(_):
            with closing(http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)) as conn:
                conn.request('POST', path, json.dumps(payload), approved)
                response = conn.getresponse(); response.read()
                return response.status
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(run, range(4)))
        self.assertEqual(sorted(results), [200, 403, 403, 403])
        self.assertEqual(len(observed), 1)
        # A genuine unreachable transport, not a mocked success, retains intent.
        missing = self.request('POST', '/api/machines', {'name': 'unreachable fixture', 'endpoint': 'http://127.0.0.1:1', 'credential_env': 'FIXTURE_COMPUTE_TOKEN'}, 201)
        bad_path = path.replace(path.split('/')[3], missing['id'])
        bad = self.issue([{'method': 'POST', 'path': bad_path}]); bh = self.bearer(bad['token'])
        proposal = self.request('POST', '/api/approvals', {'method': 'POST', 'path': bad_path, 'payload': payload}, 201, headers=bh)
        self.request('POST', '/api/approvals/' + proposal['id'] + '/approve', {})
        # Original operation UUID is globally retained even under another actor.
        self.request('POST', bad_path, payload, 409, headers=dict(bh, **{'X-Approval-ID': proposal['id']}))
        fresh = dict(payload, operation_id=str(uuid.uuid4()))
        proposal = self.request('POST', '/api/approvals', {'method': 'POST', 'path': bad_path, 'payload': fresh}, 201, headers=bh)
        self.request('POST', '/api/approvals/' + proposal['id'] + '/approve', {})
        attempt = dict(bh, **{'X-Approval-ID': proposal['id']})
        self.request('POST', bad_path, fresh, 503, headers=attempt)
        self.stop(); self.start(); self.pair()
        self.request('POST', bad_path, fresh, 403, headers=attempt)
        receipt = self.request('GET', '/api/integration-operations', headers=bh)['operations'][0]
        self.assertEqual((receipt['id'], receipt['status']), (fresh['operation_id'], 'uncertain'))
        peer = self.issue()
        self.assertEqual(self.request('GET', '/api/approvals', headers=self.bearer(peer['token'])), {'approvals': []})

    def test_inference_worker_and_integration_credential_aliases_never_gain_owner_authority(self):
        self.stop()
        shared = 'alias-fixture-0123456789abcdef-' * 3
        self.env.update(PROJECT_BOTS_API_TOKEN=shared, PROJECT_BOTS_INFERENCE_ADMIN_TOKEN=shared)
        self.start(); self.pair()
        self.request('GET', '/api/settings', status=403, headers=self.bearer(shared))
        self.stop()
        self.env.pop('PROJECT_BOTS_INFERENCE_ADMIN_TOKEN')
        self.env['PROJECT_BOTS_LLAMA_TOKEN_ENV'] = 'CUSTOM_INFERENCE_AUTH'
        self.env['CUSTOM_INFERENCE_AUTH'] = shared
        self.start(); self.pair()
        self.request('GET', '/api/settings', status=403, headers=self.bearer(shared))
        self.stop(); self.env.pop('CUSTOM_INFERENCE_AUTH'); self.env.pop('PROJECT_BOTS_LLAMA_TOKEN_ENV')
        self.env['CHAT_FIXTURE_TOKEN'] = shared
        self.env['PROJECT_BOTS_API_TOKEN'] = 'separate-owner-0123456789abcdef-' * 3
        self.start(); self.pair()
        agent = self.request('POST', '/api/agents', {'name': 'chat worker', 'role': 'research'}, 201)
        self.request('POST', '/api/agents/' + agent['id'] + '/chat-identity', {'credential_env': 'CHAT_FIXTURE_TOKEN', 'enabled': True})
        self.stop(); self.env['PROJECT_BOTS_API_TOKEN'] = shared; self.start(); self.pair()
        self.request('GET', '/api/settings', status=403, headers=self.bearer(shared))
        self.request('POST', '/api/agents', {'name': 'same-reference inference', 'role': 'research', 'config': {'credential_env': 'PROJECT_BOTS_API_TOKEN'}}, 201)
        self.stop(); self.env['PROJECT_BOTS_API_TOKEN'] = 'unique-owner-0123456789abcdef-' * 3; self.start(); self.pair()
        self.request('GET', '/api/settings', status=403, headers=self.bearer(self.env['PROJECT_BOTS_API_TOKEN']))


if __name__ == '__main__':
    unittest.main()
