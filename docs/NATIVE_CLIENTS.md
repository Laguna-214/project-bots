# Native client verification — 2026-11-03

> **Android NOT ACCEPTED: replacement built; independent review and Android runtime/device execution still pending.** The user approved the actual native redesign. The old unsafe browser renderer is removed; the new artifact below has executed host transport/API evidence, not phone acceptance. `ANDROID_NOT_ACCEPTED.txt` remains. See [architecture, tests and archived blocker](../clients/android/REDIRECT_CONFINEMENT.md).

These clients share the existing backend/business logic. Android now uses native Java widgets and typed API calls; Linux retains the existing web UI. They do not make Hermes mandatory, launch model instances, grant worker host access, or alter the five-stage roadmap.

## Produced and verified

- `clients/artifacts/ProjectBots-android-debug.apk`
  - SHA256: `875a5b42fd69dcb1a3bcee5304c93c4bd00865b69b3fdc61d4b67121b3c367f8`
  - Version `0.2.0-native` (code 2), 60,548 bytes. Actual Gradle `assembleDebug assembleDebugAndroidTest lintDebug`: BUILD SUCCESSFUL with strict dependency verification; official apksigner verified v2 signatures for app and test APK. Lint: 12 `SetTextI18n` warnings, no Error/Fatal. Platform-tools-not-installed/license warning remains; no SDK/device downloads or policy changes were made. Debug-signed, not a production release.
  - Compiled, **not executed**, runtime regression artifact: `clients/artifacts/ProjectBots-android-regression-test.apk`; SHA256 `3b8e47fc9b2aad76751764fb6424f16ac9e80f54fee9c12f723bdec4124dd715`.
- `clients/artifacts/ProjectBots-linux-x64.tar.gz`
  - SHA256: `e76c5741476058bfd2976beffb701a3f0564c70fa9feee1de3ccbc1619c94de4`
  - Actual packaging completed. Nine native shell/unit contracts and two artifact/fuse checks passed. Binaries and caches are ignored by Git.

## Approved native Android redesign — executed evidence and gaps

- Native Chats: pair to one configured origin; list/create individual and group chats; select history; send persistent messages with retry-stable client UUIDs; edit group membership. History is manually refreshed/paginated (100 messages per backend page), not a background subscription.
- Native Agents: list actual definitions; create name/role/optional model definitions. This does **not** create a worker, enroll conversational credentials/instructions, or start inference. Existing enrolled agents require the separately configured shared backend runner; model availability is not fabricated or inferred from a definition.
- Native Activity: actual reported jobs, security coverage/limitations/incidents/evidence and chat security events; pending human approvals with full bound plaintext payload and explicit approve/reject confirmation; confirmed per-agent incident/stop and global emergency stop, followed by status/list readback. A control-plane latch is not verified remote termination/network isolation. Incident acknowledgment/recovery, integration issuance, VM controls and private conversation configuration are intentionally not native controls in this bounded increment.
- Emergency-stop availability review fix: Activity renders the confirmed global stop synchronously before any information request. Security, jobs, events and approvals load separately with section-local failures; successful security status renders per-agent stop controls even if all other sections fail. A behavioral JVM harness executes the production `MainActivity` with explicit UI/API doubles: the initial test failed with “global stop absent before informational loads: jobs”; it now passes five failure combinations, confirmation dispatch and stale-session confirmation rejection. It also reproduces and fixes stop dispatch starvation: with both informational workers blocked and all four queue slots occupied, a confirmed stop reaches the adapter through a reserved one-thread, zero-queue control lane. Global and per-agent stops use that lane; a concurrent stop already in progress yields an explicit busy rejection rather than queued/retried mutations. It is controller/presentation proof, not Android widget/runtime proof. The isolated real-backend HTTPS fixture additionally creates 70 valid 16,000-character job inputs, verifies an over-1-MiB jobs body is refused by the unchanged Java transport, then fetches security status successfully. The compiled-only Android instrumentation adds real-widget/transport checks against failed informational endpoints; it has not executed. Independent review/parent verification and runtime gates remain open.
- Sole network boundary: fixed-origin `HttpURLConnection`, system TLS/hostname checks, HTTPS outside exact loopback, no automatic redirects (all 300–399 rejected), complete bounded JSON POST bodies (64 KiB), bounded response (1 MiB declared and streaming), 5 s connect / 10 s read timeouts and a 20 s disconnect deadline. No remote HTML/JS, resource loader, URL intents, arbitrary transport/channel or browser/native bridge exists. Selection generations reject stale responses including A→B→A/logout; message sequence/cursor and draft-edit revision bookkeeping are memory-only presentation state, not duplicated domain logic.
- Executed Java socket harness: two real HTTP origins, GET/script-analogue and POST for every status 300–399, **zero forbidden-origin contacts**, exact POST body/method/auth/Origin/CSRF, unsupported method/path rejection, request/declared/chunked response limits, read and cumulative drip timeout failures. Executed delayed generation and monotonic history/dedup/newer-draft cases. The script analogue is a redirected typed request/plaintext URL payload, not an executing script engine.
- Executed isolated actual platform HTTPS/SQLite roundtrip through the production Java transport: disposable CA in a **test JVM truststore only**; untrusted TLS and trusted-chain hostname mismatch fail; eight-digit one-use pairing, session/CSRF, rejected missing-CSRF mutation, agents with role/model, individual/group chat creation, idempotent send, literal script-like text persistence, unrelated-chat empty history, membership readback, jobs/security/events, real bound approval/rejection and stop readback. Fixture scoped proposals are created by actual backend permissions/approval services; no compute/model action is dispatched. Fixture HOME/CODEX_HOME/database/keys are isolated; no production tokens/state are used.
- `python3 -m unittest discover -s tests -q`: **209 tests run, OK (skipped=3)** on the combined source tree. This is backend/source regression evidence, separate from Android tests. An earlier module-name invocation failed on test import paths; discovery is the successful command, not that failed invocation.
- Host JVM specifics matter: desktop Java suppresses `Origin` unless the harness starts with `-Dsun.net.http.allowRestrictedHeaders=true`. Android does not use this JVM flag. The dependency-free Android `Instrumentation` runner compiles real two-origin redirect/POST-header tests to check the actual Android HTTP stack, but **has not run**. No adb/emulator/image is installed and the management user lacks KVM read/write access; no device permissions or VMs were changed.
- Secure screen lock, encrypted/unlocked credential storage, secure-window flag, no backup, non-debuggable app, disabled view-state saving/autofill retained. Only endpoint is persisted; tokens, history and drafts are not cached on disk. Process death/configuration recreation requires a fresh console pairing code (backend codes are one-use, so a backend restart may be needed). No notifications, background service, offline delivery or durable enrollment is implemented.

