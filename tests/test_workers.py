import tempfile,unittest,uuid
from pathlib import Path
from project_bots.repository import SQLiteRepository
from project_bots.service import PlatformService,ConflictError

PROFILE={'model':'qwen3:1.7b','context':32768,'max_output':256,'temperature':0.2,'memory_mib':4096,'priority':10}
class WorkerTests(unittest.TestCase):
    def test_explicit_dispatch_persists_result_and_never_repeats(self):
        with tempfile.TemporaryDirectory() as t:
            repo=SQLiteRepository(Path(t)/'private'/'p.db'); service=PlatformService(repo)
            a=service.create_agent({'name':'First','role':'ProjectWorker'})
            w=service.register_worker(a['id'], {'vm_id':str(uuid.uuid4()),'endpoint':'http://127.0.0.1:19889','credential_env':'WORKER_TOKEN','profile':PROFILE})
            self.assertEqual(w['status'],'configured')
            job=service.create_job({'title':'proof','input':'Reply checkpoint-ok','agent_id':a['id']})
            calls=[]
            def run(worker,job):
                calls.append(job['id']); return {'id':'resp_realshape','status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'checkpoint-ok'}]}]}
            with self.assertRaises(ValueError):service.dispatch_job(job['id'],{},run)
            result=service.dispatch_job(job['id'],{'confirmation':'dispatch:'+job['id']},run)
            self.assertEqual(result['status'],'succeeded'); self.assertEqual(result['result'],'checkpoint-ok')
            self.assertEqual(SQLiteRepository(repo.path).get_job(job['id'])['result'],'checkpoint-ok')
            with self.assertRaises(ConflictError):service.dispatch_job(job['id'],{'confirmation':'dispatch:'+job['id']},run)
            self.assertEqual(calls,[job['id']])
            self.assertEqual(repo.execution(job['id'])['response_id'],'resp_realshape')

    def test_failed_incomplete_and_uncertain_runs_are_not_success(self):
        with tempfile.TemporaryDirectory() as t:
            repo=SQLiteRepository(Path(t)/'private'/'p.db'); service=PlatformService(repo)
            a=service.create_agent({'name':'First','role':'ProjectWorker'})
            service.register_worker(a['id'], {'vm_id':str(uuid.uuid4()),'endpoint':'http://127.0.0.1:19889','credential_env':'WORKER_TOKEN','profile':PROFILE})
            for status in ('failed','incomplete'):
                j=service.create_job({'title':'failure','input':'test','agent_id':a['id']})
                r=service.dispatch_job(j['id'],{'confirmation':'dispatch:'+j['id']},lambda *_:{'status':status,'output':[]})
                self.assertEqual(r['status'],'failed')
            j=service.create_job({'title':'uncertain','input':'test','agent_id':a['id']})
            def timeout(*_):raise TimeoutError('secret must not escape')
            r=service.dispatch_job(j['id'],{'confirmation':'dispatch:'+j['id']},timeout)
            self.assertEqual(repo.execution(j['id'])['status'],'uncertain'); self.assertNotIn('secret',r['error'])
            with self.assertRaises(ConflictError): service.job_action(j['id'],'cancel',{})
            # A live execution cannot be manually completed or canceled under a false success claim.
            j2=service.create_job({'title':'queued','input':'test','agent_id':a['id']})
            with self.assertRaises(ConflictError):service.dispatch_job(j2['id'],{'confirmation':'dispatch:'+j2['id']},timeout)
            self.assertEqual(service.job_action(j2['id'],'cancel',{})['status'],'canceled')

    def test_running_receipt_blocks_legacy_mutations_after_restart(self):
        with tempfile.TemporaryDirectory() as t:
            repo=SQLiteRepository(Path(t)/'private'/'p.db'); service=PlatformService(repo)
            a=service.create_agent({'name':'First','role':'ProjectWorker'})
            w=service.register_worker(a['id'], {'vm_id':str(uuid.uuid4()),'endpoint':'http://127.0.0.1:19889','credential_env':'WORKER_TOKEN','profile':PROFILE})
            j=service.create_job({'title':'crash','input':'test','agent_id':a['id']})
            repo.begin_execution(j['id'],w)
            service=PlatformService(SQLiteRepository(repo.path))
            for action,data in [('cancel',{}),('complete',{'result':'fake'}),('fail',{'error':'fake'})]:
                with self.assertRaises(ConflictError): service.job_action(j['id'],action,data)

    def test_gateway_wire_contract_and_isolated_local_config(self):
        import os,json,threading
        from http.server import BaseHTTPRequestHandler,HTTPServer
        from project_bots.workers import gateway_run,worker_config
        observed={}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_POST(self):
                observed.update(path=self.path,authorization=self.headers.get('Authorization'),body=json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"status":"completed","output":[]}')
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.handle_request);thread.start()
        os.environ['TEST_WORKER_TOKEN']='test-gateway-token-'+('0123456789abcdef'*3)
        try:
            w={'endpoint':'http://127.0.0.1:'+str(server.server_port),'credential_env':'TEST_WORKER_TOKEN','profile':PROFILE}
            gateway_run(w,{'id':str(uuid.uuid4()),'input':'hello'})
            self.assertEqual(observed['path'],'/v1/responses')
            self.assertEqual(observed['authorization'],'Bearer '+os.environ['TEST_WORKER_TOKEN'])
            self.assertEqual(observed['body']['model'],'openclaw/default')
            self.assertEqual(observed['body']['max_output_tokens'],256)
            self.assertNotIn('previous_response_id',observed['body'])
            cfg=worker_config(PROFILE)
            self.assertEqual(cfg['gateway']['auth']['mode'],'token')
            self.assertTrue(cfg['gateway']['http']['endpoints']['responses']['enabled'])
            self.assertEqual(cfg['models']['providers']['ollama']['baseUrl'],'http://127.0.0.1:11434')
            self.assertEqual(cfg['agents']['defaults']['model']['fallbacks'],[])
            self.assertFalse(cfg['tools']['agentToAgent']['enabled'])
        finally:thread.join(5);server.server_close();os.environ.pop('TEST_WORKER_TOKEN')

    def test_platform_worker_routes_require_auth_and_explicit_dispatch(self):
        import os,json,threading,urllib.request,urllib.error
        from http.server import ThreadingHTTPServer
        from project_bots.platform_web import make_platform_handler
        with tempfile.TemporaryDirectory() as t:
            service=PlatformService(SQLiteRepository(Path(t)/'private'/'p.db'))
            a=service.create_agent({'name':'First','role':'ProjectWorker'})
            os.environ['PROJECT_BOTS_API_TOKEN']='platform-test-'+('0123456789abcdef'*3)
            server=ThreadingHTTPServer(('127.0.0.1',0),make_platform_handler('12345678',service));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def api(path,body=None,auth=True):
                r=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+os.environ['PROJECT_BOTS_API_TOKEN']} if auth else {})})
                with urllib.request.urlopen(r) as f:return json.load(f)
            try:
                route='/api/agents/'+a['id']+'/worker'
                with self.assertRaises(urllib.error.HTTPError) as c:api(route,auth=False)
                self.assertEqual(c.exception.code,403)
                c.exception.close()
                w=api(route,{'vm_id':str(uuid.uuid4()),'endpoint':'http://127.0.0.1:19889','credential_env':'WORKER_TOKEN','profile':PROFILE})
                self.assertEqual(api(route),w)
                j=service.create_job({'title':'test','input':'hi','agent_id':a['id']})
                with self.assertRaises(urllib.error.HTTPError) as c:api('/api/jobs/'+j['id']+'/dispatch',{'confirmation':'wrong'})
                self.assertEqual(c.exception.code,400)
                c.exception.close()
                self.assertEqual(service.get_job(j['id'])['status'],'queued')
                with self.assertRaises(urllib.error.HTTPError) as c:api('/api/models/pull',{'model':'qwen3:cloud','confirmation':'pull:qwen3:cloud'})
                self.assertEqual(c.exception.code,400)
                c.exception.close()
            finally:server.shutdown();server.server_close();thread.join(5);os.environ.pop('PROJECT_BOTS_API_TOKEN')

if __name__=='__main__':unittest.main()
