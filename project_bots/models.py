"""Local llama.cpp broker operations. No model or cloud fallback."""
import re
import threading
import itertools
from contextlib import contextmanager


class Admission:
    """Single-process bounded priority/FIFO admission, not a VRAM measurement."""
    def __init__(self, memory_mib=8192, concurrency=1, queue_limit=4):
        self.memory_mib, self.concurrency, self.queue_limit = memory_mib, concurrency, queue_limit
        self.condition = threading.Condition()
        self.waiters = []
        self.sequence = itertools.count()
        self.active = self.reserved = 0

    @property
    def pending(self):
        with self.condition:
            return len(self.waiters)

    @contextmanager
    def slot(self, memory_mib, priority):
        with self.condition:
            if type(memory_mib) is not int or not 0 < memory_mib <= self.memory_mib or len(self.waiters) >= self.queue_limit:
                raise ValueError('Inference admission budget or queue exceeded')
            ticket = (priority, next(self.sequence))
            self.waiters.append(ticket)
            try:
                self.condition.wait_for(lambda: ticket == min(self.waiters) and self.active < self.concurrency and self.reserved + memory_mib <= self.memory_mib)
            except BaseException:
                self.waiters.remove(ticket)
                self.condition.notify_all()
                raise
            self.waiters.remove(ticket)
            self.active += 1
            self.reserved += memory_mib
        try:
            yield
        finally:
            with self.condition:
                self.active -= 1
                self.reserved -= memory_mib
                self.condition.notify_all()


class DurableAdmission:
    """SQLite priority/FIFO gate shared by processes using the same platform DB.

    Active leases deliberately never expire: a dead HTTP client does not stop
    remote inference. An interrupted/uncertain lease requires local reconciliation.
    This bounds reservations, not measured host RAM or VRAM.
    """
    def __init__(self, repository, memory_mib=8192, concurrency=1, queue_limit=4):
        self.repository = repository
        self.memory_mib, self.concurrency, self.queue_limit = memory_mib, concurrency, queue_limit

    @property
    def pending(self):
        return self.repository.admission_pending()

    @contextmanager
    def slot(self, memory_mib, priority, timeout: float = 30):
        import time
        import uuid
        if type(memory_mib) is not int or not 0 < memory_mib <= self.memory_mib:
            raise ValueError('Inference admission budget exceeded')
        if type(priority) is not int or not 0 <= priority <= 100 or not 0 < timeout <= 300:
            raise ValueError('Invalid admission priority or deadline')
        ticket = str(uuid.uuid4())
        self.repository.admission_enqueue(ticket, memory_mib, priority, time.time() + timeout, self.queue_limit)
        class Lease:
            uncertain = False
            def retain(self):
                self.uncertain = True
        lease = Lease()
        deadline = time.monotonic() + timeout
        try:
            while not self.repository.admission_acquire(ticket, self.memory_mib, self.concurrency):
                if time.monotonic() >= deadline:
                    raise TimeoutError('Inference admission timed out before remote dispatch')
                time.sleep(.02)
            yield lease
        finally:
            self.repository.admission_release(ticket, lease.uncertain)


def local_model(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}', name) or '..' in name or '://' in name or 'cloud' in name.lower():
        raise ValueError('A local model tag is required')
    return name


class NativeClient:
    """Unauthenticated daemon is allowed only on explicit local SSH loopback."""
    def __init__(self, address, token_env=None):
        from urllib.parse import urlsplit
        from urllib.request import build_opener, ProxyHandler
        from .machine_client import NoRedirect
        from .machine_http import loopback
        p = urlsplit(address)
        if p.scheme != 'http' or not loopback(p.hostname) or p.path or p.username or p.password or p.query or p.fragment:
            raise ValueError('llama.cpp broker must use private loopback without /v1')
        self.address = address
        import os
        self.token = os.environ.get(token_env, '') if token_env else ''
        if token_env and not self.token:
            raise ValueError('Missing native broker credential')
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, method, path, data=None):
        import json
        from urllib.request import Request
        routes = {'/management/models':'GET' if method == 'GET' else 'DELETE', '/management/loaded':'GET', '/management/show':'POST', '/management/download':'POST', '/models':'GET', '/models?reload=1':'GET', '/models/load':'POST', '/models/unload':'POST'}
        if routes.get(path) != method:
            raise ValueError('Unsupported native model operation')
        headers = {'Content-Type':'application/json'}
        if self.token:
            headers['Authorization'] = 'Bearer '+self.token
        r = Request(self.address+path, data=None if data is None else json.dumps(data).encode(), method=method, headers=headers)
        with self.opener.open(r, timeout=300 if path in ('/models/load', '/management/download') else 15) as response:
            raw = response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024:
                raise ValueError('Oversized model response')
            return json.loads(raw) if raw.strip() else {}


