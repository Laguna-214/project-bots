# Project Bots

**Self-hosted local AI agents made easy.** Project Bots is an open-source project for people who want to run useful AI agents on a spare computer or homelab without assembling a complicated stack.

> **Status: planning.** There is no working release or installer yet. This repository documents the direction of the project; features below are goals, not shipped capabilities.

## The idea

A server app runs the agents and local AI models on your computer. A simple web UI on your LAN lets you give an agent a task, follow its progress, review results, and approve important actions. An optional companion app and Tailscale-based remote access may follow.

The intended first-run experience is: install the server, let a setup advisor check the machine's resources, choose what you want agents to do, accept a recommended local model and configuration, and create your first agent.

## Design goals

- **Local-first:** run models and agent work on hardware you control.
- **Easy setup:** sensible defaults and a guided setup instead of manual configuration.
- **Clear control:** show what an agent is doing and request approval for consequential actions.
- **Honest isolation:** distinguish agents sharing a host environment from agents isolated in separate VMs.
- **Useful from anywhere at home:** a responsive LAN web UI, with optional private remote access rather than a public internet port.

## Execution modes under consideration

1. **Host mode:** one or more agents run on the server under limited permissions. Simple and efficient, but separate agents in this mode are **not** security boundaries.
2. **Isolated mode:** multiple agents each run in a configurable VM. This is a longer-term option, not a prerequisite for a useful first release.

A shared local model service could serve agents in either execution mode, avoiding a separate model loaded inside every VM.

## Initial milestone

Prove one complete, safe workflow: install the server, pair a device on the LAN, grant access to a selected folder, ask a local-model agent to summarize its contents with citations, and review the result. The agent must not modify files or access folders outside its granted scope.

The setup advisor, additional integrations, companion app, scheduling, and per-agent VMs should be developed against a working core rather than promised as part of the first milestone.

## Security direction

The design aims for local-only networking by default, authenticated device pairing, least-privilege access to files and tools, protected credentials, and explicit approvals for sending, publishing, purchases, deletion, and system changes. These are design goals, **not guarantees of the current repository**. Do not use this project for sensitive tasks until an implementation and its security properties have been reviewed.

## Contributing

The project is at the planning stage. Ideas, use cases, and constructive design feedback are welcome through GitHub Issues. Implementation and contribution guidelines will be added as the project takes shape.

## License

[MIT](LICENSE)
