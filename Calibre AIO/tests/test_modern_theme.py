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
        self.assertIn('class="aio-search-icon"', source)
        self.assertIn('<button type="button" aria-expanded="true">', source)
        # Standalone: CWA's standard branch renders, caliBlur never loads.
        self.assertNotIn('g.current_theme', source)
        self.assertNotIn(' intent ', source)
        self.assertGreaterEqual(source.count('{% if false %}'), 4)
        self.assertIn("{% if true %}", source)
        self.assertIn('class="aio-back"', source)
        self.assertNotIn('message[0] == "theme_migration"', source)

    def test_shelf_heading_actions_preserve_native_visibility(self):
        from types import SimpleNamespace as NS
        from jinja2 import Environment
        from modern_theme import ThemeLoader
        source = '''{% if current_user.is_authenticated or allow_anonymous %}
<li class="nav-head public-shelves">{{_('Shelves')}}</li>
<li id="nav_createshelf" class="create-shelf"><a>Old create</a></li>{% endif %}
{% if current_user.is_authenticated and magic_shelf_routes.render %}
<li class="nav-head">{{_('Magic Shelves ✨')}}</li>
<li id="nav_createmagicshelf" class="create-shelf"><a>Old magic create</a></li>{% endif %}'''
        env = Environment(loader=ThemeLoader(DictLoader({'layout.html': source})), autoescape=True)
        env.globals.update(_=lambda value: value, url_for=lambda endpoint: endpoint)
        for authenticated, anonymous, allow_anonymous, render, create, expected in (
                (True, False, False, True, True, 2),
                (True, False, False, True, False, 1),
                (True, False, False, False, True, 1),
                (False, True, True, True, True, 0),
                (False, True, False, True, True, 0)):
            with self.subTest(authenticated=authenticated, render=render, create=create):
                result = env.get_template('layout.html').render(
                    current_user=NS(is_authenticated=authenticated, is_anonymous=anonymous),
                    allow_anonymous=allow_anonymous, magic_shelf_routes=NS(render=render, create=create))
                self.assertEqual(result.count('class="aio-section-create"'), expected)
                self.assertNotIn('nav_createshelf', result)
                self.assertNotIn('nav_createmagicshelf', result)
                self.assertNotIn('✨', result)
                if authenticated and render:
                    self.assertIn('>Magic Shelves</button>', result)

    def test_magic_heading_keeps_catalog_translation_without_emoji(self):
        from jinja2 import Environment
        from types import SimpleNamespace as NS
        from modern_theme import ThemeLoader
        env = Environment(loader=ThemeLoader(DictLoader({
            'layout.html': '<li class="nav-head">{{_(\'Magic Shelves ✨\')}}</li>'})), autoescape=True)
        env.globals.update(_=lambda key: {'Magic Shelves ✨': 'Magische Regale ✨'}[key])
        result = env.get_template('layout.html').render(magic_shelf_routes=NS(create=False))
        self.assertIn('>Magische Regale</button>', result)
        self.assertNotIn('✨', result)

    @unittest.skipUnless(os.environ.get('CWA_SOURCE'), 'requires pinned CWA source')
    def test_series_script_is_the_native_one(self):
        from jinja2 import FileSystemLoader, Environment
        from modern_theme import ThemeLoader
        self.assertEqual(self.client.get('/aio-theme/filter_grid.js', headers=self.headers).status_code, 404)
        loader = ThemeLoader(FileSystemLoader(Path(os.environ['CWA_SOURCE']) / 'cps/templates'))
        source, _, _ = loader.get_source(Environment(), 'grid.html')
        self.assertIn("url_for('static', filename='js/filter_grid.js')", source)

    @unittest.skipUnless(os.environ.get('CWA_SOURCE'), 'requires pinned CWA source')
    def test_pinned_browse_headers_exist_before_script_execution(self):
        from jinja2 import FileSystemLoader, Environment
        from modern_theme import ThemeLoader
        upstream = FileSystemLoader(Path(os.environ['CWA_SOURCE']) / 'cps/templates')
        loader = ThemeLoader(upstream)
        environment = Environment()
        for template in ('list.html', 'grid.html', 'index.html', 'duplicates.html'):
            with self.subTest(template=template):
                original, _, _ = upstream.get_source(environment, template)
                source, _, _ = loader.get_source(environment, template)
                environment.parse(source)
                self.assertEqual(source.count('<header class="aio-page-header'), 1)
                if template == 'duplicates.html':
                    self.assertIn('<details class="settings-container aio-duplicate-options">', source)
                    self.assertIn('class="selection-info">0 BOOKS SELECTED</span>', source)
                else:
                    self.assertEqual(source.count('<div class="filterheader'), 1)
                    self.assertNotIn('data-toggle="modal"', source)
                    header = source.split('</header>', 1)[0]
                    self.assertIn('<div class="aio-page-tools">', header)
                    self.assertIn('<div class="filterheader', header)
                    self.assertIn('class="aio-sort ', header)
                    self.assertNotIn('glyphicon-sort-', header)
                # This adapter must never edit the installed upstream source.
                self.assertEqual(upstream.get_source(environment, template)[0], original)
