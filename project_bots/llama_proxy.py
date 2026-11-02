"""Authenticated llama.cpp OpenAI broker; /management is Project Bots API.

Only pinned local registry entries are permitted. No arbitrary upstream proxy,
cloud inference, unverified download, or deletion of preserved model blobs.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac,json,os
from urllib.request import Request
from .models import DurableAdmission,NativeClient,local_model,memory_required_mib,router_transition
from .repository import SQLiteRepository


def make_handler(workers,admission,upstream,admin_env,registry=None,backend_env=None,store=None):
    native=NativeClient(upstream,token_env=backend_env)
    registry={} if registry is None else registry
    def inventory():
        result=[]
        for item in native.request('GET','/models')['data']:
            name=item['id']
            if name not in registry:continue
            entry=registry[name]
            effective=(item.get('memory') or {}).get('effective') or {}
            devices=effective.get('devices',[])
            allocated=sum(d.get(k,0) for d in devices for k in ('model','context','compute'))
            vram=sum(d.get(k,0) for d in devices if d.get('kind')=='device' for k in ('model','context','compute'))
            result.append({'name':name,'size':entry['size'],'sha256':entry['sha256'],
                'context_length':item.get('meta',{}).get('n_ctx',entry['context']),
                'loaded':item['status']['value']=='loaded','allocated_bytes':allocated,'size_vram':vram,'memory_observation_available':bool(devices)})
        return result
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.0'
        def log_message(self,*args):pass
        def respond(self,code,data):
            raw=json.dumps(data).encode()
            self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
        def handle_native(self):
            from urllib.parse import urlsplit
            try:
                host=urlsplit('//'+self.headers.get('Host',''))
                if host.hostname not in ('localhost','127.0.0.1','::1') or not host.port or host.path or host.username or host.password or host.query or host.fragment or any(k in self.headers for k in ('Origin','Sec-Fetch-Site')):
                    self.respond(403,{'error':'Forbidden'});return
            except ValueError:self.respond(403,{'error':'Forbidden'});return
            supplied=self.headers.get('Authorization','').encode()
            def matches(value):return bool(value) and hmac.compare_digest(supplied,('Bearer '+value).encode())
            admin=matches(os.environ.get(admin_env,''))
            worker=next((w for w in workers.list('workers') if matches(os.environ.get(w['credential_env'],''))),None)
            if not admin and worker is None:self.respond(403,{'error':'Forbidden'});return
            allowed={'GET':('/v1/models','/management/models','/management/loaded'),'POST':('/v1/chat/completions','/management/show','/models/load','/models/unload','/management/download'),'DELETE':('/management/models',)}
            if self.path not in allowed.get(self.command,()):self.respond(404,{'error':'Unsupported llama.cpp broker route'});return
            if not admin and self.path not in ('/v1/chat/completions','/v1/models'):
                self.respond(403,{'error':'Model management requires platform authority'});return
            if admin and self.path=='/v1/chat/completions':
                self.respond(403,{'error':'Inference requires worker identity'});return
            if (self.path=='/management/download' or self.command=='DELETE') and store is None:
                self.respond(409,{'error':'Administrator-pinned model store is not configured'});return
            sent=False
            try:
                body=None;model=None
                if self.command!='GET':
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=4*1024*1024:raise ValueError('Invalid body size')
                    body=json.loads(self.rfile.read(length))
                    if not isinstance(body,dict):raise ValueError('Invalid body')
                    model=local_model(body.get('model'))
                    if model not in registry and not (self.path=='/management/download' and model in store.config['catalog']):raise ValueError('Unregistered local model')
                    if not admin and model!=worker['profile']['model']:raise ValueError('Unassigned model')
                if self.command=='GET':
                    items=inventory()
                    if not admin:items=[m for m in items if m['name']==worker['profile']['model']]
                    if self.path=='/v1/models':self.respond(200,{'object':'list','data':[{'id':m['name'],'object':'model','owned_by':'llamacpp'} for m in items]})
                    else:self.respond(200,{'models':[m for m in items if m['loaded'] or self.path!='/management/loaded']})
                    return
                if self.path=='/management/download' or self.command=='DELETE':
                    if self.command=='DELETE' and any(w['profile']['model']==model for w in workers.list('workers')):
                        self.respond(409,{'error':'Model is assigned to a worker'});return
                    if self.command=='DELETE' and not registry[model].get('managed'):
                        self.respond(409,{'error':'Preserved model cannot be removed'});return
                    with admission.slot(8192,50) as lease:
                        try:
                            sent=True
                            if self.command=='DELETE':router_transition(native.request,model,'unload')
                            result=store.apply(model,'delete' if self.command=='DELETE' else 'download')
                            native.request('GET','/models?reload=1')
                            self.respond(200,result)
                        except BaseException:
                            lease.retain();raise
                    return
                entry=registry[model]
                if self.path=='/management/show':
                    self.respond(200,{k:entry[k] for k in ('capabilities','model_info','context','sha256','size')});return
                memory,priority=8192,50
                if self.path=='/v1/chat/completions':
                    profile=worker['profile'];memory,priority=profile['memory_mib'],profile['priority']
                    if profile['context']!=entry['context'] or 'tools' not in entry['capabilities']:raise ValueError('Server context/tool mismatch')
                    body={k:body[k] for k in ('model','messages','tools','tool_choice','stream','stream_options','parallel_tool_calls') if k in body}
                    body.update(temperature=profile['temperature'],max_tokens=profile['max_output'])
                required=memory_required_mib(entry['model_info'],entry['size'],entry['context'])
                if required>memory:raise ValueError('Insufficient memory reservation')
                with admission.slot(memory,priority) as lease:
                    try:
                        if not any(m['name']==model for m in inventory()):raise ValueError('Model absent from router')
                        headers={'Content-Type':'application/json'}
                        if native.token:headers['Authorization']='Bearer '+native.token
                        request=Request(native.address+self.path,method='POST',data=json.dumps(body).encode(),headers=headers)
                        sent=True
                        if self.path in ('/models/load','/models/unload'):
                            result=router_transition(native.request,model,self.path.rsplit('/',1)[1])
                            self.respond(200,result);return
                        with native.opener.open(request,timeout=300) as response:
                            self.send_response(response.status);self.send_header('Content-Type',response.headers.get('Content-Type','application/json'));self.send_header('Cache-Control','no-store');self.end_headers()
                            total=0
                            while True:
                                chunk=response.read1(65536)
                                if not chunk:break
                                total+=len(chunk)
                                if total>16*1024*1024:raise ValueError('Response limit exceeded')
                                self.wfile.write(chunk);self.wfile.flush()
                    except BaseException:
                        if sent:lease.retain()
                        raise
            except ValueError:
                if not sent:self.respond(400,{'error':'Local model/profile/budget validation failed'})
            except TimeoutError:
                if not sent:self.respond(503,{'error':'Inference admission timed out'})
            except Exception:
                if not sent:self.respond(503,{'error':'llama.cpp backend unavailable'})
        do_GET=handle_native
        do_POST=handle_native
        do_DELETE=handle_native
    return Handler


def main():
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workers-db',required=True)
    p.add_argument('--admission-db',required=True)
    p.add_argument('--registry',required=True)
    p.add_argument('--store-config')
    p.add_argument('--upstream',default='http://127.0.0.1:21434')
    p.add_argument('--port',default=21435,type=int)
    p.add_argument('--admin-env',default='PROJECT_BOTS_INFERENCE_ADMIN_TOKEN')
    p.add_argument('--backend-env',default='PROJECT_BOTS_LLAMA_BACKEND_TOKEN')
    args=p.parse_args()
    if len(os.environ.get(args.admin_env,''))<32 or len(os.environ.get(args.backend_env,''))<32:raise ValueError('Strong private admin/backend tokens required')
    workers=SQLiteRepository(args.workers_db);gate=DurableAdmission(SQLiteRepository(args.admission_db))
    registry=json.loads(Path(args.registry).read_text())
    store=None
    if args.store_config:
        from .llama_store import SSHModelStore
        store=SSHModelStore(json.loads(Path(args.store_config).read_text()),args.registry,registry)
    with ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(workers,gate,args.upstream,args.admin_env,registry,args.backend_env,store)) as server:server.serve_forever()

if __name__=='__main__':main()
