"""Configure upstream Shelfmark before import, after dropping privileges."""
import os
import json
from pathlib import Path
import sys

from shelfmark_bypass import clear_retired_settings, external_url

options = json.loads(os.environ.pop('AIO_SSO_OPTIONS'))
if not options['enabled']:
    raise ValueError('Calibre AIO requires ingress SSO')
prefix = Path('/run/calibre-aio/prefix').read_text()
os.environ.update({
    'CONFIG_DIR': '/data/shelfmark', 'LOG_ROOT': '/data/shelfmark-logs',
    'TMP_DIR': '/data/shelfmark-staging', 'INGEST_DIR': '/cwa-book-ingest',
    'URL_BASE': prefix + '/shelfmark', 'AUTH_METHOD': 'proxy',
    'PROXY_AUTH_USER_HEADER': 'X-AIO-User',
    'PROXY_AUTH_ADMIN_GROUP_HEADER': 'X-AIO-Groups',
    'PROXY_AUTH_ADMIN_GROUP_NAME': 'system-admin', 'PROXY_AUTH_DEFAULT_ROLE': 'user',
    'CALIBRE_WEB_URL': prefix + '/library/',
    'LIBRARY_CHECK_CALIBRE_ENABLED': 'true',
    'CALIBRE_LIBRARY_DB_PATH': '/calibre-library/metadata.db',
    'SHELFMARK_API_KEY': '', 'DOCKERMODE': 'true',
    'BOOKS_OUTPUT_MODE': 'folder',
    'DESTINATION_AUDIOBOOK': '/data/shelfmark-audiobooks',
    'HARDLINK_TORRENTS': 'false',
    'FLASK_HOST': '127.0.0.1', 'FLASK_PORT': '8085',
})
clear_retired_settings('/data/shelfmark')
external_bypass_url = external_url(options)
if external_bypass_url:
    # An explicit option keeps the external service; otherwise Shelfmark's own
    # settings and internal Chromium bypass stay freely configurable.
    os.environ.update({'USE_CF_BYPASS': 'true', 'USING_EXTERNAL_BYPASSER': 'true',
                       'EXT_BYPASSER_URL': external_bypass_url})
sys.path.insert(0, '/app/shelfmark')
import shelfmark.main as upstream
from shelfmark_gateway import IngressIdentity
from shelfmark_socket_auth import install_socket_auth
from shelfmark_ui import install_reader_ui

app = upstream.app
install_socket_auth(upstream)
install_reader_ui(app)
app.config['SESSION_COOKIE_PATH'] = prefix + '/shelfmark/'
app.wsgi_app = IngressIdentity(app.wsgi_app, options)
