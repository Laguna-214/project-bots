#!/usr/bin/env python3
"""Actual Java transport → isolated actual Python platform, HTTPS and SQLite.
No production state, machine/model bridge, network trust bypass or mock API handlers.
"""
import base64, contextlib, http.server, json, os, pathlib, secrets, ssl, subprocess, sys, tempfile, threading, unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from project_bots.platform_web import make_platform_handler
from project_bots.repository import SQLiteRepository
from project_bots.service import PlatformService
TOOLS=pathlib.Path(os.environ.get('NATIVE_TOOLS_CACHE',str(pathlib.Path.home()/'.cache/project-bots/native-tools')))
JAVA=TOOLS/'jdk-17.0.17+10/bin/java'
class NativePlatform(unittest.TestCase):
 def test_https_pair_session_csrf_persistent_chat_and_security(self):
  with contextlib.ExitStack() as isolated:
   folder=isolated.enter_context(tempfile.TemporaryDirectory(prefix='android-api-',dir=os.environ.get('TMPDIR')))
   isolated.enter_context(patch.dict(os.environ,{'HOME':folder,'CODEX_HOME':str(pathlib.Path(folder)/'codex')}))
   home=pathlib.Path(folder);cert=home/'cert.pem';key=home/'key.pem';store=home/'trust.p12'
   subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost'],check=True,capture_output=True,timeout=15)
   subprocess.run([str(TOOLS/'jdk-17.0.17+10/bin/keytool'),'-importcert','-noprompt','-alias','fixture','-file',str(cert),'-keystore',str(store),'-storepass','fixture-password','-storetype','PKCS12'],check=True,capture_output=True,timeout=15)
   repository=SQLiteRepository(str(home/'private/db'));service=PlatformService(repository);code=''.join(secrets.choice('0123456789') for _ in range(8))
   server=http.server.ThreadingHTTPServer(('127.0.0.1',0),make_platform_handler(code,service));ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(cert,key);server.socket=ctx.wrap_socket(server.socket,server_side=True)
   thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin=f'https://localhost:{server.server_port}'
   def launch(trusted=True,endpoint=origin):
    command=[str(JAVA),'-Dsun.net.http.allowRestrictedHeaders=true']
    if trusted:command += ['-Djavax.net.ssl.trustStore='+str(store),'-Djavax.net.ssl.trustStorePassword=fixture-password']
    return subprocess.Popen(command+['-cp',str(TOOLS/'test-classes'),'app.projectbots.FixtureBridge',endpoint],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
   def request(process,method,path,data=None,token='',csrf=''):
    body=base64.b64encode(json.dumps(data).encode()).decode() if data is not None else ''
    process.stdin.write('\t'.join([method,path,body,token,csrf])+'\n');process.stdin.flush();line=process.stdout.readline().strip().split('\t',1)
    self.assertEqual(len(line),2,'bridge stopped unexpectedly')
    return (True,json.loads(base64.b64decode(line[1]))) if line[0]=='OK' else (False,line[1])
   @contextlib.contextmanager
   def bridge(**kwargs):
    p=launch(**kwargs)
    try:yield p
    finally:p.stdin.close();p.wait(timeout=5);p.stdout.close();p.stderr.close()
   try:
    with bridge(trusted=False) as p:
     ok,error=request(p,'GET','/api/session');self.assertFalse(ok);self.assertIn('SSLHandshake',error)
    # Trusted chain, wrong hostname still fatal; no hostname-verifier override.
    with bridge(endpoint=f'https://127.0.0.1:{server.server_port}') as p:
     ok,error=request(p,'GET','/api/session');self.assertFalse(ok);self.assertIn('SSLHandshake',error)
    with bridge() as p:
     self.assertFalse(request(p,'GET','/api/agents')[0])
     ok,pair=request(p,'POST','/api/pair',{'code':code});self.assertTrue(ok);token=pair['token'];self.assertGreaterEqual(len(token),32)
     self.assertFalse(request(p,'POST','/api/pair',{'code':code})[0])
     ok,session=request(p,'GET','/api/session',token=token);self.assertTrue(ok);csrf=session['csrf']
     self.assertFalse(request(p,'POST','/api/agents',{'name':'not-created','role':'research'},token=token)[0])
     def get(path):
      ok,result=request(p,'GET',path,token=token,csrf=csrf);self.assertTrue(ok,path);return result
     def post(path,data):
      ok,result=request(p,'POST',path,data,token,csrf);self.assertTrue(ok,path);return result
     agents=[post('/api/agents',{'name':name,'role':'research','config':{'model':'fixture-definition-only'}}) for name in ['Native A','Native B']]
     self.assertEqual(len(get('/api/agents')),2)
     individual=post('/api/chats',{'title':'Private fixture','kind':'individual','agent_ids':[agents[0]['id']]})
     group=post('/api/chats',{'title':'Group fixture','kind':'group','agent_ids':[a['id'] for a in agents]})
     import uuid
     client_id=str(uuid.uuid4());payload={'client_id':client_id,'content':'<script src="https://never-contact.invalid/payload.js">plain text</script>'}
     sent=post('/api/chats/'+individual['id']+'/messages',payload);again=post('/api/chats/'+individual['id']+'/messages',payload);self.assertEqual(sent['sequence'],again['sequence'])
     self.assertEqual(get('/api/chats/'+individual['id']+'/messages?after=0')['messages'][0]['content'],payload['content'])
     self.assertEqual(get('/api/chats/'+group['id']+'/messages?after=0')['messages'],[])
     post('/api/chats/'+group['id']+'/members',{'agent_ids':[agents[1]['id']]})
     listed=get('/api/chats');self.assertEqual(len(listed),2)
     self.assertEqual(next(c for c in listed if c['id']==group['id'])['agent_ids'],[agents[1]['id']])
     self.assertIsInstance(get('/api/jobs'),list);self.assertIn('incidents',get('/api/security/status'));self.assertIn('events',get('/api/security/events'));self.assertIn('approvals',get('/api/approvals'))
     # Human approval proposals are issued through the real scoped-authority service,
     # not invented successful UI data. No external authority or compute action runs.
     from project_bots.permissions import Permissions
     from project_bots.approvals import Approvals
     jobs=[post('/api/jobs',{'title':'Approval fixture','input':'No dispatch'}) for _ in range(2)]
     paths=['/api/jobs/'+job['id']+'/cancel' for job in jobs]
     issued=Permissions(repository).issue({'name':'isolated Android fixture','expires_in':600,'grants':[{'method':'POST','path':path} for path in paths]},True)
     principal=Permissions(repository).authenticate('Bearer '+issued['token'])
     proposal=Approvals(repository).request(principal,{'method':'POST','path':paths[0],'payload':{},'expires_in':300})
     post('/api/approvals/'+proposal['id']+'/approve',{})
     proposal2=Approvals(repository).request(principal,{'method':'POST','path':paths[1],'payload':{},'expires_in':300})
     post('/api/approvals/'+proposal2['id']+'/reject',{})
     self.assertEqual({v['status'] for v in get('/api/approvals')['approvals']},{'approved','rejected'})
     # A valid large jobs history must still be rejected by the unchanged 1 MiB cap,
     # without preventing the separately requested security status from succeeding.
     for index in range(70):
      post('/api/jobs',{'title':f'Oversize listing {index}','input':'x'*16000})
     import urllib.request
     measured=urllib.request.Request(origin+'/api/jobs',headers={'Authorization':'Bearer '+token,'X-Setup-Origin':origin,'Origin':origin})
     with urllib.request.urlopen(measured,context=ssl.create_default_context(cafile=str(cert)),timeout=5) as response:
      size=len(response.read())
     self.assertGreater(size,1024*1024)
     print(f'PASS actual backend jobs body {size} bytes exceeds unchanged 1 MiB cap; separate security status succeeds')
     ok,error=request(p,'GET','/api/jobs',token=token,csrf=csrf)
     self.assertFalse(ok);self.assertIn('IOException',error)
     self.assertIn('agents',get('/api/security/status'))
     post('/api/security/incidents',{'agent_id':agents[0]['id'],'severity':'high','behavior':'Administrator requested agent stop','resource':'worker runtime and communication','evidence':'Isolated native API fixture confirmation'})
     post('/api/security/emergency-stop',{'reason':'Isolated native API fixture confirmation'})
     self.assertTrue(get('/api/security/status')['global_stop'])
     # Re-open repository: persistence, not an in-memory transcript.
     from project_bots.chat import ChatService
     reopened=SQLiteRepository(str(home/'private/db'))
     self.assertEqual(ChatService(reopened).history(individual['id'],0,'admin')['messages'][0]['content'],payload['content'])
   finally:server.shutdown();server.server_close();thread.join(timeout=5)
if __name__=='__main__':unittest.main()
