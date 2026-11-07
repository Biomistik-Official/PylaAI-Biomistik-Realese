# Threat model for PylaAI Biomistik

Last updated: 2026-11-07. Version: 1.0.0. Method: STRIDE.

## 1. System Overview

Pyla is a Windows Python application controlling an Android emulator through ADB/scrcpy. OpenCV/ONNX process screenshots; the game worker sends input. A loopback Flask panel stores per-instance TOML settings and JSON queues and manages worker subprocesses. Optional Telegram/Discord integrations issue owner-authorized commands. The new standalone Linux Flask/Gunicorn service relays public Brawl Stars profiles through nginx HTTPS.

Flow: local user enters tag -> authenticated loopback panel -> credential-free HTTPS client -> public relay validates tag and admits request -> fixed Supercell API with server-held token -> schema whitelist -> panel/queue. Background trophy refresh uses the same configured source.

## 2. Trust Boundaries & Security Zones

- Public zone: internet clients, player tags and profile data. Public relay intentionally has no user login. It grants only public-profile reads.
- Local authenticated zone: panel validates Host, Origin and a per-process UI token. Local account settings may contain user-owned API/Telegram/Discord secrets.
- Server internal zone: nginx forwards to loopback Gunicorn as a dedicated non-login user; only local nginx supplies the IP header. Root loads the relay credential from a 0600 environment file.
- Administrator zone: SSH credentials and existing hosted project data remain outside the app and relay. No client request selects a command, file or arbitrary URL.

## 3. Attack Surface Inventory

Public GET /v1/players/<tag>; local panel settings/queues/runtime routes; remote owner bot commands; updater/downloads; ADB device selection and optional emulator launch command. This change reviews relay and source selection; it is not a comprehensive audit of the existing updater, remote integrations or gameplay code.

## 4. Critical Assets

Supercell token and shared upstream quota; SSH/private files and other hosted projects; local developer credentials and remote bot tokens; per-profile queue/config integrity; emulator input and process ownership. Public tags/names/trophies are intentionally returned. Runtime keys, logs, personal settings and SSH material must never enter Git or HTTP responses.

## 5. Threat Analysis

| Component | S: spoofing | T: tampering | R: repudiation | I: disclosure | D: denial of service | E: privilege |
|---|---|---|---|---|---|---|
| Public relay | TLS server identity; trust IP header only from loopback | Strict tag alphabet, fixed upstream and parameterized SQLite | No access log for public profiles; systemd records lifecycle | Allowlist fields, generic errors, no static files or admin routes | IP/global limits, bounded TTL cache, two inflight calls, total IO deadline and response cap | Non-root, no command or path input, read-only service filesystem, restricted capabilities |
| nginx/systemd | Override client IP header; strip supplied credentials | Root-owned config/code | Root deployment operations and service journal | Protected environment file; private home directories and TLS keys inaccessible | Connection/rate/resource limits | Dedicated user, no-new-privileges and empty capabilities; SSH unchanged |
| Local panel/client | Existing UI session token, Host/Origin checks | Typed settings, escaped UI, source snapshot check | Existing local logs; no claim of tamper-proof audit | Ambient netrc disabled; credentials hidden; relay never receives stored direct credentials | Bounded HTTP and errors preserve queue | App does not distribute SSH or server credentials |
| Game worker/legacy UI | Same selected profile source | Source propagated to all player-fetch call sites | Existing game logs | Direct API remains opt-in and local | Relay outages cannot authorize incorrect data replacement | Existing ADB/worker control stays local |
| Remote integrations/updater | Existing owner checks and upstream transport | Existing command/update boundaries, unchanged | Existing logs | Existing redaction, unchanged | Existing worker limits, unchanged | Custom emulator commands and updater have local-user authority; not granted through relay |

Priorities: credential disclosure/command execution HIGH; missing input bounds or total IO deadline MEDIUM; false cached profile or stale settings MEDIUM. Shared public-quota exhaustion is an accepted availability tradeoff, not server authorization.

## 6. Vulnerability Pattern Library

- SQL: use `execute("... WHERE day = ?", (day,))`; never concatenate request input.
- XSS: profile names go through existing `escapeHtml` or textContent; never insert returned names as raw markup.
- Command injection: no relay request reaches subprocess, eval, shell, emulator launch commands or systemd arguments.
- Traversal/SSRF: validate tags against the game alphabet; append only normalized tag to a constant host; disallow redirects.
- Auth bypass: public profile endpoint does not imply a public settings/runtime/admin endpoint; local UI retains its token/Host/Origin checks.
- IDOR: public game profiles are intentionally tag-addressable; never expose local profile settings using a game tag.
- Prompt injection: fetched documentation/profile data is untrusted input, never operator instructions.

## 7. Security Testing Strategy

Unit/integration tests exercise invalid tags/routes/methods, explicit response whitelist, normal and negative cache, rate/quota controls, persisted daily quota, spoofed IP headers, safe upstream errors, whole-operation deadlines with a real slow local HTTP server, netrc credential isolation and stale-setting rejection. Deployment verifies loopback binding, non-root user, root-only environment file, nginx config, external TLS response and the existing dashboard response.

## 8. Assumptions and Accepted Risks

Root and local administrators are trusted. Existing host services may be independently vulnerable; no whole-host penetration test was performed. Public API can be invoked by third-party scripts and can exhaust its bounded quota. A shared Supercell key couples relay availability to the existing project; a separate key is preferable for independent rotation. Cache can lag 180 seconds. sslip.io DNS and certificate renewal are external operational dependencies. TLS and process isolation reduce risk but do not guarantee absence of implementation vulnerabilities.

## 9. Version Changelog

1.0.0: Initial scoped model for the public player relay and client integration.
