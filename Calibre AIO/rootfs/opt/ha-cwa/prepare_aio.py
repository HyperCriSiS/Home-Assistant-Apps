"""Render deployment-owned configuration without modifying upstream sources."""
import json
from pathlib import Path
import re
import sys
from ingress_sso import read_options


def validate_prefix(value):
    if not re.fullmatch(r'/api/hassio_ingress/[A-Za-z0-9_-]+', value):
        raise ValueError('Unexpected Supervisor ingress path')
    return value


def main():
    prefix = validate_prefix(sys.argv[1])
    with open('/data/options.json', encoding='utf-8') as handle:
        options = read_options(json.load(handle))
    if not options['enabled']:
        raise ValueError('Calibre AIO requires sso.enabled: true')
    runtime = Path('/run/calibre-aio')
    (runtime / 'www').mkdir(parents=True, exist_ok=True)
    template = Path('/etc/nginx/cwa-ingress.conf.template').read_text()
    Path('/etc/nginx/cwa-ingress.conf').write_text(template.replace('__CWA_INGRESS_PATH__', prefix))
    template = Path('/opt/ha-cwa/index.html').read_text()
    (runtime / 'www/index.html').write_text(template.replace('__AIO_BASE__', prefix))
    (runtime / 'prefix').write_text(prefix)


if __name__ == '__main__':
    main()
