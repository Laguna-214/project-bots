"""Deterministic Linux sensor fixtures, not GPU offload proof."""
from pathlib import Path
import tempfile
import unittest

class TelemetryTests(unittest.TestCase):
    def test_cpu_delta_and_amd_sensor_values(self):
        from project_bots.telemetry import collect_metrics
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); proc=root/'proc'; proc.mkdir(); drm=root/'drm'; drm.mkdir()
            (proc/'stat').write_text('cpu 100 0 50 850 0 0 0 0 0 0\n')
            dev=drm/'card1'/'device';dev.mkdir(parents=True)
            for name,value in {'vendor':'0x1002','gpu_busy_percent':'37','mem_info_vram_total':'17179869184','mem_info_vram_used':'2147483648'}.items(): (dev/name).write_text(value)
            def advance(_): (proc/'stat').write_text('cpu 120 0 60 920 0 0 0 0 0 0\n')
            result=collect_metrics(proc,drm,sleep=advance)
            self.assertEqual(result['cpu']['busy_percent'],30.0)
            self.assertEqual(result['gpus'][0]['busy_percent'],37)
            self.assertEqual(result['gpus'][0]['vram_used_bytes'],2147483648)
            self.assertEqual(result['gpus'][0]['status'],'available')
            self.assertIn('not proof',result['notice'])
    def test_missing_sensors_are_unavailable_not_idle_or_protected(self):
        from project_bots.telemetry import collect_metrics
        with tempfile.TemporaryDirectory() as folder:
            result=collect_metrics(Path(folder)/'missing-proc',Path(folder)/'missing-drm',sleep=lambda _:None)
            self.assertEqual(result['cpu']['status'],'unavailable')
            self.assertIsNone(result['cpu']['busy_percent'])
            self.assertEqual(result['gpus'],[])
            self.assertEqual(result['gpu_status'],'unavailable')
