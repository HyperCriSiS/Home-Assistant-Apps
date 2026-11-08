"""Add an optional deployment-owned theme without editing CWA's source files."""
from pathlib import Path
import re

from flask import send_from_directory
from jinja2 import BaseLoader

ASSETS = Path(__file__).with_name('theme')


def _svg(paths, css_class=''):
    return ('<svg xmlns="http://www.w3.org/2000/svg" class="' + css_class + '" '
            'width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
            + ''.join('<path d="' + path + '"></path>' for path in paths) + '</svg>')


def _nav_heading(match):
    classes = match[1].split()
    classes = [value for value in classes if value != 'hidden-xs'] + ['aio-nav-section']
    action = ''
    label = match[3]
    if 'public-shelves' in classes:
        action = '''{% if not current_user.is_anonymous %}<a class="aio-section-create" href="{{url_for('shelf.create_shelf')}}" title="{{_('Create Shelf')}}" aria-label="{{_('Create Shelf')}}">+</a>{% endif %}'''
    elif match[3].strip() == "{{_('Magic Shelves ✨')}}":
        # Translate the existing catalog key, then remove its decorative emoji.
        label = "{{_('Magic Shelves ✨')|replace('✨', '')|trim}}"
        action = '''{% if magic_shelf_routes.create %}<a class="aio-section-create" href="{{url_for('web.create_magic_shelf')}}" title="{{_('Create Magic Shelf')}}" aria-label="{{_('Create Magic Shelf')}}">+</a>{% endif %}'''
    return ('<li class="' + ' '.join(classes) + '"' + match[2] + '>'
            '<button type="button" aria-expanded="true">' + label + '</button>' + action + '</li>')


def _div_end(source, start):
    """Find a trusted template div's end, accounting for nested controls."""
    depth = 0
    for tag in re.finditer(r'<div\b[^>]*>|</div\s*>', source[start:]):
        depth += -1 if tag.group().startswith('</') else 1
        if depth == 0:
            return start + tag.end()
    raise ValueError('Unbalanced Modern theme template region')


def _sort_icons(tools):
    # Render the same symbols as the script's fallback before the first paint.
    icons = {
        'author': ['M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0', 'M4 21v-2a8 8 0 0 1 16 0v2'],
        'added': ['M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H4z', 'M13 8h7v11h-3', 'M17 2v6M14 5h6'],
        'published': ['M5 5h14v16H5z', 'M8 2v6M16 2v6M5 10h14', 'M9 14h2v3H9z'],
        'series': ['M4 5h12M4 12h12M4 19h12', 'M20 4v2M20 11v2M20 18v2'],
        'downloads': ['M12 3v12M7 10l5 5 5-5', 'M4 17v4h16v-4'],
    }
    sorts = {'new': ('added', False), 'old': ('added', True),
             'asc': ('title', True), 'desc': ('title', False),
             'auth_az': ('author', True), 'auth_za': ('author', False),
             'pub_new': ('published', False), 'pub_old': ('published', True),
             'series_asc': ('series', True), 'series_desc': ('series', False),
             'hot_asc': ('downloads', True), 'hot_desc': ('downloads', False)}

    def replace(match):
        tag, attributes, control = match[1], match[2], match[3]
        if control == 'sort_name':
            symbol = _svg(icons['author']) + _svg(['M4 8h16l-4-4M20 16H4l4 4'])
        elif control in sorts:
            kind, ascending = sorts[control]
            symbol = ('<span aria-hidden="true">A–Z</span>' if kind == 'title' else _svg(icons[kind]))
            symbol += _svg(['M12 20V4M6 10l6-6 6 6'] if ascending else ['M12 4v16M6 14l6 6 6-6'], 'aio-sort-arrow')
        else:
            return match[0]
        attributes = attributes.replace('class="', 'class="aio-sort ', 1)
        return '<' + tag + attributes + '>' + symbol + '</' + tag + '>'

    controls = '|'.join((*sorts, 'sort_name'))
    return re.sub(r'<(a|div)(\b[^>]*\bid="(' + controls + r')"[^>]*)>.*?</\1>', replace, tools, flags=re.S)


def _page_header(heading, tools=''):
    tools = _sort_icons(tools)
    return '''<header class="aio-page-header{% if page == 'magicshelf' %} aio-tools-only{% endif %}"{% if page == 'magicshelf' %} aria-label="{{ title|striptags }}"{% endif %}>
{% if page != 'magicshelf' %}''' + heading + '''{% endif %}
''' + ('<div class="aio-page-tools">' + tools + '</div>' if tools else '') + '</header>'


