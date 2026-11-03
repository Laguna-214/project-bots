"""Actual local HTTP fixture backend; NOT real-model/GPU acceptance."""
import concurrent.futures
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from project_bots.models import DurableAdmission
from project_bots.repository import SQLiteRepository
from project_bots.inference_proxy import make_handler
from project_bots.service import PlatformService
from project_bots.security import SecurityService
from security_fixtures import fixture_security

MODEL = 'shared-model'
ENTRY = {'size':1024, 'context':2048, 'sha256':'a'*64, 'capabilities':['tools'],
         'model_info':{'general.architecture':'test','test.block_count':1,
                       'test.attention.head_count_kv':1,'test.attention.key_length':1,'test.attention.value_length':1}}


class SharedHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository(Path(self.temp.name)/'private'/'db')
        self.workers = fixture_security(SQLiteRepository(Path(self.temp.name)/'workers'/'db'))
        self.security = SecurityService(self.workers)
        self.calls = []
        self.running = self.peak = 0
        self.loaded = True
        self.lock = threading.Lock()
        self.block = threading.Event()
        self.block.set()
        self.delay = .08
        self.streaming = False
        self.inventory_delay = 0
        owner = self
        class Backend(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                time.sleep(owner.inventory_delay)
                raw = json.dumps({'data':[{'id':MODEL,'status':{'value':'loaded' if owner.loaded else 'unloaded'}}]}).encode()
                try:
                    self.send_response(200); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
                except (BrokenPipeError,ConnectionResetError):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path=='/models/unload':
                    owner.loaded=False
                    self.send_response(200);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'{}');return
                with owner.lock:
                    owner.calls.append(body); owner.running+=1; owner.peak=max(owner.peak,owner.running)
                try:
                    if owner.streaming:
                        self.send_response(200);self.end_headers();self.wfile.write(b'first\n');self.wfile.flush()
                        owner.block.wait(5)
                        self.wfile.write(b'late-private-output');return
                    owner.block.wait(5); time.sleep(owner.delay)
                    raw=json.dumps({'choices':[{'message':{'content':body['messages'][0]['content']}}]}).encode()
                    self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError): pass
                finally:
                    with owner.lock: owner.running-=1
        self.backend=ThreadingHTTPServer(('127.0.0.1',0), Backend)
        threading.Thread(target=self.backend.serve_forever,daemon=True).start()
        service = PlatformService(self.workers)
        import uuid
        self.rows=[]
        for i in range(4):
            agent=service.create_agent({'name':'fixture-'+str(i),'role':'Researcher',
                                        'config':{'credential_env':'INDEPENDENT_INFERENCE_'+str(i)}})
            self.rows.append(service.register_worker(agent['id'], {
                'vm_id':str(uuid.uuid4()), 'endpoint':'http://127.0.0.1:19889',
                'credential_env':'INFERENCE_TEST_AGENT_'+str(i),
                'profile':{'model':MODEL,'context':2048,'temperature':0,'max_output':16,'memory_mib':2048,'priority':10}}))
        self.env={r['credential_env']:'independent-'+str(i)+'-'+'x'*40 for i,r in enumerate(self.rows)}
        self.env.update(TEST_BROKER_ADMIN='admin-'+'a'*40,TEST_BROKER_BACKEND='backend-'+'b'*40)
        self.patch=patch.dict(os.environ,self.env);self.patch.start()
        self.servers=[]

    def start(self, **kwargs):
        for row in self.rows:self.workers.save_worker(row)
        gate=DurableAdmission(self.repo, memory_mib=kwargs.pop('memory_mib',8192),concurrency=kwargs.pop('concurrency',1), queue_limit=kwargs.pop('queue_limit',8))
        handler=make_handler(self.workers,gate,'http://127.0.0.1:'+str(self.backend.server_port), 'TEST_BROKER_ADMIN', {MODEL:ENTRY},'TEST_BROKER_BACKEND', **kwargs)
        server=ThreadingHTTPServer(('127.0.0.1',0),handler)
        threading.Thread(target=server.serve_forever,daemon=True).start();self.servers.append(server)
        return server

    def request(self, server, agent, *, body=None, path='/v1/chat/completions', request_id=None):
        body=body or {'model':MODEL,'messages':[{'role':'system','content':'private-agent-'+str(agent)}]}
        headers={'Authorization':'Bearer '+os.environ[self.rows[agent]['credential_env']], 'Content-Type':'application/json'}
        if request_id:headers['X-Request-ID']=request_id
        req=Request('http://127.0.0.1:'+str(server.server_port)+path,data=json.dumps(body).encode(),headers=headers)
        try:
            with urlopen(req,timeout=5) as response:return response.status,response.read()
        except HTTPError as exc:
            try:return exc.code,exc.read()
            finally:exc.close()

    def wait_calls(self,n):
        deadline=time.monotonic()+3
        while len(self.calls)<n and time.monotonic()<deadline:time.sleep(.005)
        self.assertGreaterEqual(len(self.calls),n)

    def tearDown(self):
        self.block.set()
        for s in self.servers:s.shutdown();s.server_close()
        self.backend.shutdown();self.backend.server_close();self.patch.stop();self.temp.cleanup()

    def test_registered_chat_alias_never_gains_broker_authority_after_env_changes(self):
        from project_bots.chat import ChatService
        chat = ChatService(self.workers)
        with patch.dict(os.environ, {'BROKER_CHAT_ONLY': 'chat-only-'+'c'*40}):
            chat.configure_identity(self.rows[0]['agent_id'], {'credential_env':'BROKER_CHAT_ONLY','enabled':True})
            server = self.start()
            def management(token):
                req = Request('http://127.0.0.1:'+str(server.server_port)+'/management/models',
                              headers={'Authorization':'Bearer '+token})
                try:
                    with urlopen(req, timeout=5) as response: return response.status
                except HTTPError as exc:
                    try: return exc.code
                    finally: exc.close()
            legitimate = os.environ['TEST_BROKER_ADMIN']
            for enabled in (True, False):
                chat.configure_identity(self.rows[0]['agent_id'], {'credential_env':'BROKER_CHAT_ONLY','enabled':enabled})
                with patch.dict(os.environ, {'TEST_BROKER_ADMIN':os.environ['BROKER_CHAT_ONLY']}):
                    self.assertEqual(management(os.environ['BROKER_CHAT_ONLY']),403)
                self.assertEqual(management(legitimate),200)
                with patch.dict(os.environ, {self.rows[0]['credential_env']:os.environ['BROKER_CHAT_ONLY']}):
                    self.assertEqual(self.request(server,0)[0],403)

    def test_unreadable_chat_registry_denies_admin_without_handler_crash(self):
        import sqlite3
        from contextlib import contextmanager, closing
        from types import SimpleNamespace
        @contextmanager
        def bare_transaction():
            with closing(sqlite3.connect(':memory:')) as db:
                yield db
        for repository in (SimpleNamespace(list=lambda kind: []),
                           SimpleNamespace(list=lambda kind: [],transaction=bare_transaction)):
            handler = make_handler(repository,DurableAdmission(self.repo),
                'http://127.0.0.1:'+str(self.backend.server_port), 'TEST_BROKER_ADMIN', {MODEL:ENTRY})
            server = ThreadingHTTPServer(('127.0.0.1',0),handler)
            threading.Thread(target=server.serve_forever,daemon=True).start();self.servers.append(server)
            req = Request('http://127.0.0.1:'+str(server.server_port)+'/management/models',
                headers={'Authorization':'Bearer '+os.environ['TEST_BROKER_ADMIN']})
            with self.assertRaises(HTTPError) as denied: urlopen(req,timeout=5)
            self.assertEqual(denied.exception.code,403);denied.exception.close()

    def test_four_independent_agents_same_backend_bounded_parallel_private_context(self):
        for concurrency in (1,2):
            with self.subTest(concurrency=concurrency):
                self.calls.clear();self.peak=0
                server=self.start(concurrency=concurrency)
                start=time.monotonic();latencies=[]
                def timed_request(i):
                    started=time.monotonic()
                    result=self.request(server,i)
                    latencies.append(time.monotonic()-started)
                    return result
                with concurrent.futures.ThreadPoolExecutor(4) as pool:
                    results=list(pool.map(timed_request,range(4)))
                elapsed=time.monotonic()-start
                self.assertTrue(all(code==200 for code,_ in results),results)
                self.assertEqual(self.peak,concurrency)
                self.assertEqual(len(self.calls),4)
                for i,(_,raw) in enumerate(results):
                    self.assertIn(('private-agent-'+str(i)).encode(),raw)
                    for j in range(4):
                        if i!=j:self.assertNotIn(('private-agent-'+str(j)).encode(),raw)
                metrics={'agents':4,'requests':4,'concurrency':concurrency,'peak':self.peak,'seconds':round(elapsed,4),'requests_per_second':round(4/elapsed,3),'latency_ms_sorted':[round(x*1000,3) for x in sorted(latencies)]}
                print('FIXTURE_HTTP_BENCHMARK',json.dumps(metrics))

    def contain(self, agent=0):
        return self.security.report({'agent_id':self.rows[agent]['agent_id'], 'severity':'high',
            'behavior':'fixture containment','resource':'fixture','evidence':'isolated HTTP test'})

    def test_mandatory_containment_denies_even_with_allowing_external_hook(self):
        server=self.start(admission_check=lambda *args:True)
        self.contain()
        self.assertEqual(self.request(server,0)[0],403)
        self.assertEqual(self.calls,[])

    def test_global_stop_and_missing_monitor_deny_without_optional_hook(self):
        server=self.start()
        for coverage in ('runtime','network','identity','audit','enforcer'):
            with self.subTest(coverage=coverage):
                with self.workers.transaction() as db:
                    db.execute('DELETE FROM security_state WHERE key=?', ('coverage:'+coverage,))
                self.assertEqual(self.request(server,0)[0],403)
                fixture_security(self.workers)
        self.security.emergency_stop({'reason':'isolated fixture stop'})
        self.assertEqual(self.request(server,0)[0],403)
        req=Request('http://127.0.0.1:'+str(server.server_port)+'/management/models',
                    headers={'Authorization':'Bearer '+os.environ['TEST_BROKER_ADMIN']})
        with urlopen(req) as response:self.assertEqual(response.status,200)
        self.assertEqual(self.calls,[])

    def test_owner_cancellation_remains_available_after_containment(self):
        import uuid
        from project_bots.inference_scheduler import SharedScheduler
        allowed=threading.Event();allowed.set()
        scheduler=SharedScheduler(DurableAdmission(self.repo))
        server=self.start(scheduler=scheduler,admission_check=lambda *args:allowed.is_set())
        ticket=str(uuid.uuid4())
        with scheduler.slot(self.rows[0]['agent_id'],2048,10,100,request_id=ticket):
            self.contain();allowed.clear()
            wrong=self.request(server,1,path='/v1/requests/cancel',body={'request_id':ticket})
            self.assertFalse(json.loads(wrong[1])['cancel_requested'])
            result=self.request(server,0,path='/v1/requests/cancel',body={'request_id':ticket})
            self.assertEqual(result[0],202)
            self.assertTrue(json.loads(result[1])['cancel_requested'])
            self.assertFalse(json.loads(result[1])['backend_stopped'])

    def test_containment_while_queued_prevents_dispatch(self):
        from project_bots.inference_scheduler import SharedScheduler
        scheduler=SharedScheduler(DurableAdmission(self.repo))
        server=self.start(scheduler=scheduler)
        self.block.clear()
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            active=pool.submit(self.request,server,0)
            self.wait_calls(1)
            queued=pool.submit(self.request,server,1)
            deadline=time.monotonic()+2
            while scheduler.gate.pending!=1 and time.monotonic()<deadline:time.sleep(.005)
            self.assertEqual(scheduler.gate.pending,1)
            self.contain(1)
            self.assertEqual(queued.result(timeout=2)[0],403)
            self.block.set()
            self.assertEqual(active.result()[0],200)
        self.assertEqual(len(self.calls),1)

    def test_security_lost_during_inventory_prevents_forward(self):
        self.inventory_delay=.2
        server=self.start()
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            result=pool.submit(self.request,server,0)
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                with self.repo.transaction() as db:
                    if db.execute("SELECT 1 FROM inference_admission WHERE state='active'").fetchone():break
                time.sleep(.005)
            self.security.observe('identity',healthy=False,source='isolated failure fixture')
            self.assertEqual(result.result()[0],403)
        self.assertEqual(self.calls,[])

    def test_active_http_containment_and_monitor_loss_suppress_late_output(self):
        import http.client
        self.streaming=True;self.block.clear()
        for agent,loss in enumerate(('containment','monitor','global_stop')):
            with self.subTest(loss=loss):
                if loss=='global_stop':fixture_security(self.workers)
                server=self.start(concurrency=3) if loss=='containment' else self.servers[0]
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=2)
                try:
                    connection.request('POST','/v1/chat/completions',json.dumps({'model':MODEL,'messages':[]}),
                        headers={'Authorization':'Bearer '+os.environ[self.rows[agent]['credential_env']]})
                    response=connection.getresponse()
                    self.assertEqual(response.read(6),b'first\n')
                    if loss=='containment':self.contain(agent)
                    elif loss=='global_stop':self.security.emergency_stop({'reason':'active HTTP fixture'})
                    else:
                        with self.workers.transaction() as db:
                            db.execute("DELETE FROM security_state WHERE key='coverage:network'")
                    self.assertEqual(response.read(),b'')
                    self.assertEqual(self.request(server,agent)[0],403)
                    with self.repo.transaction() as db:
                        self.assertEqual(db.execute("SELECT count(*) FROM inference_admission WHERE state='uncertain'").fetchone()[0],agent+1)
                finally:connection.close()

    def test_unregistered_agent_and_mismatched_independent_rotation_reference_denied(self):
        credentials={r['agent_id']:'INDEPENDENT_INFERENCE_'+str(i) for i,r in enumerate(self.rows)}
        credentials[self.rows[0]['agent_id']]='UNTRACKED_INFERENCE_FIXTURE'
        with patch.dict(os.environ,{'UNTRACKED_INFERENCE_FIXTURE':'isolated-new-token-'+'z'*40}):
            server=self.start(requester_credentials=credentials)
            req=Request('http://127.0.0.1:'+str(server.server_port)+'/v1/chat/completions',
                data=json.dumps({'model':MODEL,'messages':[]}).encode(),
                headers={'Authorization':'Bearer '+os.environ['UNTRACKED_INFERENCE_FIXTURE']})
            with self.assertRaises(HTTPError) as caught:urlopen(req)
            self.assertEqual(caught.exception.code,403);caught.exception.close()
        # A stale/orphan worker row must not create an execution identity.
        with self.workers.transaction() as db:
            db.execute('DELETE FROM workers WHERE agent_id=?',(self.rows[0]['agent_id'],))
            db.execute('DELETE FROM agents WHERE id=?',(self.rows[0]['agent_id'],))
        # Fixture wrapper retains the stale row but delegates real security storage.
        owner=self
        class StaleRegistry:
            transaction=owner.workers.transaction
            get_settings=owner.workers.get_settings
            def list(inner,name):return owner.rows
        stale_workers=StaleRegistry()
        gate=DurableAdmission(self.repo)
        handler=make_handler(stale_workers,gate,'http://127.0.0.1:'+str(self.backend.server_port),'TEST_BROKER_ADMIN',{MODEL:ENTRY})
        server=ThreadingHTTPServer(('127.0.0.1',0),handler)
        threading.Thread(target=server.serve_forever,daemon=True).start();self.servers.append(server)
        self.assertEqual(self.request(server,0)[0],403)
        self.assertEqual(self.calls,[])

    def test_recovered_identity_cannot_restore_revoked_inference_token(self):
        credentials={r['agent_id']:'INDEPENDENT_INFERENCE_'+str(i) for i,r in enumerate(self.rows)}
        with patch.dict(os.environ,{ref:'fixture-inference-'+str(i)+'z'*40 for i,ref in enumerate(credentials.values())}):
            server=self.start(requester_credentials=credentials)
            agent=self.rows[0]['agent_id'];ref=credentials[agent]
            old=os.environ[ref]
            service=PlatformService(self.workers)
            machine=service.create_machine({'name':'fixture-only','endpoint':'http://127.0.0.1:19889'})
            with self.workers.transaction() as db:
                data=json.loads(db.execute('SELECT data FROM agents WHERE id=?',(agent,)).fetchone()[0])
                data['machine_id']=machine['id']
                db.execute('UPDATE agents SET machine_id=?,data=? WHERE id=?',(machine['id'],json.dumps(data),agent))
            # Trusted runtime-stop readback fixture, not a real Machine Manager.
            self.security.compute_request=lambda *args: {'id':self.rows[0]['vm_id'],'state':'shut off'}
            incident=self.contain()
            self.security.acknowledge(incident['id'],{'note':'fixture investigation'})
            os.environ[ref]='rotated-fixture-inference-'+'n'*40
            os.environ[self.rows[0]['credential_env']]='rotated-fixture-gateway-'+'m'*40
            self.security.recover({'note':'fixture explicit recovery','credential_rotated':True},incident['id'])
            self.workers.save_worker(self.rows[0])
            def independent_request():
                req=Request('http://127.0.0.1:'+str(server.server_port)+'/v1/chat/completions',
                    data=json.dumps({'model':MODEL,'messages':[{'role':'user','content':'rotation fixture'}]}).encode(),headers={'Authorization':'Bearer '+os.environ[ref]})
                try:
                    with urlopen(req) as response:return response.status
                except HTTPError as exc:
                    code=exc.code;exc.close();return code
            self.assertEqual(independent_request(),200)
            os.environ[ref]=old
            self.assertEqual(independent_request(),403)
            self.assertEqual(len(self.calls),1)

    def test_configured_admission_failure_is_closed(self):
        def broken(*args):raise RuntimeError('unavailable')
        server=self.start(admission_check=broken)
        self.assertEqual(self.request(server,0)[0],403)
        self.assertEqual(self.calls,[])

    def test_custom_admin_alias_of_gateway_is_denied_with_independent_map(self):
        credentials={r['agent_id']:'INDEPENDENT_INFERENCE_'+str(i) for i,r in enumerate(self.rows)}
        server=self.start(requester_credentials=credentials)
        os.environ[self.rows[0]['credential_env']]=os.environ['TEST_BROKER_ADMIN']
        self.assertEqual(self.request(server,0,path='/management/show')[0],403)

    def test_equal_credential_alias_and_admin_alias_rejected(self):
        server=self.start()
        os.environ[self.rows[1]['credential_env']]=os.environ[self.rows[0]['credential_env']]
        self.assertEqual(self.request(server,0)[0],403)
        os.environ[self.rows[1]['credential_env']]=self.env[self.rows[1]['credential_env']]
        os.environ[self.rows[0]['credential_env']]=os.environ['TEST_BROKER_ADMIN']
        self.assertEqual(self.request(server,0)[0],403)
        self.assertEqual(self.calls,[])

    def test_http_fairness_prioritizes_interactive_without_repeat_agent_monopoly(self):
        from project_bots.inference_scheduler import SharedScheduler
        self.rows[1]['profile']['priority']=90
        self.rows[2]['profile']['priority']=1
        scheduler=SharedScheduler(DurableAdmission(self.repo,queue_limit=8))
        server=self.start(scheduler=scheduler)
        self.block.clear()
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            futures=[pool.submit(self.request,server,0)]
            self.wait_calls(1)
            for i,agent in enumerate((0,1,2),1):
                futures.append(pool.submit(self.request,server,agent))
                deadline=time.monotonic()+2
                while scheduler.gate.pending!=i and time.monotonic()<deadline:time.sleep(.005)
                self.assertEqual(scheduler.gate.pending,i)
            self.block.set()
            self.assertTrue(all(f.result()[0]==200 for f in futures))
        self.assertEqual([b['messages'][0]['content'] for b in self.calls],['private-agent-0','private-agent-2','private-agent-1','private-agent-0'])

    def test_model_mutation_excludes_all_parallel_inference(self):
        server=self.start(concurrency=2,memory_mib=16384)
        self.block.clear()
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            active=pool.submit(self.request,server,0)
            self.wait_calls(1)
            def unload():
                req=Request('http://127.0.0.1:'+str(server.server_port)+'/models/unload',data=json.dumps({'model':MODEL}).encode(),headers={'Authorization':'Bearer '+os.environ['TEST_BROKER_ADMIN']})
                with urlopen(req,timeout=3) as response:return response.read()
            mutation=pool.submit(unload)
            time.sleep(.1)
            self.assertFalse(mutation.done(),'unload overlapped active inference')
            self.assertTrue(self.loaded)
            self.block.set();self.assertEqual(active.result()[0],200)
            mutation.result()
            self.assertFalse(self.loaded)

    def test_queue_overload_and_owned_cancellation_never_dispatch_queued_request(self):
        import uuid
        from project_bots.inference_scheduler import SharedScheduler
        scheduler=SharedScheduler(DurableAdmission(self.repo,queue_limit=1),queue_timeout=.4)
        server=self.start(scheduler=scheduler)
        self.block.clear()
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            active=pool.submit(self.request,server,0)
            self.wait_calls(1)
            ticket=str(uuid.uuid4())
            queued=pool.submit(self.request,server,1,request_id=ticket)
            deadline=time.monotonic()+2
            while scheduler.gate.pending!=1 and time.monotonic()<deadline:time.sleep(.005)
            self.assertEqual(scheduler.gate.pending,1)
            self.assertEqual(self.request(server,2)[0],429)
            wrong=self.request(server,2,path='/v1/requests/cancel',body={'request_id':ticket})
            self.assertFalse(json.loads(wrong[1])['cancel_requested'])
            right=self.request(server,1,path='/v1/requests/cancel',body={'request_id':ticket})
            self.assertTrue(json.loads(right[1])['cancel_requested'])
            self.assertFalse(json.loads(right[1])['backend_stopped'])
            self.assertEqual(queued.result()[0],403)
            self.block.set()
            self.assertEqual(active.result()[0],200)
        self.assertEqual(len(self.calls),1)

    def test_active_stream_cancellation_interrupts_forwarding_but_retains_reservation(self):
        import http.client,uuid
        self.streaming=True;self.block.clear()
        server=self.start()
        ticket=str(uuid.uuid4())
        connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
        try:
            connection.request('POST','/v1/chat/completions',json.dumps({'model':MODEL,'messages':[{'role':'user','content':'private'}]}),headers={'Authorization':'Bearer '+os.environ[self.rows[0]['credential_env']],'X-Request-ID':ticket})
            response=connection.getresponse()
            self.assertEqual(response.read(6),b'first\n')
            result=self.request(server,0,path='/v1/requests/cancel',body={'request_id':ticket})
            self.assertTrue(json.loads(result[1])['cancel_requested'])
            self.assertEqual(response.read(),b'')
            self.assertEqual(self.running,1,'backend has not confirmed stopping')
            with self.repo.transaction() as db:self.assertEqual(db.execute('SELECT state FROM inference_admission').fetchone()[0],'uncertain')
        finally:connection.close();self.block.set()

    def test_active_revocation_preserves_uncertain_work_and_discards_response(self):
        import uuid
        allowed={self.rows[0]['agent_id']:True}
        server=self.start(admission_check=lambda agent,action:allowed.get(agent,True))
        self.block.clear()
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            result=pool.submit(self.request,server,0,request_id=str(uuid.uuid4()))
            self.wait_calls(1)
            allowed[self.rows[0]['agent_id']]=False
            time.sleep(.06)
            self.block.set()
            self.assertEqual(result.result()[0],403)
        with self.repo.transaction() as db:
            self.assertEqual(db.execute('SELECT state FROM inference_admission').fetchone()[0],'uncertain')
        self.assertEqual(self.request(server,0)[0],403)

    def test_backend_deadline_includes_inventory_before_dispatch(self):
        self.inventory_delay=.1
        server=self.start(request_timeout=.03)
        self.assertEqual(self.request(server,0)[0],503)
        self.assertEqual(self.calls,[])
        with self.repo.transaction() as db:self.assertEqual(db.execute('SELECT count(*) FROM inference_admission').fetchone()[0],0)

    def test_timeout_retains_actual_backend_work(self):
        server=self.start(request_timeout=.05)
        self.block.clear()
        result=self.request(server,0)
        self.assertEqual(result[0],504)
        self.assertEqual(self.running,1)
        with self.repo.transaction() as db:
            self.assertEqual(db.execute('SELECT state FROM inference_admission').fetchone()[0],'uncertain')
        self.block.set()

    def test_rate_budget_is_per_agent_and_payload_priority_cannot_override(self):
        from project_bots.inference_scheduler import SharedScheduler
        scheduler=SharedScheduler(DurableAdmission(self.repo),requests_per_minute=1)
        server=self.start(scheduler=scheduler)
        body={'model':MODEL,'messages':[{'role':'user','content':'rate-test'}],'priority':0,'max_tokens':99999,'temperature':2,'user':'another-agent'}
        self.assertEqual(self.request(server,0,body=body)[0],200)
        self.assertEqual(self.request(server,0)[0],429)
        self.assertEqual(self.request(server,1)[0],200)
        self.assertEqual(self.calls[0]['max_tokens'],16)
        self.assertEqual(self.calls[0]['temperature'],0)
        self.assertNotIn('priority',self.calls[0])
        self.assertNotIn('user',self.calls[0])

    def test_logs_metadata_only_and_independent_credentials_can_be_required(self):
        credentials={r['agent_id']:'INDEPENDENT_INFERENCE_'+str(i) for i,r in enumerate(self.rows)}
        for agent,ref in credentials.items():os.environ[ref]='isolated-inference-'+agent+'z'*40
        try:
            server=self.start(requester_credentials=credentials)
            self.assertEqual(self.request(server,0)[0],403)
            legacy=os.environ[self.rows[0]['credential_env']]
            with patch.dict(os.environ,{self.rows[0]['credential_env']:os.environ[credentials[self.rows[0]['agent_id']]]}):
                # An equal-valued gateway alias must also fail, even with another ref.
                self.assertEqual(self.request(server,0)[0],403)
            req=Request('http://127.0.0.1:'+str(server.server_port)+'/v1/chat/completions',data=json.dumps({'model':MODEL,'messages':[{'role':'user','content':'PRIVATE-CONTEXT'}]}).encode(),headers={'Authorization':'Bearer '+os.environ[credentials[self.rows[0]['agent_id']]]})
            with self.assertLogs('project_bots.inference',level='INFO') as logs:
                with urlopen(req) as response:self.assertIn(b'PRIVATE-CONTEXT',response.read())
            self.assertNotIn('PRIVATE-CONTEXT',' '.join(logs.output))
            self.assertNotIn(legacy,' '.join(logs.output))
            self.assertIn('completed',' '.join(logs.output))
        finally:
            for ref in credentials.values():os.environ.pop(ref,None)

    def test_context_budget_rejects_before_dispatch(self):
        server=self.start()
        result=self.request(server,0,body={'model':MODEL,'messages':[{'role':'user','content':'x'*3000}]})
        self.assertEqual(result[0],400)
        self.assertEqual(self.calls,[])
