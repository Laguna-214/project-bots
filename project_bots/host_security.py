"""Narrow Linux enforcement primitives, not a public command/PID service.

Trusted launchers bind an inherited namespace descriptor and owned Popen handle.
No worker/admin assertion can install a binding. No host firewall is ever edited.
A dedicated host integration must prove VM/backend membership before binding;
existing session-libvirt passt VMs are NOT implicitly namespace-contained.
"""
import json
import os
import signal
import subprocess


class OwnedProcess:
    """Disposable/launcher-owned child only, pinned against PID reuse via pidfd."""
    def __init__(self, child):
        if not isinstance(child, subprocess.Popen) or child.poll() is not None:
            raise ValueError('A live launcher-owned Popen child is required')
        self.child = child
        self.fd = os.pidfd_open(child.pid)

    def force_stop(self):
        if self.child.poll() is None:
            signal.pidfd_send_signal(self.fd, signal.SIGKILL)
            self.child.wait(timeout=5)
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        return {'terminated': self.child.poll() is not None, 'returncode': self.child.returncode,
                'source': 'pidfd SIGKILL and waitpid on launcher-owned child'}


class BoundNamespaceRuntime:
    """Trusted launcher binding for ONE disposable subprocess, not a VM adapter.

    Construct only after deny-all installation and before releasing untrusted work.
    Existing passt/libvirt domains cannot be bound by presenting a VM UUID here.
    Their launcher must independently prove emulator AND all networking backends
    reside inside the pinned namespace; that VM launch integration is not supplied.
    """
    def __init__(self, runtime_id, child, firewall):
        import uuid
        if str(uuid.UUID(runtime_id)) != runtime_id:
            raise ValueError('Canonical runtime UUID required')
        if not firewall.inspect()['blocked']:
            raise ValueError('Default deny must be installed before runtime binding')
        self.runtime_id = runtime_id
        self.firewall = firewall
        self.process = OwnedProcess(child)
        try:
            if os.stat('/proc/' + str(child.pid)).st_uid == os.geteuid():
                raise ValueError('Untrusted runtime must not share enforcer UID')
            if os.stat('/proc/' + str(child.pid) + '/ns/net').st_ino != firewall.inode:
                raise ValueError('Runtime network namespace does not match pinned boundary')
        except Exception:
            self.close()
            raise

    def close(self):
        if self.process.fd is not None:
            os.close(self.process.fd)
            self.process.fd = None

    def _target(self, runtime_id):
        if runtime_id != self.runtime_id:
            raise LookupError('Runtime not owned by this binding')

    def inspect(self, runtime_id):
        self._target(runtime_id)
        result = self.firewall.inspect()
        result.update(status='enforced' if result['blocked'] else 'bound', runtime_kind='subprocess',
                      runtime_terminated=self.process.child.poll() is not None)
        if self.process.child.poll() is None:
            try:
                if os.stat('/proc/' + str(self.process.child.pid) + '/ns/net').st_ino != self.firewall.inode:
                    result.update(blocked=False, status='bound', error_kind='NamespaceMismatch')
            except OSError:
                result.update(blocked=False, status='bound', error_kind='RuntimeObservationUnavailable')
        return result

    def block(self, runtime_id):
        self._target(runtime_id)
        self.firewall.block()
        result = self.inspect(runtime_id)
        if result['blocked'] is not True:
            raise RuntimeError('Runtime namespace/readback mismatch')
        return result

    def force_stop(self, runtime_id):
        self._target(runtime_id)
        return self.process.force_stop()


class NamespaceFirewall:
    """Pinned non-host netns; fixed IPv4/IPv6 deny-all, including loopback.

    Needs CAP_SYS_ADMIN for setns and CAP_NET_ADMIN *inside this namespace*.
    Rules are persistent on process death. No unblock/delete API: namespace
    retirement is the rollback, after owned runtime termination and admin review.
    """
    TABLE = 'project_bots_guard'

    def __init__(self, namespace_fd):
        self.fd = os.dup(namespace_fd)
        identity = os.fstat(self.fd)
        self.inode = identity.st_ino
        try:
            if (os.readlink('/proc/self/fd/' + str(self.fd)).split(':')[0] != 'net' or
                    self.inode == os.stat('/proc/1/ns/net').st_ino):
                raise ValueError('Only a pinned disposable/dedicated non-host network namespace is permitted')
        except Exception:
            self.close()
            raise

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _run(self, args, data=None):
        if self.fd is None:
            raise ValueError('Namespace descriptor closed')
        result = subprocess.run(['nsenter', '--net=/proc/self/fd/' + str(self.fd), '--', 'nft', *args],
                                input=data, capture_output=True, text=True, check=True,
                                pass_fds=(self.fd,), timeout=5,
                                env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})
        return result.stdout

    def inspect(self):
        try:
            entries = json.loads(self._run(['-j', 'list', 'table', 'inet', self.TABLE]))['nftables']
        except subprocess.CalledProcessError:
            # Missing table OR permission/monitor failure is never healthy.
            return {'blocked': False, 'namespace_inode': self.inode, 'source': 'nft readback unavailable'}
        chains = [x['chain'] for x in entries if 'chain' in x]
        rules = [x['rule'] for x in entries if 'rule' in x]
        valid = (len(chains) == 3 and {c.get('hook') for c in chains} == {'input', 'output', 'forward'}
                 and all(c.get('policy') == 'drop' and c.get('type') == 'filter' and c.get('prio') == 0 for c in chains)
                 and len(rules) == 3)
        packets = 0
        for rule in rules:
            expr = rule.get('expr', [])
            valid = valid and len(expr) == 2 and 'counter' in expr[0] and expr[1] == {'drop': None}
            if expr and 'counter' in expr[0]:
                packets += expr[0]['counter'].get('packets', 0)
        valid = valid and {r.get('chain') for r in rules} == {'input', 'output', 'forward'}
        return {'blocked': bool(valid), 'namespace_inode': self.inode, 'dropped_packets': packets,
                'source': 'kernel nftables JSON readback', 'table': self.TABLE}

    def block(self):
        if self.inspect()['blocked']:
            return self.inspect()
        # A single atomic nft transaction replaces only our table in a pinned
        # non-host namespace. Failure retains the prior transaction/rules.
        existing = json.loads(self._run(['-j', 'list', 'tables']))['nftables']
        present = any(x.get('table', {}).get('family') == 'inet' and x.get('table', {}).get('name') == self.TABLE for x in existing)
        script = ('delete table inet ' + self.TABLE + '\n') if present else ''
        script += 'table inet ' + self.TABLE + ' {\n'
        for hook in ('input', 'output', 'forward'):
            script += ' chain ' + hook + ' { type filter hook ' + hook + ' priority 0; policy drop; counter drop; }\n'
        script += '}\n'
        self._run(['-f', '-'], script)
        result = self.inspect()
        if not result['blocked']:
            raise RuntimeError('Network block readback failed; no containment claim')
        return result
