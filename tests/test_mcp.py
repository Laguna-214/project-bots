"""Real official-SDK stdio protocol against a local HTTP fixture (not VM evidence)."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import anyio
    SDK = True
except ImportError:
    SDK = False

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(SDK, 'optional MCP SDK dependency (requirements-mcp.txt)')
class MCPProtocolTests(unittest.TestCase):
    def test_job_dispatch_requires_exact_intent_and_retrievable_receipt(self):
        from project_bots.mcp_server import create_server
        calls = []
        class Client:
            def request(self, method, path, data=None):
                calls.append((method, path, data))
                return {'id': '11111111-1111-4111-8111-111111111111', 'status': 'succeeded'}
        async def exercise():
            server = create_server(Client())
            names = [t.name for t in await server.list_tools()]
            self.assertIn('dispatch_job', names)
            job = '11111111-1111-4111-8111-111111111111'
            from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
            with self.assertRaises(ToolError) as caught:
                await server.call_tool('dispatch_job', {'job_id': job, 'confirmation': 'yes'})
            self.assertNotIsInstance(caught.exception, UnexpectedToolError)
            self.assertEqual(calls, [])
            result = await server.call_tool('dispatch_job', {'job_id': job, 'confirmation': 'dispatch:' + job})
            self.assertFalse(result.is_error)
            self.assertEqual(calls[-1], ('POST', '/api/jobs/' + job + '/dispatch', {'confirmation': 'dispatch:' + job}))
            result = await server.call_tool('get_job', {'job_id': job})
            self.assertFalse(result.is_error)
            result = await server.call_tool('get_job_execution', {'job_id': job})
            self.assertFalse(result.is_error)
            self.assertEqual(calls[-1], ('GET', '/api/jobs/' + job + '/execution', None))
        anyio.run(exercise)

    def test_cancel_job_uses_existing_state_guarded_route(self):
        from project_bots.mcp_server import create_server
        calls = []
        class Client:
            def request(self, method, path, data=None):
                calls.append((method, path, data)); return {'status': 'canceled'}
        async def exercise():
            server = create_server(Client())
            job = '11111111-1111-4111-8111-111111111111'
            result = await server.call_tool('cancel_job', {'job_id': job})
            self.assertFalse(result.is_error)
            self.assertEqual(calls, [('POST', '/api/jobs/' + job + '/cancel', {})])
        anyio.run(exercise)

    def test_agent_registration_is_metadata_not_worker_start(self):
        from project_bots.mcp_server import create_server
        calls = []
        class Client:
            def request(self, method, path, data=None):
                calls.append((method, path, data)); return {'status': 'registered'}
        async def exercise():
            server = create_server(Client())
            await server.call_tool('register_agent', {'name': 'test', 'role': 'Researcher', 'model': 'local-model'})
            self.assertEqual(calls, [('POST', '/api/agents', {'name': 'test', 'role': 'Researcher', 'machine_id': None, 'config': {'model': 'local-model'}})])
        anyio.run(exercise)

    def test_worker_profile_binding_and_role_inventory_use_existing_api(self):
        from project_bots.mcp_server import create_server
        calls = []
        class Client:
            def request(self, method, path, data=None):
                calls.append((method, path, data)); return {} if method == 'POST' else []
        async def exercise():
            server = create_server(Client())
            aid = '11111111-1111-4111-8111-111111111111'
            vm = '22222222-2222-4222-8222-222222222222'
            args = dict(agent_id=aid, vm_id=vm, endpoint='http://127.0.0.1:1234', credential_env='WORKER_TOKEN', model='local-model', context=4096, temperature=0.2, max_output=512, memory_mib=8192, priority=50)
            await server.call_tool('configure_worker', args)
            self.assertEqual(calls[-1], ('POST', '/api/agents/' + aid + '/worker', {'vm_id': vm, 'endpoint': args['endpoint'], 'credential_env': 'WORKER_TOKEN', 'profile': {k: args[k] for k in ('model', 'context', 'temperature', 'max_output', 'memory_mib', 'priority')}}))
            await server.call_tool('list_roles', {})
            self.assertEqual(calls[-1], ('GET', '/api/roles', None))
        anyio.run(exercise)

    def test_token_file_rejects_unsafe_files_without_exposing_secret(self):
        import tempfile
        from project_bots.mcp_server import read_token_file
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'token'
            token = secrets.token_urlsafe(48)
            path.write_text(token + '\n'); path.chmod(0o600)
            self.assertEqual(read_token_file(path), token)
            for mode in (0o644, 0o660, 0o400):
                path.chmod(mode)
                with self.assertRaises(ValueError) as caught:
                    read_token_file(path)
                self.assertNotIn(token, str(caught.exception))
            path.chmod(0o600)
            link = Path(directory) / 'link'; link.symlink_to(path)
            with self.assertRaises(ValueError): read_token_file(link)
            with self.assertRaises(ValueError): read_token_file(directory)
            path.write_text('short')
            with self.assertRaises(ValueError): read_token_file(path)

    def test_undispatched_execution_absence_is_structured_not_sdk_error(self):
        from project_bots.mcp_server import create_server
        class Client:
            def request(self, method, path, data=None): return None
        async def exercise():
            result = await create_server(Client()).call_tool('get_job_execution', {'job_id': '11111111-1111-4111-8111-111111111111'})
            self.assertFalse(result.is_error)
            self.assertEqual(result.structured_content, {'execution': None})
        anyio.run(exercise)

    def test_job_creation_and_assignment_only_supported_fields(self):
        from project_bots.mcp_server import create_server
        calls = []
        class Client:
            def request(self, method, path, data=None):
                calls.append((method, path, data)); return {'ok': True}
        async def exercise():
            server = create_server(Client())
            names = [t.name for t in await server.list_tools()]
            self.assertIn('create_job', names)
            agent = '11111111-1111-4111-8111-111111111111'
            job = '22222222-2222-4222-8222-222222222222'
            await server.call_tool('create_job', {'title': 'test', 'input': 'read report', 'agent_id': agent})
            self.assertEqual(calls[-1], ('POST', '/api/jobs', {'title': 'test', 'input': 'read report', 'agent_id': agent}))
            await server.call_tool('assign_job', {'job_id': job, 'agent_id': agent})
            self.assertEqual(calls[-1], ('POST', '/api/jobs/' + job + '/assign', {'agent_id': agent}))
            await server.call_tool('list_agents', {})
            self.assertEqual(calls[-1], ('GET', '/api/agents', None))
        anyio.run(exercise)

    def test_machine_lifecycle_routes_preserve_operation_and_confirmation(self):
        from project_bots.mcp_server import create_server
        from mcp.server.mcpserver.exceptions import UnexpectedToolError
        calls = []
        class Client:
            def request(self, method, path, data=None):
                calls.append((method, path, data)); return [] if path.endswith('/vms') and method == 'GET' else {'ok': True}
        async def exercise():
            server = create_server(Client())
            self.assertIn('vm_action', [t.name for t in await server.list_tools()])
            mid = '11111111-1111-4111-8111-111111111111'
            vm = '22222222-2222-4222-8222-222222222222'
            op = '33333333-3333-4333-8333-333333333333'
            for tool, args, route in [('list_machines', {}, '/api/machines'), ('machine_health', {'machine_id':mid}, '/api/machines/'+mid+'/health'), ('list_vms', {'machine_id':mid}, '/api/machines/'+mid+'/vms'), ('get_vm', {'machine_id':mid,'vm_id':vm}, '/api/machines/'+mid+'/vms/'+vm), ('get_operation', {'machine_id':mid,'operation_id':op}, '/api/machines/'+mid+'/operations/'+op)]:
                await server.call_tool(tool,args)
                self.assertEqual(calls[-1],('GET',route,None))
            for action in ('start','shutdown','restart','pause','resume','delete','snapshot-create','snapshot-restore'):
                args={'machine_id':mid,'vm_id':vm,'action':action,'operation_id':op,'confirmation':'yes'}
                count=len(calls)
                with self.assertRaises(UnexpectedToolError):await server.call_tool('vm_action',args)
                self.assertEqual(len(calls),count)
                args['confirmation']=action+':'+vm
                if action.startswith('snapshot-'):args['snapshot']='test-checkpoint'
                await server.call_tool('vm_action',args)
                payload={'operation_id':op,'confirmation':action+':'+vm}
                if action.startswith('snapshot-'):payload['snapshot']='test-checkpoint'
                self.assertEqual(calls[-1],('POST','/api/machines/'+mid+'/vms/'+vm+'/'+action,payload))
        anyio.run(exercise)

    def test_create_vm_and_inventory_use_fixed_supported_contracts(self):
        from project_bots.mcp_server import create_server
        from mcp.server.mcpserver.exceptions import UnexpectedToolError
        calls = []
        class Client:
            def request(self, method, path, data=None):
                calls.append((method, path, data)); return {'ok': True}
        async def exercise():
            server=create_server(Client()); names=[t.name for t in await server.list_tools()]
            self.assertIn('create_vm',names)
            mid='11111111-1111-4111-8111-111111111111'; op='22222222-2222-4222-8222-222222222222'
            args={'machine_id':mid,'template':'ubuntu-24.04','cpus':1,'ram_mib':2048,'disk_gib':16,'ssh_key':'ssh-ed25519 public-test','operation_id':op,'confirmation':'yes'}
            with self.assertRaises(UnexpectedToolError):await server.call_tool('create_vm',args)
            self.assertEqual(calls,[])
            args['confirmation']='create'
            await server.call_tool('create_vm',args)
            self.assertEqual(calls[-1],('POST','/api/machines/'+mid+'/vms',{k:v for k,v in args.items() if k!='machine_id'}))
            for tool,args,path in [('list_models',{},'/api/models'),('loaded_models',{},'/api/models/loaded'),('worker_health',{'agent_id':mid},'/api/agents/'+mid+'/worker/health')]:
                await server.call_tool(tool,args);self.assertEqual(calls[-1],('GET',path,None))
        anyio.run(exercise)

    def test_initialize_list_call_authenticated_workers(self):
        self.assertIsNotNone(importlib.util.find_spec('project_bots.mcp_server'), 'MCP server missing')
        token = secrets.token_urlsafe(48)
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append((self.path, self.headers.get('Authorization')))
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
                self.wfile.write(json.dumps([{'agent_id': 'fixture-worker', 'status': 'verified'}]).encode())
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        async def exercise():
            params = StdioServerParameters(command=sys.executable, args=['-m', 'project_bots.mcp_server', '--endpoint', f'http://127.0.0.1:{server.server_port}', '--token-env', 'TEST_MCP_TOKEN'], cwd=ROOT, env={'TEST_MCP_TOKEN': token})
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    self.assertEqual(init.server_info.name, 'project-bots')
                    tools = await session.list_tools()
                    self.assertIn('list_workers', [t.name for t in tools.tools])
                    result = await session.call_tool('list_workers', {})
                    self.assertFalse(result.is_error)
                    self.assertEqual(result.structured_content, {'workers': [{'agent_id': 'fixture-worker', 'status': 'verified'}]})
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / 'token'
            token_file.write_text(token); token_file.chmod(0o600)
            async def exercise_file():
                params = StdioServerParameters(command=sys.executable, args=['-m', 'project_bots.mcp_server', '--endpoint', f'http://127.0.0.1:{server.server_port}', '--token-file', str(token_file)], cwd=ROOT)
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool('list_workers', {})
                        self.assertFalse(result.is_error)
            try:
                anyio.run(exercise)
                anyio.run(exercise_file)
                self.assertEqual(seen, [('/api/workers', 'Bearer ' + token)] * 2)
            finally:
                server.shutdown(); server.server_close(); thread.join()
