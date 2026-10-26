"""Exercise real settings HTTP routes, persistence and approval boundaries."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from server import Controller
from storage import read, write
import test_http_auth as http_tests


class IngressSettingsTests(unittest.TestCase):
    setUp = http_tests.HTTPTests.setUp
    tearDown = http_tests.HTTPTests.tearDown
    serve = http_tests.HTTPTests.serve
    def request_settings(self, data):
        url = self.serve(ingress=True)
        return requests.post(url + '/api/settings', json=data,
                             headers={'X-CSRF-Token': self.c.csrf}, timeout=5)

    def payload(self, **changes):
        return {'revision': self.c.identity(), 'options': {**self.c.options, **changes}}

    def approve(self):
        write(self.directory / 'analysis.json', {'fingerprint': self.c.identity()})
        self.c.action('approve', {})

    def test_save_applies_immediately_revokes_approval_and_survives_restart(self):
        self.approve()
        with patch.object(self.c, 'stop_watch') as stop:
            response = self.request_settings(self.payload(sync_interval_minutes=90, ratings=True))
        self.assertEqual(response.status_code, 200, response.text)
        stop.assert_called_once()
        self.assertEqual(self.c.options['sync_interval_minutes'], 90)
        self.assertFalse(self.c.approved())
        self.assertFalse((self.directory / 'analysis.json').exists())
        self.assertTrue(Controller(self.directory).options['ratings'])

    def test_secrets_are_write_only_and_blank_preserves_values(self):
        payload = self.payload()
        payload['credentials'] = {'plex_token': 'PRIVATE_FIXTURE_TOKEN', 'client_id': 'PRIVATE_FIXTURE_ID',
                                  'client_secret': 'PRIVATE_FIXTURE_SECRET'}
        response = self.request_settings(payload)
        self.assertEqual(response.status_code, 200, response.text)
        url = self.serve(ingress=True)
        for path in ('/api/settings', '/api/status'):
            text = requests.get(url + path, timeout=5).text
            self.assertNotIn('PRIVATE_FIXTURE', text)
        self.assertNotIn('PRIVATE_FIXTURE', response.text)
        saved = self.c.credentials()
        self.c.action('settings', {**self.payload(), 'credentials': {'plex_token': '', 'client_id': '', 'client_secret': ''}})
        self.assertEqual(self.c.credentials(), saved)
        self.assertTrue(response.json()['stored_credentials']['plex_token'])

    def test_invalid_input_has_no_side_effects(self):
        self.approve()
        original = read(self.directory / 'options.json')
        for changes in ({'collection': True}, {'sync_interval_minutes': 1}, {'plex_url': 'javascript:alert(1)'},
                        {'plex_url': 'https://user:secret@plex:32400'}, {'plex_url': 'http://plex:999999'},
                        {'plex_username': []}, {'ignore_ids': ['abc']}, {'ratings': 'yes'},
                        {'liked_list_overrides': [{'name': 'X', 'keep_watched': True}, {'name': 'X', 'keep_watched': False}]}):
            with self.subTest(changes=changes):
                response = self.request_settings({**self.payload(**changes), 'credentials': {'plex_token': 'must-not-save'}})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(read(self.directory / 'options.json'), original)
                self.assertEqual(self.c.credentials(), {})
                self.assertTrue(self.c.approved())

    def test_stale_tab_busy_worker_and_csrf_cannot_change_settings(self):
        old = self.payload(ratings=True)
        self.c.action('settings', self.payload(batch_delay=7))
        self.assertEqual(self.request_settings(old).status_code, 400)
        self.assertFalse(self.c.options['ratings'])
        self.c.lock.acquire()
        try:
            self.assertEqual(self.request_settings(self.payload(ratings=True)).status_code, 400)
        finally:
            self.c.lock.release()
        url = self.serve(ingress=True)
        self.assertEqual(requests.post(url + '/api/settings', json=self.payload(ratings=True), timeout=5).status_code, 403)
        self.assertFalse(self.c.options['ratings'])

    def test_noop_keeps_approval_and_tokens(self):
        write(self.directory / '.pytrakt.json', {'OAUTH_TOKEN': 'fixture'})
        self.approve()
        response = self.request_settings(self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.c.approved())
        self.assertTrue((self.directory / '.pytrakt.json').exists())

    def test_all_option_types_round_trip(self):
        options = dict(self.c.options)
        for key, value in options.items():
            if type(value) is bool:
                options[key] = not value
        options.update(plex_url='https://plex.invalid:32400', plex_username='fixture', sync_interval_minutes=120,
                       plex_timeout=40, request_timeout=45, batch_delay=8, rating_priority='plex', sync_media='tv',
                       movie_provider='tmdb', show_provider='tmdb', log_level='warning',
                       include_libraries=['Series'], exclude_libraries=['Private'], ignore_ids=['123'],
                       watch_ignore_clients=['client'], liked_list_overrides=[{'name': 'List', 'keep_watched': False}])
        response = self.request_settings({'revision': self.c.identity(), 'options': options})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['options'], options)
        self.assertEqual(Controller(self.directory).options, options)

    def test_disk_failure_revokes_approval_before_any_changed_file(self):
        self.approve()
        original = dict(self.c.options)
        with patch('server.write', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.c.action('settings', self.payload(ratings=True))
        self.assertFalse(self.c.approved())
        self.assertIsNone(read(self.directory / 'analysis.json'))
        self.assertEqual(self.c.options, original)
        self.assertEqual(Controller(self.directory).options, original)

    def test_replacing_trakt_client_secret_invalidates_old_authorization(self):
        self.c.action('credentials', {'client_id': 'one', 'client_secret': 'old'})
        write(self.directory / '.pytrakt.json', {'OAUTH_TOKEN': 'fixture'})
        self.approve()
        self.c.action('settings', {**self.payload(), 'credentials': {'client_secret': 'new'}})
        self.assertFalse((self.directory / '.pytrakt.json').exists())
        self.assertFalse(self.c.approved())

    def test_static_asset_allowlist_and_security_headers(self):
        url = self.serve(ingress=True)
        for path, mime in (('/', 'text/html'), ('/styles.css', 'text/css'), ('/ui.js', 'text/javascript')):
            response = requests.get(url + path, timeout=5)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.headers['Content-Type'].startswith(mime))
            self.assertIn("script-src 'self'", response.headers['Content-Security-Policy'])
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        for path in ('/credentials.json', '/default-options.json', '/api/missing', '/app/server.py'):
            self.assertEqual(requests.get(url + path, timeout=5).status_code, 404)
        html = requests.get(url, timeout=5).text
        self.assertNotIn('onclick=', html)
        self.assertIn('href="styles.css"', html)
        self.assertIn('src="ui.js"', html)


if __name__ == '__main__':
    unittest.main()
