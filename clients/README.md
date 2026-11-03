# Native clients (development artifacts)

> **Android NOT ACCEPTED — independent review/device gate pending:** the approved redesign replaces the unsafe browser renderer with native widgets and typed API calls. Host transport/API tests and a replacement APK now exist; Android runtime/device acceptance is still unverified. Keep `artifacts/ANDROID_NOT_ACCEPTED.txt`. See [architecture and evidence](android/REDIRECT_CONFINEMENT.md). Linux findings and tests are separate.

Android is a native Java client of the existing authenticated API; Linux wraps the existing web UI. They do not run a second backend or duplicate chat/agent business logic. Closing either client does not stop a separately running backend.

## Current scope

- Android: actual native Chats / Agents / Activity screens, console-code pairing, individual/group chat creation and membership, persistent message history/send, agent definitions with role/model, reported jobs/security incidents, confirmed human approve/reject and agent/all stop. No browser engine, remote HTML/JavaScript, URL intents, remote resources or native bridges. HTTPS outside exact loopback; system certificate/hostname validation; all 300–399 responses rejected without following. Secure screen lock, encrypted unlocked app storage, secure-window flag, disabled backup/autofill/view-state persistence and non-debuggable build retained.
- Linux x86-64: Electron shell, isolated local setup origin and narrow endpoint-selection IPC; remote UI has no preload, Node, filesystem or terminal bridge. Renderer sandbox and context isolation remain enabled. Unexpected origins, frames, popups, downloads, permissions and certificate errors are denied.
- Only the endpoint is saved. Authentication sessions are memory-only; users must pair again after closing the app. Durable device enrollment/session recovery and native/background notifications are not implemented. This is a known usability/feature limitation, not a plaintext credential fallback.
- Configure a backend certificate trusted by the client. An untrusted self-signed certificate is rejected. On a phone, `127.0.0.1` means the phone itself, not the server; a LAN server needs HTTPS.

## Android build

Prerequisites: Linux x86-64, Python 3.12+, curl and a shell. Official JDK/Gradle/Android SDK archives are checksum-pinned in `tools/toolchains.lock.json`; Gradle dependencies use strict verification metadata.

From the repository root:

```sh
python3 clients/tools/bootstrap.py
sh clients/tools/build-android.sh
```

Default caches are under `${XDG_CACHE_HOME:-$HOME/.cache}/project-bots/`. `NATIVE_TOOLS_CACHE` and `NATIVE_GRADLE_CACHE` override them. The tools cache must be caller-owned/private; bootstrap rejects unsafe existing permissions without changing them. Hermes is not required.

The build runs Java real-two-origin redirect/body/header/bounds tests, delayed selection/history/draft state cases, an isolated real Python platform HTTPS/pair/session/CSRF/chat/approval/security roundtrip, Python architecture guards, Gradle debug + instrumentation APK assembly/lint, and APK signature verification. It writes `artifacts/ProjectBots-android-debug.apk` plus its checksum. Instrumentation compilation is not execution; no device/emulator is available here. The debug signing key stays outside the repository. This is a debug-signed development APK, not a production-signed or store-reviewed release.

## Linux build

```sh
cd clients/desktop
npm ci
npm test
npm run package
node --test test/artifact.check.cjs
```

Output: `clients/artifacts/ProjectBots-linux-x64.tar.gz` and checksum. Extract and run `ProjectBots-linux-x64/AppRun`. Standard Linux GUI/runtime libraries are needed. The archive does not install system dependencies or a privileged sandbox helper.

Sandboxing is mandatory. On systems restricting unprivileged user namespaces, an administrator may need a normal root-owned installation of the matching vendor `chrome-sandbox`. Never setuid a user-writable helper, disable the sandbox, weaken AppArmor/sysctls, or move a writable binary into a privileged vendor path. Acceptance used a hash-verified, root-owned helper **inside the separately approved disposable VM only**.

## Verification and limits

See [native verification](../docs/NATIVE_CLIENTS.md) and [resume checkpoint](../docs/RESUME_CHECKPOINT_2026-11-03.md). Build success, native window/security tests, physical-phone acceptance and hostile-worker containment are distinct gates. Source/binaries are development work; no full-product completion or production deployment is implied.