def router_transition(request, name, action, poll_interval=.1):
    """The router's acknowledgment is asynchronous; retain lease until readback."""
    import time
    if action not in ('load', 'unload'):
        raise ValueError('Unsupported router transition')
    current = request('GET', '/models')['data']
    target = 'loaded' if action == 'load' else 'unloaded'
    if any(m['id'] == name and m['status']['value'] == target for m in current):
        return {'success': True, 'already': True}
    result = request('POST', '/models/' + action, {'model': local_model(name)})
    deadline = time.monotonic() + 120
    while True:
        models = request('GET', '/models')['data']
        item = next((m for m in models if m['id'] == name), None)
        if item and item['status']['value'] == ('loaded' if action == 'load' else 'unloaded'):
            return result
        if time.monotonic() >= deadline:
            raise TimeoutError('Router state transition uncertain')
        time.sleep(poll_interval)


class ModelManager:
    def __init__(self, request):
        self.request = request

    def tags(self):
        return self.request('GET', '/management/models', None)

    def loaded(self):
        return self.request('GET', '/management/loaded', None)

    def show(self, name):
        return self.request('POST', '/management/show', {'model': local_model(name)})

    def pull(self, name):
        return self.request('POST', '/management/download', {'model': local_model(name)})

    def load(self, name):
        return self.request('POST', '/models/load', {'model': local_model(name)})

    def unload(self, name):
        return self.request('POST', '/models/unload', {'model': local_model(name)})

    def delete(self, name):
        return self.request('DELETE', '/management/models', {'model': local_model(name)})


def memory_required_mib(info, weights_bytes, context, loaded_bytes=0):
    """Conservative dense-transformer reservation, not an OS/VRAM hard quota.

    Budget full FP16 KV cache, 25% model/KV overhead and 1 GiB workspace.
    Unknown cache geometry fails closed; measured loaded size can raise the floor.
    """
    if not isinstance(info, dict) or not isinstance(info.get('general.architecture'), str):
        raise ValueError('Model cache geometry unavailable; cannot budget safely')
    architecture = info['general.architecture']
    geometry = [info.get(architecture + '.' + key) for key in ('block_count', 'attention.head_count_kv', 'attention.key_length', 'attention.value_length')]
    if any(type(n) is not int or not 0 < n <= 65536 for n in geometry):
        raise ValueError('Model cache geometry unavailable; cannot budget safely')
    if type(weights_bytes) is not int or weights_bytes <= 0 or type(loaded_bytes) is not int or loaded_bytes < 0 or type(context) is not int or not 2048 <= context <= 131072:
        raise ValueError('Invalid model memory observation')
    layers, heads, keys, values = geometry
    kv_bytes = layers * heads * (keys + values) * 2 * context
    estimated = (weights_bytes + kv_bytes) * 5 // 4 + 1024**3
    observed = loaded_bytes * 5 // 4 + 512 * 1024**2 if loaded_bytes else 0
    return (max(estimated, observed) + 1024**2 - 1) // 1024**2


def model_profile(data):
    import math
    from .service import fields
    fields(data, ('model', 'context', 'temperature', 'max_output', 'memory_mib', 'priority'), ('model', 'context', 'temperature', 'max_output', 'memory_mib', 'priority'))
    local_model(data['model'])
    for key, low, high in [('context', 2048, 131072), ('max_output', 1, data['context']), ('memory_mib', 512, 65536), ('priority', 0, 100)]:
        if type(data[key]) is not int or not low <= data[key] <= high:
            raise ValueError('Invalid model profile bound')
    t = data['temperature']
    if type(t) not in (int, float) or not math.isfinite(t) or not 0 <= t <= 2:
        raise ValueError('Invalid temperature')
    return dict(data)
