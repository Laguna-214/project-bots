# Android native redesign — replacement built, NOT ACCEPTED

The user explicitly approved replacing the unsafe browser renderer with actual
native Chats / Agents / Activity screens. `MainActivity` now renders plaintext
native widgets and calls a typed `BackendApi`; only `NativeTransport` opens a
network connection. The old allowed-URL browser fallback is removed, not patched
with another initial-URL callback. Backend, web and desktop logic were not changed.

`NativeTransport` disables redirects before any request, rejects all 300–399
responses without following `Location`, preserves complete JSON POST bodies and
authentication/Origin/CSRF headers, validates one fixed selected origin, and uses
system TLS/hostname checks without production trust overrides. It bounds methods,
request/response bytes and timeouts. Remote payloads cannot request resources,
launch intents, choose transports or execute HTML/JavaScript.

Executed host tests use two independently counted HTTP origins for GET and POST
across every status 300–399: **zero second-origin contacts**. HTTPS fixtures exercise
fatal untrusted-chain and trusted-chain hostname errors and actual isolated shared
platform pair/session/CSRF/chat/approval/security routes through this transport.
This is host-JDK/API evidence, **not Android runtime acceptance**. In particular,
the test JVM needs an Origin-header flag that is not used on Android. A compiled
no-dependency Android socket Instrumentation runner is provided but unexecuted.

New app SHA256: `875a5b42fd69dcb1a3bcee5304c93c4bd00865b69b3fdc61d4b67121b3c367f8`.
The Activity availability regression now executes production `MainActivity` with
explicit host UI/API doubles: global stop renders before loads; section failures
do not hide it or successful-security agent controls. Confirmed stops dispatch on
a reserved bounded one-thread/zero-queue lane even with the informational executor
blocked/full; a second stop already in progress causes explicit busy rejection,
never automatic retry or queued mutation. Real Android widget coverage
is compiled into instrumentation but remains unexecuted. The API fixture also
checks a valid oversized jobs response against the unchanged 1 MiB transport cap.
The build wrapper executes transport/API/state/presentation/architecture checks, strict Gradle
assembly + instrumentation assembly + lint, and apksigner verification before
copying/checksumming the new debug artifact. See [current evidence and limitations](../../docs/NATIVE_CLIENTS.md).

**Keep `clients/artifacts/ANDROID_NOT_ACCEPTED.txt`: independent review and actual
Android/device workflows remain pending.** No adb/emulator/image was installed,
no KVM/device permissions changed, and no VM started. Memory-only pairing,
no notifications/background delivery, manual refresh, and separate backend
conversation enrollment/runner requirements remain explicit limitations.

## Archived WebView review — historical evidence, not current source status

Everything below describes the superseded, blocked APK
`d15eff2d2d483477c31a2059a878e22398fec6a8852322041d72f1fe73d465d6`
and the earlier callback-only attempt. Its API analysis explains why that design
was rejected; its old source locations, failing-test counts and no-replacement
statements are historical, not claims about the new native artifact.

## API-sourced boundary analysis

References actually read:

