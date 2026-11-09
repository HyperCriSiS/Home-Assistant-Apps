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


def render_index(template, prefix, start_page='library', app_slug='', setup_required=False):
    validate_prefix(prefix)
    if start_page not in ('library', 'shelfmark'):
        raise ValueError('start_page must be library or shelfmark')
    if app_slug and not re.fullmatch(r'[A-Za-z0-9_-]+', app_slug):
        raise ValueError('Unexpected Supervisor app slug')
    return (template.replace('__AIO_BASE__', prefix)
            .replace('__APP_SLUG__', app_slug)
            .replace('__SETUP_REQUIRED__', 'true' if setup_required else 'false')
            .replace('__FRAME_SRC__', 'about:blank' if setup_required else start_page + '/')
            .replace('__AIO_SCRIPT__', Path(__file__).with_name('aio.js').read_text(encoding='utf-8'))
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
    runtime = Path('/run/calibre-aio')
    (runtime / 'www').mkdir(parents=True, exist_ok=True)
    template = Path('/etc/nginx/cwa-ingress.conf.template').read_text()
    Path('/etc/nginx/cwa-ingress.conf').write_text(template.replace('__CWA_INGRESS_PATH__', prefix))
    template = Path('/opt/ha-cwa/index.html').read_text()
    (runtime / 'www/index.html').write_text(render_index(
        template, prefix, config.get('start_page', 'library'),
        sys.argv[2] if len(sys.argv) > 2 else '', not options.get('admin_username')),
        encoding='utf-8')
    (runtime / 'prefix').write_text(prefix)


if __name__ == '__main__':
    main()
