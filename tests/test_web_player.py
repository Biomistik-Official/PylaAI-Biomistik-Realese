import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import toml

from webui import player_api


class WebPlayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'cfg').mkdir()
        self.path = self.root / 'cfg/brawl_stars_api.toml'
        self.config = dict(player_tag='#TEST', player_source='direct', developer_email='private-email',
                           developer_password='private-password', api_token='',
                           auto_refresh_token=False, delete_old_auto_tokens=True,
                           delete_all_tokens=True, timeout_seconds=15)
        self.path.write_text(toml.dumps(self.config))

    def load(self):
        # The subprocess sets its cwd and instance before calling this boundary.
        return player_api.load_player(self.root, 1)

    def test_explicit_login_works_when_scheduled_refresh_disabled_without_revoking_keys(self):
        def refresh(config, *args, **kwargs):
            self.assertTrue(config['auto_refresh_token'])
            self.assertFalse(config['delete_all_tokens'])
            self.assertFalse(config['delete_old_auto_tokens'])
            self.assertFalse(kwargs['persist'])
            return dict(config, api_token='new-private-key', last_public_ip='127.0.0.1')
        with patch('common.utils.refresh_brawl_stars_api_token_if_enabled', side_effect=refresh), \
             patch('common.utils.fetch_brawl_stars_player', return_value={'name': 'Player', 'brawlers': []}):
            self.assertEqual(self.load()['name'], 'Player')
        saved = toml.load(self.path)
        self.assertEqual(saved['api_token'], 'new-private-key')
        self.assertFalse(saved['auto_refresh_token'])
        self.assertTrue(saved['delete_all_tokens'])

    def test_working_token_does_not_login_or_issue_another_key(self):
        self.path.write_text(toml.dumps(dict(self.config, api_token='existing')))
        with patch('common.utils.refresh_brawl_stars_api_token_if_enabled') as refresh, \
             patch('common.utils.fetch_brawl_stars_player', return_value={'brawlers': []}):
            self.load()
        refresh.assert_not_called()

    def test_invalid_ip_token_is_refreshed_on_explicit_load(self):
        self.path.write_text(toml.dumps(dict(self.config, api_token='stale-key')))
        with patch('common.utils.refresh_brawl_stars_api_token_if_enabled', return_value=dict(self.config, api_token='new-key')), \
             patch('common.utils.fetch_brawl_stars_player', side_effect=[RuntimeError('Brawl Stars API accessDenied'), {'name': 'Player'}]):
            self.assertEqual(self.load()['name'], 'Player')
        self.assertEqual(toml.load(self.path)['api_token'], 'new-key')

    def test_missing_player_does_not_create_more_tokens(self):
        self.path.write_text(toml.dumps(dict(self.config, api_token='existing')))
        with patch('common.utils.refresh_brawl_stars_api_token_if_enabled') as refresh, \
             patch('common.utils.fetch_brawl_stars_player', side_effect=RuntimeError('API error 404: notFound')):
            with self.assertRaises(player_api.PlayerError) as raised:
                self.load()
        self.assertEqual(raised.exception.code, 'tag')
        refresh.assert_not_called()

    def test_changed_account_during_login_does_not_receive_old_account_token(self):
        def fetch(*args):
            self.path.write_text(toml.dumps(dict(self.config, developer_email='other-email')))
            return {'name': 'Old account'}
        with patch('common.utils.refresh_brawl_stars_api_token_if_enabled', return_value=dict(self.config, api_token='old-account-token')), \
             patch('common.utils.fetch_brawl_stars_player', side_effect=fetch):
            with self.assertRaises(player_api.PlayerError) as raised:
                self.load()
        self.assertEqual(raised.exception.code, 'changed')
        self.assertEqual(toml.load(self.path)['api_token'], '')

    def test_direct_token_result_is_rejected_when_source_changes_during_fetch(self):
        self.path.write_text(toml.dumps(dict(self.config, api_token='existing')))
        def fetch(*args):
            self.path.write_text(toml.dumps(dict(self.config, player_source='relay')))
            return {'name': 'Old profile'}
        with patch('common.utils.fetch_brawl_stars_player', side_effect=fetch):
            with self.assertRaises(player_api.PlayerError) as raised:
                self.load()
        self.assertEqual(raised.exception.code, 'changed')

    def test_memory_only_refresh_does_not_save_override_flags_or_revoke_keys(self):
        from common import utils
        def post(session, endpoint, payload, timeout):
            if endpoint == 'account/load':
                return {'developer': {'allowedScopes': ['brawlstars']}}
            if endpoint == 'apikey/list':
                return {'keys': [{'id': 'keep-this', 'name': 'Pyla-Biomistik Auto old'}]}
            if endpoint == 'apikey/create':
                return {'key': 'new-key'}
            if endpoint == 'apikey/revoke':
                self.fail('Explicit login must not revoke existing keys')
            return {}
        with patch.object(utils, 'get_public_ip', return_value='127.0.0.1'), \
             patch.object(utils, '_developer_api_post', side_effect=post), \
             patch.object(utils, 'save_dict_as_toml') as save, \
             patch.object(utils, '_brawl_stars_api_refresh_done', False), \
             patch.object(utils, '_brawl_stars_api_refresh_signature', None), \
             contextlib.redirect_stdout(io.StringIO()):
            config = dict(self.config, auto_refresh_token=True, delete_all_tokens=False, delete_old_auto_tokens=False)
            self.assertEqual(utils.refresh_brawl_stars_api_token_if_enabled(config, force=True, persist=False)['api_token'], 'new-key')
        save.assert_not_called()

    def test_missing_login_is_actionable_without_exposing_credentials(self):
        self.path.write_text(toml.dumps(dict(self.config, developer_password='')))
        with self.assertRaisesRegex(ValueError, 'почту.*пароль|токен'):
            self.load()

    def test_child_failure_is_safe_and_actionable(self):
        output = io.StringIO()
        with patch.object(player_api, 'load_player', side_effect=RuntimeError('private-password')), \
             patch.object(player_api.os, 'chdir'), \
             contextlib.redirect_stdout(output):
            player_api.main()
        self.assertNotIn('private-password', output.getvalue())
        self.assertIn(player_api.MARKER, output.getvalue())


if __name__ == '__main__':
    unittest.main()
