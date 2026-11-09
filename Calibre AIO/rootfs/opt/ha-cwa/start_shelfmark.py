"""Drop privileges before Gunicorn creates worker files and imports Shelfmark."""
import json
import os
from urllib.parse import urlsplit
from launch import load_options_and_drop_privileges


def check_bypass_url(url):
    if not url:
        return
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or any(c.isspace() for c in url):
        raise ValueError('shelfmark.external_bypass_url must be an HTTP(S) URL')


def main():
    options = load_options_and_drop_privileges()
    if not options['enabled']:
        raise ValueError('Calibre AIO requires ingress SSO')
    check_bypass_url(options.get('external_bypass_url', ''))
    os.environ['AIO_SSO_OPTIONS'] = json.dumps(options)
    os.environ['HOME'] = '/data/shelfmark'
    os.environ['XDG_CACHE_HOME'] = '/data/shelfmark/cache'
    executable = '/app/shelfmark/.venv/bin/gunicorn'
    os.execv(executable, [executable, '--bind', '127.0.0.1:8085',
                        '--workers', '1', '--timeout', '300',
                        '--worker-class', 'geventwebsocket.gunicorn.workers.GeventWebSocketWorker',
                        '--error-logfile', '-', 'shelfmark_wsgi:app'])


if __name__ == '__main__':
    main()
