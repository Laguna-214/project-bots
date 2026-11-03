import os
import unittest
from unittest.mock import patch
from project_bots.compute import ComputeService

class CPUCapacityTests(unittest.TestCase):
    def test_explicit_aggregate_cpu_cap_preserves_host_reservation(self):
        backend=object.__new__(ComputeService)
        backend.host_resources=lambda:{'cpu_count':20,'memory_total_mib':62967,'storage_free_gib':810}
        for configured,expected in [('9',9),('100',18),('',8),('0',8),('invalid',8)]:
            with self.subTest(configured=configured), patch.dict(os.environ,{'PROJECT_BOTS_COMPUTE_CPU_CAP':configured}):
                self.assertEqual(backend.capacity()['cpus'],expected)
