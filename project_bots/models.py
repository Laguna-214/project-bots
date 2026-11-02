"""Native local-only Ollama operations. No model or cloud fallback."""
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


def local_model(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}', name) or '..' in name or '://' in name or 'cloud' in name.lower():
        raise ValueError('A local model tag is required')
    return name


class NativeClient:
    """Unauthenticated daemon is allowed only on explicit local SSH loopback."""
    def __init__(self, address):
        from urllib.parse import urlsplit
        from urllib.request import build_opener, ProxyHandler
        from .machine_client import NoRedirect
        from .machine_http import loopback
        p = urlsplit(address)
        if p.scheme != 'http' or not loopback(p.hostname) or p.path or p.username or p.password or p.query or p.fragment:
            raise ValueError('Native Ollama must use private loopback without /v1')
        self.address = address
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, method, path, data=None):
        import json
        from urllib.request import Request
        routes = {'/api/tags':'GET', '/api/ps':'GET', '/api/show':'POST', '/api/pull':'POST', '/api/delete':'DELETE'}
        if routes.get(path) != method:
            raise ValueError('Unsupported native model operation')
        r = Request(self.address+path, data=None if data is None else json.dumps(data).encode(), method=method, headers={'Content-Type':'application/json'})
        with self.opener.open(r, timeout=600 if path=='/api/pull' else 15) as response:
            raw = response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024:
                raise ValueError('Oversized model response')
            return json.loads(raw) if raw.strip() else {}


class ModelManager:
    def __init__(self, request):
        self.request = request

    def tags(self):
        return self.request('GET', '/api/tags')

    def loaded(self):
        return self.request('GET', '/api/ps')

    def show(self, name):
        return self.request('POST', '/api/show', {'model': local_model(name)})

    def pull(self, name):
        return self.request('POST', '/api/pull', {'model': local_model(name), 'stream': False})

    def delete(self, name):
        return self.request('DELETE', '/api/delete', {'model': local_model(name)})


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
