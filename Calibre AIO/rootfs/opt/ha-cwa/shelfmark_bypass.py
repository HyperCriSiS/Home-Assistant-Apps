"""Resolve the bypass option and drop the retired loopback bypasser settings."""
import json
from pathlib import Path
from urllib.parse import urlsplit

RETIRED_HOSTS = ('127.0.0.1', 'localhost')


def retired(url):
    """Earlier releases pointed Shelfmark at a local service that no longer exists."""
    return urlsplit(str(url)).hostname in RETIRED_HOSTS


def external_url(options):
    url = options.get('external_bypass_url') or ''
    return '' if retired(url) else url


def clear_retired_settings(config_dir):
    for path in [Path(config_dir, 'settings.json'), *Path(config_dir, 'plugins').glob('*.json')]:
        if not path.is_file():
            continue
        settings = json.loads(path.read_text())
        if 'EXT_BYPASSER_URL' in settings and retired(settings['EXT_BYPASSER_URL']):
            del settings['EXT_BYPASSER_URL']
            settings.pop('USING_EXTERNAL_BYPASSER', None)
            path.write_text(json.dumps(settings, indent=2))
