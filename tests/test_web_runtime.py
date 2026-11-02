import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

from tests import test_web_storage
from webui.runtime import ProcessManager


FIXTURE = '''
import os, pathlib, time
path = pathlib.Path(os.environ['PYLAAI_CONTROL_PATH'])
print('fixture ready', flush=True)
while not path.exists() or path.read_text().strip() != 'stopped':
    time.sleep(.02)
print('fixture stopped', flush=True)
'''


class WebRuntimeTests(unittest.TestCase):
    def setUp(self):
        setup = test_web_storage.WebStorageTests('test_queue_persists_worker_fields_without_touching_legacy_save')
        setup.setUp()
        self.addCleanup(setup.doCleanups)
        self.store = setup.store
        self.store.save_queue(1, [{'brawler': 'shelly'}])
        self.manager = ProcessManager(self.store, command_factory=lambda instance: [sys.executable, '-u', '-c', FIXTURE])
        self.addCleanup(self.manager.close)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.02)
        self.fail('Worker did not reach expected state.')

    def test_real_worker_pause_resume_stop_and_logs(self):
        state = self.manager.start(1)
        self.assertGreater(state['pid'], 0)
        self.wait_for(lambda: 'fixture ready' in '\n'.join(self.manager.logs(1)))
        self.manager.pause(1)
        path = next((self.store.root / 'logs').glob('runtime_control_*.state'))
        self.assertEqual(path.read_text().strip(), 'paused')
        self.manager.resume(1)
        self.assertEqual(path.read_text().strip(), 'running')
        self.manager.stop(1)
        self.assertEqual(self.manager.status(1)['state'], 'stopped')
        self.assertIn('fixture stopped', '\n'.join(self.manager.logs(1)))
        self.assertFalse((self.store.root / 'logs/instance_1.lock').exists())

    def test_duplicate_start_does_not_launch_second_process(self):
        pid = self.manager.start(1)['pid']
        with self.assertRaises(ValueError):
            self.manager.start(1)
        self.assertEqual(self.manager.status(1)['pid'], pid)

    def test_worker_error_is_visible(self):
        manager = ProcessManager(self.store, command_factory=lambda instance: [sys.executable, '-c', 'raise SystemExit(7)'])
        self.addCleanup(manager.close)
        manager.start(1)
        self.wait_for(lambda: manager.status(1)['state'] == 'error')
        self.assertEqual(manager.status(1)['returncode'], 7)

    def test_empty_queue_cannot_start(self):
        self.store.save_queue(1, [])
        with self.assertRaises(ValueError):
            self.manager.start(1)

    def test_remote_control_changes_are_reflected_in_browser_status(self):
        self.manager.start(1)
        self.manager.records[1]['state_path'].write_text('paused')
        self.assertEqual(self.manager.status(1)['state'], 'paused')

    def test_old_tokens_stay_hidden_after_settings_are_cleared(self):
        manager = ProcessManager(self.store, command_factory=lambda instance: [sys.executable, '-u', '-c', "print('private-token', flush=True);" + FIXTURE])
        self.addCleanup(manager.close)
        manager.start(1)
        self.wait_for(lambda: 'fixture ready' in '\n'.join(manager.logs(1)))
        manager.stop(1)
        self.store.update_settings(1, 'telegram', {}, clear_secrets=['telegram_bot_token'])
        self.assertNotIn('private-token', '\n'.join(manager.logs(1)))

    def test_worker_refreshed_token_is_hidden_before_first_log_read(self):
        code = "from pathlib import Path; Path('cfg/telegram_config.toml').write_text('telegram_bot_token = \\\"rotated-fixture-token\\\"\\n'); print('request failed rotated-fixture-token', flush=True)"
        manager = ProcessManager(self.store, command_factory=lambda instance: [sys.executable, '-u', '-c', code])
        self.addCleanup(manager.close)
        manager.start(1)
        self.wait_for(lambda: manager.status(1)['state'] == 'stopped')
        manager.records[1]['reader'].join(timeout=2)
        self.store.update_settings(1, 'telegram', {}, clear_secrets=['telegram_bot_token'])
        self.assertNotIn('rotated-fixture-token', '\n'.join(manager.logs(1)))


if __name__ == '__main__':
    unittest.main()
