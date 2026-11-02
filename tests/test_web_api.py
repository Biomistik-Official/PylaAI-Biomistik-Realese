import re
import unittest

from tests import test_web_storage
from webui.app import create_app


class WebApiTests(unittest.TestCase):
    def setUp(self):
        fixture = test_web_storage.WebStorageTests('test_queue_persists_worker_fields_without_touching_legacy_save')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.store = fixture.store
        self.app = create_app(self.store.root, device_loader=lambda: [], player_loader=lambda instance: {
            'brawlers': [{'name': 'COLT', 'trophies': 800}, {'name': 'SHELLY', 'trophies': 250}]
        })
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.headers = {'X-Pyla-UI-Token': self.app.config['UI_API_TOKEN']}
        self.addCleanup(self.app.config['runtime_manager'].close)

    def test_api_requires_session_token_even_for_reads(self):
        self.assertEqual(self.client.get('/api/bootstrap').status_code, 403)
        response = self.client.get('/api/bootstrap', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['brawlers'], ['colt', 'shelly'])

    def test_external_host_and_cross_origin_are_rejected(self):
        for headers in [dict(self.headers, Host='attacker.invalid'), dict(self.headers, Origin='https://attacker.invalid')]:
            self.assertEqual(self.client.get('/api/bootstrap', headers=headers).status_code, 403)

    def test_html_contains_session_token_but_no_stored_secrets(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.app.config['UI_API_TOKEN'], response.text)
        self.assertNotIn('private-token', response.text)

    def test_settings_response_hides_secrets(self):
        response = self.client.get('/api/instances/1/settings/telegram', headers=self.headers)
        self.assertNotIn('private-token', response.text)
        self.assertEqual(response.status_code, 200)

    def test_queue_and_settings_are_saved_and_bad_json_leaves_them_unchanged(self):
        path = '/api/instances/1/queue'
        response = self.client.put(path, headers=self.headers, json={'queue': [{'brawler': 'colt', 'push_until': 500}]})
        self.assertEqual(response.status_code, 200)
        for payload in [[], None, {'queue': [{'brawler': 'unknown'}]}]:
            self.assertEqual(self.client.put(path, headers=self.headers, json=payload).status_code, 400)
        self.assertEqual(self.store.queue(1)[0]['brawler'], 'colt')

    def test_instance_creation_never_overwrites_other_config(self):
        response = self.client.post('/api/instances', headers=self.headers, json={'instance': 2})
        self.assertEqual(response.status_code, 200)
        self.assertTrue((self.store.root / 'cfg_2/general_config.toml').is_file())

    def test_push_all_uses_owned_brawlers_below_target_sorted_by_trophies(self):
        response = self.client.post('/api/instances/1/queue/push-all', headers=self.headers, json={'target': 750})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['brawler'] for row in response.json['queue']], ['shelly'])
        self.assertEqual(response.json['queue'][0]['trophies'], 250)

    def test_unknown_section_is_json_error(self):
        response = self.client.get('/api/instances/1/settings/nope', headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json['ok'])

    def test_catalog_has_display_names_and_local_portraits(self):
        data = self.client.get('/api/bootstrap', headers=self.headers).json
        self.assertEqual(data['catalog'][0]['name'], 'colt')
        self.assertEqual(data['catalog'][0]['display_name'], 'Colt')
        self.assertTrue(data['catalog'][0]['icon'].startswith('/assets/brawlers/'))
        response = self.client.get(data['catalog'][0]['icon'])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.mimetype.startswith('image/'))
        self.assertEqual(self.client.get('/assets/brawlers/unknown.png').status_code, 404)

    def test_explicit_player_load_does_not_replace_queue(self):
        self.store.save_queue(1, [{'brawler': 'colt', 'push_until': 500}])
        response = self.client.post('/api/instances/1/player', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['player']['brawlers'][0]['name'], 'COLT')
        self.assertEqual(self.store.queue(1)[0]['push_until'], 500)


if __name__ == '__main__':
    unittest.main()
