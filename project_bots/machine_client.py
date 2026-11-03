"""Verified TLS (or explicit loopback SSH tunnel) management transport."""
import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler

from .compute import ComputeUnavailable
from .machine_http import loopback, validate_listener
from .service import endpoint, ConflictError, identifier, fields


def containment_request(repository, machine_id, method, route, data=None):
    """Trusted, registry-bound stop/readback only; no execution or shell channel."""
    import os
    parts = route.split('/')
    if identifier(machine_id) is None or len(parts) not in (2, 3) or parts[0] not in ('vms', 'operations') or identifier(parts[1]) is None:
        raise ValueError('Invalid containment target')
    if method == 'POST':
        if len(parts) != 3 or parts[0] != 'vms' or parts[2] not in ('shutdown', 'force-stop', 'network-block'):
            raise ValueError('Containment-only action required')
        fields(data, ('confirmation', 'operation_id'), ('confirmation', 'operation_id'))
        if data['confirmation'] != parts[2] + ':' + parts[1] or identifier(data['operation_id']) is None:
            raise ValueError('Exact containment confirmation and operation ID required')
    elif method != 'GET' or (len(parts) != 2 and not (len(parts) == 3 and parts[0] == 'vms' and parts[2] == 'network')) or data is not None:
        raise ValueError('Unsupported containment request')
    machine = next((m for m in repository.list('machines') if m['id'] == machine_id), None)
    if machine is None:
        raise LookupError('Machine not found')
    client = MachineClient(machine['endpoint'], os.environ.get(machine['credential_env'], ''), os.environ.get('PROJECT_BOTS_MACHINE_CA_FILE'))
    return client.request(method, '/v1/' + route, data)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class MachineClient:
    def __init__(self, address, token, ca_file=None):
        self.endpoint = endpoint(address).rstrip('/')
        parsed = urlsplit(self.endpoint)
        if parsed.path or (parsed.scheme == 'http' and not loopback(parsed.hostname)):
            raise ValueError('Use HTTPS or a loopback SSH tunnel, with no endpoint path')
        validate_listener('127.0.0.1', token, None, None)
        self.token = token
        try:
            context = ssl.create_default_context(cafile=ca_file)
        except (OSError, ValueError):
            raise ComputeUnavailable('Compute TLS trust configuration unavailable') from None
        self.opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPSHandler(context=context))

    def request(self, method, path, data=None):
        if method not in ('GET', 'POST') or not path.startswith('/v1/') or '?' in path or '#' in path:
            raise ValueError('Unsupported machine API route')
        body = None if data is None else json.dumps(data).encode()
        request = Request(self.endpoint + path, data=body, method=method,
                          headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=15) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise ValueError('Oversized compute response')
                return json.loads(raw)
        except HTTPError as exc:
            status = exc.code; exc.close()
            if status == 409:
                raise ConflictError('Compute operation conflicts or needs reconciliation') from None
            if status == 400:
                raise ValueError('Compute rejected request') from None
            if status == 404:
                raise LookupError('Compute resource not found') from None
            raise ComputeUnavailable('Compute HTTP request failed') from None
        except (OSError, URLError, ValueError):
            raise ComputeUnavailable('Compute unavailable or invalid response; retain operation ID and inspect before retry') from None
