"""Authenticated llama.cpp OpenAI broker; /management is Project Bots API.

Only pinned local registry entries are permitted. No arbitrary upstream proxy,
cloud inference, unverified download, or deletion of preserved model blobs.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac,json,os,logging,time,uuid,threading,socket
from .inference_scheduler import SharedScheduler, Overloaded, Revoked

logger = logging.getLogger('project_bots.inference')
from urllib.request import Request
from .models import DurableAdmission,NativeClient,local_model,memory_required_mib,router_transition
from .repository import SQLiteRepository


def make_handler(workers,admission,upstream,admin_env,registry=None,backend_env=None,store=None,
                 *, scheduler=None, admission_check=None, requester_credentials=None,
                 request_timeout=300):
    """Mandatory registry security gate plus optional restrictive admission_check.

    The optional admission_check(agent_id, action) must return exactly True.

    requester_credentials maps agent IDs to independent inference-only env refs.
    Without it the legacy worker credential is retained for compatibility. No
    caller-supplied identity, priority, generation limits or credential is trusted.
    """
    native=NativeClient(upstream,token_env=backend_env)
    registry={} if registry is None else registry
    scheduler = scheduler or SharedScheduler(admission)
    if not 0 < request_timeout <= 300:
        raise ValueError('Invalid request timeout')
    def reference(w):
        return w['credential_env'] if requester_credentials is None else requester_credentials.get(w['agent_id'], '')
    def chat_credential(supplied):
        try:
            from .chat import ChatService
            return ChatService(workers).is_chat_credential(supplied.decode())
        except Exception:
            # An unreadable registry cannot establish a higher authority.
            return True
    def authenticate(supplied):
        if chat_credential(supplied):
            return None
        rows = workers.list('workers')
        matches = [w for w in rows if len(os.environ.get(reference(w), '')) >= 32 and hmac.compare_digest(supplied, ('Bearer '+os.environ[reference(w)]).encode())]
        protected = {admin_env, backend_env, 'PROJECT_BOTS_API_TOKEN', 'PROJECT_BOTS_COMPUTE_TOKEN', 'PROJECT_BOTS_INFERENCE_ADMIN_TOKEN', 'PROJECT_BOTS_LLAMA_BACKEND_TOKEN', os.environ.get('PROJECT_BOTS_LLAMA_TOKEN_ENV')}
        if hasattr(workers, 'get_settings'):
            protected.add((workers.get_settings() or {}).get('machine_api_env'))
        if requester_credentials is not None:
            protected.update(w['credential_env'] for w in rows)
        if len(matches) != 1 or any(os.environ.get(ref or '') and hmac.compare_digest(supplied, ('Bearer '+os.environ[ref]).encode()) for ref in protected):
            return None
        return matches[0]
    def authorized(supplied, worker, action):
        current = authenticate(supplied)
        if current != worker:
            return False
        try:
            from .security import check_agent_execution
            # The worker registry, never the independent scheduling DB, owns
            # durable revocation and trusted monitor coverage.
            with workers.transaction() as db:
                row = db.execute('SELECT data FROM agents WHERE id=?', (worker['agent_id'],)).fetchone()
                if row is None:
                    return False
                if requester_credentials is not None:
                    configured = json.loads(row[0]).get('config', {}).get('credential_env')
                    if not configured or reference(worker) != configured:
                        return False
                check_agent_execution(workers, worker['agent_id'], db=db)
            return admission_check is None or admission_check(worker['agent_id'], action) is True
        except Exception:
            return False
    def inventory(timeout=None):
        result=[]
        for item in native.request('GET','/models',timeout=timeout)['data']:
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
            worker=authenticate(supplied)
            if admin and (chat_credential(supplied) or any(matches(os.environ.get(ref,'')) for w in workers.list('workers') for ref in (reference(w),w['credential_env']))):
                self.respond(403,{'error':'Ambiguous authority'});return
            if not admin and worker is None:self.respond(403,{'error':'Forbidden'});return
            # Cancellation reduces authority only; retain authenticated owner access
            # even when execution or external admission has been revoked.
            if worker is not None and self.path != '/v1/requests/cancel' and not authorized(supplied,worker,self.path):
                self.respond(403,{'error':'Admission denied'});return
            allowed={'GET':('/v1/models','/management/models','/management/loaded'),'POST':('/v1/chat/completions','/v1/requests/cancel','/management/show','/models/load','/models/unload','/management/download'),'DELETE':('/management/models',)}
            if self.path not in allowed.get(self.command,()):self.respond(404,{'error':'Unsupported llama.cpp broker route'});return
            if not admin and self.path not in ('/v1/chat/completions','/v1/models','/v1/requests/cancel'):
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
                    if self.path=='/v1/requests/cancel':
                        if admin or set(body) != {'request_id'}:raise ValueError('Invalid cancellation')
                        ticket=str(uuid.UUID(body['request_id']))
                        self.respond(202,{'cancel_requested':scheduler.cancel(worker['agent_id'],ticket),'backend_stopped':False});return
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
                    with admission.slot(admission.memory_mib,50) as lease:
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
                    messages=body.get('messages')
                    if not isinstance(messages,list) or any(not isinstance(m,dict) or m.get('role') not in ('system','user','assistant','tool','developer') for m in messages):
                        raise ValueError('Invalid private message context')
                    # UTF-8 bytes + structural/template reserve is a deliberately
                    # conservative admission estimate, not an exact tokenizer count.
                    tokens=len(json.dumps({k:body[k] for k in ('messages','tools','tool_choice') if k in body},ensure_ascii=False).encode())+256+profile['max_output']
                    if tokens>profile['context']:raise ValueError('Context budget exceeded')
                    request_id=self.headers.get('X-Request-ID') or str(uuid.uuid4())
                    if str(uuid.UUID(request_id))!=request_id:raise ValueError('Canonical request UUID required')
                    self.inference(body,worker,supplied,memory,priority,tokens,request_id)
                    return
                required=memory_required_mib(entry['model_info'],entry['size'],entry['context'])
                if required>memory:raise ValueError('Insufficient memory reservation')
                with admission.slot(admission.memory_mib,priority) as lease:
                    try:
                        if not any(m['name']==model for m in inventory()):raise ValueError('Model absent from router')
                        sent=True
                        result=router_transition(native.request,model,self.path.rsplit('/',1)[1])
                        self.respond(200,result);return
                    except BaseException:
                        if sent:lease.retain()
                        raise
            except ValueError:
                if not sent:self.respond(400,{'error':'Local model/profile/budget validation failed'})
            except TimeoutError:
                if not sent:self.respond(503,{'error':'Inference admission timed out'})
            except Exception:
                if not sent:self.respond(503,{'error':'llama.cpp backend unavailable'})
        def inference(self, body, worker, supplied, memory, priority, tokens, request_id):
            started=time.monotonic();status='rejected';sent=False;headers_sent=False
            agent=worker['agent_id'];model=body['model'];entry=registry[model]
            if memory_required_mib(entry['model_info'],entry['size'],entry['context'])>memory:
                raise ValueError('Insufficient memory reservation')
            check=lambda: authorized(supplied,worker,'/v1/chat/completions')
            try:
                with scheduler.slot(agent,memory,priority,tokens,request_id=request_id,check=check) as lease:
                    done=threading.Event();aborted=threading.Event();response_holder=[]
                    deadline=time.monotonic()+request_timeout
                    def watch():
                        while not done.wait(.025):
                            try:
                                scheduler.check(agent,request_id,check)
                                if time.monotonic()>=deadline:raise TimeoutError()
                            except Exception:
                                aborted.set()
                                if response_holder:
                                    try:
                                        # Interrupt a blocked read; disconnection is
                                        # NOT backend-stop proof, so retain the lease.
                                        response_holder[0].fp.raw._sock.shutdown(socket.SHUT_RDWR)
                                    except (AttributeError,OSError):pass
                                return
                    watcher=threading.Thread(target=watch,daemon=True)
                    try:
                        scheduler.check(agent,request_id,check)
                        if not any(m['name']==model for m in inventory(timeout=max(.001,deadline-time.monotonic()))):raise ValueError('Model absent from router')
                        scheduler.check(agent,request_id,check)
                        if time.monotonic()>=deadline:raise TimeoutError('Inference deadline exceeded before dispatch')
                        headers={'Content-Type':'application/json'}
                        if native.token:headers['Authorization']='Bearer '+native.token
                        request=Request(native.address+'/v1/chat/completions',method='POST',data=json.dumps(body).encode(),headers=headers)
                        sent=True;status='uncertain';watcher.start()
                        with native.opener.open(request,timeout=max(.001,deadline-time.monotonic())) as response:
                            response_holder.append(response)
                            scheduler.check(agent,request_id,check)
                            if aborted.is_set():raise Revoked('Request interrupted')
                            self.send_response(response.status);self.send_header('Content-Type',response.headers.get('Content-Type','application/json'));self.send_header('Cache-Control','no-store');self.send_header('X-Request-ID',request_id);self.end_headers();headers_sent=True
                            total=0;expected=response.length
                            while True:
                                scheduler.check(agent,request_id,check)
                                if aborted.is_set() or time.monotonic()>=deadline:raise TimeoutError('Inference deadline exceeded')
                                chunk=response.read1(65536)
                                scheduler.check(agent,request_id,check)
                                if aborted.is_set():raise Revoked('Request interrupted')
                                if not chunk:
                                    if expected is not None and total!=expected:raise OSError('Truncated backend response')
                                    break
                                total+=len(chunk)
                                if total>16*1024*1024:raise ValueError('Response limit exceeded')
                                self.wfile.write(chunk);self.wfile.flush()
                            status='completed'
                    except BaseException:
                        if sent:lease.retain()
                        raise
                    finally:
                        done.set()
                        if watcher.ident is not None:watcher.join(1)
            except Overloaded:
                status='overloaded'
                if not headers_sent:self.respond(429,{'error':'Inference capacity or agent budget exceeded','request_id':request_id})
            except Revoked:
                if not sent:status='revoked'
                if not headers_sent:self.respond(403,{'error':'Request cancelled or admission revoked','request_id':request_id})
            except TimeoutError:
                if not sent:status='queue_timeout'
                if not headers_sent:self.respond(504 if sent else 503,{'error':'Inference deadline exceeded','request_id':request_id})
            except Exception:
                if not headers_sent:self.respond(503,{'error':'Inference unavailable; uncertain work requires reconciliation' if sent else 'Inference unavailable','request_id':request_id})
            finally:
                logger.info('inference_request %s',json.dumps({'request_id':request_id,'agent_id':agent,'model':model,'status':status,'budget_tokens':tokens,'elapsed_ms':round((time.monotonic()-started)*1000,3)}))
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
    p.add_argument('--memory-mib',type=int,default=8192)
    p.add_argument('--concurrency',type=int,default=1)
    p.add_argument('--queue-limit',type=int,default=4)
    p.add_argument('--queue-timeout',type=float,default=30)
    p.add_argument('--request-timeout',type=float,default=300)
    p.add_argument('--per-agent-active',type=int,default=1)
    p.add_argument('--per-agent-queue',type=int,default=2)
    p.add_argument('--requests-per-minute',type=int,default=60)
    p.add_argument('--tokens-per-minute',type=int,default=131072)
    p.add_argument('--starvation-seconds',type=float,default=5)
    p.add_argument('--requester-credentials',help='Trusted JSON agent-ID to inference-only environment-reference map')
    p.add_argument('--admission-check',help='Trusted Python module:callable; failure denies admission')
    args=p.parse_args()
    logging.basicConfig(level=logging.INFO)
    if len(os.environ.get(args.admin_env,''))<32 or len(os.environ.get(args.backend_env,''))<32 or hmac.compare_digest(os.environ[args.admin_env],os.environ[args.backend_env]):raise ValueError('Distinct strong private admin/backend tokens required')
    workers=SQLiteRepository(args.workers_db);gate=DurableAdmission(SQLiteRepository(args.admission_db),memory_mib=args.memory_mib,concurrency=args.concurrency,queue_limit=args.queue_limit)
    scheduler=SharedScheduler(gate,queue_timeout=args.queue_timeout,per_agent_active=args.per_agent_active,per_agent_queue=args.per_agent_queue,requests_per_minute=args.requests_per_minute,tokens_per_minute=args.tokens_per_minute,starvation_seconds=args.starvation_seconds)
    credentials=None
    if args.requester_credentials:
        import re
        credentials=json.loads(Path(args.requester_credentials).read_text())
        if not isinstance(credentials,dict) or any(not isinstance(k,str) or not isinstance(v,str) or not re.fullmatch('[A-Z][A-Z0-9_]{0,127}',v) for k,v in credentials.items()) or len(set(credentials.values()))!=len(credentials):raise ValueError('Invalid independent credential references')
    check=None
    if args.admission_check:
        import importlib
        module,name=args.admission_check.split(':')
        check=getattr(importlib.import_module(module),name)
        if not callable(check):raise ValueError('Admission check must be callable')
    registry=json.loads(Path(args.registry).read_text())
    store=None
    if args.store_config:
        from .llama_store import SSHModelStore
        store=SSHModelStore(json.loads(Path(args.store_config).read_text()),args.registry,registry)
    with ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(workers,gate,args.upstream,args.admin_env,registry,args.backend_env,store,scheduler=scheduler,admission_check=check,requester_credentials=credentials,request_timeout=args.request_timeout)) as server:server.serve_forever()

if __name__=='__main__':main()
