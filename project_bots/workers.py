"""One independently isolated OpenClaw Gateway; supported Responses HTTP only."""
import json
import os
from urllib.request import Request
from .machine_client import MachineClient
from .models import model_profile


def gateway_run(worker, job):
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


def worker_config(profile):
    p = model_profile(profile)
    return {
        'gateway': {'mode': 'local', 'bind': 'loopback', 'port': 18789, 'auth': {'mode': 'token'},
                    'http': {'endpoints': {'responses': {'enabled': True, 'files': {'allowUrl': False}, 'images': {'allowUrl': False}}}}},
        'models': {'providers': {'ollama': {'baseUrl': 'http://127.0.0.1:11434', 'apiKey': 'ollama-local', 'api': 'ollama',
            'models': [{'id': p['model'], 'name': p['model'], 'contextWindow': p['context'], 'maxTokens': p['max_output'],
                        'params': {'num_ctx': p['context'], 'temperature': p['temperature'], 'thinking': False}}]}}},
        'agents': {'defaults': {'workspace': '~/.openclaw/workspace', 'model': {'primary': 'ollama/'+p['model'], 'fallbacks': []},
            'skipBootstrap': True, 'maxConcurrent': 1, 'timeoutSeconds': 240}},
        'browser': {'enabled': True, 'headless': True, 'defaultProfile': 'openclaw'},
        'tools': {'profile': 'minimal', 'agentToAgent': {'enabled': False}, 'elevated': {'enabled': False}},
        'discovery': {'mdns': {'mode': 'off'}}
    }
