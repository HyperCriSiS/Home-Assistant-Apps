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


def render_index(template, prefix, start_page='library'):
    validate_prefix(prefix)
    if start_page not in ('library', 'shelfmark'):
        raise ValueError('start_page must be library or shelfmark')
    return (template.replace('__AIO_BASE__', prefix)
            .replace('__START_PAGE__', start_page)
            .replace('__LIBRARY_CURRENT__', ' aria-current="page"' if start_page == 'library' else '')
            .replace('__SHELFMARK_CURRENT__', ' aria-current="page"' if start_page == 'shelfmark' else ''))


def main():
    prefix = validate_prefix(sys.argv[1])
    with open('/data/options.json', encoding='utf-8') as handle:
        config = json.load(handle)
        options = read_options(config)
    if not options['enabled']:
        raise ValueError('Calibre AIO requires sso.enabled: true')
    if not options.get('admin_username'):
        raise ValueError('Set sso.admin_username to your Home Assistant login name (not a user ID)')
    runtime = Path('/run/calibre-aio')
    (runtime / 'www').mkdir(parents=True, exist_ok=True)
    template = Path('/etc/nginx/cwa-ingress.conf.template').read_text()
    Path('/etc/nginx/cwa-ingress.conf').write_text(template.replace('__CWA_INGRESS_PATH__', prefix))
    template = Path('/opt/ha-cwa/index.html').read_text()
    (runtime / 'www/index.html').write_text(render_index(template, prefix, config.get('start_page', 'library')))
    (runtime / 'prefix').write_text(prefix)


if __name__ == '__main__':
    main()
