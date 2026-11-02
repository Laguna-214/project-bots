import unittest,tempfile,threading,json,os,uuid,urllib.request,urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from unittest.mock import patch
from project_bots.repository import SQLiteRepository
from project_bots.service import PlatformService
from project_bots.models import DurableAdmission

class ProxyTests(unittest.TestCase):
    def test_authenticated_llamacpp_worker_stream_uses_durable_gate_and_rejects_wrong_model(self):
        from project_bots.inference_proxy import make_handler
        with tempfile.TemporaryDirectory() as t:
            repo=SQLiteRepository(Path(t)/'workers'/'state.db');s=PlatformService(repo)
            a=s.create_agent({'name':'test','role':'Researcher'})
            profile={'model':'qwen3:1.7b','context':32768,'max_output':256,'temperature':0,'memory_mib':8192,'priority':10}
            s.register_worker(a['id'],{'vm_id':str(uuid.uuid4()),'endpoint':'http://127.0.0.1:19889','credential_env':'TEST_PROXY_WORKER','profile':profile})
            gate_repo=SQLiteRepository(Path(t)/'gate'/'state.db');gate=DurableAdmission(gate_repo)
            calls=[]
            class Upstream(BaseHTTPRequestHandler):
                def log_message(self,*a):pass
                def do_POST(self):
                    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    if self.path=='/v1/chat/completions':
                        with gate_repo.transaction() as db:
                            active=db.execute("SELECT count(*) FROM inference_admission WHERE state='active'").fetchone()[0]
                        calls.append((body,active,self.headers.get('Authorization')))
                        raw=b'{"message":{"content":"hello"},"done":true}\n'
                    else:raw=json.dumps({'capabilities':['tools'],'model_info':{'general.architecture':'qwen3','qwen3.block_count':28,'qwen3.attention.head_count_kv':8,'qwen3.attention.key_length':128,'qwen3.attention.value_length':128}}).encode()
                    self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
                def do_GET(self):
                    raw=json.dumps({'data':[{'id':'qwen3:1.7b','status':{'value':'loaded'},'meta':{'n_ctx':32768},'memory':{'effective':{'devices':[]}}}]}).encode()
                    self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            upstream=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
            threading.Thread(target=upstream.serve_forever,daemon=True).start()
            token='test-proxy-token-'+('0123456789abcdef'*3)
            with patch.dict(os.environ,{'TEST_PROXY_WORKER':token}):
                server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(repo,gate,'http://127.0.0.1:'+str(upstream.server_port),'ADMIN_PROXY_TOKEN', registry={'qwen3:1.7b':{'size':1359293444,'context':32768,'sha256':'a'*64,'capabilities':['tools'],'model_info':{'general.architecture':'qwen3','qwen3.block_count':28,'qwen3.attention.head_count_kv':8,'qwen3.attention.key_length':128,'qwen3.attention.value_length':128}}}))
                threading.Thread(target=server.serve_forever,daemon=True).start()
                def request(model,auth=token):
                    return urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+'/v1/chat/completions',data=json.dumps({'model':model,'messages':[],'stream':True,'options':{'num_batch':1048576}}).encode(),headers={'Authorization':'Bearer '+auth,'Content-Type':'application/json'}))
                try:
                    with self.assertRaises(urllib.error.HTTPError) as e:request('qwen3:1.7b','wrong')
                    self.assertEqual(e.exception.code,403);e.exception.close()
                    with self.assertRaises(urllib.error.HTTPError) as e:request('other:local')
                    self.assertEqual(e.exception.code,400);e.exception.close()
                    with request('qwen3:1.7b') as response:self.assertIn(b'hello',response.read())
                    self.assertEqual(calls[0][1],1)
                    self.assertIsNone(calls[0][2])
                    self.assertNotIn('options',calls[0][0])
                    self.assertEqual(calls[0][0]['max_tokens'],256)
                    self.assertEqual(calls[0][0]['temperature'],0)
                    with gate_repo.transaction() as db:self.assertEqual(db.execute('SELECT count(*) FROM inference_admission').fetchone()[0],0)
                finally:server.shutdown();server.server_close()
            upstream.shutdown();upstream.server_close()
