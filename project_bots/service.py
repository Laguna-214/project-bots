"""Platform rules, explicit compute operations and verified local worker execution."""
import re
import uuid
from urllib.parse import urlsplit


def fields(data, allowed, required=()):
    if not isinstance(data, dict) or data.keys() - set(allowed) or set(required) - data.keys():
        raise ValueError('Invalid or missing fields')
    return data


def text(value, limit=200, multiline=False):
    allowed_controls = '\n\t\r' if multiline else ''
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 and c not in allowed_controls for c in value):
        raise ValueError('Invalid text field')
    return value


def identifier(value):
    if value is None:
        return None
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError('Invalid UUID reference') from None
    return value


def env_reference(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Z_][A-Z0-9_]{0,127}', value):
        raise ValueError('Expected environment variable name, not a credential value')
    return value


def endpoint(value):
    text(value, 2048)
    try:
        parsed = urlsplit(value)
        if any(c.isspace() for c in value) or parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port == 0:
            raise ValueError
    except ValueError:
        raise ValueError('Expected HTTP(S) endpoint without credentials, query or fragment') from None
    return value


def agent_config(value):
    # Intentionally narrow: references, not arbitrary secret-bearing provider blobs.
    fields(value, ('model', 'credential_env', 'instructions'))
    result = {}
    for key, item in value.items():
        result[key] = env_reference(item) if key == 'credential_env' else text(item, 4000 if key == 'instructions' else 200, multiline=key == 'instructions')
    return result


class ConflictError(Exception):
    """A well-formed operation conflicts with the durable job state."""


