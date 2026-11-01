"""Run Shelfmark's real internal bypass helper as the service user."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
import tempfile
import threading

os.environ.update({'CONFIG_DIR': '/data/shelfmark', 'LOG_ROOT': '/data/shelfmark-logs',
                   'DOCKERMODE': 'true', 'HOME': '/data/shelfmark'})
os.chdir('/app/shelfmark')
sys.path.insert(0, '/app/shelfmark')
from shelfmark.bypass.internal_bypasser import get_bypassed_page

site = tempfile.mkdtemp()
Path(site, 'index.html').write_text(
    '<html><title>Books</title><body>' + '<p>Calibre AIO browser probe</p>' * 8000 + '</body></html>')
handler = partial(SimpleHTTPRequestHandler, directory=site)
server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
html = get_bypassed_page(f'http://127.0.0.1:{server.server_port}/')
assert html and 'Calibre AIO browser probe' in html, 'Internal browser returned no page'
print('Internal Shelfmark browser loaded a page as the service user')
