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
    parser = argparse.ArgumentParser(prog='project-bots', description='Project Bots configuration (no inference runtime). Commands: setup web, setup local, codex login, codex status')
    sub = parser.add_subparsers(dest='command')
    setup = sub.add_parser('setup', help='Configure providers')
    modes = setup.add_subparsers(dest='mode')
    modes.add_parser('local', help='Interactive local setup')
    web = modes.add_parser('web', help='LAN setup on port 8032')
    web.add_argument('--host', default='0.0.0.0')
    web.add_argument('--port', type=int, default=8032)
    codex = sub.add_parser('codex', help='Official Codex CLI authentication')
    codex.add_argument('action', choices=['login', 'status'])
    args = parser.parse_args(argv)
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
    parser.print_help()
    print('Commands: setup web, setup local, codex login, codex status')
    return 0


if __name__ == '__main__':
    sys.exit(main())
