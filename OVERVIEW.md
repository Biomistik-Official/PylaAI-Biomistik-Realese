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
- `webui/player_api.py` isolates developer-portal/player loading. Explicit login preserves account keys and rejects stale settings before saving a token.
- `webui/static/setup-flow.js` defines sequential emulator/account/brawlers/confirmation screens. Advanced pages retain settings, styles, history and runtime controls.

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
