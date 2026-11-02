# Stage 3 browser: bounded administrator install and acceptance passed

## Current verified result

The user subsequently explicitly approved a **one-time bounded guest-agent root
installation** in the four existing named guests. This supersedes the earlier
proposed exclusion of guest-agent execution below; it does **not** authorize a
permanent root service/API, arbitrary root jobs, bot sudo or any host policy edit.

All four installed the exact pinned Chrome package below. Immediately before each
fixed root command, authenticated platform VM detail verified UUID, running state,
service-owner XML metadata, exact disks and isolation. Artifact transfer used
ordinary bot SSH. Root copied bytes into mode-0600 `/root` staging and checked the
full SHA-256 **before** package parsing. Simulation and installation both reported
**0 upgraded, 1 newly installed, 0 to remove, 18 not upgraded**. No apt update,
upgrade, removal, automatic yes, security-policy edit or manual helper chmod ran.
Each staging directory was removed by its fixed trap. Readback on every guest:
`google-chrome-stable 156.0.8078.79-1 install ok installed`, browser `root:root 755`,
packaged sandbox helper `root:root 4755`.

Authenticated installed OpenClaw CLI start, `open about:blank`, offline controlled
DOM fixture, snapshot, referenced-button click and matching post-click snapshot
passed on each guest. The DOM fixture is a locally generated random challenge,
not a network service or model-provided answer. Loopback HTTP and data URLs were
correctly refused by existing navigation policy; that policy was **not** relaxed.
No private-network navigation or broad browsing-policy acceptance is claimed.
The offline supported browser evaluate action only supplies the controlled page;
the later OpenClaw snapshot/click actions observe and mutate it normally.

| Role | Preserved VM UUID | Challenge observed after click |
|---|---|---|
| ProjectWorker | `4accba4d-24c9-4942-aec9-fd54de816319` | `34f230ea-f10b-42b3-b4ea-d628b29e6608` |
| Researcher | `55545d36-bd05-4e48-9eb4-cea5fbe8c8f4` | `0f0f822c-1ecb-4d63-9acf-42baba8ccc11` |
| Programmer | `4c827ae7-02ab-40f8-8cc9-3af9c6340526` | `f892317d-cdc0-4f55-b2e4-afca8f9b1e05` |
| HomelabEngineer | `b4974b11-1c8a-409a-9f04-6401b9407ff1` | `323576ae-5e9e-43fd-8d3d-cb1059fb6829` |

All actual configs validated with enabled/headless true, noSandbox false and
`/usr/bin/google-chrome-stable`. All non-browser config objects equal the retained
pre-install backups, including credentials/models/role tools. Programmer and
HomelabEngineer still **deny browser** to the model; this is authenticated operator
CLI acceptance, not a role expansion. Each separate VM's private profile is
`/home/bot/.openclaw/browser/openclaw/user-data`, UID 1000, mode 0700: the same path
string names different guest filesystems, not a shared profile.

No Chrome process included `--no-sandbox`. Actual renderer processes showed
`NoNewPrivs: 1`, `Seccomp: 2`, UID 1000 and one seccomp filter. The existing vendor
AppArmor label reads `chrome (unconfined)`; this is Ubuntu's existing userns-grant
profile, **not a claim of enforcing AppArmor file confinement**. The system userns
restriction remains 1. All four original boot IDs remain unchanged, authenticated
worker health is healthy and both admission tables are empty with no FK errors.
Compute available RAM was 25561 MiB; whole-GPU VRAM 6247194624 bytes. Existing
llama.cpp accelerated tool-job evidence remains in LLAMA_CPP_MIGRATION.md.

Private active-profile scratch evidence: `stage3_browser_prepare.json`,
`stage3_browser_install.json`, per-role `stage3_browser_*_acceptance.json`, and
`stage3_browser_pool_acceptance.json`. Guest readback evidence is
`~bot/.openclaw/system-browser-acceptance.json`; config backup is
`~bot/.openclaw/pre-system-browser.json`. One-time operator harness
`stage3_browser_operator.py` is private scratch only, not installed as an API.
Stage 3's sandboxed isolated-browser gate is closed on this explicit offline
controlled-page basis. Stage 4 may now begin; no autonomous Stage 5 is implied.

## Future bootstrap boundary

Fresh workers must not assume Desktop includes Chromium or extract a bot-owned
Chrome tree. Keep the fixed non-root worker bootstrap unchanged. A trusted
operator must separately stage this exact publisher-verified artifact and run the
fixed hash-before-parser root recipe below through approved guest administration,
first simulating with `apt-get --simulate --no-remove --no-upgrade` and accepting
only the one pinned new-package transaction. Never add a package URL, package list,
shell command, guest-exec or root endpoint to client requests. Updated Chrome pins
need a new publisher verification/review; never silently substitute latest. Normal
provisioning remains explicitly incomplete for browser readiness until this step
and per-guest authenticated browser acceptance succeed.

## Historical pre-approval blocker (superseded)


## Fresh blocking test

At source baseline `cc7ac9f`, the authenticated Researcher CLI call
`openclaw browser start --json` returned exit 1 with **No supported browser found**.
The token was supplied privately; no credential was logged. On **all four existing
guests**, `chromium`, `chromium-browser`, and `google-chrome-stable` are absent from
PATH, and `/snap/chromium/current` does not exist. Ubuntu Desktop installation did
**not** install Chromium. There is consequently no installed distro/snap browser
whose supported launch can close this gate without administrator installation.

