"""Stage 3 llama.cpp broker boundary; fake transport is not hardware proof."""
import unittest
from project_bots import models


class ModelsTests(unittest.TestCase):
    def test_native_broker_token_is_private_header_not_address(self):
        import os
        from unittest.mock import patch
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,*args):return b'{"models":[]}'
        with patch.dict(os.environ,{'TEST_NATIVE_BROKER':'secret-native-broker'}):
            client=models.NativeClient('http://127.0.0.1:21435',token_env='TEST_NATIVE_BROKER')
            with patch.object(client.opener,'open',return_value=Response()) as call:
                client.request('GET','/management/models')
                request=call.call_args.args[0]
                self.assertEqual(request.get_header('Authorization'),'Bearer secret-native-broker')
                self.assertNotIn('secret',request.full_url)

    def test_local_native_inventory_and_tool_capability(self):
        calls = []
        def request(method, path, data=None):
            calls.append((method, path, data))
            return {'capabilities': ['completion', 'tools']} if path == '/management/show' else {'models': []}
        manager = models.ModelManager(request)
        self.assertEqual(manager.tags(), {'models': []})
        self.assertEqual(manager.loaded(), {'models': []})
        self.assertIn('tools', manager.show('qwen3:4b')['capabilities'])
        self.assertEqual(calls, [('GET', '/management/models', None), ('GET', '/management/loaded', None), ('POST', '/management/show', {'model': 'qwen3:4b'})])
        for name in ('qwen3:cloud', 'https://example.com/model', '../bad', '', 'model-cloud'):
            with self.assertRaises(ValueError): manager.show(name)


    def test_pull_delete_are_explicit_and_profile_is_bounded(self):
        calls = []
        manager = models.ModelManager(lambda *args: calls.append(args) or {})
        manager.pull('qwen3:1.7b')
        manager.delete('qwen3:1.7b')
        self.assertEqual(calls, [('POST', '/management/download', {'model': 'qwen3:1.7b'}), ('DELETE', '/management/models', {'model': 'qwen3:1.7b'})])
        profile = {'model': 'qwen3:1.7b', 'context': 32768, 'temperature': 0.2, 'max_output': 256, 'memory_mib': 4096, 'priority': 10}
        self.assertEqual(models.model_profile(profile), profile)
        for key, value in [('context', 0), ('context', True), ('temperature', float('nan')), ('max_output', 40000), ('memory_mib', 0), ('priority', -1), ('model', 'qwen3:cloud')]:
            with self.assertRaises(ValueError): models.model_profile({**profile, key: value})
        with self.assertRaises(ValueError): models.model_profile({**profile, 'api_key': 'secret'})


    def test_admission_is_bounded_priority_fifo_and_conservative(self):
        import threading,time
        gate=models.Admission(memory_mib=8192, concurrency=1, queue_limit=2)
        entered=[]
        with gate.slot(8192,10):
            def work(priority):
                with gate.slot(8192,priority):entered.append(priority)
            a=threading.Thread(target=work,args=(50,));a.start()
            for _ in range(100):
                if gate.pending==1:break
                time.sleep(.005)
            b=threading.Thread(target=work,args=(1,));b.start()
            for _ in range(100):
                if gate.pending==2:break
                time.sleep(.005)
            with self.assertRaises(ValueError):
                with gate.slot(8192,0):pass
        a.join(5);b.join(5);self.assertEqual(entered,[1,50])
        with self.assertRaises(ValueError):
            with gate.slot(9000,0):pass


    def test_memory_budget_accounts_for_weights_kv_context_and_loaded_size(self):
        info={'general.architecture': 'qwen3', 'qwen3.block_count': 28, 'qwen3.attention.head_count_kv': 8, 'qwen3.attention.key_length': 128, 'qwen3.attention.value_length': 128}
        low=models.memory_required_mib(info, 1359293444, 2048)
        high=models.memory_required_mib(info, 1359293444, 32768)
        self.assertGreater(high, low)
        self.assertGreater(high, 5120)
        self.assertLess(high, 8192)
        self.assertGreater(models.memory_required_mib(info, 1359293444, 32768, loaded_bytes=8*1024**3), 8192)
        with self.assertRaises(ValueError): models.memory_required_mib({}, 1359293444, 32768)
        with self.assertRaises(ValueError): models.memory_required_mib({**info, 'qwen3.block_count': True}, 1359293444, 32768)

    def test_platform_unload_requires_confirmation_and_retains_failed_mutation(self):
        import os
        from unittest.mock import patch
        from project_bots.compute import ComputeUnavailable
        from project_bots.service import PlatformService
        from project_bots.repository import SQLiteRepository
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            repo = SQLiteRepository(Path(directory)/'private'/'p.db')
            service = PlatformService(repo)
            with patch.dict(os.environ, {'PROJECT_BOTS_LLAMA_ENDPOINT': 'http://127.0.0.1:21434'}):
                with self.assertRaises(ValueError): service.model_request('unload', {'model': 'qwen3:1.7b'})
                with patch.object(models.NativeClient, 'request', return_value={'done': True}):
                    self.assertEqual(service.model_request('unload', {'model': 'qwen3:1.7b', 'confirmation': 'unload:qwen3:1.7b'}), {'done': True})
                with patch.object(models.NativeClient, 'request', side_effect=TimeoutError('remote may still be pulling')):
                    with self.assertRaises(ComputeUnavailable): service.model_request('pull', {'model': 'qwen3:4b', 'confirmation': 'pull:qwen3:4b'})
                with repo.transaction() as db:
                    self.assertEqual([row[0] for row in db.execute('SELECT state FROM inference_admission')], ['uncertain'])

    def test_unload_uses_llamacpp_router_without_generation(self):
        calls = []
        manager = models.ModelManager(lambda *args: calls.append(args) or {'done': True})
        self.assertEqual(manager.unload('qwen3:1.7b'), {'done': True})
        self.assertEqual(calls, [('POST', '/models/unload', {'model': 'qwen3:1.7b'})])

    def test_native_client_refuses_remote_urls_and_uses_native_json(self):
        import json,threading
        from http.server import BaseHTTPRequestHandler,HTTPServer
        calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,format,*args):pass
            def do_POST(self):
                calls.append((self.path,json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(200);self.end_headers();self.wfile.write(b'{"capabilities":["tools"]}')
        s=HTTPServer(('127.0.0.1',0),Handler);t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
        try:
            c=models.NativeClient('http://127.0.0.1:'+str(s.server_port))
            self.assertEqual(c.request('POST','/management/show',{'model':'qwen3:1.7b'})['capabilities'],['tools'])
            models.ModelManager(c.request).unload('qwen3:1.7b')
            self.assertEqual(calls,[('/management/show',{'model':'qwen3:1.7b'}), ('/models/unload', {'model': 'qwen3:1.7b'})])
            for endpoint in ('http://10.0.50.56:11434','https://ollama.com','http://127.0.0.1:11434/v1'):
                with self.assertRaises(ValueError):models.NativeClient(endpoint)
        finally:s.shutdown();t.join(5);s.server_close()


if __name__ == '__main__': unittest.main()
