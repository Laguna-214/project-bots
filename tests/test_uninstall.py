import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UninstallTests(unittest.TestCase):
    def test_uninstall_removes_program_but_preserves_configuration(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home)
            install = subprocess.run(['sh', str(ROOT / 'install.sh')], env=env, capture_output=True, text=True)
            self.assertEqual(install.returncode, 0, install.stderr)
            bin_path = Path(home) / '.local/bin/project-bots'
            lib_path = Path(home) / '.local/lib/project-bots'
            config = Path(home) / '.config/project-bots/config.json'
            config.parent.mkdir(parents=True)
            config.write_text('{"provider":"ollama"}')
            unrelated = Path(home) / '.local/bin/my-other-tool'
            unrelated.write_text('keep')
            self.assertTrue(bin_path.exists())
            self.assertTrue(lib_path.exists())
            installed_uninstaller = Path(home) / '.local/bin/project-bots-uninstall'
            self.assertTrue(installed_uninstaller.is_file())

            uninstall = subprocess.run(['sh', str(installed_uninstaller)], env=env, capture_output=True, text=True)
            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
            self.assertFalse(installed_uninstaller.exists())
            self.assertFalse(bin_path.exists())
            self.assertFalse(lib_path.exists())
            self.assertTrue(config.exists())
            self.assertTrue(unrelated.exists())

            again = subprocess.run(['sh', str(ROOT / 'uninstall.sh')], env=env, capture_output=True, text=True)
            self.assertEqual(again.returncode, 0, again.stderr)

    def test_uninstall_refuses_unrecognized_installation(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home)
            bin_path = Path(home) / '.local/bin/project-bots'
            bin_path.parent.mkdir(parents=True)
            bin_path.write_text('unrelated program')
            uninstall = subprocess.run(['sh', str(ROOT / 'uninstall.sh')], env=env, capture_output=True, text=True)
            self.assertNotEqual(uninstall.returncode, 0)
            self.assertIn('not a Project Bots installation', uninstall.stderr)
            self.assertEqual(bin_path.read_text(), 'unrelated program')
