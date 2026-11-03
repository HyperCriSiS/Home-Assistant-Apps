"""Add an optional deployment-owned theme without editing CWA's source files."""
from pathlib import Path

from flask import send_from_directory
from jinja2 import BaseLoader

ASSETS = Path(__file__).with_name('theme')


class ThemeLoader(BaseLoader):
    def __init__(self, upstream):
        self.upstream = upstream

    def get_source(self, environment, template):
        source, filename, uptodate = self.upstream.get_source(environment, template)
        if template == 'layout.html':
            # Modern uses caliBlur's navigation/layout, independently of a
            # user's saved upstream palette. Never rewrite that saved choice.
            source = source.replace('g.current_theme == 1', 'true')
            source = source.replace('<html ', '<html class="aio-modern" ', 1)
            source = source.replace('</head>', '''
    <link rel="stylesheet" href="{{ url_for('aio_theme', filename='modern.css') }}?v=2">
    <script defer src="{{ url_for('aio_theme', filename='modern.js') }}?v=2"></script>
  </head>''', 1)
        elif template == 'list.html':
            source = source.replace('''{% if title == "Downloads" %}
      <h1 style="padding-top: 1rem; padding-bottom: 2rem;">Users Downloaded Books:</h1>''', '''{% if data == "download" %}
      <p class="aio-download-help">
        {% if current_user.locale.startswith('de') %}
          Downloads nach Benutzer: Hier erscheinen Bücher, die Benutzer über Calibre Web herunterladen oder an einen E-Reader versenden. Shelfmark-Importe werden hier nicht erfasst.
        {% else %}
          Downloads by user: Books appear here when users download them through Calibre Web or send them to an e-reader. Shelfmark imports are not included.
        {% endif %}
      </p>
      {% if not entries %}<p class="aio-empty">
        {% if current_user.locale.startswith('de') %}Noch keine Benutzer-Downloads erfasst.{% else %}No user downloads recorded yet.{% endif %}
      </p>{% endif %}''', 1)
        return source, filename, uptodate

    def list_templates(self):
        return self.upstream.list_templates()


def install_modern_theme(app):
    def asset(filename):
        # Keep the asset surface explicit; authentication remains CWA's hook.
        if filename not in ('modern.css', 'modern.js'):
            from flask import abort
            abort(404)
        return send_from_directory(ASSETS, filename)

    app.add_url_rule('/aio-theme/<filename>', 'aio_theme', asset)
    app.jinja_env.loader = ThemeLoader(app.jinja_env.loader)
    app.jinja_env.cache.clear()