Build with the cache overrides in `clients/README.md` and `sh clients/tools/build-android.sh`. On a separately authorized Android device, install both app/test APKs and execute:

```sh
adb shell am instrument -w app.projectbots.test/app.projectbots.NativeRegressionInstrumentation
```

Then separately exercise the visible pairing/chat/group/agent/approval/stop workflows against an isolated real backend with trusted HTTPS. Compiled instrumentation does not prove UI interaction, Android header fidelity, device storage protections or hardware acceptance. Keep the not-accepted marker until independent review/parent verification and the required runtime gates close.

## Actual Linux GUI/runtime acceptance

The separately approved administrator lab VM was used, not an original worker. Standard Ubuntu signed GUI/Xvfb packages were installed there. The archive hash was checked before extraction; only the matching lab-local root-owned vendor sandbox helper received mode 4755. No host AppArmor, sysctl, sandbox setting or original VM was changed.

The packaged application first launched under Xvfb. An attempt to run a test entry by passing it to the packaged binary instead launched the normal application and timed out; this was **not counted as a passed test**, and that exact owned test process was terminated. For harness execution, a lab-only hardlink copy of the verified runtime retained the same binary/fuses but removed its application entry directory so Electron's default loader could run the test entry. The original installed artifact remained intact. Tests used the production shell/setup source; this is runtime integration, not an untouched end-user release certification.

Both actual Electron programs subsequently exited 0:

1. `clients/desktop/test/electron-acceptance.cjs`: renderer had no Node/process/preload/remote connection bridge; real `/proc/<renderer>/status` showed **NoNewPrivs 1 and seccomp filter mode 2**. Cross-origin/file/subframe/popup restrictions and fatal rejection of an untrusted HTTPS certificate passed. Expected TLS-rejection and Chromium shutdown diagnostics were emitted.
2. `clients/desktop/test/native-app-flow.cjs`: actual production main/setup protocol and preload displayed the local setup form, submitted its restricted connect IPC, and displayed an explicitly labeled loopback HTTP fixture in the remote window without exposing that setup bridge remotely.

No `--no-sandbox` or disabled web security was used. `--disable-gpu` selected CPU rendering for the virtual display; it did not disable renderer sandboxing.

## Not yet accepted

- Installation and interaction on a physical Android device, real certificate enrollment, production authentication/chat/approval workflows through either native shell, and native background notifications.
- Durable native device enrollment/session persistence: current sessions deliberately remain memory-only and require re-pairing after close.
- A signed production distribution or automated dependency/sandbox installation for Linux.
- Hostile-agent VM containment, protected monitoring/audit/watchdog deployment, or four real workers using one loaded GPU model. Client tests do not close these backend/hardware gates.

Build commands, cache overrides and sandbox prerequisites: [clients README](../clients/README.md).
