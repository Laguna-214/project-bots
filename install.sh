#!/bin/sh
set -eu
src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
prefix=${HOME:?}/.local
mkdir -p "$prefix/lib/project-bots" "$prefix/bin"
cp -R "$src/project_bots" "$prefix/lib/project-bots/"
printf '#!/bin/sh\nPYTHONPATH="%s/lib/project-bots" exec python3 -m project_bots.cli "$@"\n' "$prefix" > "$prefix/bin/project-bots"
chmod 755 "$prefix/bin/project-bots"
cp "$src/uninstall.sh" "$prefix/bin/project-bots-uninstall"
chmod 755 "$prefix/bin/project-bots-uninstall"
printf 'Installed %s/bin/project-bots (add %s/bin to PATH if needed)\n' "$prefix" "$prefix"