def _render_page_header(source, template):
    """Render the final header in HTML instead of moving it after first paint."""
    if template in ('list.html', 'grid.html'):
        if template == 'grid.html':
            source = source.replace("url_for('static', filename='js/filter_grid.js')", "url_for('aio_theme', filename='filter_grid.js')")
        heading = '<h1 class="{{page}}">{{_(title)}}</h1>'
        start = source.index('<div class="filterheader')
        end = _div_end(source, start)
        tools = source[start:end]
        return source[:start].replace(heading, _page_header(heading, tools), 1) + source[end:]
    if template == 'index.html' and '<div class="discover load-more">' in source:
        heading = re.search(r'<h2 class="{{title}}">.*?</h2>', source, re.S).group()
        start = source.index("{% set show_shelf_actions")
        closing = '{% if show_shelf_actions %}</div>{% endif %}'
        end = source.index(closing, start) + len(closing)
        tools = source[start:end]
        source = (source[:start] + source[end:]).replace(heading, '', 1)
        return source.replace('{% block body %}', '{% block body %}' + _page_header(heading, tools), 1)
    if template == 'duplicates.html':
        source = source.replace('<span id="selection_count" class="selection-info"></span>',
                                '<span id="selection_count" class="selection-info">0 BOOKS SELECTED</span>', 1)
        source = source.replace('<div class="discover">\n  <h2>{{title}}</h2>',
                                _page_header('<h2>{{title}}</h2>') + '<div class="discover">', 1)
        start = source.index('<div class="settings-container" style="margin-bottom: 30px;')
        end = _div_end(source, start)
        panel = source[start:end]
        panel = re.sub(r'^<div[^>]*>', '<details class="settings-container aio-duplicate-options">', panel, count=1)
        panel = re.sub(r'<h4\b[^>]*>.*?</h4>', "<summary>{{_('Auto-Resolve Duplicates')}}</summary>", panel, count=1, flags=re.S)
        return source[:start] + panel[:-6] + '</details>' + source[end:]
    return source


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
            source = re.sub(r'<li class="([^"\n]*\bnav-head\b[^"\n]*)"([^>]*)>(.*?)</li>',
                            _nav_heading, source, flags=re.S)
            source = re.sub(r'<li id="nav_create(?:magic)?shelf"[^>]*>.*?</li>', '', source, flags=re.S)
            search_icon = _svg(['M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0', 'm15 15 6 6'], 'aio-search-icon')
            source = source.replace('<input type="text" class="form-control" id="query"',
                                    search_icon + '<input type="text" class="form-control" id="query"', 1)
            source = source.replace('id="query_submit" class="btn btn-default">{{_(\'Search\')}}</button>',
                                    'id="query_submit" class="btn btn-default"><span class="sr-only">{{_(\'Search\')}}</span>'
                                    + _svg(['M4 12h16M14 6l6 6-6 6']) + '</button>', 1)
            source = source.replace('<div class="col-sm-10">', '''<div class="col-sm-10 aio-main{% if page is string and page.endswith('list') %} aio-list-page{% endif %}">''', 1)
            source = source.replace('<span class="btn btn-default btn-file">{{_(\'Upload\')}}<input', '''<details class="aio-upload-menu"><summary aria-label="{{ _('Add books') }}">+</summary><div class="aio-upload-options"><label class="btn btn-default btn-file">{{ _('Upload') }}<input''', 1)
            source = source.replace('multiple></span>', '''multiple></label><button type="button" class="aio-folder-trigger">{% if current_user.locale.startswith('de') %}Ordner hinzufügen …{% else %}Add folder …{% endif %}</button></div></details>''', 1)
            source = source.replace('</head>', '''
    <link rel="stylesheet" href="{{ url_for('aio_theme', filename='modern.css') }}?v=10">
    <script defer src="{{ url_for('aio_theme', filename='modern.js') }}?v=8"></script>
  </head>''', 1)
        elif template == 'list.html':
            source = source.replace('''{% if title == "Downloads" %}
      <h1 style="padding-top: 1rem; padding-bottom: 2rem;">Users Downloaded Books:</h1>''', '''{% if data == "download" %}
      {% if not entries %}<p class="aio-empty">
        {% if current_user.locale.startswith('de') %}Noch keine Benutzer-Downloads erfasst.{% else %}No user downloads recorded yet.{% endif %}
      </p>{% endif %}''', 1)
        source = _render_page_header(source, template)
        return source, filename, uptodate

    def list_templates(self):
        return self.upstream.list_templates()


def install_modern_theme(app):
    def asset(filename):
        if filename == 'filter_grid.js':
            # Preserve native filtering/sorting while matching the initial CSS
            # rows. caliBlur's centered mode shifts partial rows after loading.
            source = (Path(app.static_folder) / 'js/filter_grid.js').read_text(encoding='utf-8')
            return app.response_class(source.replace('selectedLayoutMode = "fitRowsCentered";',
                                                    'selectedLayoutMode = "fitRows";'), mimetype='text/javascript')
        # Keep the asset surface explicit; authentication remains CWA's hook.
        if filename not in ('modern.css', 'modern.js'):
            from flask import abort
            abort(404)
        return send_from_directory(ASSETS, filename)

    app.add_url_rule('/aio-theme/<filename>', 'aio_theme', asset)
    app.jinja_env.loader = ThemeLoader(app.jinja_env.loader)
    app.jinja_env.cache.clear()
