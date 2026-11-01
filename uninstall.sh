#!/bin/sh
set -eu

case ${HOME:-} in
    ''|/) printf '%s\n' 'HOME must be a non-root home directory.' >&2; exit 1 ;;
esac

prefix=$HOME/.local
launcher=$prefix/bin/project-bots
package=$prefix/lib/project-bots
uninstaller=$prefix/bin/project-bots-uninstall

# Never delete a file or directory we cannot identify as ours.
if [ -e "$launcher" ] || [ -L "$launcher" ]; then
    if [ ! -f "$launcher" ] || [ -L "$launcher" ] || ! grep -Fq 'exec python3 -m project_bots.cli "$@"' "$launcher"; then
        printf '%s\n' "$launcher is not a Project Bots installation; nothing removed." >&2
        exit 1
    fi
fi
if [ -e "$package" ] || [ -L "$package" ]; then
    if [ ! -d "$package" ] || [ -L "$package" ] || [ ! -f "$package/project_bots/cli.py" ]; then
        printf '%s\n' "$package is not a Project Bots installation; nothing removed." >&2
        exit 1
    fi
fi

if [ -e "$uninstaller" ] || [ -L "$uninstaller" ]; then
    if [ ! -f "$uninstaller" ] || [ -L "$uninstaller" ] || ! grep -Fq 'Project Bots program removed.' "$uninstaller"; then
        printf '%s\n' "$uninstaller is not a Project Bots installation; nothing removed." >&2
        exit 1
    fi
fi

[ ! -f "$launcher" ] || rm -- "$launcher"
[ ! -d "$package" ] || rm -rf -- "$package"
[ ! -f "$uninstaller" ] || rm -- "$uninstaller"
printf '%s\n' 'Project Bots program removed. Configuration in ~/.config/project-bots was preserved.'
