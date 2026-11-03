# Approved Android native-client redesign

## Decision

The user explicitly approved replacing the Android WebView wrapper with native Chats, Agents and Activity screens using the existing backend/API. This supersedes attempts to repair redirected-subresource confinement using WebView callbacks. Web and Linux desktop are unchanged; the five-stage roadmap is unchanged. This is an approved design direction, not a completion or acceptance claim.

## Boundaries

- Keep all permissions, persistent chats, agent registry, model selection, approvals and security decisions in the existing backend. Native code is presentation and typed API transport, not a second agent system or inference server.
- Do not execute remote HTML/JavaScript or add a JavaScript/native, terminal, filesystem, arbitrary-intent or worker-control bridge.
- Bind transport to the explicitly configured backend origin, require HTTPS except exact loopback, retain platform certificate/hostname verification, and reject every HTTP redirect before following it. Rejecting same-origin redirects too is acceptable; the actual API routes should not require them.
- Preserve complete methods/bodies and bearer/CSRF handling for pairing and authenticated mutations. Use real backend route/field contracts, bounded bodies/responses/timeouts, plain-text rendering and generation-bound asynchronous results.
- Keep endpoint-only persistence and memory-only credentials; disclose re-pairing limitations. Preserve backup/debug protections, encrypted-storage/screen-lock requirements and least-privilege permissions. Native/background notifications are not claimed without implementation and verification.

## Acceptance gates frozen before implementation

1. Behavioral Java transport tests against two actual origins: redirected GET and POST responses (including 302/303/307/308) cause **zero** requests to the forbidden origin. Confirm supported same-origin API calls preserve methods, bodies and auth headers.
2. Verify fatal bad-TLS rejection, no production trust override, bounded failures and no accidental remote resource execution. A source-string assertion alone is not a behavioral security test.
3. Exercise native transport against an isolated actual Project Bots backend for pairing/session/CSRF and representative persistent chat/control APIs where possible; do not substitute fake replies for unsupported server functionality.
4. Produce the actual APK through the existing checksum-pinned cached toolchain, strict Gradle dependency verification, assembly/lint/signature/checksum checks. Existing insecure artifact is not reused as accepted output.
5. Independently review the new implementation and parent-verify combined regressions before a verified commit/publication. Record unresolved backend capabilities and physical-device gates explicitly.
6. Physical Android UI/OS acceptance remains separate. No established ADB/device/emulator/system image or permitted management-user KVM access exists. No host security weakening, device-permission changes, new VM or speculative large download is authorized by this decision.

## Current execution state

Bounded implementation `deleg_94cec731` produced native app and instrumentation APKs; parent repeated build/host transport/API/state checks and the 209-test source regression suite successfully (3 default skips). Parent verified artifact hashes and native API DEX classes without WebKit references. Initial native review `deleg_9d34bd02` found a stop-availability defect; the subsequent fix and scoped independent re-review `deleg_9c4a7a48` passed, with no blocking findings. The previous WebView APK is superseded, not accepted. The replacement remains **NOT ACCEPTED** pending review and actual Android/runtime/header/UI execution; instrumentation compilation is not execution. Do not remove the warning marker or claim product completion. Production VM isolation/monitoring and four-real-agent/shared-loaded-model acceptance remain independent pending gates.
