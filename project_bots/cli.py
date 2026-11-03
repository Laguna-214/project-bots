"""Project Bots setup commands (configuration only; no model inference)."""
import argparse
import shutil
import subprocess
import sys

from .config import PRESETS, load_config, save_config, validate_config


def codex_status():
    if not shutil.which('codex'):
        return 'Codex CLI not installed', False
    try:
        result = subprocess.run(['codex', 'login', 'status'], capture_output=True, text=True, timeout=15)
        return ('Codex signed in' if result.returncode == 0 else 'Codex not signed in'), result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return 'Codex status unavailable', False


def main(argv=None):
    parser = argparse.ArgumentParser(prog='project-bots', description='Project Bots configuration (no inference runtime). Commands: setup web, setup local, codex login, codex status, update')
    sub = parser.add_subparsers(dest='command')
    setup = sub.add_parser('setup', help='Configure providers')
    modes = setup.add_subparsers(dest='mode')
    modes.add_parser('local', help='Interactive local setup')
    web = modes.add_parser('web', help='LAN setup on port 8032')
    web.add_argument('--host', default='0.0.0.0')
    web.add_argument('--port', type=int, default=8032)
    codex = sub.add_parser('codex', help='Official Codex CLI authentication')
    codex.add_argument('action', choices=['login', 'status'])
    sub.add_parser('update', help='Update from the official GitHub main branch')
    platform = sub.add_parser('serve', help='Persistent Stage 1 workforce dashboard')
    platform.add_argument('--host', default='127.0.0.1')
    platform.add_argument('--port', type=int, default=8032)
    platform.add_argument('--tls-cert', help='Trusted server certificate chain for direct HTTPS')
    platform.add_argument('--tls-key', help='Private server key; provide together with --tls-cert')
    machine = sub.add_parser('machine-service', help='Dedicated authenticated session-libvirt compute service')
    machine.add_argument('--host', default='127.0.0.1')
    machine.add_argument('--port', type=int, default=9443)
    machine.add_argument('--catalog', required=True, help='Trusted admin-local template catalog JSON')
    machine.add_argument('--state-dir', required=True, help='Private dedicated compute state directory')
    machine.add_argument('--token-env', default='PROJECT_BOTS_COMPUTE_TOKEN')
    machine.add_argument('--tls-cert')
    machine.add_argument('--tls-key')
    backup = sub.add_parser('backup', help='Consistent private database backup (no worker disks or secrets)')
    backup.add_argument('--database', required=True, help='Existing private platform database')
    backup.add_argument('--output', required=True, help='New file in an existing private directory')
    restore = sub.add_parser('restore', help='Validate and restore into a NEW offline database path only')
    restore.add_argument('--backup', required=True, help='Private validated SQLite backup')
    restore.add_argument('--database', required=True, help='New database path; existing files are never replaced')
    args = parser.parse_args(argv)
    if args.command in ('backup', 'restore'):
        from .backup import run_copy
        import sqlite3
        try:
            source = args.database if args.command == 'backup' else args.backup
            destination = args.output if args.command == 'backup' else args.database
            run_copy(source, destination, args.command)
        except (ValueError, OSError, sqlite3.Error):
            print('Database copy refused: check source integrity, private ownership/permissions and a new destination path.', file=sys.stderr)
            return 1
        return 0
    if args.command == 'machine-service':
        from .machine_http import serve as machine_serve
        try:
            machine_serve(args.host, args.port, args.state_dir, args.catalog, args.token_env, args.tls_cert, args.tls_key)
        except (ValueError, OSError) as exc:
            # Validation errors are fixed messages, never submitted secrets.
            print('Machine service could not start: ' + (str(exc) if isinstance(exc, ValueError) else 'check local files and listener'), file=sys.stderr)
            return 1
        return 0
    if args.command == 'serve':
        from .platform_web import serve
        try:
            serve(args.host, args.port, args.tls_cert, args.tls_key)
        except (ValueError, OSError):
            print('Platform could not start: check private database, listener and HTTPS certificate/key configuration.', file=sys.stderr)
            return 1
        return 0
    if args.command == 'setup' and args.mode == 'local':
        print('Providers: ' + ', '.join(PRESETS))
        try:
            provider = input('Provider: ').strip().lower()
            model = input('Model identifier: ').strip()
            endpoint = input('Endpoint (blank for preset): ').strip()
            env = input('API key environment variable (blank for preset): ').strip()
            data = {'provider': provider, 'model': model}
            if endpoint:
                data['endpoint'] = endpoint
            if env:
                data['api_key_env'] = env
            save_config(validate_config(data))
        except (ValueError, EOFError, KeyboardInterrupt) as exc:
            print(f'Configuration not saved: {exc}', file=sys.stderr)
            return 1
        print('Saved. Set the named API key environment variable on the server before running an agent.')
        return 0
    if args.command == 'setup' and args.mode == 'web':
        from .web import serve
        serve(args.host, args.port)
        return 0
    if args.command == 'codex':
        if not shutil.which('codex'):
            print('Codex CLI not installed. Install the official Codex CLI first.')
            return 1
        if args.action == 'login':
            return subprocess.call(['codex', 'login', '--device-auth'])
        message, ready = codex_status()
        print(message)
        return 0 if ready else 1
    if args.command == 'update':
        from .update import update
        return update()
    parser.print_help()
    print('Commands: setup web, setup local, codex login, codex status, update')
    return 0


if __name__ == '__main__':
    sys.exit(main())
