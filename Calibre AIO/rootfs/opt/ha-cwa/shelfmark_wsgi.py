"""Configure upstream Shelfmark before import, after dropping privileges."""
import os
import json
from pathlib import Path
import sys

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
    'USE_CF_BYPASS': 'true' if options.get('external_bypass_url') else 'false',
    'USING_EXTERNAL_BYPASSER': 'true',
    'EXT_BYPASSER_URL': options.get('external_bypass_url') or 'http://127.0.0.1:8191',
    'BOOKS_OUTPUT_MODE': 'folder',
    'DESTINATION_AUDIOBOOK': '/data/shelfmark-audiobooks',
    'HARDLINK_TORRENTS': 'false',
    'FLASK_HOST': '127.0.0.1', 'FLASK_PORT': '8085',
})
sys.path.insert(0, '/app/shelfmark')
import shelfmark.main as upstream
from shelfmark_gateway import IngressIdentity
from shelfmark_socket_auth import install_socket_auth

app = upstream.app
install_socket_auth(upstream)
app.config['SESSION_COOKIE_PATH'] = prefix + '/shelfmark/'
app.wsgi_app = IngressIdentity(app.wsgi_app, options)
