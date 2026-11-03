# GitHub delivery checkpoint

The user requested finishing the remaining work and updating GitHub. Work is continuing; **the product is not complete**.

## Publication preparation

- Canonical target verified through GitHub: `Laguna-214/project-bots`, default branch `main`.
- GitHub CLI authentication is working. Local HEAD and `origin/main` matched before creating `feat/shared-platform-native-clients`; no force push or destructive reset is planned.
- The working tree contains the preserved backend/web/security/inference/native continuation. Candidate publication inventory contained no files over 1 MB or credential-named files. A private-key/GitHub-token/AWS-key pattern scan found no matches; this is a limited scan, not proof that every possible secret is absent.
- New `.github/workflows/source-checks.yml` uses upstream-read pinned action commits and read-only repository permissions. It runs Python/MCP fixture contracts, six web UI programs, and desktop shell tests. Its JSON document is valid YAML-compatible flow syntax; embedded shell scripts passed syntax checks. Fresh isolated `npm ci --ignore-scripts` plus all nine desktop unit tests passed. The initial push was rejected for missing OAuth `workflow` scope. The user subsequently approved that scope, the CLI cached-username mismatch was resolved through fresh login, and the workflow was published in `0afa60c43f8f3c2469b3f271289d3ceece792a61`. Both actual GitHub source/UI runs completed successfully: [41712609751](https://github.com/Laguna-214/project-bots/actions/runs/41712609751) and [41712610766](https://github.com/Laguna-214/project-bots/actions/runs/41712610766). This does not close hardware/device/security acceptance.
- Do not describe this workflow as Android, GPU/model, or privileged hostile-VM acceptance. It deliberately does not enable privileged host tests on a public runner.

## Published checkpoint

Source checkpoint `e93415b1be89a1d4885a4b52e184c14c8f48474c` was pushed and read back from GitHub. [Draft PR #1](https://github.com/Laguna-214/project-bots/pull/1) is open against `main`, not merged or released. The remote ref and PR head matched the local commit. At initial publication `gh pr checks` reported no checks; after authorized workflow publication, both checks on `0afa60c` passed.

The next bounded implementation is trusted VM launch/kernel network enforcement (`deleg_39d8d404`), with no original VM/physical host mutation and independent review required before new privileged lab code executes. This work is not part of the checkpoint passing-test claim. Production monitoring/watchdog/audit and hardware/device acceptance remain incomplete.

## Scoped source review result

Native Android review `deleg_9d34bd02` found no concrete security issue but one emergency-stop availability bug: a failed/oversized informational Activity listing suppresses stop controls. Bounded TDD fix `deleg_d2f207db` completed. Parent repeated the actual native build: synchronous global control, independent section failures, security-success per-agent controls, stale-confirmation rejection and reserved stop dispatch under saturated informational work all passed. The real backend oversized jobs body remains rejected by the unchanged 1 MiB cap. Independent scoped re-review `deleg_9c4a7a48` **passed**, with no blocking security/logic findings. Source-fix review is closed; Android runtime acceptance is not. The replacement APK remains **not accepted**. Re-review and parent verification are required before publishing it as verified; device/instrumentation execution remains a separate unperformed gate.

## Completion boundaries

Unfinished implementation remains, not merely missing test results: the production VM network launcher/adapter, protected runtime/identity/audit monitors, independent watchdog/protected evidence store, and remaining mobile notification/enrollment experience are not delivered as a complete installed system. Fifteen malicious-agent VM chains, four real agents through one loaded RX6800 model, and Android device/UI/header execution are not accepted. Existing original VMs and host security policies remain protected by the earlier narrow authorization; publishing code does not authorize activating an unverified enforcer or weakening host policy.

After the source fix/review, commit explicitly scoped source/docs without caches, signing keys, tokens or build outputs (and without the locally retained workflow that requires additional OAuth scope); push the feature branch, create an honest draft PR if acceptance remains open, and read back the exact remote commit/PR/CI before claiming GitHub updated. Do not merge/release or label Stage 5 complete based only on passing unit/fixture tests.
