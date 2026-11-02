"""Theme integration: ingress prefixes, authentication and native templates."""
from pathlib import Path
import os
import sys
import unittest

from flask import Flask, abort, render_template, request
from jinja2 import DictLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rootfs/opt/ha-cwa'))
from modern_theme import install_modern_theme


class ModernThemeTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.jinja_loader = DictLoader({
            'layout.html': '<html lang="de"><head></head><body>{% block body %}{% endblock %}</body></html>',
            'index.html': '{% extends "layout.html" %}{% block body %}<a href="/sort/abc">Books</a>{% endblock %}',
            'reader.html': '<html><head></head><body>Reader</body></html>',
        })

        @self.app.before_request
        def authenticate():
            if request.headers.get('X-Test-Identity') != 'reader':
                abort(403)

        @self.app.route('/')
        def index():
            return render_template('index.html')

        @self.app.route('/reader')
        def reader():
            return render_template('reader.html')

        install_modern_theme(self.app)
        self.client = self.app.test_client()
        self.headers = {'X-Test-Identity': 'reader'}

    def test_assets_follow_ingress_prefix_and_do_not_replace_book_links(self):
        result = self.client.get('/', headers=self.headers,
                                 environ_overrides={'SCRIPT_NAME': '/api/hassio_ingress/test/library'})
        self.assertIn(b'/api/hassio_ingress/test/library/aio-theme/modern.css', result.data)
        self.assertIn(b'/api/hassio_ingress/test/library/aio-theme/modern.js', result.data)
        self.assertIn(b'<html class="aio-modern"', result.data)
        self.assertIn(b'href="/sort/abc"', result.data)
        self.assertNotIn(b'aio-theme', self.client.get('/reader', headers=self.headers).data)

    def test_assets_require_the_same_identity_and_are_allowlisted(self):
        for asset, content_type in [('modern.css', 'text/css'), ('modern.js', 'javascript')]:
            self.assertEqual(self.client.get('/aio-theme/' + asset).status_code, 403)
            response = self.client.get('/aio-theme/' + asset, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertIn(content_type, response.content_type)
            response.close()
        self.assertEqual(self.client.get('/aio-theme/secret.txt', headers=self.headers).status_code, 404)

    @unittest.skipUnless(os.environ.get('CWA_SOURCE'), 'requires pinned CWA source')
    def test_real_pinned_layout_accepts_the_overlay(self):
        from jinja2 import FileSystemLoader, Environment
        from modern_theme import ThemeLoader
        loader = ThemeLoader(FileSystemLoader(Path(os.environ['CWA_SOURCE']) / 'cps/templates'))
        source, _, _ = loader.get_source(Environment(), 'layout.html')
        self.assertEqual(source.count('filename=\'modern.css\''), 1)
        self.assertLess(source.index('css/cwa.css'), source.index("filename='modern.css'"))
        self.assertIn('navbar-toggle', source)