class PlatformService:
    def __init__(self, repository):
        self.repository = repository
        from .models import DurableAdmission
        self.admission = DurableAdmission(repository)

    def create_machine(self, data):
        fields(data, ('name', 'endpoint', 'credential_env'), ('name', 'endpoint'))
        machine = {'id': str(uuid.uuid4()), 'name': text(data['name']), 'endpoint': endpoint(data['endpoint']), 'status': 'unverified', 'credential_env': None}
        if data.get('credential_env') is not None:
            machine['credential_env'] = env_reference(data['credential_env'])
        return self.repository.insert_machine(machine)

    def create_agent(self, data):
        fields(data, ('name', 'role', 'config', 'machine_id'), ('name', 'role'))
        agent = {'id': str(uuid.uuid4()), 'name': text(data['name']), 'role': text(data['role']), 'config': agent_config(data.get('config', {})), 'machine_id': identifier(data.get('machine_id')), 'status': 'registered'}
        return self.repository.insert_agent(agent)

    def get_settings(self):
        return self.repository.get_settings() or {'inference_endpoint': 'http://127.0.0.1:11434', 'machine_api_env': 'PROJECT_BOTS_API_TOKEN', 'cloud_fallback': False}

    def save_settings(self, data):
        fields(data, ('inference_endpoint', 'machine_api_env', 'cloud_fallback'), ('inference_endpoint', 'machine_api_env', 'cloud_fallback'))
        if data['cloud_fallback'] is not False:
            raise ValueError('Cloud fallback is not implemented and must remain disabled')
        return self.repository.save_settings({'inference_endpoint': endpoint(data['inference_endpoint']), 'machine_api_env': env_reference(data['machine_api_env']), 'cloud_fallback': False})

    def create_job(self, data):
        fields(data, ('title', 'input', 'agent_id'), ('title', 'input'))
        return self.repository.insert_job({'id': str(uuid.uuid4()), 'title': text(data['title']), 'input': text(data['input'], 16000, multiline=True), 'agent_id': identifier(data.get('agent_id')), 'status': 'queued', 'progress': 0, 'message': '', 'result': None, 'error': None})

    def get_job(self, job_id):
        identifier(job_id)
        return self.repository.get_job(job_id)

    def job_action(self, job_id, action, data):
        identifier(job_id)
        allowed_states = {'assign': ('queued',), 'claim': ('queued',), 'progress': ('running',), 'complete': ('running',), 'fail': ('running',), 'cancel': ('queued', 'running')}
        if action not in allowed_states:
            raise ValueError('Unknown job action')
        def change(job):
            if job['status'] not in allowed_states[action]:
                raise ConflictError('Job state does not allow this action')
            if action == 'assign':
                fields(data, ('agent_id',), ('agent_id',))
                job['agent_id'] = identifier(data['agent_id'])
            elif action == 'claim':
                fields(data, ('agent_id',), ('agent_id',))
                agent_id = identifier(data['agent_id'])
                if agent_id is None:
                    raise ValueError('Claim requires agent_id')
                if job['agent_id'] not in (None, agent_id):
                    raise ConflictError('Job is assigned to another agent')
                job['agent_id'] = agent_id
                job['status'] = 'running'
            elif action == 'progress':
                fields(data, ('progress', 'message'), ('progress',))
                progress = data['progress']
                if type(progress) is not int or not 0 <= progress <= 100:
                    raise ValueError('Progress must be an integer from 0 to 100')
                if progress < job['progress']:
                    raise ConflictError('Progress cannot decrease')
                job['progress'] = progress
                if 'message' in data:
                    if not isinstance(data['message'], str):
                        raise ValueError('Message must be text')
                    job['message'] = text(data['message'], 4000, multiline=True) if data['message'] else ''
            elif action == 'complete':
                fields(data, ('result',), ('result',))
                job.update(status='succeeded', result=text(data['result'], 16000, multiline=True), progress=100)
            elif action == 'fail':
                fields(data, ('error',), ('error',))
                job.update(status='failed', error=text(data['error'], 4000))
            elif action == 'cancel':
                fields(data, ())
                job['status'] = 'canceled'
            return job
        return self.repository.mutate_job(job_id, change)

    def compute_request(self, machine_id, method, route, data=None):
        import os
        from .machine_client import MachineClient
        identifier(machine_id)
        machine = next((m for m in self.repository.list('machines') if m['id'] == machine_id), None)
        if machine is None:
            raise LookupError('Machine not found')
        parts = route.split('/')
        if method == 'POST':
            if route == 'vms':
                expected = 'create'
            elif len(parts) == 3 and parts[0] == 'vms' and parts[2] in ('start', 'shutdown', 'restart', 'pause', 'resume', 'delete', 'resources', 'snapshot-create', 'snapshot-restore'):
                identifier(parts[1]); expected = parts[2] + ':' + parts[1]
            else:
                raise ValueError('Unsupported compute action')
            if not isinstance(data, dict) or data.get('confirmation') != expected or identifier(data.get('operation_id')) is None:
                raise ValueError('Explicit action confirmation and operation UUID required')
        elif method == 'GET':
            if route not in ('health', 'vms'):
                if len(parts) != 2 or parts[0] not in ('vms', 'operations') or identifier(parts[1]) is None:
                    raise ValueError('Unsupported compute route')
        else:
            raise ValueError('Unsupported method')
        reference = machine['credential_env']
        if not reference:
            raise ValueError('Configure a compute credential environment reference')
        client = MachineClient(machine['endpoint'], os.environ.get(reference, ''), os.environ.get('PROJECT_BOTS_MACHINE_CA_FILE'))
        return client.request(method, '/v1/' + route, data)

    def register_worker(self, agent_id, data):
        from .models import model_profile
        from .machine_client import MachineClient
        identifier(agent_id)
        fields(data, ('vm_id', 'endpoint', 'credential_env', 'profile', 'identity_endpoint'), ('vm_id', 'endpoint', 'credential_env', 'profile'))
        if identifier(data['vm_id']) is None:
            raise ValueError('VM UUID required')
        # Validate transport without resolving or contacting the configured host.
        MachineClient(data['endpoint'], 'validation-only-' + '0123456789abcdef'*3)
        worker = {'agent_id': agent_id, 'vm_id': data['vm_id'], 'endpoint': data['endpoint'],
            'credential_env': env_reference(data['credential_env']), 'profile': model_profile(data['profile']), 'status': 'configured'}
        if data.get('identity_endpoint'):
            MachineClient(data['identity_endpoint'], 'validation-only-' + '0123456789abcdef'*3)
            worker['identity_endpoint'] = data['identity_endpoint']
            worker['health'] = self.check_worker_identity(worker)
            worker['status'] = 'verified'
        return self.repository.save_worker(worker)

    def check_worker_identity(self, worker):
        import os,time
        from .machine_client import MachineClient
        agent = next((a for a in self.repository.list('agents') if a['id'] == worker['agent_id']), None)
        if not agent or not agent['machine_id'] or not worker.get('identity_endpoint'):
            raise ConflictError('Assign a compute machine and configure authenticated worker identity before real dispatch')
        vm = self.compute_request(agent['machine_id'], 'GET', 'vms/' + worker['vm_id'])
        if vm.get('id') != worker['vm_id'] or vm.get('state') != 'running':
            raise ConflictError('Worker VM identity or running state is not verified by compute')
        token = os.environ.get(worker['credential_env'], '')
        observation = MachineClient(worker['identity_endpoint'], token).request('GET', '/v1/health')
        try:
            valid = (observation['vm_id'] == worker['vm_id'] and identifier(observation['boot_id']) is not None
                and observation['status'] == 'healthy' and abs(time.time() - observation['observed_at']) <= 30
                and observation['gateway_authenticated'] is True and observation['native_llamacpp'] is True
                and observation['cloud_fallback'] is False
                and all(observation[key] == worker['profile'][key] for key in ('model','context','temperature','max_output')))
            if not valid:
                raise ConflictError('Worker identity, freshness or deployed model profile mismatch')
            gateway = MachineClient(worker['endpoint'], token).request('GET', '/v1/models')
            if not any(m.get('id') == 'openclaw/default' for m in gateway['data']):
                raise ConflictError('Configured Gateway is not authenticated and ready')
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ConflictError('Worker identity observation is incomplete or invalid') from None
        return {key: observation[key] for key in ('vm_id', 'boot_id', 'status', 'observed_at', 'model', 'context', 'temperature', 'max_output', 'gateway_authenticated', 'native_llamacpp', 'cloud_fallback')}

    def dispatch_job(self, job_id, data, runner=None):
        fields(data, ('confirmation',), ('confirmation',))
        identifier(job_id)
        if data['confirmation'] != 'dispatch:' + job_id:
            raise ValueError('Explicit dispatch confirmation required')
        job = self.repository.get_job(job_id)
        worker = self.repository.worker(job['agent_id'])
        self.repository.assert_worker_idle(worker['agent_id'])
        real_gateway = runner is None
        if real_gateway:
            from .workers import gateway_run
            runner = gateway_run
        with self.admission.slot(worker['profile']['memory_mib'], worker['profile']['priority']) as lease:
            if real_gateway:
                self.check_worker_model(worker)
                self.check_worker_identity(worker)
            try:
                result = self._dispatch_admitted(job_id, worker, runner)
                if self.repository.execution(job_id)['status'] == 'uncertain':
                    lease.retain()
                return result
            except BaseException:
                # Failed receipt persistence/read cannot prove remote work stopped.
                lease.retain()
                receipt = self.repository.execution(job_id)
                if not receipt or receipt['status'] not in ('running', 'uncertain'):
                    lease.uncertain = False
                raise

    def check_worker_model(self, worker):
        import os
        from .models import ModelManager, NativeClient, memory_required_mib
        from .compute import ComputeUnavailable
        address = os.environ.get('PROJECT_BOTS_LLAMA_ENDPOINT')
        if not address:
            raise ValueError('Configure the private shared model endpoint before real dispatch')
        manager = ModelManager(NativeClient(address, token_env=os.environ.get('PROJECT_BOTS_LLAMA_TOKEN_ENV')).request)
        profile = worker['profile']
        try:
            inventory = manager.tags()['models']
            model = next((m for m in inventory if m.get('name') == profile['model']), None)
            if model is None:
                raise ValueError('Assigned local model is not installed; no automatic pull or fallback')
            details = manager.show(profile['model'])
            if 'tools' not in details.get('capabilities', []):
                raise ValueError('Assigned model has no verified native tool capability')
            loaded = manager.loaded()['models']
            matching = [m for m in loaded if m.get('name') == profile['model']]
            if any(m.get('context_length') != profile['context'] for m in matching):
                raise ValueError('Loaded model context differs from the worker profile')
            required = memory_required_mib(details.get('model_info'), model.get('size'), profile['context'], max((m.get('size', 0) for m in matching), default=0))
            other_bytes = [m.get('size') for m in loaded if m.get('name') != profile['model']]
            if any(type(size) is not int or size <= 0 for size in other_bytes):
                raise ValueError('Loaded model memory observation unavailable')
            required += (sum(other_bytes) * 5 // 4 + 1024**2 - 1) // 1024**2
            if required > profile['memory_mib']:
                raise ValueError('Worker reservation cannot cover model weights, context cache and headroom')
            return {'required_mib': required, 'reserved_mib': profile['memory_mib']}
        except OSError:
            raise ComputeUnavailable('Model preflight unavailable; no remote job dispatched') from None
        except (KeyError, TypeError, AttributeError):
            raise ValueError('Model resource observation is incomplete; no remote job dispatched') from None

    def _dispatch_admitted(self, job_id, worker, runner):
        job = self.repository.begin_execution(job_id, worker)
        try:
            response = runner(worker, job)
        except Exception:
            return self.repository.finish_execution(job_id, 'uncertain')
        try:
            output = '\n'.join(part['text'] for item in response['output'] if item.get('type') == 'message' for part in item.get('content', []) if part.get('type') == 'output_text')
            if response['status'] != 'completed' or not output.strip() or len(output) > 16000:
                return self.repository.finish_execution(job_id, 'failed', response_id=response.get('id'))
            return self.repository.finish_execution(job_id, 'succeeded', text(output,16000,multiline=True), response.get('id'))
        except (KeyError, TypeError, ValueError, AttributeError):
            return self.repository.finish_execution(job_id, 'uncertain')

    def model_request(self, action, data=None):
        import os
        from .models import ModelManager, NativeClient, local_model
        from .compute import ComputeUnavailable
        if action not in ('tags', 'loaded', 'show', 'pull', 'delete', 'unload', 'load'):
            raise ValueError('Unknown model operation')
        if action in ('show', 'pull', 'delete', 'unload', 'load'):
            fields(data, ('model', 'confirmation') if action != 'show' else ('model',), ('model',))
            name = local_model(data['model'])
            if action != 'show' and data.get('confirmation') != action + ':' + name:
                raise ValueError('Explicit model confirmation required')
            if action == 'delete' and any(w['profile']['model'] == name for w in self.repository.list('workers')):
                raise ConflictError('Model is assigned to a worker')
        address = os.environ.get('PROJECT_BOTS_LLAMA_ENDPOINT')
        if not address:
            raise ValueError('Configure a private llama.cpp broker endpoint in service environment')
        manager = ModelManager(NativeClient(address, token_env=os.environ.get('PROJECT_BOTS_LLAMA_TOKEN_ENV')).request)
        try:
            if action in ('tags', 'loaded'):
                return getattr(manager, action)()
            if action == 'show':
                return manager.show(name)
            with self.admission.slot(8192, 50) as lease:
                try:
                    return getattr(manager, action)(name)
                except BaseException:
                    lease.retain()
                    raise
        except (OSError, ValueError):
            raise ComputeUnavailable('Local model service unavailable; inspect before retrying model mutations') from None

    def list(self, collection):
        return self.repository.list(collection)
