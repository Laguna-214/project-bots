"""Stage 3 native Ollama boundary; fake transport is not hardware proof."""
import unittest
from project_bots import models


class ModelsTests(unittest.TestCase):
    def test_local_native_inventory_and_tool_capability(self):
        calls = []
        def request(method, path, data=None):
            calls.append((method, path, data))
            return {'capabilities': ['completion', 'tools']} if path == '/api/show' else {'models': []}
        manager = models.ModelManager(request)
        self.assertEqual(manager.tags(), {'models': []})
        self.assertEqual(manager.loaded(), {'models': []})
        self.assertIn('tools', manager.show('qwen3:4b')['capabilities'])
        self.assertEqual(calls, [('GET', '/api/tags', None), ('GET', '/api/ps', None), ('POST', '/api/show', {'model': 'qwen3:4b'})])
        for name in ('qwen3:cloud', 'https://example.com/model', '../bad', '', 'model-cloud'):
            with self.assertRaises(ValueError): manager.show(name)


    def test_pull_delete_are_explicit_and_profile_is_bounded(self):
        calls = []
        manager = models.ModelManager(lambda *args: calls.append(args) or {})
        manager.pull('qwen3:1.7b')
        manager.delete('qwen3:1.7b')
        self.assertEqual(calls, [('POST', '/api/pull', {'model': 'qwen3:1.7b', 'stream': False}), ('DELETE', '/api/delete', {'model': 'qwen3:1.7b'})])
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


    def test_native_client_refuses_remote_urls_and_uses_native_json(self):
        import json,threading
        from http.server import BaseHTTPRequestHandler,HTTPServer
        calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,format,*args):pass
            def do_POST(self):
                calls.append((self.path,json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(200);self.end_headers();self.wfile.write(b'{"capabilities":["tools"]}')
        s=HTTPServer(('127.0.0.1',0),Handler);t=threading.Thread(target=s.handle_request,daemon=True);t.start()
        try:
            c=models.NativeClient('http://127.0.0.1:'+str(s.server_port))
            self.assertEqual(c.request('POST','/api/show',{'model':'qwen3:1.7b'})['capabilities'],['tools'])
            self.assertEqual(calls,[('/api/show',{'model':'qwen3:1.7b'})])
            for endpoint in ('http://10.0.50.56:11434','https://ollama.com','http://127.0.0.1:11434/v1'):
                with self.assertRaises(ValueError):models.NativeClient(endpoint)
        finally:t.join(5);s.server_close()


if __name__ == '__main__': unittest.main()
