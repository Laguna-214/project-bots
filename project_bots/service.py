"""Platform application rules; no HTTP, inference, VM or worker execution."""
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

    def list(self, collection):
        return self.repository.list(collection)
