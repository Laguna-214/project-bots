"""Read-only, loopback-only worker identity sidecar. No command/job/file API."""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import time
from .machine_client import MachineClient
from .machine_http import validate_listener
from .service import identifier


def observe(config_path, instance_path, boot_path, gateway_check):
    vm_id = identifier(Path(instance_path).read_text().strip())
    boot_id = identifier(Path(boot_path).read_text().strip())
    if not vm_id or not boot_id:
        raise ValueError('Missing VM instance or boot identity')
    config = json.loads(Path(config_path).read_text())
    gateway = config['gateway']
    provider = config['models']['providers']['llamacpp']
    defaults = config['agents']['defaults']
    primary = defaults['model']['primary']
    if gateway['bind'] != 'loopback' or gateway['auth']['mode'] != 'token' or provider['api'] != 'openai-completions' or provider['baseUrl'] != 'http://127.0.0.1:11434/v1' or defaults['model'].get('fallbacks') != []:
        raise ValueError('Worker isolation or native local model policy mismatch')
    if not primary.startswith('llamacpp/'):
        raise ValueError('Worker is not using the local llama.cpp provider')
    name = primary.removeprefix('llamacpp/')
    model = next(m for m in provider['models'] if m['id'] == name)
    if not any(m.get('id') == 'openclaw/default' for m in gateway_check()['data']):
        raise ValueError('Authenticated Gateway is not ready')
    return {'vm_id': vm_id, 'boot_id': boot_id, 'status': 'healthy', 'observed_at': time.time(),
            'model': name, 'context': model['contextWindow'], 'temperature': model['params']['temperature'],
            'max_output': model['maxTokens'], 'gateway_authenticated': True,
            'native_llamacpp': True, 'cloud_fallback': False}


def make_handler(token, observation):
    validate_listener('127.0.0.1', token, None, None)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def respond(self, status, data):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            from urllib.parse import urlsplit
            try:
                host = urlsplit('//' + self.headers.get('Host', ''))
                allowed_host = host.hostname in ('127.0.0.1', 'localhost', '::1') and host.port is not None and not host.username and not host.password and not host.path and not host.query and not host.fragment
            except ValueError:
                allowed_host = False
            if not allowed_host or any(k in self.headers for k in ('Origin', 'Sec-Fetch-Site')) or not hmac.compare_digest(self.headers.get('Authorization', '').encode(), ('Bearer '+token).encode()):
                self.respond(403, {'error': 'Forbidden'})
            elif self.path != '/v1/health':
                self.respond(404, {'error': 'Not found'})
            else:
                try:
                    self.respond(200, observation())
                except Exception:
                    self.respond(503, {'error': 'Worker identity or authenticated Gateway health unavailable'})

        def do_POST(self):
            self.respond(405, {'error': 'Read-only identity service'})
    return Handler


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18790)
    args = parser.parse_args()
    token = os.environ.get('OPENCLAW_GATEWAY_TOKEN', '')
    config_path = Path.home()/'.openclaw/openclaw.json'
    gateway = MachineClient('http://127.0.0.1:18789', token)
    observation = lambda: observe(config_path, '/var/lib/cloud/data/instance-id', '/proc/sys/kernel/random/boot_id', lambda: gateway.request('GET', '/v1/models'))
    with ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(token, observation)) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
