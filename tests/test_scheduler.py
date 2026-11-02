"""Durable inference admission across independent platform processes."""
import multiprocessing
from pathlib import Path
import tempfile
import time
import unittest

from project_bots.repository import SQLiteRepository
from project_bots import models


def contender(path, entered):
    gate = models.DurableAdmission(SQLiteRepository(path))
    with gate.slot(8192, 1, timeout=3):
        entered.set()


def crash_holder(path, entered):
    gate = models.DurableAdmission(SQLiteRepository(path))
    with gate.slot(8192, 1):
        entered.set()
        time.sleep(60)


class SchedulerTests(unittest.TestCase):
    def test_killed_process_does_not_release_possibly_running_remote_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private' / 'platform.db'
            gate = models.DurableAdmission(SQLiteRepository(path))
            entered = multiprocessing.Event()
            child = multiprocessing.Process(target=crash_holder, args=(str(path), entered))
            child.start()
            try:
                self.assertTrue(entered.wait(5))
            finally:
                child.terminate(); child.join(5)
            restarted = models.DurableAdmission(SQLiteRepository(path))
            with self.assertRaises(TimeoutError):
                with restarted.slot(8192, 1, timeout=.05): pass
            with restarted.repository.transaction() as db:
                self.assertEqual([row[0] for row in db.execute('SELECT state FROM inference_admission')], ['active'])

    def test_priority_fifo_timeout_and_uncertain_reservation_survive_restart(self):
        import threading
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private' / 'platform.db'
            gate = models.DurableAdmission(SQLiteRepository(path), queue_limit=2)
            entered = []
            def run(priority, label):
                other = models.DurableAdmission(SQLiteRepository(path))
                with other.slot(8192, priority, timeout=3):
                    entered.append(label)
            with gate.slot(8192, 10):
                low = threading.Thread(target=run, args=(50, 'low')); low.start()
                deadline = time.monotonic() + 3
                while gate.pending < 1 and time.monotonic() < deadline: time.sleep(.01)
                high = threading.Thread(target=run, args=(1, 'high')); high.start()
                deadline = time.monotonic() + 3
                while gate.pending < 2 and time.monotonic() < deadline: time.sleep(.01)
                with self.assertRaises(ValueError):
                    with gate.slot(8192, 0): pass
            low.join(5); high.join(5)
            self.assertEqual(entered, ['high', 'low'])
            with gate.slot(8192, 10) as lease:
                lease.retain()
            restarted = models.DurableAdmission(SQLiteRepository(path))
            with self.assertRaises(TimeoutError):
                with restarted.slot(8192, 1, timeout=.05): pass
            self.assertEqual(restarted.pending, 0)

    def test_platform_uses_shared_gate_and_retains_remote_uncertainty(self):
        from project_bots.service import PlatformService
        import uuid
        with tempfile.TemporaryDirectory() as directory:
            repo = SQLiteRepository(Path(directory) / 'private' / 'platform.db')
            service = PlatformService(repo)
            self.assertIsInstance(service.admission, models.DurableAdmission)
            agent = service.create_agent({'name': 'test', 'role': 'analyst'})
            profile = {'model': 'qwen3:1.7b', 'context': 32768, 'max_output': 256, 'temperature': .2, 'memory_mib': 4096, 'priority': 10}
            service.register_worker(agent['id'], {'vm_id': str(uuid.uuid4()), 'endpoint': 'http://127.0.0.1:19889', 'credential_env': 'WORKER_TOKEN', 'profile': profile})
            job = service.create_job({'title': 'timeout', 'input': 'test', 'agent_id': agent['id']})
            def timeout(*_): raise TimeoutError('remote may still run')
            service.dispatch_job(job['id'], {'confirmation': 'dispatch:' + job['id']}, timeout)
            with repo.transaction() as db:
                self.assertEqual([row[0] for row in db.execute('SELECT state FROM inference_admission')], ['uncertain'])

    def test_failed_receipt_storage_or_read_never_releases_remote_reservation(self):
        from project_bots.service import PlatformService
        from unittest.mock import patch
        import uuid
        with tempfile.TemporaryDirectory() as directory:
            repo=SQLiteRepository(Path(directory)/'private'/'p.db');service=PlatformService(repo)
            agent=service.create_agent({'name':'Storage failure','role':'ProjectWorker'})
            profile={'model':'qwen3:1.7b','context':32768,'max_output':256,'temperature':0,'memory_mib':8192,'priority':10}
            service.register_worker(agent['id'],{'vm_id':str(uuid.uuid4()),'endpoint':'http://127.0.0.1:19889','credential_env':'WORKER_TOKEN','profile':profile})
            job=service.create_job({'title':'Uncertain storage','input':'test','agent_id':agent['id']})
            def timeout(*_):raise TimeoutError('Remote may still run')
            with patch.object(repo,'finish_execution',side_effect=OSError('DB unavailable')),patch.object(repo,'execution',side_effect=OSError('DB read unavailable')):
                with self.assertRaises(OSError):service.dispatch_job(job['id'],{'confirmation':'dispatch:'+job['id']},timeout)
            with repo.transaction() as db:
                self.assertEqual([row[0] for row in db.execute('SELECT state FROM inference_admission')],['uncertain'])
            self.assertEqual(repo.execution(job['id'])['status'],'running')

    def test_independent_process_cannot_exceed_shared_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private' / 'platform.db'
            gate = models.DurableAdmission(SQLiteRepository(path))
            entered = multiprocessing.Event()
            with gate.slot(8192, 50):
                child = multiprocessing.Process(target=contender, args=(str(path), entered))
                child.start()
                try:
                    deadline = time.monotonic() + 3
                    while gate.pending != 1 and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertEqual(gate.pending, 1)
                    self.assertFalse(entered.is_set())
                except BaseException:
                    child.terminate(); child.join(3)
                    raise
            child.join(5)
            self.assertEqual(child.exitcode, 0)
            self.assertTrue(entered.is_set())


if __name__ == '__main__':
    unittest.main()
