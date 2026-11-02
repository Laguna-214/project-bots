"""llama.cpp migration contracts, not a GPU acceptance substitute."""
import unittest
from project_bots.models import ModelManager
from project_bots.workers import worker_config

PROFILE={'model':'qwen3-1_7b','context':32768,'temperature':0.2,'max_output':256,'memory_mib':8192,'priority':10}

class LlamaMigrationTests(unittest.TestCase):
    def test_already_unloaded_router_model_does_not_send_another_mutation(self):
        from project_bots import models
        calls=[]
        def request(method,path,data=None):
            calls.append((method,path))
            return {'data':[{'id':'qwen3-1_7b','status':{'value':'unloaded'}}]}
        self.assertEqual(models.router_transition(request,'qwen3-1_7b','unload'),{'success':True,'already':True})
        self.assertEqual(calls,[('GET','/models')])

    def test_router_unload_is_observed_before_admission_can_release(self):
        from project_bots import models
        calls=[];states=iter(['loaded','loaded','unloaded'])
        def request(method,path,data=None):
            calls.append((method,path))
            if path=='/models':return {'data':[{'id':'qwen3-1_7b','status':{'value':next(states)}}]}
            return {'success':True}
        result=models.router_transition(request,'qwen3-1_7b','unload',poll_interval=0)
        self.assertEqual(result,{'success':True})
        self.assertEqual(calls,[('GET','/models'),('POST','/models/unload'),('GET','/models'),('GET','/models')])

    def test_pinned_download_is_admitted_before_store_and_refresh(self):
        import tempfile,os,json,threading,urllib.request
        from pathlib import Path
        from http.server import ThreadingHTTPServer
        from unittest.mock import patch
        from project_bots.llama_proxy import make_handler
        from project_bots.repository import SQLiteRepository
        from project_bots.models import DurableAdmission
        with tempfile.TemporaryDirectory() as t:
            repo=SQLiteRepository(Path(t)/'private/state.db');observed=[]
            class Store:
                config={'catalog':{'tiny':{'size':100}}}
                def apply(self,name,action):
                    with repo.transaction() as db:
                        observed.append(db.execute("SELECT count(*) FROM inference_admission WHERE state='active'").fetchone()[0])
                    return {'sha256':'a'*64,'name':name}
            with patch.dict(os.environ,{'TEST_ADMIN':'admin-token'}),patch('project_bots.models.NativeClient.request',return_value={'data':[]}):
                server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(repo,DurableAdmission(repo),'http://127.0.0.1:21434','TEST_ADMIN',store=Store()))
                threading.Thread(target=server.serve_forever,daemon=True).start()
                try:
                    req=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+'/management/download',data=b'{"model":"tiny"}',headers={'Authorization':'Bearer admin-token','Content-Type':'application/json'})
                    with urllib.request.urlopen(req) as response:self.assertEqual(json.load(response)['name'],'tiny')
                    self.assertEqual(observed,[1])
                    import time
                    for _ in range(100):
                        with repo.transaction() as db:count=db.execute('SELECT count(*) FROM inference_admission').fetchone()[0]
                        if not count:break
                        time.sleep(.01)
                    self.assertEqual(count,0)
                finally:server.shutdown();server.server_close()

    def test_worker_uses_openai_completions_without_ollama_options(self):
        config=worker_config(PROFILE)
        self.assertEqual(set(config['models']['providers']),{'llamacpp'})
        provider=config['models']['providers']['llamacpp']
        self.assertEqual(provider['api'],'openai-completions')
        self.assertEqual(provider['baseUrl'],'http://127.0.0.1:11434/v1')
        self.assertNotIn('num_ctx',str(config))
        self.assertEqual(config['agents']['defaults']['model']['primary'],'llamacpp/qwen3-1_7b')

    def test_model_manager_uses_explicit_broker_management_not_ollama_native(self):
        calls=[]
        manager=ModelManager(lambda *args: calls.append(args) or {'models':[]})
        manager.tags();manager.loaded();manager.show('qwen3-1_7b');manager.unload('qwen3-1_7b');manager.load('qwen3-1_7b')
        self.assertEqual(calls,[('GET','/management/models',None),('GET','/management/loaded',None),('POST','/management/show',{'model':'qwen3-1_7b'}),('POST','/models/unload',{'model':'qwen3-1_7b'}),('POST','/models/load',{'model':'qwen3-1_7b'})])
