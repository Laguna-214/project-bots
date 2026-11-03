"""Administrator-local consistent SQLite copies; never overwrite an existing database.

Backups contain sensitive history. These operations do not include worker disks,
model files or environment secrets and must run outside untrusted worker accounts.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile


def _private_parent(path):
    parent = path.parent
    info = parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Use an existing caller-owned private directory (0700)')


def _source(path):
    _private_parent(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Source must be a caller-owned private regular database (0600)')
    return info


def _validate(db):
    db.execute('PRAGMA trusted_schema=OFF')
    if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise ValueError('Database integrity validation failed')
    if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise ValueError('Database foreign-key validation failed')
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'agents', 'jobs'} <= tables or db.execute('PRAGMA user_version').fetchone()[0] < 1:
        raise ValueError('Source is not a recognized Project Bots database')


def copy_database(source, destination, operation):
    if operation not in ('backup', 'restore'):
        raise ValueError('Unknown copy operation')
    source, destination = Path(source).expanduser().absolute(), Path(destination).expanduser().absolute()
    original = _source(source)
    _private_parent(destination)
    if os.path.lexists(destination):
        raise ValueError('Destination already exists; restore only to a new offline database path')
    fd, temporary = tempfile.mkstemp(prefix='.project-bots-copy-', suffix='.db', dir=destination.parent)
    try:
        os.fchmod(fd, 0o600)
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=5)) as src:
            _validate(src)
            with closing(sqlite3.connect(temporary)) as dst:
                src.backup(dst)
                _validate(dst)
                dst.commit()
        current = source.lstat()
        if (original.st_dev, original.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError('Source identity changed during copy')
        os.fsync(fd)
        # Atomic exclusive publication; concurrent callers never overwrite.
        os.link(temporary, destination, follow_symlinks=False)
        directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.close(fd)
        os.unlink(temporary)
    return {'operation': operation, 'database': str(destination), 'integrity': 'ok',
            'notice': 'Database only; no worker disks, model blobs or environment secrets. Restore does not start workers.'}


def run_copy(source, destination, operation):
    print(json.dumps(copy_database(source, destination, operation)))
