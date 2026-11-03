"""One independently isolated OpenClaw Gateway; supported Responses HTTP only."""
import json
import os
from urllib.request import Request
from .machine_client import MachineClient
from .models import model_profile


def gateway_run(worker, job, *, repository=None):
    from .service import ConflictError
    from .security import check_agent_execution
    if repository is None:
        raise ConflictError('Trusted security repository required before Gateway dispatch')
    check_agent_execution(repository, worker.get('agent_id'))
    client = MachineClient(worker['endpoint'], os.environ.get(worker['credential_env'], ''))
    p = model_profile(worker['profile'])
    body = {'model': 'openclaw/default', 'input': job['input'], 'stream': False,
            'user': 'project-bots-job-' + job['id'], 'max_output_tokens': p['max_output'], 'temperature': p['temperature']}
    request = Request(client.endpoint + '/v1/responses', method='POST', data=json.dumps(body).encode(),
                      headers={'Authorization': 'Bearer ' + client.token, 'Content-Type': 'application/json'})
    with client.opener.open(request, timeout=300) as response:
        raw = response.read(2*1024*1024+1)
        if len(raw) > 2*1024*1024:
            raise ValueError('Gateway response too large')
        return json.loads(raw)


def role_presets():
    """Fresh source-owned presets; these never provision VMs or grant host access."""
    presets = {
        'ProjectWorker': {'instructions': 'Implement and test authorized project tasks inside this independent non-sudo VM. Do not assume access to other workers or management. Report concrete evidence. No cloud fallback.', 'allow': ['read', 'write', 'edit', 'apply_patch', 'exec', 'process', 'session_status'], 'deny': ['browser', 'gateway', 'nodes', 'message']},
        'Researcher': {'instructions': 'Research the supplied question, distinguish evidence from inference and cite sources. Do not publish, message, change infrastructure or use credentials without explicit authorization. No cloud fallback.', 'allow': ['read', 'web_fetch', 'browser', 'session_status'], 'deny': ['write', 'edit', 'apply_patch', 'exec', 'process', 'gateway', 'nodes', 'message']},
        'Reviewer': {'instructions': 'Review supplied workspace artifacts read-only. Identify defects and missing tests with evidence. Do not modify files, run commands or change infrastructure. No cloud fallback.', 'allow': ['read', 'session_status'], 'deny': ['write', 'edit', 'apply_patch', 'exec', 'process', 'browser', 'gateway', 'nodes', 'message']},
        'HomelabObserver': {'instructions': 'Analyze explicitly supplied homelab reports read-only. Only workspace report files are available; no live homelab credentials or remote command access are granted. Never change services, VMs, security policy, groups, devices, network or storage. Report observations and propose changes for separate human approval. No cloud fallback.', 'allow': ['read', 'session_status'], 'deny': ['write', 'edit', 'apply_patch', 'exec', 'process', 'browser', 'gateway', 'nodes', 'message']},
    }
    import copy
    presets['Programmer'] = copy.deepcopy(presets['ProjectWorker'])
    presets['HomelabEngineer'] = copy.deepcopy(presets['HomelabObserver'])
    return presets


def canonical_role(role):
    return {'Programmer': 'ProjectWorker', 'HomelabEngineer': 'HomelabObserver'}.get(role, role)


def role_instructions(role):
    try:
        return role_presets()[canonical_role(role)]['instructions']
    except (KeyError, TypeError):
        raise ValueError('Unknown role preset') from None


def worker_config(profile, role=None):
    p = model_profile(profile)
    config = {
        'gateway': {'mode': 'local', 'bind': 'loopback', 'port': 18789, 'auth': {'mode': 'token'},
                    'http': {'endpoints': {'responses': {'enabled': True, 'files': {'allowUrl': False}, 'images': {'allowUrl': False}}}}},
        'models': {'providers': {'llamacpp': {'baseUrl': 'http://127.0.0.1:11434/v1', 'apiKey': 'private-broker-required', 'api': 'openai-completions',
            'models': [{'id': p['model'], 'name': p['model'], 'contextWindow': p['context'], 'maxTokens': p['max_output'],
                        'params': {'temperature': p['temperature']}}]}}},
        'agents': {'defaults': {'workspace': '~/.openclaw/workspace', 'model': {'primary': 'llamacpp/'+p['model'], 'fallbacks': []},
            'skipBootstrap': True, 'maxConcurrent': 1, 'timeoutSeconds': 240}},
        'browser': {'enabled': True, 'headless': True, 'defaultProfile': 'openclaw'},
        'tools': {'profile': 'minimal', 'toolSearch': False, 'agentToAgent': {'enabled': False}, 'elevated': {'enabled': False}},
        'discovery': {'mdns': {'mode': 'off'}}
    }
    if role is not None:
        role_instructions(role)  # Validate before constructing a privileged tool surface.
        preset = role_presets()[canonical_role(role)]
        config['tools'].update(profile='full', allow=preset['allow'], deny=preset['deny'], fs={'workspaceOnly': True})
        config['browser']['enabled'] = 'browser' in preset['allow']
    return config
