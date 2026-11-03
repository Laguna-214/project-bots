"""Application contracts with a real local HTTP FIXTURE, not real-model acceptance."""
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from project_bots.repository import SQLiteRepository
from project_bots.service import PlatformService
from project_bots.chat import ChatService
from security_fixtures import fixture_security


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = fixture_security(SQLiteRepository(Path(self.temp.name)/'private/db'))
        self.chat = ChatService(self.repo)
        self.platform = PlatformService(self.repo)
        self.agents = [self.platform.create_agent({'name':str(i),'role':'Researcher', 'config':{'credential_env':'REPLY_INFERENCE_'+str(i)}})['id'] for i in range(2)]
        self.calls = []
        self.hook = None
        self.response_message = None
        owner = self
        class Fixture(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                raw=json.dumps({'data':[{'id':'shared-model','status':{'value':'loaded'}}]}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.calls.append((self.path, self.headers['Authorization'], body))
                if owner.hook and self.path == '/v1/chat/completions': owner.hook()
                raw=json.dumps({'choices':[{'message':owner.response_message or {'content':'Public fixture answer', 'reasoning_content':'PRIVATE REASONING'}}]}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.env=patch.dict(os.environ, {'FIXTURE_ADMIN':'a'*48,'FIXTURE_BACKEND':'b'*48, **{'REPLY_INFERENCE_'+str(i):'inference-'+str(i)+'x'*40 for i in range(4)}, **{'REPLY_CHAT_'+str(i):'chat-'+str(i)+'y'*40 for i in range(4)}})
        self.env.start();self.addCleanup(self.env.stop)
        for i,aid in enumerate(self.agents):
            self.chat.configure_identity(aid, {'credential_env':'REPLY_CHAT_'+str(i),'enabled':True})
            self.repo.save_worker({'agent_id':aid,'vm_id':str(uuid.uuid4()),'credential_env':'GATEWAY_'+str(i),'profile':{'model':'shared-model','context':8192,'max_output':128}})

    def service(self):
        from project_bots.conversations import ConversationService
        return ConversationService(self.repo)

    def configure(self, aid, **updates):
        data={'enabled':True,'system_instructions':'PRIVATE SYSTEM '+aid,'memory':'PRIVATE MEMORY '+aid,'tools':[], 'max_replies':8}
        data.update(updates)
        return self.service().configure(aid, data)

    def runner(self):
        from project_bots.chat_runner import ChatRunner
        return ChatRunner(self.repo, 'http://127.0.0.1:'+str(self.server.server_port))

    def test_job_api_keeps_new_and_unresolved_jobs_visible_after_large_history(self):
        from project_bots.platform_web import make_platform_handler
        from urllib.request import Request, urlopen
        self.configure(self.agents[0])
        c = self.chat.create({'title':'Long history','kind':'individual','agent_ids':[self.agents[0]]})
        self.chat.send(c['id'], {'client_id':str(uuid.uuid4()),'content':'Trigger'})
        with self.repo.transaction() as db:
            db.execute('DELETE FROM conversation_jobs')
            # Each row references a real message and has a unique agent/trigger pair.
            def add(status, stamp):
                mid = db.execute('INSERT INTO chat_messages(chat_id,sender,client_id,content,created_at) VALUES (?,?,?,?,?)',
                    (c['id'],'admin',str(uuid.uuid4()),'Historical turn',stamp)).lastrowid
                jid = str(uuid.uuid4())
                db.execute('INSERT INTO conversation_jobs VALUES (?,?,?,?,?,?,?,?)',
                    (jid,c['id'],self.agents[0],mid,status,'fixture',stamp,stamp))
                return jid
            oldest_uncertain = add('uncertain',0)
            for i in range(501): add('completed',i+1)
            ids = {status:add(status,502+i) for i,status in enumerate(('queued','running','uncertain','cancelling'))}
        server = ThreadingHTTPServer(('127.0.0.1',0), make_platform_handler('12345678',self.platform))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        def request(path, data=None):
            req = Request('http://127.0.0.1:'+str(server.server_port)+path,
                data=None if data is None else json.dumps(data).encode(),
                headers={'Authorization':'Bearer '+'z'*48,'Content-Type':'application/json'})
            with urlopen(req,timeout=5) as response: return json.load(response)
        with patch.dict(os.environ, {'PROJECT_BOTS_API_TOKEN':'z'*48}):
            for suffix in ('','?chat_id='+c['id']):
                jobs = request('/api/conversations/jobs'+suffix)
                self.assertTrue(set(ids.values()).issubset({j['id'] for j in jobs}))
                self.assertIn(oldest_uncertain,{j['id'] for j in jobs})
                self.assertEqual([j['created_at'] for j in jobs],sorted(j['created_at'] for j in jobs))
            for status, expected in (('queued','cancelled'),('running','cancelling'),('uncertain','uncertain'),('cancelling','cancelling')):
                result = request('/api/conversations/jobs/'+ids[status]+'/cancel',{})
                self.assertEqual(result['status'],expected)
            visible = {j['id']:j['status'] for j in request('/api/conversations/jobs')}
            self.assertEqual(visible[ids['queued']],'cancelled')
            self.assertEqual(visible[ids['running']],'cancelling')
            self.assertEqual(visible[ids['uncertain']],'uncertain')

    def test_reply_budget_recovers_after_rolling_window_not_lifetime_lockout(self):
        import time
        self.configure(self.agents[0], max_replies=1)
        chat = self.chat.create({'title':'Long running', 'kind':'individual', 'agent_ids':[self.agents[0]]})
        self.chat.send(chat['id'], {'client_id':str(uuid.uuid4()), 'content':'First turn'})
        self.chat.send(chat['id'], {'client_id':str(uuid.uuid4()), 'content':'Rate-limited turn'})
        self.assertEqual(len(self.service().jobs()), 1)
        future = time.time() + 61
        with patch('project_bots.conversations.time.time', return_value=future):
            self.chat.send(chat['id'], {'client_id':str(uuid.uuid4()), 'content':'Later legitimate turn'})
        self.assertEqual(len(self.service().jobs()), 2, 'Conversations must not permanently exhaust a lifetime reply cap')

    def test_group_keeps_public_agent_role_without_private_memory(self):
        self.configure(self.agents[0])
        chat = self.chat.create({'title':'Public team', 'kind':'group', 'agent_ids':[self.agents[0]]})
        self.chat.send(chat['id'], {'client_id':str(uuid.uuid4()), 'content':'Describe your assigned role'})
        self.runner().run_once()
        system = self.calls[0][2]['messages'][0]['content']
        self.assertIn('Researcher', system)
        self.assertNotIn('PRIVATE SYSTEM', system)
        self.assertNotIn('PRIVATE MEMORY', system)

    def test_later_group_reply_sees_authorized_peer_answer_in_same_turn(self):
        for aid in self.agents:
            self.configure(aid)
        chat = self.chat.create({'title':'Collaborative team', 'kind':'group', 'agent_ids':self.agents})
        self.chat.send(chat['id'], {'client_id':str(uuid.uuid4()), 'content':'Collaborate on this task'})
        self.assertTrue(self.runner().run_once())
        self.assertTrue(self.runner().run_once())
        self.assertEqual(len(self.calls), 2)
        later_context = json.dumps(self.calls[1][2]['messages'])
        self.assertIn('Public fixture answer', later_context, 'Second group participant must see the completed shared peer reply')
        self.assertNotIn('PRIVATE MEMORY', later_context)
        self.assertNotIn('PRIVATE SYSTEM', later_context)
        self.assertEqual(len(self.service().jobs()), 2, 'Peer replies must not create recursive jobs')

    def test_explicit_enrollment_durable_individual_reply_and_no_reasoning(self):
        c=self.chat.create({'title':'Private','kind':'individual','agent_ids':[self.agents[0]]})
        self.chat.send(c['id'], {'client_id':str(uuid.uuid4()),'content':'Before enrollment'})
        self.assertEqual(self.service().jobs(), [])
        self.configure(self.agents[0])
        payload={'client_id':str(uuid.uuid4()),'content':'Explain public result'}
        self.chat.send(c['id'],payload); self.chat.send(c['id'],payload)
        self.assertEqual(len(self.service().jobs()),1)
        self.assertTrue(self.runner().run_once())
        history=ChatService(SQLiteRepository(self.repo.path)).history(c['id'])['messages']
        self.assertEqual(history[-1]['sender'], self.agents[0])
        self.assertEqual(history[-1]['content'],'Public fixture answer')
        self.assertNotIn('PRIVATE REASONING',str(history))
        self.assertIn('PRIVATE MEMORY '+self.agents[0],str(self.calls))
        self.assertNotIn(self.agents[1],str(self.calls))
        self.assertFalse(self.runner().run_once())
        self.assertEqual(self.service().jobs()[0]['status'],'completed')

    def test_membership_revoke_and_readd_during_reply_cannot_publish_old_context(self):
        for aid in self.agents: self.configure(aid)
        c=self.chat.create({'title':'Group','kind':'group','agent_ids':self.agents})
        self.chat.send(c['id'],{'client_id':str(uuid.uuid4()),'content':'Shared question'})
        def membership_change():
            self.chat.set_members(c['id'],{'agent_ids':[self.agents[1]]})
            self.chat.set_members(c['id'],{'agent_ids':self.agents})
        self.hook=membership_change
        self.runner().run_once()
        self.assertEqual(len(self.chat.history(c['id'])['messages']),1)

    def test_admin_routes_and_agent_admin_denial(self):
        from project_bots.platform_web import chat_request
        aid=self.agents[0]
        self.configure(aid)
        result,status=chat_request(self.repo,'GET','/api/agents/'+aid+'/conversation',None,'admin')
        self.assertEqual(status,200);self.assertEqual(result['agent_id'],aid)
        for path in ('/api/agents/'+aid+'/conversation','/api/conversations/jobs'):
            with self.assertRaises(PermissionError): chat_request(self.repo,'GET',path,None,aid)
        self.assertEqual(chat_request(self.repo,'GET','/api/conversations/jobs',None,'admin'),([],200))

    def test_active_cancel_preserves_uncertainty_and_blocks_later_dispatch(self):
        self.configure(self.agents[0])
        c=self.chat.create({'title':'Private','kind':'individual','agent_ids':[self.agents[0]]})
        for _ in range(2): self.chat.send(c['id'],{'client_id':str(uuid.uuid4()),'content':'Question'})
        job=self.service().jobs()[0]
        self.hook=lambda:self.service().cancel(job['id'])
        self.runner().run_once()
        self.assertEqual(self.service().jobs()[0]['status'],'uncertain')
        self.assertFalse(self.runner().run_once())
        self.assertEqual(len(self.chat.history(c['id'])['messages']),2)

    def test_existing_shared_broker_four_uuid_agents_one_fixture_backend(self):
        from project_bots.llama_proxy import make_handler
        from project_bots.models import DurableAdmission
        from project_bots.chat_runner import ChatRunner
        import concurrent.futures
        for i in range(2,4):
            aid=self.platform.create_agent({'name':str(i),'role':'Researcher','config':{'credential_env':'REPLY_INFERENCE_'+str(i)}})['id']
            self.agents.append(aid)
            self.repo.save_worker({'agent_id':aid,'vm_id':str(uuid.uuid4()),'credential_env':'GATEWAY_'+str(i),'profile':{'model':'shared-model','context':8192,'max_output':128,'memory_mib':2048,'temperature':0,'priority':10}})
        for i,aid in enumerate(self.agents):
            os.environ['REPLY_INFERENCE_'+str(i)]='inference-'+str(i)+'x'*40
            os.environ['REPLY_CHAT_'+str(i)]='chat-'+str(i)+'y'*40
            self.chat.configure_identity(aid,{'credential_env':'REPLY_CHAT_'+str(i),'enabled':True})
            worker=self.repo.worker(aid)
            worker['profile'].update(memory_mib=2048,temperature=0,priority=10)
            self.repo.save_worker(worker)
            self.configure(aid)
        entry={'size':1024,'context':8192,'sha256':'a'*64,'capabilities':['tools'],'model_info':{'general.architecture':'test','test.block_count':1,'test.attention.head_count_kv':1,'test.attention.key_length':1,'test.attention.value_length':1}}
        admission=DurableAdmission(SQLiteRepository(Path(self.temp.name)/'scheduler/db'),memory_mib=8192,concurrency=1,queue_limit=8)
        broker=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.repo,admission,'http://127.0.0.1:'+str(self.server.server_port),'FIXTURE_ADMIN',{'shared-model':entry},'FIXTURE_BACKEND',requester_credentials={aid:'REPLY_INFERENCE_'+str(i) for i,aid in enumerate(self.agents)}))
        threading.Thread(target=broker.serve_forever,daemon=True).start()
        self.addCleanup(broker.server_close);self.addCleanup(broker.shutdown)
        with patch.dict(os.environ,{'FIXTURE_ADMIN':'a'*48,'FIXTURE_BACKEND':'b'*48}):
            group=self.chat.create({'title':'Four','kind':'group','agent_ids':self.agents})
            self.chat.send(group['id'],{'client_id':str(uuid.uuid4()),'content':'Share approved public findings'})
            def run(_): return ChatRunner(self.repo,'http://127.0.0.1:'+str(broker.server_port)).run_once()
            with concurrent.futures.ThreadPoolExecutor(4) as pool: self.assertTrue(all(pool.map(run,range(4))))
        self.assertEqual(len(self.calls),4)
        self.assertTrue(all(j['status']=='completed' for j in self.service().jobs()),self.service().jobs())
        self.assertEqual({m['sender'] for m in self.chat.history(group['id'])['messages']},{'admin',*self.agents})
        self.assertEqual({call[1] for call in self.calls},{'Bearer '+'b'*48})
        self.assertTrue(all(call[2]['model']=='shared-model' for call in self.calls))

    def test_chat_identity_cannot_alias_any_inference_identity(self):
        from project_bots.service import ConflictError
        with patch.dict(os.environ,{'ALIASED_INFERENCE':os.environ['REPLY_INFERENCE_0']}):
            for ref in ('REPLY_INFERENCE_0','ALIASED_INFERENCE'):
                with self.assertRaises(ConflictError):
                    self.chat.configure_identity(self.agents[1],{'credential_env':ref,'enabled':True})

    def test_identity_rotate_reenable_during_reply_cannot_publish(self):
        aid=self.agents[0]
        self.configure(aid)
        c=self.chat.create({'title':'Private','kind':'individual','agent_ids':[aid]})
        self.chat.send(c['id'],{'client_id':str(uuid.uuid4()),'content':'Question'})
        def rotate():
            self.chat.configure_identity(aid,{'credential_env':'REPLY_CHAT_0','enabled':False})
            self.chat.configure_identity(aid,{'credential_env':'REPLY_CHAT_0','enabled':True})
        self.hook=rotate
        self.runner().run_once()
        self.assertEqual(len(self.chat.history(c['id'])['messages']),1)

    def test_http_enrollment_send_runner_readback_and_worker_admin_denial(self):
        from project_bots.platform_web import make_platform_handler
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        server=ThreadingHTTPServer(('127.0.0.1',0),make_platform_handler('12345678',self.platform))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        def request(path,data=None,token='z'*48):
            req=Request('http://127.0.0.1:'+str(server.server_port)+path,data=json.dumps(data).encode() if data is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            with urlopen(req,timeout=5) as response:return json.load(response)
        with patch.dict(os.environ,{'PROJECT_BOTS_API_TOKEN':'z'*48}):
            aid=self.agents[0]
            enrollment={'enabled':True,'system_instructions':'Private assistant','memory':'Private fixture memory','tools':[],'max_replies':4}
            self.assertTrue(request('/api/agents/'+aid+'/conversation',enrollment)['enabled'])
            c=request('/api/chats',{'title':'HTTP','kind':'individual','agent_ids':[aid]})
            request('/api/chats/'+c['id']+'/messages',{'client_id':str(uuid.uuid4()),'content':'Public request'})
            self.runner().run_once()
            self.assertEqual(request('/api/chats/'+c['id']+'/messages')['messages'][-1]['sender'],aid)
            jobs=request('/api/conversations/jobs?chat_id='+c['id'])
            self.assertEqual(jobs[0]['status'],'completed')
            with self.assertRaises(HTTPError) as denied:
                request('/api/agents/'+aid+'/conversation',token=os.environ['REPLY_CHAT_0'])
            self.assertEqual(denied.exception.code,403);denied.exception.close()

    def test_active_revocation_requests_broker_cancellation_without_claiming_stop(self):
        import time
        aid=self.agents[0]
        self.configure(aid)
        c=self.chat.create({'title':'Private','kind':'individual','agent_ids':[aid]})
        self.chat.send(c['id'],{'client_id':str(uuid.uuid4()),'content':'Question'})
        entered=threading.Event();release=threading.Event()
        def hold(): entered.set();release.wait(5)
        self.hook=hold
        runner=threading.Thread(target=self.runner().run_once)
        runner.start()
        try:
            self.assertTrue(entered.wait(3))
            self.chat.configure_identity(aid,{'credential_env':'REPLY_CHAT_0','enabled':False})
            deadline=time.monotonic()+3
            while not any(call[0]=='/v1/requests/cancel' for call in self.calls) and time.monotonic()<deadline: time.sleep(.01)
            cancellations=[call for call in self.calls if call[0]=='/v1/requests/cancel']
            self.assertEqual(len(cancellations),1)
            self.assertEqual(cancellations[0][2]['request_id'],self.service().jobs()[0]['id'])
        finally:
            release.set();runner.join(6)
        self.assertFalse(runner.is_alive())
        self.assertEqual(self.service().jobs()[0]['status'],'uncertain')
        self.assertEqual(len(self.chat.history(c['id'])['messages']),1)

    def test_standalone_runner_once_executes_durable_job(self):
        import subprocess
        import sys
        self.configure(self.agents[0])
        c=self.chat.create({'title':'CLI','kind':'individual','agent_ids':[self.agents[0]]})
        self.chat.send(c['id'],{'client_id':str(uuid.uuid4()),'content':'Question'})
        result=subprocess.run([sys.executable,'-m','project_bots.chat_runner','--db',str(self.repo.path),'--broker','http://127.0.0.1:'+str(self.server.server_port),'--once'],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.service().jobs()[0]['status'],'completed')

    def test_group_context_excludes_all_private_memory_instructions_and_histories(self):
        for aid in self.agents:
            self.configure(aid)
            private=self.chat.create({'title':'Private','kind':'individual','agent_ids':[aid]})
            self.chat.send(private['id'],{'client_id':str(uuid.uuid4()),'content':'SECRET HISTORY '+aid})
            self.runner().run_once()
        self.calls.clear()
        group=self.chat.create({'title':'Collaboration','kind':'group','agent_ids':self.agents})
        self.chat.send(group['id'],{'client_id':str(uuid.uuid4()),'content':'Work together on public plan'})
        while self.runner().run_once(): pass
        self.assertEqual(len(self.calls),2)
        self.assertNotIn('PRIVATE',str(self.calls)); self.assertNotIn('SECRET HISTORY',str(self.calls))
        self.assertTrue(all(c[2]['tools']==[] and c[2]['tool_choice']=='none' for c in self.calls))
        self.assertEqual({m['sender'] for m in self.chat.history(group['id'])['messages']}, {'admin',*self.agents})
        self.assertEqual(len(self.service().jobs(group['id'])),2)
        self.assertEqual(self.chat.events()['events'][0]['behavior'],'chat_identity_changed')

    def test_identity_revocation_during_reply_blocks_publication(self):
        self.configure(self.agents[0])
        c=self.chat.create({'title':'Private','kind':'individual','agent_ids':[self.agents[0]]})
        self.chat.send(c['id'],{'client_id':str(uuid.uuid4()),'content':'Reply please'})
        self.hook=lambda:self.chat.configure_identity(self.agents[0],{'credential_env':'REPLY_CHAT_0','enabled':False})
        self.runner().run_once()
        self.assertEqual(len(self.chat.history(c['id'])['messages']),1)
        self.assertFalse(self.runner().run_once())

    def test_empty_tool_allowlist_is_enforced_by_backend(self):
        with self.assertRaises(ValueError): self.configure(self.agents[0],tools=['shell'])
        self.assertEqual(self.service().jobs(),[])

    def test_uncertain_restart_never_replays_and_blocks_agent(self):
        self.configure(self.agents[0])
        c=self.chat.create({'title':'Private','kind':'individual','agent_ids':[self.agents[0]]})
        for _ in range(2): self.chat.send(c['id'],{'client_id':str(uuid.uuid4()),'content':'Question'})
        first=self.service().jobs()[0]
        with self.repo.transaction() as db:
            db.execute("UPDATE conversation_jobs SET status='running' WHERE id=?",(first['id'],))
            db.execute("UPDATE conversation_jobs SET status='cancelling' WHERE id<>?",(first['id'],))
        self.assertEqual(self.runner().recover(),2)
        self.assertFalse(self.runner().run_once())
        self.assertEqual(self.calls,[])

    def test_budget_cancel_and_missing_health_fail_closed(self):
        self.configure(self.agents[0],max_replies=2)
        c=self.chat.create({'title':'Private','kind':'individual','agent_ids':[self.agents[0]]})
        for _ in range(4): self.chat.send(c['id'],{'client_id':str(uuid.uuid4()),'content':'Question'})
        jobs=self.service().jobs();self.assertEqual(len(jobs),2)
        self.service().cancel(jobs[0]['id'])
        with self.repo.transaction() as db: db.execute("DELETE FROM security_state WHERE key='coverage:network'")
        self.assertTrue(self.runner().run_once())
        self.assertEqual(self.calls,[])
        self.assertEqual([j['status'] for j in self.service().jobs()],['cancelled','blocked'])

    def test_tool_calls_and_tagged_reasoning_are_not_persisted(self):
        self.configure(self.agents[0])
        c=self.chat.create({'title':'Private','kind':'individual','agent_ids':[self.agents[0]]})
        self.chat.send(c['id'],{'client_id':str(uuid.uuid4()),'content':'Question'})
        self.response_message={'content':'<think>secret</think>Answer'}
        self.runner().run_once()
        self.assertEqual(len(self.chat.history(c['id'])['messages']),1)
        self.assertEqual(self.service().jobs()[0]['status'],'uncertain')
