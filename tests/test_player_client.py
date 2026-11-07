import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import toml

from common import player_client
from webui.player_api import load_player, PlayerError
from webui.storage import ProjectStore


class PlayerClientTests(unittest.TestCase):
    def test_tag_only_load_ignores_saved_portal_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'cfg').mkdir()
            path = root / 'cfg/brawl_stars_api.toml'
            original = toml.dumps(dict(player_tag='#RJC8VGR2P', developer_email='old',
                                       developer_password='old', api_token='old'))
            path.write_text(original)
            with patch('common.player_client.fetch_relay_player', return_value={'tag': '#RJC8VGR2P', 'brawlers': []}), \
                 patch('common.utils.refresh_brawl_stars_api_token_if_enabled', side_effect=AssertionError('No portal login')):
                self.assertEqual(load_player(root, 1)['tag'], '#RJC8VGR2P')
            self.assertEqual(path.read_text(), original)
            fields = {f['key']: f for f in ProjectStore(root).settings(1, 'api')}
            self.assertEqual(fields['player_source']['value'], 'relay')
            ProjectStore(root).update_settings(1, 'api', {'player_source': 'direct'})
            self.assertEqual(toml.load(path)['player_source'], 'direct')

    def test_relay_http_sends_no_saved_secrets_and_normalizes_tag(self):
        def get(url, **kwargs):
            self.assertEqual(url, 'https://pyla-api.185-251-38-246.sslip.io/v1/players/RJC8VGR2P')
            self.assertNotIn('Authorization', kwargs.get('headers', {}))
            return 200, {'tag': '#RJC8VGR2P', 'name': 'Player', 'brawlers': []}
        with patch('common.player_client.bounded_json_get', side_effect=get):
            self.assertEqual(player_client.fetch_relay_player(' rjc8vgr2p ')['name'], 'Player')

    def test_relay_rejects_invalid_tag_and_bad_response(self):
        with self.assertRaises(ValueError):
            player_client.fetch_relay_player('https://evil.test')
        with patch('common.player_client.bounded_json_get', return_value=(200, {'tag': '#OTHER', 'brawlers': []})):
            with self.assertRaises(player_client.RelayError):
                player_client.fetch_relay_player('#RJC8VGR2P')

    def test_network_errors_are_sanitized(self):
        with patch('common.player_client.bounded_json_get', side_effect=player_client.HTTPJSONError()):
            with self.assertRaises(player_client.RelayError) as raised:
                player_client.fetch_relay_player('#RJC8VGR2P')
        self.assertNotIn('private-password', str(raised.exception))

    def test_background_relay_does_not_refresh_developer_tokens(self):
        from common import utils
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'api.toml'
            path.write_text(toml.dumps(dict(player_tag='#RJC8VGR2P', auto_refresh_token=True,
                                            developer_email='old', developer_password='old')))
            with patch.object(utils, 'refresh_brawl_stars_api_token_if_enabled',
                              side_effect=AssertionError('No portal login')):
                self.assertEqual(utils.load_brawl_stars_api_config(str(path), force_refresh=True)['player_source'], 'relay')
        with patch('common.player_client.fetch_relay_player', return_value={'brawlers': []}):
            self.assertEqual(utils.fetch_brawl_stars_player('', '#RJC8VGR2P', source='relay'), {'brawlers': []})

    def test_gameplay_refresh_uses_tag_only_source(self):
        from core.stage_manager import StageManager
        with patch('core.stage_manager.load_brawl_stars_api_config',
                   return_value={'player_tag': '#RJC8VGR2P', 'player_source': 'relay'}), \
             patch('common.player_client.fetch_relay_player', return_value={'brawlers': [{'name': 'SHELLY', 'trophies': 12}]}):
            self.assertEqual(StageManager.fetch_push_all_player_data()['brawlers'][0]['trophies'], 12)

    def test_relay_not_found_maps_to_actionable_player_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'cfg').mkdir()
            (root / 'cfg/brawl_stars_api.toml').write_text('player_tag="#RJC8VGR2P"')
            with patch('common.player_client.fetch_relay_player', side_effect=player_client.RelayError('tag')):
                with self.assertRaises(PlayerError) as raised:
                    load_player(root, 1)
            self.assertEqual(raised.exception.code, 'tag')


if __name__ == '__main__':
    unittest.main()
