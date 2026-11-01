# Project Bots

**Self-hosted local AI agents made easy** for spare computers and homelabs. **Current state is configuration-only:** the installer, CLI, and setup UI work, but there is no agent runtime, model inference, local-model installer, device pairing, desktop GUI, or remote access yet.

The planned product has a server running agents and local models, with a simple LAN web UI and optional companion app. The intended first-run flow is guided hardware detection, a recommended model and configuration, and a clear first task. Host execution comes first; per-agent VMs are a future advanced option. Agents sharing a host are not isolated from one another.

## Install (Linux, Python 3, no root)

```sh
git clone https://github.com/Laguna-214/project-bots.git
cd project-bots
sh install.sh
export PATH="$HOME/.local/bin:$PATH"
project-bots --help
```

The installer copies the stdlib-only Python package to `~/.local/lib/project-bots` and creates `~/.local/bin/project-bots` and `~/.local/bin/project-bots-uninstall`; the clone can then be removed. Re-run `sh install.sh` to update. Python 3.9+ recommended. No system services or global packages are changed.

## Update

```sh
project-bots update
```

This one command fetches the latest `main` revision from the [official repository](https://github.com/Laguna-214/project-bots) over HTTPS and reinstalls the program. It works even if you deleted the original clone, requires `git`, and leaves `~/.config/project-bots/config.json` untouched. Running it again when the installed revision matches reports that it is up to date. Updates are **manual** and currently track the development branch rather than signed releases; review the repository before updating if you need a pinned, audited build. Stop a running setup server before updating, then restart it to load the new code.

## Uninstall

```sh
~/.local/bin/project-bots-uninstall
# Or, from the repository clone: sh uninstall.sh
```

This removes the installed CLI, package, and uninstaller. It **keeps** `~/.config/project-bots/config.json` so settings are not deleted unexpectedly. Stop any running setup server first. To remove the retained configuration too, delete it manually after reviewing it.

## Configure

```sh
project-bots setup local            # interactive wizard at the server terminal
project-bots setup web              # binds 0.0.0.0:8032; open http://SERVER_LAN_IP:8032
project-bots setup web --host 127.0.0.1  # safer over SSH port forwarding
```

The web server prints a fresh, random bootstrap access token **only on its console**; enter that token in the page. Every `/api/*` request requires it. It changes on every server start and is never saved. The UI indicates Codex CLI sign-in status. Stop the server with Ctrl-C when finished. Web configuration and local wizard share `~/.config/project-bots/config.json` (override with `PROJECT_BOTS_CONFIG`), written atomically with mode `0600`. Config stores provider, endpoint, model, and **the name** of the server environment variable for an API key, never the key itself.

Providers: OpenAI, Anthropic, Google Gemini, xAI, OpenRouter, DeepSeek, Mistral, Groq, Together AI, Fireworks AI, Ollama, LM Studio, Codex/ChatGPT, and custom OpenAI-compatible HTTPS endpoints. Explicit HTTP endpoints are allowed only on loopback. Enter a model identifier supported by your provider; setup validates its syntax, **not** remote availability or compatibility. Presets are configuration hints, not implemented provider adapters.

For key-based providers, provision the named variable **on the server**, outside the web UI, before any future runtime is started; for example `export OPENAI_API_KEY=...` in a private terminal. Never paste key values into setup or its JSON APIs. Do not put them in shell history or shared files. Codex uses its **official installed CLI** instead:

```sh
project-bots codex login      # invokes: codex login --device-auth (server console only)
project-bots codex status     # invokes: codex login status
```

Install the official Codex CLI yourself first; Project Bots neither reads nor copies its credentials and does not implement OAuth.

## Security limitations

The LAN UI uses **plaintext HTTP**. API key *values* are not collected, transmitted or stored, but the bootstrap token and non-secret configuration do cross the LAN in plaintext. Use only on a trusted LAN. For an untrusted network, bind loopback and use an SSH tunnel (`ssh -L 8032:127.0.0.1:8032 SERVER`), then open `http://127.0.0.1:8032`. **Do not expose port 8032 to the public internet.** HTTP offers no confidentiality against LAN sniffing and no server identity. The token is bearer authentication, not a substitute for TLS. Setup also validates Host and Origin, requires a custom origin header and per-process CSRF token for writes, blocks cross-origin browser access, avoids logging requests, and sends a restrictive content security policy. These measures do not protect against a compromised browser or host. Saved config is private to the user, not encrypted at rest. No agent permissions or file isolation exist because no agent runtime exists.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

## Roadmap

Agent runtime and inference, permissioned folders, approvals, local models, and desktop GUI are future work; none are shipped here. [MIT](LICENSE).
