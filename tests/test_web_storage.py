import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import toml

from webui.storage import ProjectStore


class WebStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'cfg').mkdir()
        (self.root / 'playstyles').mkdir()
        (self.root / 'cfg/brawlers_info.json').write_text(json.dumps({'shelly': {}, 'colt': {}}))
        (self.root / 'cfg/general_config.toml').write_text('emulator_port = 5555\nmax_ips = 0\ncurrent_emulator = "LDPlayer"\n')
        (self.root / 'cfg/telegram_config.toml').write_text('telegram_bot_token = "private-token"\ntelegram_control_enabled = false\ntelegram_control_user_id = ""\n')
        self.store = ProjectStore(self.root)

    def test_secret_is_never_returned_and_blank_edit_preserves_it(self):
        fields = self.store.settings(1, 'telegram')
        token = next(field for field in fields if field['key'] == 'telegram_bot_token')
        self.assertEqual(token['value'], '')
        self.assertTrue(token['configured'])
        self.store.update_settings(1, 'telegram', {'telegram_bot_token': ''})
        self.assertEqual(toml.load(self.root / 'cfg/telegram_config.toml')['telegram_bot_token'], 'private-token')

    def test_clear_secret_is_explicit(self):
        self.store.update_settings(1, 'telegram', {}, clear_secrets=['telegram_bot_token'])
        self.assertEqual(toml.load(self.root / 'cfg/telegram_config.toml')['telegram_bot_token'], '')

    def test_bad_settings_do_not_partially_write(self):
        with self.assertRaises(ValueError):
            self.store.update_settings(1, 'general', {'max_ips': 30, 'emulator_port': 'bad'})
        self.assertEqual(toml.load(self.root / 'cfg/general_config.toml')['max_ips'], 0)
        with self.assertRaises(ValueError):
            self.store.update_settings(1, 'general', {'emulator_port': 5037})

    def test_other_instance_is_isolated_and_existing_config_is_preserved(self):
        self.store.create_instance(2)
        self.store.update_settings(2, 'general', {'max_ips': 20})
        self.store.create_instance(2)
        self.assertEqual(toml.load(self.root / 'cfg_2/general_config.toml')['max_ips'], 20)
        self.assertEqual(toml.load(self.root / 'cfg/general_config.toml')['max_ips'], 0)

    def test_queue_persists_worker_fields_without_touching_legacy_save(self):
        queue = self.store.save_queue(1, [{'brawler': 'shelly', 'push_until': 1000, 'trophies': 100, 'type': 'trophies', 'automatically_pick': True}])
        self.assertEqual(queue[0]['win_streak'], 0)
        self.assertEqual(queue[0]['wins'], 0)
        self.assertEqual(self.store.queue(1)[0]['push_until'], 1000)
        self.assertFalse((self.root / 'latest_brawler_data.json').exists())

    def test_invalid_queue_never_replaces_saved_queue(self):
        self.store.save_queue(1, [{'brawler': 'colt', 'push_until': 500}])
        for row in [{'brawler': '../../outside', 'push_until': 1}, {'brawler': 'colt', 'push_until': -1}, {'brawler': 'colt', 'push_until': True}, {'brawler': 'colt', 'automatically_pick': 'false'}]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.store.save_queue(1, [row])
        self.assertEqual(self.store.queue(1)[0]['push_until'], 500)

    def test_instance_ids_cannot_escape_config_folder(self):
        for invalid in ['../x', 0, -1, True, 99999]:
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                self.store.config_dir(invalid)

    def test_remote_control_needs_explicit_owner_when_token_is_filled(self):
        with self.assertRaises(ValueError):
            self.store.update_settings(1, 'telegram', {'telegram_control_enabled': True})

    def test_playstyle_cannot_escape_playstyles_directory(self):
        (self.root / 'playstyles/default.pyla').write_text('movement = (0, 0)')
        (self.root / 'cfg/bot_config.toml').write_text('current_playstyle = "default.pyla"\n')
        with self.assertRaises(ValueError):
            self.store.activate_playstyle(1, '../outside.pyla')

    def test_adaptive_learning_does_not_overwrite_other_instance(self):
        from common.adaptive_brain import AdaptiveBrain
        import os
        old_cwd = Path.cwd()
        try:
            os.chdir(self.root)
            with patch.dict(os.environ, {'PYLAAI_INSTANCE': '2'}):
                AdaptiveBrain().record_result('victory')
            self.assertTrue((self.root / 'cfg_2/adaptive_state.json').exists())
            self.assertFalse((self.root / 'cfg/adaptive_state.json').exists())
        finally:
            os.chdir(old_cwd)

    def test_thread_settings_can_switch_between_auto_and_integer(self):
        path = self.root / 'cfg/general_config.toml'
        path.write_text(path.read_text() + 'used_threads = 4\n')
        self.store.update_settings(1, 'general', {'used_threads': 'auto'})
        self.store.update_settings(1, 'general', {'used_threads': '2'})
        self.assertEqual(toml.load(path)['used_threads'], 2)


if __name__ == '__main__':
    unittest.main()
