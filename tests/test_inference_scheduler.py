"""Durable broker scheduling contracts, not GPU acceptance."""
import tempfile
import unittest
from pathlib import Path
from project_bots.repository import SQLiteRepository
from project_bots.models import DurableAdmission


class SchedulerTests(unittest.TestCase):
    def test_cli_exposes_safe_scheduler_configuration(self):
        import subprocess,sys
        result=subprocess.run([sys.executable,'-m','project_bots.inference_proxy','--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        for flag in ('--concurrency','--queue-limit','--queue-timeout','--request-timeout','--per-agent-active','--per-agent-queue','--requests-per-minute','--tokens-per-minute','--starvation-seconds','--requester-credentials','--admission-check'):
            self.assertIn(flag,result.stdout)

    def test_priority_fair_turns_and_starvation(self):
        import threading,time
        from project_bots.inference_scheduler import SharedScheduler
        for starvation,expected in ((5,['interactive','batch','repeat']),(.01,['repeat','batch','interactive'])):
            with self.subTest(starvation=starvation), tempfile.TemporaryDirectory() as t:
                repo=SQLiteRepository(Path(t)/'private'/'gate.db')
                gate=DurableAdmission(repo,queue_limit=8)
                scheduler=SharedScheduler(gate,starvation_seconds=starvation)
                order=[];errors=[];threads=[]
                def work(agent,priority,label):
                    try:
                        with scheduler.slot(agent,2048,priority,100):order.append(label)
                    except Exception as exc:errors.append(exc)
                with scheduler.slot('a',2048,10,100):
                    for agent,priority,label in [('a',0,'repeat'),('b',90,'batch'),('c',1,'interactive')]:
                        thread=threading.Thread(target=work,args=(agent,priority,label));thread.start();threads.append(thread)
                        deadline=time.monotonic()+2
                        while gate.pending<len(threads) and time.monotonic()<deadline:time.sleep(.005)
                        self.assertEqual(gate.pending,len(threads))
                    if starvation<1:time.sleep(.03)
                for thread in threads:thread.join(3);self.assertFalse(thread.is_alive())
                self.assertEqual(errors,[])
                self.assertEqual(order,expected)

    def test_process_crash_preserves_active_reservation(self):
        import subprocess,sys
        from project_bots.inference_scheduler import SharedScheduler
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'private'/'gate.db'
            repo=SQLiteRepository(path)
            script="""import os,sys
from project_bots.repository import SQLiteRepository
from project_bots.models import DurableAdmission
from project_bots.inference_scheduler import SharedScheduler
scheduler=SharedScheduler(DurableAdmission(SQLiteRepository(sys.argv[1])))
with scheduler.slot('crashed-agent',8192,10,100):
    os._exit(0)
"""
            result=subprocess.run([sys.executable,'-c',script,str(path)],capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            with repo.transaction() as db:self.assertEqual(db.execute('SELECT state FROM inference_admission').fetchone()[0],'active')
            with self.assertRaises(TimeoutError):
                with SharedScheduler(DurableAdmission(repo),queue_timeout=.04).slot('other',8192,10,100):self.fail('released crashed work')

    def test_retained_work_blocks_new_scheduler_after_restart(self):
        from project_bots.inference_scheduler import SharedScheduler
        with tempfile.TemporaryDirectory() as t:
            repo = SQLiteRepository(Path(t)/'private'/'gate.db')
            scheduler = SharedScheduler(DurableAdmission(repo), queue_timeout=.05)
            with scheduler.slot('a', 8192, 10, 100) as lease:
                lease.retain()
            restarted = SharedScheduler(DurableAdmission(repo), queue_timeout=.05)
            with self.assertRaises(TimeoutError):
                with restarted.slot('b', 8192, 10, 100):
                    self.fail('uncertain backend work was released')
            with repo.transaction() as db:
                self.assertEqual(db.execute("SELECT state FROM inference_admission").fetchone()[0], 'uncertain')
