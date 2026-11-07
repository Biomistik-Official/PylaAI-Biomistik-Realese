# PylaAI Biomistik

Fork of [PylaAI](https://github.com/PylaAI/PylaAI) with browser menus, multiple emulator profiles, playstyles and Telegram/Discord controls.

## Getting started

Requirements: Windows, Python 3.11 (64-bit), and an Android emulator with Brawl Stars. The recommended game resolution is 1920×1080.

To set up the project on another computer:

1. Install Python 3.11 (64-bit) and enable **Add Python to PATH**.
2. [Download the project as a ZIP archive](https://github.com/Biomistik-Official/PylaAI-Biomistik-Realese/archive/refs/heads/main.zip) and extract it into a separate folder.
3. Open a terminal in the extracted folder and run the commands below. Installing dependencies requires an Internet connection and may take several minutes.
4. Start your Android emulator, enable ADB if it is disabled, and open Brawl Stars.
5. After installation, use `start-browser.bat` to open the panel.

Run these commands from the project folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-web.txt
.\start-browser.bat
```

The setup wizard opens in your browser, usually at [127.0.0.1:5185](http://127.0.0.1:5185):

1. Select a connected emulator.
2. Optionally connect to the Brawl Stars API. Enter only your player tag, then click Load brawlers. Developer registration, passwords and API tokens are not needed in the default mode. You can skip this step.
3. Select brawler cards, set trophy or win targets, and build your queue.
4. Review the settings and click the button to start the bot.

For the legacy desktop menus, run `python PylaLauncher.py --legacy`. To run the panel without opening a browser tab, use `python PylaLauncher.py --no-browser --port 5185`.

Closing the browser tab does not stop gameplay: use the Stop button in the panel. Pressing Ctrl+C in the panel's terminal stops its bot instances. Keep the ADB executable and DLL files in the project root; they are required at runtime.

## Multiple accounts

To play on five accounts simultaneously, you need five separate Android emulator instances, each signed in to its own Brawl Stars account. Add profiles 2–5 from the panel's overview page. In each profile, select the corresponding device with its own ADB port, configure the queue, and start the bot. Two running profiles cannot share the same emulator.

Sign in to Brawl Stars inside each emulator. The optional API connection in the panel's second setup step only loads player data and trophies; it does not sign in to the game. Set the appropriate player tag for each profile's API settings. The default tag-only service works across computers and networks. Advanced users can choose their own direct API in Integrations.

Do not copy the `.venv` folder from your old computer: recreate it using the commands above. Enter your personal settings locally on the new device.

## Settings and personal data

The repository includes empty configuration templates for the API, Telegram, Discord, and login. Passwords, tokens, IDs, player tags, queues, match history, learning data, logs, and private screenshots are excluded from this publication. Enter these values locally and do not commit populated settings to Git.

Leaving a password or token field empty preserves its existing value. The Clear button removes it when you save. Direct API mode first tries the existing token and does not delete account keys. The default relay mode sends only the public player tag; server and SSH credentials are never shipped with the app. See [player relay documentation](docs/PLAYER-RELAY.md) for service limits and deployment. Set your owner ID before enabling remote control. Additional profiles are stored in `cfg_N/`.

## Updates

This version incorporates upstream models and game UI support from October 31, 2026: brawler selection by name search, updated vision models, terrain and spawnable detection, and new reward screens. Legacy models and scrolling selection remain available as fallbacks. See the [migration notes](docs/UPSTREAM-MIGRATION.md).

This is a source distribution. Legacy installers, EXE updaters, and one-off patch scripts are not included. Use `start-browser.bat` to launch this version. The built-in updater downloads source files from this repository's `main` branch.

On November 6, 2026, dependencies were installed in a newly created Python 3.11 environment on Windows. The panel returned HTTP 200, both models completed inference on CPU and DirectML, and the emulator and game modules imported successfully. Of 199 tests, 198 passed and one was skipped. See the [publication verification report](docs/PUBLICATION-2026-11-06.md). Full matches after the migration, five simultaneous games, and installation on a separate clean Windows machine still require verification.

## Development

Project architecture: [OVERVIEW.md](OVERVIEW.md).

```powershell
python -m unittest discover -s tests -q
node tests/test_setup_flow.cjs
node --check webui/static/app.js
git diff --check
```

Node.js is only needed for JavaScript checks; the panel itself runs on Python.

Original project authors: Iyordanov, AngelFire. Fork author: Biomistik.
