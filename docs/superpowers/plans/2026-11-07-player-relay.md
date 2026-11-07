# Player tag relay implementation plan

> For agentic workers: use executing-plans inline. Steps use checkboxes.

**Goal:** Load player data by tag without distributing any server credentials.
**Architecture:** An isolated loopback WSGI service behind nginx HTTPS holds the upstream key. The Windows client uses this relay by default and supports an explicit direct API mode.
**Tech stack:** Python standard library + Flask/Gunicorn on VPS; existing Python/Flask/JavaScript client.
**Spec:** ../specs/2026-11-07-player-relay-design.md

## Global constraints
- Source base: GitHub main 07bff534a6bedbcddd70dab9d31ea2e03acf8ff5; preserve old development checkout and Money configuration.
- Only a fixed HTTPS player endpoint, no SSH credentials or upstream token in public client.
- Separate service user, bounded cache and network IO, fixed upstream with redirects disabled.
- Existing sites remain operational; use a distinct hostname and HTTPS certificate.
- No automatic revocation or refresh of the Money key.

## Review focus
- Malformed tags, URLs and encoded paths never become arbitrary upstream URLs.
- Concurrent cache misses, repeated errors and spoofed forwarded headers cannot bypass global limits.
- Slow or oversized upstream responses do not consume unbounded resources or leak exceptions.
- Existing profiles default to relay; explicit direct mode retains legacy token refresh behavior.
- Background trophy refresh uses the same mode as the account loader; failed refresh preserves saved data.

## Task 1: Relay
Files: server/player_relay.py, server/requirements.txt, tests/test_player_relay.py, server/pyla-player-relay.service, server/nginx-player-relay.conf.
Interface: create_app(token, fetch=None, clock=None) -> Flask; GET /v1/players/<tag> returns filtered official-compatible player JSON.
- [x] Write tests for successful filtering, invalid requests, not-found/error handling, caching and rate/global limits; run unittest and observe missing implementation failure.
- [x] Implement fixed upstream request, bounded response/filtering, per-IP/global admission and bounded TTL cache. Single Gunicorn process with threads shares limits; global 20 upstream attempts/minute and 2000/day, per-IP 30 requests/minute, 2 concurrent upstream calls, cache 180s/max 512 entries, short negative cache, circuit cooldown on upstream auth/429 failures.
- [x] Run tests green; add deployment templates using non-root user and hardened systemd isolation.

## Task 2: Client and account UI
Files: common/player_client.py, common/utils.py, webui/player_api.py, webui/storage.py, webui/static/app.js, cfg/brawl_stars_api.toml; tests/test_player_client.py and tests/test_web_player.py.
Interface: fetch_relay_player(tag, timeout=15) -> dict; player_source config is relay or direct. Existing fetch_brawl_stars_player(token,tag,timeout) signature remains compatible for direct mode; stage_manager explicitly selects source.
- [x] Write RED tests for tag-only account load, safe failures, no portal access in relay mode, profile default/mode persistence and background refresh routing.
- [x] Implement relay client, default mode, mode-aware config loading and background refresh. Wizard shows tag and mode; developer fields remain under direct mode in integrations. Keep data on errors.
- [x] Run focused tests, full unittest discovery, node syntax check and git diff --check.

## Task 3: Deploy, verify and deliver
Files: docs/PLAYER-RELAY.md, OVERVIEW.md, README.md.
- [x] Read current nginx and DNS; create distinct host pyla-api.185-251-38-246.sslip.io with its own certificate and service.
- [x] Transfer only tested server files. Copy the Money key entirely on VPS into root-owned 0600 environment file; never print it. Install server dependencies in separate venv and enable hardened service.
- [x] Verify nginx configuration before reload. Check external HTTPS profile/invalid paths/methods, service user and sandbox, existing Money panel response, and Windows client tag-only call.
- [x] Review whole diff, security scan actual changes and verify tests; fix findings with regression tests. Commit and publish client changes only after clean checks (publication is part of approved public-client update); preserve separate desktop installation unless explicitly requested.

## Execution ledger
- Design approved by user 2026-11-07. Inline execution continues without another plan-approval round; existing authorization covers VPS deployment and client implementation. Publication scope will be checked against session authorization before push.

- Task 1: complete. Relay tests pass, including persistent budget, concurrency, whitelist and proxy-header controls.
- Task 2: complete. Wizard loaded 75 brawlers from a public tag without credentials; direct mode and stale snapshots covered.
- Task 3: deployment complete. External Windows HTTPS request succeeded, secret file mode 0600, service user pyla-relay, ProtectHome=yes, ProtectSystem=strict, NoNewPrivileges=yes, loopback port 8791, Money login still HTTP 200. Final delivery commit follows verification.
- Final review: independent reviewer identified six concrete issues; fixed with deadline/netrc/stale-settings regressions and quota/concurrency checks. No unresolved findings remain in the scoped review.
- Ruling: existing approval covers inline implementation, deployment and publishing the nonsecret client update; no redundant plan or integration approval requested.
- Ruling: no change to data-source design after the additional Amethyst inspection. Its HTML parser matched both live official profiles; this research request did not ask to replace the approved relay. Cost if preference differs: switching default source will require a separate adaptation.
- Ruling: adapted skill shell helpers to native Windows tooling and recorded progress here. Existing threat model retained and extended to version 1.1.0.
- Final verification: full unittest discovery 220 tests, one skipped; node syntax check and git diff --check clean. Existing OpenCV missing optional probe-image warning remains.
