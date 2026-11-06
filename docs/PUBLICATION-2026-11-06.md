# Publication verification — 2026-11-06

The publication uses the sanitized source checkout, not private working configurations. Runtime code and resources were compared with the latest desktop development copy. Public configuration templates contain no personal credential or identity values; logs, screenshots, queues and other private runtime state are excluded. The publication scan examined 395 tracked files and found no credential patterns or matches against the local private configuration secrets. This is source review, not a binary supply-chain audit.

## Installation compatibility fix

A new Python 3.11 environment reproduced a startup failure: scrcpy-client's adbutils dependency imports `pkg_resources`, but dependency resolution installed setuptools 84, which does not provide that module. The requirement `setuptools<82` fixes the observed failure. The removal boundary is documented by [setuptools](https://setuptools.pypa.io/en/latest/deprecated/pkg_resources.html). No application logic was changed for this fix.

## Verification

On the existing Windows PC, using the newly created environment and the published requirement files:

- Full dependency installation completed; `python -m pip check` reported no broken requirements.
- `python -m unittest discover -s tests -q`: 199 tests, 198 passed, one skipped because the optional historical lobby snapshot is absent.
- `node tests/test_setup_flow.cjs`: 13 assertions passed.
- `node --check webui/static/app.js` and Git whitespace checks passed.
- A real `PylaLauncher.py --no-browser` process served HTTP 200. Its authenticated bootstrap returned 109 catalog entries, with all profiles idle and queues empty. The verification process was then stopped without starting a bot.
- Both current ONNX models completed inference on a synthetic 1920×1080 frame with CPUExecutionProvider and DmlExecutionProvider. The requested execution provider was confirmed for each model.
- `import scrcpy, main` completed successfully, without starting gameplay.

These checks do not demonstrate match quality, performance with five simultaneous games, or installation on a separate clean Windows machine. The source distribution includes no rebuilt EXE installer. Follow the root README to install dependencies and launch `start-browser.bat`.
