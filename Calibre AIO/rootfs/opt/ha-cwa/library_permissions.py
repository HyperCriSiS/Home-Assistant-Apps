"""Prepare CWA's selected persistent library before unprivileged services start."""

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile


def selected_library(dirs_path, library_root):
    root = Path(library_root).resolve(strict=True)
    with open(dirs_path, encoding='utf-8') as handle:
        library = Path(json.load(handle)['calibre_library_dir']).resolve(strict=True)
    if not library.is_relative_to(root):
        raise ValueError('Selected library must be inside /calibre-library')
    if not (library / 'metadata.db').is_file():
        raise ValueError(f'No metadata.db in selected library: {library}')
    return library


def prepare_library(library, network_share_mode, account='abc:abc'):
    if network_share_mode:
        print('[ha-cwa] Network share mode: keeping library ownership', flush=True)
        return
    # CWA uses `chown -R /calibre-library`, which leaves the contents of our
    # top-level storage symlink untouched. Resolve that link explicitly, but
    # never follow symlinks within the library into other shared directories.
    subprocess.run(['chown', '-R', '--no-dereference', account,
                    str(library.resolve(strict=True))], check=True)


def check_writable(library):
    # Run as abc, not root: SQLite needs both the DB and its parent writable
    # (journals/WAL and new book directories). Do not create a missing database.
    with tempfile.TemporaryFile(dir=library):
        pass
    # BEGIN IMMEDIATE alone can succeed on a read-only database until the
    # first page is changed. Verify the file can actually be opened for writes.
    with (library / 'metadata.db').open('r+b'):
        pass
    connection = sqlite3.connect((library / 'metadata.db').as_uri() + '?mode=rw', timeout=5)
    try:
        connection.execute('BEGIN IMMEDIATE')
        connection.rollback()
    finally:
        connection.close()


def main():
    try:
        library = selected_library('/app/calibre-web-automated/dirs.json', '/calibre-library')
        if sys.argv[1] == 'prepare':
            network = os.environ.get('NETWORK_SHARE_MODE', '').strip().lower()
            prepare_library(library, network in ('true', '1', 'yes', 'on'))
        elif sys.argv[1] == 'check':
            check_writable(library)
            print(f'[ha-cwa] Library is writable by abc: {library}', flush=True)
        else:
            raise ValueError('Expected prepare or check')
    except (OSError, ValueError, KeyError, sqlite3.Error, subprocess.CalledProcessError) as error:
        print(f'[ha-cwa] ERROR: Library preparation failed: {error}. '
              'Check that the library and metadata.db are writable by abc (UID/GID 911), '
              'including the share mount permissions when network_share_mode is enabled.',
              file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
