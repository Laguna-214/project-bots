"""Real CLI SQLite backup/restore; temporary homes only, never production files."""
from contextlib import closing
from pathlib import Path
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.data = self.home / 'private'
        self.data.mkdir(mode=0o700)
        self.source = self.data / 'source.db'
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute('CREATE TABLE agents (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('CREATE TABLE jobs (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('INSERT INTO agents VALUES (?,?)', ('a', '{"name":"Private agent"}'))
            db.execute('PRAGMA user_version=4')
        self.source.chmod(0o600)
        self.env = dict(os.environ, HOME=str(self.home), PYTHONPATH=str(ROOT))

    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'project_bots.cli', *map(str, args)],
                              env=self.env, cwd=self.home, capture_output=True, text=True, timeout=10)

    def test_cli_backup_restore_preserves_committed_wal_state_and_schema(self):
        backup = self.data / 'backup.db'
        restored = self.data / 'restored.db'
        with closing(sqlite3.connect(self.source)) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('INSERT INTO agents VALUES (?,?)', ('b', '{"name":"Second agent"}'))
            writer.commit()
            result = self.cli('backup', '--database', self.source, '--output', backup)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli('restore', '--backup', backup, '--database', restored)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['operation'], 'restore')
        self.assertEqual(restored.stat().st_mode & 0o777, 0o600)
        with closing(sqlite3.connect(restored)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM agents').fetchone()[0], 2)
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 4)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertNotIn('Private agent', result.stdout + result.stderr)


    def test_refuses_overwrite_symlinks_corrupt_input_and_unsafe_permissions(self):
        existing = self.data / 'existing.db'
        existing.write_bytes(b'important-unrelated-data')
        existing.chmod(0o600)
        result = self.cli('restore', '--backup', self.source, '--database', existing)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(existing.read_bytes(), b'important-unrelated-data')
        link = self.data / 'link.db'
        link.symlink_to(self.source)
        self.assertEqual(self.cli('backup', '--database', link, '--output', self.data / 'no.db').returncode, 1)
        corrupt = self.data / 'corrupt.db'
        corrupt.write_bytes(b'not a sqlite database')
        corrupt.chmod(0o600)
        self.assertEqual(self.cli('restore', '--backup', corrupt, '--database', self.data / 'no.db').returncode, 1)
        self.assertFalse((self.data / 'no.db').exists())
        public = self.home / 'public'
        public.mkdir(mode=0o755)
        result = self.cli('backup', '--database', self.source, '--output', public / 'no.db')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(public.stat().st_mode & 0o777, 0o755)
        self.assertFalse((public / 'no.db').exists())
        self.source.chmod(0o644)
        self.assertEqual(self.cli('backup', '--database', self.source, '--output', self.data / 'no.db').returncode, 1)

    def test_installed_copy_commands_work_without_source_path(self):
        result = subprocess.run(['sh', str(ROOT / 'install.sh')], cwd=ROOT, env=self.env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = self.home / '.local/bin/project-bots'
        # No source path in subprocess environment or working directory.
        env = dict(self.env)
        env.pop('PYTHONPATH', None)
        result = subprocess.run([str(installed), 'backup', '--database', str(self.source),
                                 '--output', str(self.data / 'installed.db')], env=env,
                                cwd=self.home, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.data / 'installed.db').is_file())
        result = subprocess.run([str(installed), 'restore', '--backup', str(self.data / 'installed.db'),
                                 '--database', str(self.data / 'installed-restored.db')], env=env,
                                cwd=self.home, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
