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
            source = source.replace('>{{instance}}</a>', '>{{title|striptags}}</a>', 1)
            source = source.replace('<div class="col-sm-10">', '''<div class="col-sm-10 aio-main{% if page is string and page.endswith('list') %} aio-list-page{% endif %}">''', 1)
            source = source.replace('<span class="btn btn-default btn-file">{{_(\'Upload\')}}<input', '''<details class="aio-upload-menu"><summary aria-label="{{ _('Add books') }}">+</summary><div class="aio-upload-options"><label class="btn btn-default btn-file">{{ _('Upload') }}<input''', 1)
            source = source.replace('multiple></span>', '''multiple></label><button type="button" class="aio-folder-trigger">{% if current_user.locale.startswith('de') %}Ordner hinzufügen …{% else %}Add folder …{% endif %}</button></div></details>''', 1)
            source = source.replace('</head>', '''
    <link rel="stylesheet" href="{{ url_for('aio_theme', filename='modern.css') }}?v=3">
    <script defer src="{{ url_for('aio_theme', filename='modern.js') }}?v=3"></script>
  </head>''', 1)
        elif template == 'list.html':
            source = source.replace('''{% if title == "Downloads" %}
      <h1 style="padding-top: 1rem; padding-bottom: 2rem;">Users Downloaded Books:</h1>''', '''{% if data == "download" %}
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
