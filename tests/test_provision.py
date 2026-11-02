import unittest,uuid

class ProvisionTests(unittest.TestCase):
    def test_create_records_intent_before_network_and_resume_does_not_duplicate(self):
        from project_bots.provision import ensure_vm
        vm=str(uuid.uuid4()); manifest={'vm_id':vm,'role':'Researcher'}
        calls=[]; saved=[]; vms={}
        def save(): saved.append(dict(manifest))
        def api(path,data=None):
            calls.append((path,data))
            if path=='/vms' and data is None:return list(vms.values())
            if path=='/vms':
                self.assertEqual(saved[-1]['phase'],'create-intent')
                vms[vm]={'id':vm,'state':'shut off','ssh_port':22001};return vms[vm]
            if path.endswith('/start'):
                vms[vm]['state']='running';return vms[vm]
            return vms[vm]
        result=ensure_vm(api,manifest,save,'ssh-ed25519 AAAATEST')
        self.assertEqual(result['id'],vm)
        ensure_vm(api,manifest,save,'ssh-ed25519 AAAATEST')
        self.assertEqual(sum(p=='/vms' and d is not None for p,d in calls),1)
        self.assertEqual(manifest['phase'],'vm-running')

    def test_uncertain_absent_vm_does_not_repeat_create(self):
        from project_bots.provision import ensure_vm
        calls=[]
        def api(path,data=None):
            calls.append((path,data));return []
        with self.assertRaises(RuntimeError):
            ensure_vm(api, {'vm_id':str(uuid.uuid4()),'phase':'create-intent'},lambda:None,'key')
        self.assertEqual(calls,[('/vms',None)])

    def test_bootstrap_refuses_to_overwrite_an_unmanaged_existing_worker(self):
        import tempfile,json
        from pathlib import Path
        from project_bots.guest_bootstrap import deployment_guard
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp); claw=home/'.openclaw';claw.mkdir()
            (claw/'openclaw.json').write_text('{}')
            with self.assertRaises(RuntimeError):deployment_guard(home,str(uuid.uuid4()))
            self.assertEqual((claw/'openclaw.json').read_text(),'{}')

    def test_bootstrap_writes_private_per_vm_units_and_is_idempotent(self):
        import tempfile,json,os
        from pathlib import Path
        from project_bots.guest_bootstrap import bootstrap
        vm=str(uuid.uuid4()); token='unique-gateway-token-'+('0123456789abcdef'*3)
        from project_bots.workers import worker_config
        profile={'model':'qwen3:1.7b','context':32768,'max_output':256,'temperature':0,'memory_mib':8192,'priority':10}
        payload={'vm_id':vm,'token':token,'role':'Researcher','config':worker_config(profile,'Researcher')}
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);identity=home/'instance';identity.write_text(vm);calls=[];installs=[]
            run=lambda args,**kw:calls.append(args)
            bootstrap(payload,home=home,instance=identity,run=run,install=lambda h:installs.append(h))
            bootstrap(payload,home=home,instance=identity,run=run,install=lambda h:installs.append(h))
            self.assertEqual(len(installs),1)
            self.assertEqual((home/'.openclaw/gateway.env').stat().st_mode & 0o777,0o600)
            self.assertIn('OPENCLAW_GATEWAY_TOKEN='+token,(home/'.openclaw/gateway.env').read_text())
            self.assertEqual(json.loads((home/'.openclaw/openclaw.json').read_text())['models']['providers']['llamacpp']['apiKey'],token)
            self.assertTrue((home/'.config/systemd/user/project-bots-worker-identity.service').exists())
            self.assertTrue(any('validate' in cmd for cmd in calls))
            payload['token']='different'
            with self.assertRaises(RuntimeError):bootstrap(payload,home=home,instance=identity,run=run,install=lambda h:None)

    def test_worker_tunnel_has_unique_loopback_ports_and_strict_ssh_identity(self):
        from project_bots.provision import tunnel_unit
        text=tunnel_unit('/private/key','/private/known','/compute/key','pbcompute@10.0.50.56',22001,19891,'00000000-0000-4000-8000-000000000001')
        self.assertIn('StrictHostKeyChecking=yes',text)
        self.assertIn('BatchMode=yes',text)
        self.assertIn('HostKeyAlias=pb-00000000-0000-4000-8000-000000000001',text)
        self.assertIn('127.0.0.1:19891:127.0.0.1:18789',text)
        self.assertIn('127.0.0.1:19892:127.0.0.1:18790',text)
        self.assertIn('127.0.0.1:11434:127.0.0.1:21435',text)
        self.assertNotIn('0.0.0.0',text)

    def test_provision_command_refuses_without_explicit_mutation_confirmation(self):
        import subprocess,sys
        from pathlib import Path
        script=Path(__file__).resolve().parents[1]/'scripts/provision_worker.py'
        result=subprocess.run([sys.executable,str(script),'--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('--confirm',result.stdout)
        self.assertIn('--manifest',result.stdout)
        result=subprocess.run([sys.executable,str(script)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)

if __name__=='__main__':unittest.main()
