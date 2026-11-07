"""Exercise the public relay boundary with only Supercell HTTP substituted."""
import tempfile
from contextlib import closing
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from server.player_relay import create_app, UpstreamError


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.calls = []
        self.payload = {'tag': '#RJC8VGR2P', 'name': 'Player', 'trophies': 123,
                        'secret': 'never-return', 'brawlers': [
                            {'id': 16000000, 'name': 'SHELLY', 'power': 11,
                             'trophies': 123, 'secret': 'never-return'}]}
        self.error = None
        def fetch(tag):
            self.calls.append(tag)
            if self.error:
                raise self.error
            return dict(self.payload, tag=tag)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fetch = fetch
        self.budget = str(Path(self.temp.name) / 'budget.sqlite')
        self.app = create_app('private-upstream-key', fetch=fetch,
                              clock=lambda: self.now, budget_path=self.budget)
        self.addCleanup(self.app.extensions['relay_budget'].close)
        self.client = self.app.test_client()

    def get(self, tag='RJC8VGR2P', ip='1.2.3.4', **kwargs):
        return self.client.get('/v1/players/' + tag,
                               environ_overrides={'REMOTE_ADDR': ip}, **kwargs)

    def test_normalizes_filters_and_caches_player(self):
        result = self.get('rjc8vgr2p')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json, {
            'tag': '#RJC8VGR2P', 'name': 'Player', 'trophies': 123,
            'brawlers': [{'id': 16000000, 'name': 'SHELLY', 'power': 11, 'trophies': 123}]})
        self.get('%23RJC8VGR2P')
        self.assertEqual(len(self.calls), 1)
        self.now += 181
        self.get()
        self.assertEqual(len(self.calls), 2)
        self.assertNotIn('private-upstream-key', result.get_data(as_text=True))

    def test_rejects_invalid_paths_query_body_and_methods_without_upstream(self):
        for tag in ('../../etc/passwd', 'https:%2F%2Fevil.test', 'INVALID', 'P' * 17):
            self.assertIn(self.get(tag).status_code, (400, 404))
        self.assertEqual(self.get(query_string={'url': 'https://evil.test'}).status_code, 400)
        self.assertEqual(self.get(data='body').status_code, 400)
        self.assertEqual(self.client.post('/v1/players/RJC8VGR2P').status_code, 405)
        self.assertEqual(self.client.get('/.env').status_code, 404)
        self.assertEqual(self.calls, [])

    def test_per_ip_limit_does_not_trust_forwarded_header(self):
        for n in range(30):
            self.assertEqual(self.get(headers={'X-Forwarded-For': str(n)}).status_code, 200)
        self.assertEqual(self.get().status_code, 429)
        self.now += 61
        self.assertEqual(self.get().status_code, 200)

    def test_global_limit_counts_misses_but_allows_cached_results(self):
        tags = ['PP' + format(n, 'b').replace('1', 'P').replace('0', 'Q') for n in range(21)]
        for n, tag in enumerate(tags[:20]):
            self.assertEqual(self.get(tag, ip=str(n)).status_code, 200)
        self.assertEqual(self.get(tags[20], ip='new').status_code, 429)
        self.assertEqual(self.get(tags[0], ip='cached').status_code, 200)
        self.assertEqual(len(self.calls), 20)

    def test_upstream_errors_are_safe_and_cooldown_limits_retries(self):
        self.error = UpstreamError(403)
        result = self.get()
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.json, {'error': 'unavailable'})
        self.assertEqual(self.get('PPP', ip='other').status_code, 503)
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn('private', result.get_data(as_text=True))

    def test_not_found_is_cached_without_blocking_other_players(self):
        self.error = UpstreamError(404)
        self.assertEqual(self.get().status_code, 404)
        self.assertEqual(self.get().status_code, 404)
        self.assertEqual(len(self.calls), 1)
        self.error = None
        self.assertEqual(self.get('PPP').status_code, 200)

    def test_daily_budget_survives_restart(self):
        import sqlite3
        with closing(sqlite3.connect(self.budget)) as conn:
            conn.execute("INSERT OR REPLACE INTO budget(day, count) VALUES (?, ?)", (0, 2000))
            conn.commit()
        app = create_app('key', fetch=self.fetch, clock=lambda: self.now, budget_path=self.budget)
        self.addCleanup(app.extensions['relay_budget'].close)
        result = app.test_client().get('/v1/players/PPP')
        self.assertEqual(result.status_code, 429)
        self.assertEqual(result.headers['Retry-After'], '85400')
        self.assertEqual(self.calls, [])

    def test_malformed_upstream_profile_never_reaches_client(self):
        self.payload['brawlers'] = 'not-a-list'
        result = self.get()
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.json, {'error': 'unavailable'})

    def test_real_ip_header_is_trusted_only_from_local_nginx(self):
        for n in range(30):
            self.assertEqual(self.get(headers={'X-Real-IP': str(n)}).status_code, 200)
        self.assertEqual(self.get(headers={'X-Real-IP': '9.9.9.9'}).status_code, 429)
        self.assertEqual(self.get(ip='127.0.0.1', headers={'X-Real-IP': '9.9.9.9'}).status_code, 200)
        self.assertEqual(self.get(ip='127.0.0.1', headers={'X-Real-IP': '1.2.3.4'}).status_code, 429)

    def test_concurrent_upstream_calls_are_bounded_and_duplicate_tags_do_not_fetch(self):
        entered = threading.Barrier(3)
        release = threading.Event()
        calls = []
        def slow(tag):
            calls.append(tag)
            entered.wait(timeout=3)
            release.wait(timeout=3)
            return dict(self.payload, tag=tag)
        app = create_app('key', fetch=slow, clock=lambda: self.now)
        self.addCleanup(app.extensions['relay_budget'].close)
        def get(tag):
            with app.test_client() as client:
                return client.get('/v1/players/' + tag)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.submit(get, 'PPP'), pool.submit(get, 'QQQ')
            try:
                entered.wait(timeout=3)
                self.assertEqual(get('PPP').status_code, 503)
                self.assertEqual(get('RRR').status_code, 503)
                self.assertEqual(len(calls), 2)
            finally:
                release.set()
            self.assertEqual(first.result().status_code, 200)
            self.assertEqual(second.result().status_code, 200)
        self.assertEqual(get('PPP').status_code, 200)
        self.assertEqual(len(calls), 2)


if __name__ == '__main__':
    unittest.main()
