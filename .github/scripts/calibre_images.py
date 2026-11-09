"""Validate Calibre image metadata and enable pull-based HA installation."""
import argparse
from pathlib import Path
import re
import subprocess

IMAGE = 'ghcr.io/hypercrisis/{arch}-calibre-aio'
VERSION = r'v\d{4}\.\d{2}\.\d{2}(?:-\d+)?(?:-dev\.\d+)?'


def read_version(text):
    match = re.search(r'^version: "(' + VERSION + r')"$', text, re.M)
    if not match:
        raise ValueError('Invalid Calibre release version')
    return match[1]


def enable(text):
    read_version(text)
    if re.search(r'^image:', text, re.M):
        if f'image: "{IMAGE}"' not in text:
            raise ValueError('Unexpected Calibre image repository')
        return text
    return text + f'image: "{IMAGE}"\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('enable', 'metadata'))
    args = parser.parse_args()
    config = Path('Calibre AIO/config.yaml')
    text = config.read_text(encoding='utf-8')
    if args.command == 'enable':
        config.write_text(enable(text), encoding='utf-8')
    else:
        print('version=' + read_version(text))
        # Fingerprint the same canonical metadata for a source branch and the
        # generated store. Enabling pulls must not invalidate an existing tag.
        config.write_text(enable(text), encoding='utf-8')
        subprocess.run(['git', 'add', '--', str(config)], check=True)
        index_tree = subprocess.check_output(['git', 'write-tree'], text=True).strip()
        tree = subprocess.check_output(
            ['git', 'rev-parse', index_tree + ':Calibre AIO'], text=True).strip()
        print('tree=' + tree)


if __name__ == '__main__':
    main()
