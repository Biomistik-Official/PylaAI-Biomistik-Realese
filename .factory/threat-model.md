# Threat model: PylaAI Biomistik

Version 1.1.0 — 2026-11-07. Method: STRIDE, source review.

## System overview and data flow

Python/Flask serves a local browser panel. Authenticated HTTP actions validate profile/queue/settings, then start owned Python workers. Workers capture emulator frames through scrcpy, run ONNX inference and send input through ADB. Optional outgoing HTTPS connects to the Brawl Stars developer/player APIs, Telegram, Discord and GitHub. Configuration is TOML/JSON; the desktop application has no SQL database. The separate public player relay uses SQLite for its bounded upstream budget.

| Component | Boundary | Criticality |
| --- | --- | --- |
| Browser/API | Other websites to loopback process | High |
| Storage | Request data to profile files | High |
| Runtime | Validated queue to executable worker | High |
| Player API | Local credentials to official portal | High |
| Remote controls | Platform messages to owner-authorized commands | High |
| Vision/assets | Local model/image inputs to inference | Medium |
| Updater/styles | Downloaded or user-authored content to local files/code | High |

## Trust zones and assets

Untrusted: other websites, HTTP inputs, upstream responses, remote messages and downloaded files. Authenticated: requests carrying the unpredictable UI token with valid loopback Host/Origin. Trusted: same-OS user, private config files, intentionally installed playstyles and emulator commands. The application is not a sandbox against another process running as the same OS user.

Assets: developer email/password, API/bot tokens and webhook URLs; owner/chat IDs and player tags; queue/progress/history; model integrity and ability to send emulator input. Publication must contain blank credential/identity templates and exclude private runtime files/screenshots. Local credential files are plaintext, protected by OS account access, not encryption.

## Attack surface

The loopback server exposes HTML/static/catalog portraits plus token-protected `/api/*` for bootstrap, devices, per-profile settings, queue/Push All/sync, player loading, playstyles, history, logs and runtime controls. API bodies are capped at 1 MiB. Instance IDs, queue names/types/numbers and settings are validated. No arbitrary file upload endpoint is present. Portrait paths are constrained by the catalog. External interfaces include developer login/key creation, player reads, remote polling/webhooks and GitHub source updates.

## STRIDE analysis

- **Spoofing:** another site could try DNS rebinding or cross-origin actions. Loopback binding, Host/Origin checks, per-process token and absent CORS grants mitigate this. Remote controls validate owner IDs; notifications alone do not authorize commands.
- **Tampering:** HTML interpolation, profile paths and shell input are sensitive sinks. Dynamic browser values are escaped; profile/catalog paths are constrained; queue writes are validated and atomic. ADB text is quoted and restricted. Local custom emulator commands and `.pyla` styles intentionally execute trusted owner input. Player loads serialize by profile and reject stale credentials before persisting tokens.
- **Repudiation:** runtime logs are local, bounded and mutable; there is no tamper-proof audit. This is accepted for a single-user desktop application. Publication excludes logs.
- **Information disclosure:** API settings return configured flags and blank secret values, blank edits preserve credentials, explicit clear removes them. Runtime ingestion and reads redact accumulated session secrets. Player failures use fixed safe messages. Private runtime files and filled configs must never be staged for publication.
- **Denial of service:** external API calls and inference can be slow. Subprocess timeouts, bounded logs and profile-scoped locks mitigate some impact. The desktop panel has no Internet-facing rate limiter; never expose that panel publicly. The separate player relay has its own nginx/systemd isolation, bounded cache, global/per-IP admission limits and persisted daily upstream budget. Model loading is inherently resource-intensive.
- **Elevation of privilege:** starting a worker executes code as the local OS user. Remote ownership and API protection are essential. Playstyles, custom launch commands and updates are privileged trusted operations, not safe formats for arbitrary third-party input. GitHub HTTPS transport and repository ownership do not provide signed update provenance.

## Review patterns and testing strategy

Inspect `innerHTML` interpolation for `escapeHtml`; reject raw user data passed to shell strings; keep path resolution under the selected profile and catalog; require API token and valid Host/Origin before reads and writes; require remote owner identity before control. SQL injection and SQL IDOR are not applicable to this file-backed design. Profile numbers are local configuration identities, not multi-user tenant authorization.

Regression tests exercise API guards, secret preservation/clearing, profile isolation, process lifecycle, named selection and stale-account behavior. Publication additionally inspects the staged index for credential values, private file paths and generated user data. Binary runtime dependencies/models are inherited resources; this review does not certify their supply chain.

## Assumptions and changelog

Assumes trusted OS user, loopback-only use, official external destinations and reviewed local styles. Accepted limitations: plaintext local secrets, unsigned updater/assets, no immutable audit, no defense against same-user local malware. This model covers the browser and gameplay migration; it does not claim a penetration test or a clean-machine installation test.

1.0.0: initial model for the sanitized browser/gameplay publication.

## Public player relay (1.1.0)

Tag-only profiles now use a dedicated HTTPS service; only explicit direct mode contacts the developer portal. See [scoped relay threat model](../docs/PLAYER-RELAY-THREAT-MODEL.md) for architecture, trust boundaries, STRIDE analysis and deployment assumptions. No SSH or upstream credentials are distributed. Ambient netrc/proxy authentication is disabled and complete HTTP operations have a deadline and response-size cap. Public quota exhaustion remains an accepted availability limitation.

1.1.0: isolated public player relay and source selection; existing desktop trust assumptions retained.
