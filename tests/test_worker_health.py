"""Worker identity observations: fake Gateway/paths, never real host acceptance."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from project_bots.workers import worker_config
from project_bots import worker_health

PROFILE={'model':'qwen3:1.7b','context':32768,'max_output':256,'temperature':0,'memory_mib':8192,'priority':10}
TOKEN='identity-test-'+('0123456789abcdef'*3)

class IdentityTests(unittest.TestCase):
    def test_instance_identity_and_gateway_profile_are_observed_not_claimed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);vm_id=str(uuid.uuid4());boot_id=str(uuid.uuid4())
            (root/'instance').write_text(vm_id+'\n');(root/'boot').write_text(boot_id+'\n')
            config=worker_config(PROFILE);(root/'config').write_text(json.dumps(config))
            observed=worker_health.observe(root/'config',root/'instance',root/'boot',lambda: {'data':[{'id':'openclaw/default'}]})
            self.assertEqual(observed['vm_id'],vm_id);self.assertEqual(observed['boot_id'],boot_id)
            self.assertEqual(observed['model'],PROFILE['model']);self.assertEqual(observed['context'],32768)
            self.assertEqual(observed['temperature'],0);self.assertEqual(observed['max_output'],256)
            self.assertEqual(observed['status'],'healthy')
            self.assertNotIn('token',json.dumps(observed))
            config['models']['providers']['llamacpp']['baseUrl']='http://127.0.0.1:11434'
            (root/'config').write_text(json.dumps(config))
            with self.assertRaises(ValueError):worker_health.observe(root/'config',root/'instance',root/'boot',lambda: {})

    def test_identity_http_authentication_fixed_readonly_route_and_failure(self):
        calls=[]
        def observe():calls.append(1);return {'vm_id':str(uuid.uuid4()),'status':'healthy'}
        server=ThreadingHTTPServer(('127.0.0.1',0),worker_health.make_handler(TOKEN,observe))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base='http://127.0.0.1:'+str(server.server_port)
            for path,headers,status in [('/v1/health',{},403),('/v1/health',{'Authorization':'Bearer '+TOKEN,'Origin':base},403),('/v1/commands',{'Authorization':'Bearer '+TOKEN},404)]:
                with self.assertRaises(HTTPError) as caught:urlopen(Request(base+path,headers=headers))
                self.assertEqual(caught.exception.code,status);caught.exception.close()
            self.assertEqual(calls,[])
            with urlopen(Request(base+'/v1/health',headers={'Authorization':'Bearer '+TOKEN})) as response:
                self.assertEqual(json.load(response)['status'],'healthy')
            with urlopen(Request(base+'/v1/health',headers={'Authorization':'Bearer '+TOKEN,'Host':'127.0.0.1:19890'})) as response:
                self.assertEqual(json.load(response)['status'],'healthy')
            self.assertEqual(calls,[1,1])
        finally:server.shutdown();thread.join(5);server.server_close()

if __name__=='__main__':unittest.main()
