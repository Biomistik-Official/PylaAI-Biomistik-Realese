# Verified project overview

Windows / Python 3.11 application using OpenCV, ONNX Runtime, ADB and scrcpy. Flask serves dependency-free browser menus on loopback. CustomTkinter remains available with `--legacy`.

Install both `requirements.txt` and `requirements-web.txt` into a new Python 3.11 venv. The `setuptools<82` constraint is required because scrcpy-client's adbutils dependency imports `pkg_resources`, which newer setuptools no longer provides. See README for another-PC and multi-account setup.

## Entry points

- `start-browser.bat` uses `.venv` when present, then runs `PylaLauncher.py`.
- `PylaLauncher.py` and `main.py` open browser menus by default.
- `webui/launcher.py` binds loopback and supports `--port` and `--no-browser`.
- `webui/app.py` authenticates API requests with a per-process session token and validates Host/Origin.
- `webui/storage.py` validates and atomically saves settings/queues, hides secrets and isolates profiles.
- `webui/runtime.py` manages worker subprocesses, pause/stop state and redacted bounded logs.
- `common/player_client.py` loads tag-only profiles via a fixed public HTTPS relay; `common/http_json.py` bounds complete HTTP operations and disables ambient authentication. `server/player_relay.py` is the separate Linux relay, with a filtered schema, bounded cache, quotas and deployment templates under `server/`. See `docs/PLAYER-RELAY.md`.
- `webui/player_api.py` isolates relay/direct player loading. `player_source` defaults to `relay` for both new and existing profiles; only explicit `direct` mode contacts the developer portal. Explicit login preserves account keys and rejects stale settings before saving a token.
- `webui/static/setup-flow.js` defines sequential emulator/account/brawlers/confirmation screens. Advanced pages retain settings, styles, history and runtime controls.
- `webui/static/style.css` defines the graphite/yellow roster theme, responsive layouts and keyboard focus. `webui/static/icons.svg` supplies local line icons; fonts use the OS stack and portraits remain local catalog assets. The presentation refresh preserves API routes, control IDs, setup gates and runtime behavior.

## Game flow and resources

`main.py` coordinates capture, state detection and match processing. `vision/window_controller.py` owns emulator/capture/input. `vision/detect.py` and `vision/entity_model.py` decode classic/pose/end-to-end/semantic outputs. `core/play.py` performs movement and combat. `core/stage_manager.py` handles lobby, rewards and queues. `remote/` contains Telegram/Discord controls.

`vision/model_profiles.py` selects the paired modern assets in `models/upstream-763c389/` by default; original assets remain available as `legacy`. Ground keypoints preserve the four-coordinate box contract. Semantic terrain blocks movement separately from shooting walls; hostile summons can be targeted.

`core/brawler_selection.py` searches the current game menu by queued name and confirms lobby return. Failed/cancelled selection cannot authorize match start or watchdog retries. Legacy scrolling is an explicit fallback. Versioned templates live in `images/upstream-763c389/`. Browser portraits come from `api/assets/brawler_icons/`; display names remain separate from canonical queue keys.

## Local data

`cfg/` contains public empty configuration templates. Additional profiles use `cfg_2/` through `cfg_99/`, selected by `PYLAAI_INSTANCE`. Queues use each profile's `browser_queue.json`; adaptive learning and history are local. Logs and process locks are created under `logs/`. These runtime files, private screenshots and environment folders are excluded from Git.

Browser workers receive `PYLAAI_CONTROL_PATH` explicitly for Windows venv PID differences. Cleanup closes the owned capture client while retaining the shared ADB server. Remote integrations require an owner ID when control is enabled. Local playstyles and custom emulator commands are trusted executable input.

## Verification and limits

Run `python -m unittest discover -s tests -q`, `node tests/test_setup_flow.cjs`, `node --check webui/static/app.js`, and `git diff --check` from the repository root. Models and game-menu selection have local smoke coverage; full gameplay and clean-machine installation remain unverified. No rebuilt installer is included. See `docs/UPSTREAM-MIGRATION.md` and `.factory/threat-model.md` for migration and trust boundaries.

Publication verification on 2026-11-06 used a newly created Python 3.11 venv on the existing Windows PC: all requirements installed, `pip check` passed, 199 tests ran (198 passed, one skipped), the real panel served HTTP 200 with 109 catalog entries and idle profiles, and both current models inferred through CPU and DirectML. See `docs/PUBLICATION-2026-11-06.md`. Five concurrent matches and a separate clean Windows host were not tested.

The UI refresh on the same date retained that Python result (199 tests, one skipped) and passed 13 setup-flow assertions and JS syntax checks. Browser checks covered the desktop dashboard at 1440px, mobile pages at 390px, search and add/remove queue actions, four setup screens, settings, integrations, styles, history and logs. No horizontal page overflow or console warnings/errors were observed; the keyboard focus ring was visible, and the empty-device step blocked Next. The queue was restored empty and gameplay was not started. See `docs/superpowers/specs/2026-11-06-ui-design.md` for the approved direction and pass report.
