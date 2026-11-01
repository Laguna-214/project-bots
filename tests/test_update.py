import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class UpdateTests(unittest.TestCase):
    def test_update_from_local_git_repo_preserves_config_and_tracks_revision(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repo, home = root / 'source', root / 'home'
            repo.mkdir()
            home.mkdir()
            shutil.copytree(ROOT / 'project_bots', repo / 'project_bots', ignore=shutil.ignore_patterns('__pycache__'))
            for name in ('install.sh', 'uninstall.sh'):
                shutil.copy2(ROOT / name, repo / name)
            def git(*args):
                return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()
            git('init', '-b', 'main')
            git('add', '.')
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-m', 'initial'], capture_output=True, check=True)
            revision = git('rev-parse', 'HEAD')
            env = dict(os.environ, HOME=str(home))
            install = subprocess.run(['sh', str(repo / 'install.sh')], env=env, capture_output=True, text=True)
            self.assertEqual(install.returncode, 0, install.stderr)
            installed = home / '.local/lib/project-bots'
            self.assertEqual((installed / 'REVISION').read_text().strip(), revision)
            config = home / '.config/project-bots/config.json'
            config.parent.mkdir(parents=True)
            config.write_text('my settings')
            (installed / 'REVISION').write_text('outdated\n')
            from project_bots.update import update
            with patch.dict(os.environ, {'HOME': str(home)}), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(update(repo_url=str(repo)), 0)
            self.assertIn('Updated', output.getvalue())
            self.assertEqual((installed / 'REVISION').read_text().strip(), revision)
            self.assertEqual(config.read_text(), 'my settings')
            with patch.dict(os.environ, {'HOME': str(home)}), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(update(repo_url=str(repo)), 0)
            self.assertIn('up to date', output.getvalue())

    def test_update_command_is_available(self):
        from project_bots.cli import main
        with contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as exit_status:
                main(['--help'])
        self.assertEqual(exit_status.exception.code, 0)
        self.assertIn('update', output.getvalue())
