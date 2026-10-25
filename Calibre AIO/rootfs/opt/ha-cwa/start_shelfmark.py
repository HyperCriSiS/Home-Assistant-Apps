"""Drop privileges before Gunicorn creates worker files and imports Shelfmark."""
import json
import os
from launch import load_options_and_drop_privileges


def main():
    options = load_options_and_drop_privileges()
    if not options['enabled']:
        raise ValueError('Calibre AIO requires ingress SSO')
    os.environ['AIO_SSO_OPTIONS'] = json.dumps(options)
    executable = '/app/shelfmark/.venv/bin/gunicorn'
    os.execv(executable, [executable, '--bind', '127.0.0.1:8085',
                        '--workers', '1', '--timeout', '300',
                        '--worker-class', 'geventwebsocket.gunicorn.workers.GeventWebSocketWorker',
                        '--error-logfile', '-', 'shelfmark_wsgi:app'])


if __name__ == '__main__':
    main()
