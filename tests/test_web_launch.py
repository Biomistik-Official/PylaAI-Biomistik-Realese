import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from remote.runtime_control import RuntimeControlWindow


class BrowserLaunchTests(unittest.TestCase):
    def test_both_entrypoints_offer_browser_options_without_importing_game(self):
        for script in ('PylaLauncher.py', 'main.py'):
            with self.subTest(script=script):
                result = subprocess.run([sys.executable, script, '--help'], capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('--no-browser', result.stdout)
                self.assertIn('--port', result.stdout)

    def test_control_path_is_shared_and_startup_preserves_pause_request(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / 'runtime.state'
            state.write_text('paused')
            with patch.dict(os.environ, {'PYLAAI_CONTROL_PATH': str(state), 'PYLAAI_HUB_MODE': '1'}):
                control = RuntimeControlWindow()
                self.assertTrue(control.is_paused())
                state.write_text('stopped')
                self.assertTrue(control.is_stopped())

    def test_legacy_launcher_passes_legacy_mode_to_its_child(self):
        import PylaLauncher
        hub = object.__new__(PylaLauncher.MultiInstanceHub)
        hub.instances = {}
        hub._add_instance_card = lambda record: None
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'main.py').touch()
            with patch.object(PylaLauncher, 'BASE_DIR', temp), patch.object(PylaLauncher, 'LOCK_DIR', str(Path(temp, 'logs'))), \
                 patch.object(PylaLauncher.subprocess, 'Popen', return_value=SimpleNamespace(pid=12345)) as popen, \
                 patch.object(PylaLauncher.threading, 'Thread'):
                hub._launch(1, 5555, 'LDPlayer')
                self.assertIn('--legacy', popen.call_args.args[0])

    def test_hub_worker_close_does_not_stop_shared_adb_server(self):
        from vision.window_controller import WindowController
        controller = object.__new__(WindowController)
        stopped = []
        controller.scrcpy_client = SimpleNamespace(stop=lambda: stopped.append(True))
        with patch.dict(os.environ, {'PYLAAI_HUB_MODE': '1'}), patch('vision.window_controller.subprocess.run') as run:
            controller.close()
            self.assertEqual(stopped, [True])
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
