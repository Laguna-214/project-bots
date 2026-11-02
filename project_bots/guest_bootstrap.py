"""Fixed non-root guest bootstrap. Refuse existing unmanaged OpenClaw state."""
import json
import os
from pathlib import Path
import subprocess
from .workers import role_instructions


def bootstrap(payload, home=None, instance=Path('/var/lib/cloud/data/instance-id'), run=subprocess.run, install=None):
    home = home or Path.home()
    vm_id = payload['vm_id']
    if Path(instance).read_text().strip() != vm_id:
        raise RuntimeError('Guest cloud-init UUID mismatch')
    marker = deployment_guard(home, vm_id)
    token = payload['token']
    env = home/'.openclaw/gateway.env'
    if env.exists() and env.read_text() != 'OPENCLAW_GATEWAY_TOKEN='+token+'\n':
        raise RuntimeError('Credential mismatch; refusing rotation')
    instructions = role_instructions(payload['role'])
    def write(path, text):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(text)
        path.chmod(0o600)
    if not marker.exists():
        (install or install_runtime)(home)
        write(marker, json.dumps({'vm_id':vm_id,'role':payload['role']}))
    import copy
    config=copy.deepcopy(payload['config'])
    config['models']['providers']['llamacpp']['apiKey']=token
    write(home/'.openclaw/openclaw.json',json.dumps(config,indent=2))
    write(env,'OPENCLAW_GATEWAY_TOKEN='+token+'\n')
    write(home/'.openclaw/workspace/AGENTS.md',instructions+'\n')
    node=home/'.local/opt/node-v24.22.2-linux-x64/bin'
    environment={**os.environ,'PATH':str(node)+':'+os.environ.get('PATH','')}
    claw=home/'.local/openclaw/node_modules/.bin/openclaw'
    run([str(claw),'config','validate'],env=environment,check=True)
    common='[Unit]\nDescription=Project Bots isolated worker\nAfter=network.target\n[Service]\nEnvironmentFile=%h/.openclaw/gateway.env\nUMask=0077\nRestart=on-failure\nRestartSec=5\n'
    worker=common+'Environment=PATH=%h/.local/opt/node-v24.22.2-linux-x64/bin:/usr/local/bin:/usr/bin:/bin\nExecStart=%h/.local/opt/node-v24.22.2-linux-x64/bin/node %h/.local/openclaw/node_modules/openclaw/openclaw.mjs gateway run\n[Install]\nWantedBy=default.target\n'
    identity=common+'Environment=PYTHONPATH=%h/.local/lib/project-bots-worker\nExecStart=/usr/bin/python3 -m project_bots.worker_health --port 18790\n[Install]\nWantedBy=default.target\n'
    units=home/'.config/systemd/user'
    write(units/'project-bots-worker.service',worker)
    write(units/'project-bots-worker-identity.service',identity)
    run(['systemctl','--user','daemon-reload'],check=True)
    run(['systemctl','--user','enable','project-bots-worker.service','project-bots-worker-identity.service'],check=True)
    run(['systemctl','--user','restart','project-bots-worker.service','project-bots-worker-identity.service'],check=True)


def install_runtime(home):
    import urllib.request
    import hashlib
    import base64
    cache=home/'.cache/project-bots-artifacts'
    cache.mkdir(parents=True,exist_ok=True,mode=0o700)
    node=cache/'node-v24.22.2-linux-x64.tar.xz'
    if not node.exists():
        urllib.request.urlretrieve('https://nodejs.org/dist/v24.22.2/'+node.name,node)
    if hashlib.file_digest(node.open('rb'),'sha256').hexdigest()!='48cc0e21e048790e54c0cf5749c2725005313d652651c40b7a21feb9697aaf75':
        raise RuntimeError('Node checksum mismatch')
    prefix=home/'.local/opt';prefix.mkdir(parents=True,exist_ok=True)
    subprocess.run(['tar','-xJf',str(node),'-C',str(prefix),'--no-same-owner'],check=True)
    metadata=json.load(urllib.request.urlopen('https://registry.npmjs.org/openclaw/2026.10.9'))
    integrity='sha512-KbIl0/7an0/nKBo92FnJg7LFcEpFVQyOgSRfHNE9yxELg1Ebql7BmBsdLL+1dDOLZnQtuwjt6Hy45CCrmYdJNA=='
    if metadata['dist']['integrity']!=integrity:
        raise RuntimeError('OpenClaw publisher integrity mismatch')
    package=cache/'openclaw-2026.10.9.tgz'
    if not package.exists():
        urllib.request.urlretrieve('https://registry.npmjs.org/openclaw/-/openclaw-2026.10.9.tgz',package)
    if 'sha512-'+base64.b64encode(hashlib.file_digest(package.open('rb'),'sha512').digest()).decode()!=integrity:
        raise RuntimeError('OpenClaw artifact checksum mismatch')
    nb=prefix/'node-v24.22.2-linux-x64/bin'
    subprocess.run([str(nb/'npm'),'install','--prefix',str(home/'.local/openclaw'),'--save-exact',str(package),'--no-fund','--no-audit'],env={**os.environ,'PATH':str(nb)+':'+os.environ.get('PATH','')},check=True)



def deployment_guard(home, vm_id):
    marker = home/'.local/share/project-bots-worker/deployment.json'
    if (home/'.openclaw/openclaw.json').exists() and not marker.exists():
        raise RuntimeError('Existing unmanaged worker; refusing replacement')
    if marker.exists() and json.loads(marker.read_text())['vm_id'] != vm_id:
        raise RuntimeError('Deployment UUID mismatch')
    return marker
