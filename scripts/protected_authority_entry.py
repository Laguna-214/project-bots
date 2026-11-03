#!/usr/bin/env python3
"""Fixed root entry; validate installed source tree BEFORE importing any project code."""
import os
from pathlib import Path
import stat
import sys

ROOT = Path('/opt/project-bots-protected')


def check_tree():
    if os.geteuid() != 0 or Path(__file__).absolute() != ROOT / 'protected_authority_entry.py':
        raise PermissionError('Fixed root-owned installation required')
    # Include directories, __init__, modules, bytecode and any unexpected file.
    for path in [*ROOT.parents, ROOT, *ROOT.rglob('*')]:
        info = path.lstat()
        if (stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022 or
                not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode))):
            raise PermissionError('Untrusted installed source tree')


if __name__ == '__main__':
    check_tree()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    from project_bots.protected_compute import serve_authority
    serve_authority()