- [WebViewClient.shouldInterceptRequest](https://developer.android.com/reference/android/webkit/WebViewClient#shouldInterceptRequest(android.webkit.WebView,%20android.webkit.WebResourceRequest)):
  returning null lets WebView load the resource itself; interception is called
  only for the initial URL, not subsequent redirect URLs. It also excludes
  javascript/blob URLs and some built-in assets. Thus an allowed same-origin
  script URL returning 302 can escape the callback's origin check.
- [WebViewClient.shouldOverrideUrlLoading](https://developer.android.com/reference/android/webkit/WebViewClient#shouldOverrideUrlLoading(android.webkit.WebView,%20android.webkit.WebResourceRequest)):
  this is navigation control, not general subresource interception; it is not
  called for POST requests or app-initiated loadUrl navigations.
- [WebResourceRequest](https://developer.android.com/reference/android/webkit/WebResourceRequest):
  exposes URL, method, headers, gesture/frame/redirect flags, but **no request
  body**. Reimplementing requests here cannot forward existing fetch POST
  bodies. Allowing POST to fall through simply retains an uncontrolled path.

Changing `shouldOverrideUrlLoading`, testing `isRedirect()`, inspecting responses
in error callbacks, or adding another initial-URL check does not repair this
boundary. A GET-only native interceptor would break pairing/API methods.

## Real browser experiment (not Android runtime acceptance)

Run `python3 clients/android/tests/redirect_fixture.py` from the repository root.
It serves two synthetic loopback origins, with no real credentials. In fresh
browser pages visit `http://127.0.0.1:18761/`, then `/unprotected`; inspect
`/stats` and `window.forbiddenScriptRan`. Stop the fixture after testing.

The checked-in fixture was exercised using browser automation with
**HeadlessChrome/145.0.0.0 on Linux**:

- Strict HTTP response CSP (`default-src/script-src/img-src/connect-src/style-src
  'self'`, frames/objects/workers/base disabled, forms self): initial same-origin
  script/image/stylesheet requests returned 302 to port 18762. **Zero forbidden
  origin requests**, script did not execute.
- Without CSP: **three forbidden-origin requests** (`/script`, `/image`, `/style`),
  and the redirected script executed.

This specifically distinguishes preventing contact from merely preventing
execution. It does **not** establish CSP behavior on Android WebView, other
versions, every resource type, POST redirects, frames/forms, workers/service
workers, WebSockets, speculative networking or non-Fetch channels. No claim is
made that strict CSP necessarily contacts the forbidden redirect target: the
three observed Chromium resource types did not.

## Exact blocker and design required

The current callback cannot inspect every hop, forward POST bodies, or modify
WebView-managed response headers. No independent trusted response-policy
boundary exists. Backend-provided/meta/JavaScript-injected CSP is not a native
mandatory response boundary and is not the requested independently enforced
network confinement. CSP would need trusted response delivery before parsing
for every document/worker, explicit coverage/denial of all resource channels,
and observed zero-contact redirect tests on supported Android WebView versions.
That architecture is **not implemented or proven here**.

A next design must add a safe native networking/serving boundary (or a separately
approved independent network enforcer), not another callback-only patch. One
candidate is an isolated loopback serving origin and native reverse transport
that receives complete methods/bodies, validates the fixed upstream origin
before every connection, disables automatic redirects and rejects off-origin
Location targets before contacting them. It must also prevent WebView direct
egress, preserve shared UI/backend API/auth behavior, handle service workers,
reject unsupported channels, and secure the local server against other apps
(Host/Origin/CSRF/session isolation). This is a design candidate, **not proof
that WebView's network-block settings alone cover all channels**. It requires
separate design review and runtime tests. No JavaScript/native bridge, TLS
bypass, broad security disabling, or silent POST-body loss is acceptable.

Keep fatal TLS verification, HTTPS outside exact loopback, memory-only auth,
no credential logging/disk caching, no file/content/device access, and existing
WebView/storage protections. Do not add a native broker that leaks tokens into
URLs or logs. No VM creation or host security-policy changes are authorized.

## Verification and artifact status

Private caches used:

```sh
export NATIVE_TOOLS_CACHE=/home/server1/.hermes/profiles/project-bot/cache/native-tools
export NATIVE_GRADLE_CACHE=/home/server1/.hermes/profiles/project-bot/cache/native-gradle
python3 clients/android/tests/security_test.py -v
sh clients/tools/build-android.sh
```

- Security contracts: **3 pass, 1 intentionally failing regression tripwire**
  detecting the known allowed-URL null fallback. This is a source contract, not
  a behavioral Android test and not sufficient acceptance for a future fix.
- Build wrapper: Java endpoint tests pass, then exits 1 at that regression,
  before assembly/copy/checksum publication. No build-script change was needed.
- Buildability was independently checked, **not as release acceptance**, using
  the existing cached JDK/SDK with JAVA_HOME, ANDROID_HOME, ANDROID_USER_HOME,
  GRADLE_USER_HOME and NATIVE_DEBUG_KEYSTORE set as in build-android.sh:
  `gradle -p clients/android --offline --no-daemon --dependency-verification strict
  :app:assembleDebug :app:lintDebug` — **BUILD SUCCESSFUL**, 51 actionable tasks,
  6 executed and 45 up-to-date; warning: platform-tools not installed. The
  lint XML contains five Warning issues and no Error/Fatal issues.
- `sdk/build-tools/35.0.0/apksigner verify --verbose
  clients/android/app/build/outputs/apk/debug/app-debug.apk`: verifies, v2 true,
  one signer. This remains debug-signed development software, not release-signed.
- `sha256sum` of both the Gradle output and retained artifact is unchanged:
  `d15eff2d2d483477c31a2059a878e22398fec6a8852322041d72f1fe73d465d6`.
  **There is no revised secure APK.** Signature/build success does not repair
  the defect. The artifact was not copied, deployed, or accepted.

Android runtime gate remains **unverified**: cached SDK contains build-tools
and platforms only; no platform-tools/adb, emulator, system image or existing
AVD was found in the checked locations. `/dev/kvm` exists but this user cannot
read/write it. No device session was established, no images were downloaded,
and no VM was created/started. A device/emulator zero-contact regression must
also verify normal pairing and authenticated POST bodies before acceptance.