Researcher's existing root-owned `/etc/apparmor.d/chrome` names exactly
`/opt/google/chrome/chrome` and grants `userns`; the SSH session itself is
`unconfined`, with `kernel.apparmor_restrict_unprivileged_userns=1`. This is a
promising **packaged Chrome** transition, not proof that its profile is loaded or
that a sandboxed browser works. Do not copy a bot-owned binary into a matching
path, rename a binary to exploit a rule, alter policy, or disable sandbox/userns
security. Prior user-local verified Chrome failed its sandbox-helper check.

Private evidence (active project-bot profile, no tokens):
`cache/scratch/stage3_browser_recheck.json` and
`cache/scratch/stage3_browser_inventory.json`. All four observed boot IDs still
match the retained worker evidence. Stage 3 llama/inference/platform and Stage 2
platform units were active at recheck. Default suite: **86 discovered, 85 passed,
1 optional schema skip**. No browser navigation/snapshot success is claimed.

## Exact bounded administrator mechanism — proposed, NOT executed

Ask the user:

> May an administrator install the already signature-chain/hash-verified official
> Google Chrome package into its normal root-owned system paths inside the four
> existing worker VMs, using their normal administrator console/access? This is
> guest browser packaging only: no host change, VM replacement, security-policy
> change, bot sudo, libvirt guest-agent root execution, or disk editing. After
> installation we will test with sandbox enabled, retaining existing roles and
> private browser profiles. Stage 4 stays stopped until real browser acceptance.

The package already verified in the earlier acceptance is
`google-chrome-stable` version `156.0.8078.79-1`, amd64, SHA-256:

```text
be1a1e161419f5c8272432f6860912550d8e29985e925913fa800493a0d0c955
```

Management's retained file is in the active profile's private scratch:
`/home/server1/.hermes/profiles/project-bot/cache/scratch/stage3_chrome/google-chrome.deb`.
Researcher also has `/home/bot/.cache/project-bots-artifacts/google-chrome.deb`.
An administrator must transfer that exact verified artifact to each other guest
through normal approved access; do not substitute a current unverified download.
The preceding signing-chain evidence is `stage3_chrome/verification.json` and
[STAGE3_GPU_POOL_ACCEPTANCE.md](STAGE3_GPU_POOL_ACCEPTANCE.md).

**Only after approval**, an administrator can run this bounded mechanism in a
root shell **inside each named guest**, not on management or compute. This is a
reviewable recipe, not an installed root API or an instruction for the bot to
obtain root. It copies bytes into a root-only staging directory and hashes those
bytes before invoking any package parser or maintainer script:

```sh
set -eu
[ "$(id -u)" = 0 ] || { printf '%s\n' 'Administrator guest root shell required' >&2; exit 1; }
# Administrator supplies this exact artifact at this path first.
source_deb=/home/bot/.cache/project-bots-artifacts/google-chrome.deb
stage=$(mktemp -d /root/project-bots-browser.XXXXXXXX)
trap 'rm -f -- "$stage/google-chrome.deb"; rmdir -- "$stage"' EXIT
install -m 0600 -- "$source_deb" "$stage/google-chrome.deb"
printf '%s  %s\n' \
  be1a1e161419f5c8272432f6860912550d8e29985e925913fa800493a0d0c955 \
  "$stage/google-chrome.deb" | sha256sum --check --status
# Review dependencies/transaction before accepting. No automatic yes, upgrades,
# removals, dist-upgrade, fix-broken action, or policy edit is authorized here.
apt-get --no-remove --no-upgrade install "$stage/google-chrome.deb"
dpkg-query -W -f='${Package} ${Version} ${Status}\n' google-chrome-stable
stat -c '%U:%G %a %n' /opt/google/chrome/chrome /opt/google/chrome/chrome-sandbox
```

If dependencies cannot be satisfied without upgrades, stop and return the exact
proposed transaction for approval. Do not broaden this recipe. Installing a
vendor package executes its vendor maintainer scripts, including repository
integration; this is why explicit administrator approval is required. No
AppArmor reload/edit is included. Do not manually grant setuid to a bot-writable
helper; normal vendor package ownership is the supported boundary. This recipe
has **not been executed** and is **not installation/acceptance evidence**.

## Post-install acceptance before Stage 4

1. As each existing non-sudo `bot`, validate the installed OpenClaw config with
   `browser.executablePath=/usr/bin/google-chrome-stable`, `headless=true`,
   `noSandbox=false`, and its own private profile/workspace. Preserve credentials
   and role tools; browser testing does not authorize expanding HomelabEngineer
   or other agents' tool policy. Administrator CLI control can test a profile
   without granting the model browser access.
2. Authenticated **OpenClaw** browser start, navigate to a controlled local test
   page, and snapshot or click must work in each guest's own profile. Put an
   unprompted random challenge in each guest's private workspace test page and
   retain the matching navigation/snapshot evidence. Static config, direct
   Chrome CDP health, or an installed package is insufficient.
3. Verify sandbox-preserving process arguments and effective confinement, private
   profile permissions, unique profile paths, unchanged VM identities and role
   policies, GPU services, all-worker readiness, resource headroom and empty/
   healthy admission state. No `--no-sandbox`, disabled userns protection or
   binary-path confinement workaround is allowed. Stop on a policy failure.
4. Only after this real Stage 3 acceptance passes begin Stage 4 MCP. Until then,
   no MCP server or Hermes profile wiring is implemented or claimed.
