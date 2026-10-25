from pathlib import Path
import sys
import unittest
from flask import Flask, session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rootfs/opt/ha-cwa'))
from shelfmark_ui import install_reader_ui


class ReaderUiTest(unittest.TestCase):
    def test_onboarding_is_hidden_only_in_reader_response(self):
        app = Flask(__name__)
        app.secret_key = 'test-only'
        saved = {'onboarding_complete': False, 'settings_enabled': True}

        @app.get('/api/config')
        def config():
            return dict(saved)

        install_reader_ui(app)
        client = app.test_client()
        for admin in (False, True):
            with client.session_transaction() as state:
                state['is_admin'] = admin
            response = client.get('/api/config')
            self.assertEqual(response.json['onboarding_complete'], not admin)
            self.assertIs(response.json['settings_enabled'], True)
            self.assertIs(saved['onboarding_complete'], False)
