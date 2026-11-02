#!/usr/bin/env python3
"""Explicit opt-in: create one independent non-sudo OpenClaw VM and register it.

The manifest is private durable intent; rerun the SAME file after inspecting any
failure. Never delete it to retry. No root, host package or security changes.
Initial guest SSH host-key enrollment is TOFU over the authenticated compute SSH
connection and the API-owned loopback port; guest cloud-init UUID is then checked.
"""
import argparse,io,json,os,re,secrets,shlex,subprocess,sys,tarfile,time,uuid
from pathlib import Path
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from project_bots.provision import ensure_vm,guest_ssh,tunnel_unit
from project_bots.workers import worker_config


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm',required=True,choices=['CREATE AND DEPLOY ONE WORKER'])
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--role',required=True,choices=['Researcher','Programmer','HomelabEngineer'])
    p.add_argument('--machine',required=True)
    p.add_argument('--platform',default='http://127.0.0.1:8033')
    p.add_argument('--platform-env',required=True,type=Path)
    p.add_argument('--compute-host',required=True)
    p.add_argument('--compute-key',required=True,type=Path)
    p.add_argument('--gateway-port',required=True,type=int)
    args=p.parse_args()
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*@[a-zA-Z0-9.-]+',args.compute_host):p.error('Invalid compute SSH target')
    if not 1024<=args.gateway_port<=65534:p.error('Invalid port')
    if not args.platform.startswith('http://127.0.0.1:'):p.error('Only trusted loopback platform supported')
    os.umask(0o077)
    args.manifest=args.manifest.resolve()
    if not args.manifest.parent.is_dir() or args.manifest.parent.stat().st_mode & 0o077:
        p.error('Manifest parent must already be a private 0700 directory')
    token=dict(l.split('=',1) for l in args.platform_env.read_text().splitlines() if '=' in l)['PROJECT_BOTS_API_TOKEN']
    def api(route,data=None):
        request=Request(args.platform+route,data=None if data is None else json.dumps(data).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urlopen(request,timeout=90) as response:return json.load(response)
    if args.manifest.exists():
        m=json.loads(args.manifest.read_text())
        if (m['role'],m['machine'],m['gateway_port'])!=(args.role,args.machine,args.gateway_port):raise RuntimeError('Manifest arguments conflict')
    else:
        m={'vm_id':str(uuid.uuid4()),'role':args.role,'machine':args.machine,'gateway_port':args.gateway_port,'token':secrets.token_urlsafe(48)}
    def save():
        tmp=args.manifest.with_suffix('.new');tmp.write_text(json.dumps(m,indent=2));tmp.chmod(0o600);tmp.replace(args.manifest)
    save()
    if m.get('registered'):
        print(json.dumps(api('/api/agents/'+m['agent_id']+'/worker/health')));return
    # This is an explicit maintenance workflow, not a background autoscaler.
    # Never intentionally restart its service dependencies during an active job.
    if any(job['status']=='running' for job in api('/api/jobs')):
        raise RuntimeError('Active jobs: defer provisioning maintenance')
    broker=subprocess.run(['systemctl','--user','is-active','project-bots-stage3-inference.service'],capture_output=True,text=True)
    if broker.returncode:
        raise RuntimeError('Install/verify the authenticated inference broker before provisioning')
    key=args.manifest.with_suffix('.ed25519');known=args.manifest.with_suffix('.known-hosts')
    if not key.exists():subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],check=True)
    route='/api/machines/'+args.machine
    vm=ensure_vm(lambda path,data=None:api(route+path,data),m,save,' '.join(key.with_suffix('.ed25519.pub').read_text().split()[:2]))
    print('vm-running',m['vm_id'],args.role,flush=True)
    compute=['ssh','-T','-i',str(args.compute_key),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',args.compute_host]
    if not known.exists():
        deadline=time.monotonic()+900
        while time.monotonic()<deadline:
            result=subprocess.run(compute+['ssh-keyscan -T 4 -t ed25519 -p '+str(vm['ssh_port'])+' 127.0.0.1'],text=True,capture_output=True,timeout=15)
            keys=[l for l in result.stdout.splitlines() if not l.startswith('#') and ' ssh-ed25519 ' in l]
            if keys:
                known.write_text('\n'.join('pb-'+m['vm_id']+' '+' '.join(l.split()[1:]) for l in keys)+'\n');known.chmod(0o600);break
            time.sleep(5)
        else:raise RuntimeError('No guest SSH host key; preserve manifest')
    ssh=guest_ssh(key,known,args.compute_key,args.compute_host,vm['ssh_port'],m['vm_id'])+['bot@127.0.0.1']
    # Wait for the fixed trusted cloud-init installation; never issue root commands.
    deadline=time.monotonic()+1200
    while time.monotonic()<deadline:
        result=subprocess.run(ssh+['cloud-init status --format json'],text=True,capture_output=True,timeout=20)
        if result.returncode==0 and json.loads(result.stdout).get('status')=='done':break
        if result.returncode==2:raise RuntimeError('Guest cloud-init failed; inspect without privileged repair')
        time.sleep(5)
    else:raise RuntimeError('Guest cloud-init readiness deadline')
    root=Path(__file__).resolve().parents[1]
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w') as archive:
        for path in sorted((root/'project_bots').glob('*')):
            if path.is_file() and path.suffix in ('.py','.html','.js'):archive.add(path,arcname='project_bots/'+path.name)
    result=subprocess.run(ssh+['mkdir -p ~/.local/lib/project-bots-worker && tar -xf - -C ~/.local/lib/project-bots-worker'],input=buf.getvalue(),capture_output=True,timeout=40)
    if result.returncode:raise RuntimeError('Guest package copy failed')
    profile={'model':'qwen3-1_7b','context':32768,'max_output':256,'temperature':0,'memory_mib':8192,'priority':10}
    payload={'vm_id':m['vm_id'],'role':args.role,'token':m['token'],'config':worker_config(profile,args.role)}
    command="PYTHONPATH=$HOME/.local/lib/project-bots-worker python3 -c 'import json,sys; from project_bots.guest_bootstrap import bootstrap; bootstrap(json.load(sys.stdin))'"
    result=subprocess.run(ssh+[command],input=json.dumps(payload),text=True,capture_output=True,timeout=900)
    log=args.manifest.with_suffix('.bootstrap.log');log.write_text(result.stdout+result.stderr);log.chmod(0o600)
    if result.returncode:raise RuntimeError('Fixed guest bootstrap failed; see private '+str(log))
    print('guest-deployed',m['vm_id'],flush=True)
    unit_name='project-bots-stage3-worker-'+m['vm_id']+'.service'
    unit=Path.home()/'.config/systemd/user'/unit_name
    unit.write_text(tunnel_unit(key,known,args.compute_key,args.compute_host,vm['ssh_port'],args.gateway_port,m['vm_id']))
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    subprocess.run(['systemctl','--user','enable','--now',unit_name],check=True)
    # Each VM has a unique secret; the browser sees only the environment reference.
    envname='PROJECT_BOTS_WORKER_'+m['vm_id'].replace('-','_').upper()
    envfile=args.manifest.with_suffix('.env');envfile.write_text(envname+'='+m['token']+'\n');envfile.chmod(0o600)
    for service in ('project-bots-stage3-platform.service','project-bots-stage3-inference.service'):
        drop=Path.home()/('.config/systemd/user/'+service+'.d');drop.mkdir(exist_ok=True)
        (drop/(m['vm_id']+'.conf')).write_text('[Service]\nEnvironmentFile='+str(envfile)+'\n')
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    subprocess.run(['systemctl','--user','restart','project-bots-stage3-inference.service','project-bots-stage3-platform.service'],check=True)
    time.sleep(1)
    for _ in range(90):
        try:
            request=Request('http://127.0.0.1:'+str(args.gateway_port+1)+'/v1/health',headers={'Authorization':'Bearer '+m['token']})
            with urlopen(request,timeout=5) as response:health=json.load(response)
            if health['vm_id']==m['vm_id'] and health['status']=='healthy':break
        except OSError:pass
        time.sleep(1)
    else:raise RuntimeError('Identity/Gateway did not become ready')
    name=args.role+' '+m['vm_id']
    agents=api('/api/agents')
    matches=[a for a in agents if a['name']==name and a['machine_id']==args.machine]
    if len(matches)>1:raise RuntimeError('Ambiguous agent registration')
    agent=matches[0] if matches else api('/api/agents',{'name':name,'role':args.role,'machine_id':args.machine})
    m['agent_id']=agent['id'];save()
    worker=api('/api/agents/'+agent['id']+'/worker',{'vm_id':m['vm_id'],'endpoint':'http://127.0.0.1:'+str(args.gateway_port),'identity_endpoint':'http://127.0.0.1:'+str(args.gateway_port+1),'credential_env':envname,'profile':profile})
    if worker['status']!='verified':raise RuntimeError('Worker not verified')
    health=api('/api/agents/'+agent['id']+'/worker/health')
    if health['status']!='healthy':raise RuntimeError('Worker final health failed')
    m['registered']=True;save()
    print(json.dumps({'vm_id':m['vm_id'],'agent_id':agent['id'],'role':args.role,'status':'verified'}),flush=True)

if __name__=='__main__':main()
