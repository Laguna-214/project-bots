"""One-command updates from the official Project Bots repository."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

OFFICIAL_REPO = 'https://github.com/Laguna-214/project-bots.git'


def update(repo_url=OFFICIAL_REPO):
    """Clone main over HTTPS and reinstall without touching saved configuration."""
    if not shutil.which('git'):
        print('Update requires git. Install git and retry.')
        return 1
    try:
        with tempfile.TemporaryDirectory(prefix='project-bots-update-') as temp:
            source = Path(temp) / 'source'
            result = subprocess.run(['git', 'clone', '--quiet', '--depth', '1', '--branch', 'main', repo_url, str(source)], capture_output=True, text=True, timeout=120)
            if result.returncode:
                print('Update download failed: ' + result.stderr.strip())
                return 1
            result = subprocess.run(['git', '-C', str(source), 'rev-parse', '--verify', 'HEAD'], capture_output=True, text=True, timeout=15)
            if result.returncode:
                print('Update failed: could not verify revision.')
                return 1
            revision = result.stdout.strip()
            installed = Path.home() / '.local/lib/project-bots/REVISION'
            if installed.exists() and installed.read_text().strip() == revision:
                print('Already up to date (' + revision[:12] + ').')
                return 0
            if not (source / 'install.sh').is_file() or not (source / 'project_bots/cli.py').is_file():
                print('Update failed: downloaded repository is missing the installer.')
                return 1
            result = subprocess.run(['sh', str(source / 'install.sh')], capture_output=True, text=True, timeout=120)
            if result.returncode:
                print('Update installation failed: ' + result.stderr.strip())
                return 1
            print('Updated Project Bots to ' + revision[:12] + '.')
            return 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        print('Update failed: ' + str(exc))
        return 1
