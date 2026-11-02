"""Exercise symlink-backed library ownership and real unprivileged SQLite writes."""

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULES = Path(__file__).resolve().parents[1] / 'rootfs/opt/ha-cwa'
sys.path.insert(0, str(MODULES))
from library_permissions import check_writable, prepare_library, selected_library


class LibrarySelectionTest(unittest.TestCase):
    def test_selected_nested_library_and_outside_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            library = root / 'library'
            nested = library / 'nested'
            nested.mkdir(parents=True)
            (nested / 'metadata.db').touch()
            dirs = root / 'dirs.json'
            dirs.write_text(json.dumps({'calibre_library_dir': str(nested)}))
            self.assertEqual(selected_library(dirs, library), nested)
            dirs.write_text(json.dumps({'calibre_library_dir': str(root)}))
            with self.assertRaisesRegex(ValueError, 'inside /calibre-library'):
                selected_library(dirs, library)

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory).resolve()
            with self.assertRaises(FileNotFoundError):
                check_writable(library)
            self.assertEqual(list(library.iterdir()), [])

    def test_network_share_mode_does_not_chown(self):
        with patch('library_permissions.subprocess.run') as run:
            prepare_library(Path('/unused'), True)
        run.assert_not_called()


@unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0,
                     'requires root on Linux for real ownership and privilege checks')
class LibraryPermissionsTest(unittest.TestCase):
    def setUp(self):
        import pwd
        self.account = pwd.getpwnam('nobody')
        self.owner = f'{self.account.pw_uid}:{self.account.pw_gid}'
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o755)
        # CI checkout files may not be readable by nobody. Stage only the
        # deployment helper in the controlled fixture before dropping UID.
        self.modules = self.root / 'modules'
        self.modules.mkdir(mode=0o755)
        self.modules.chmod(0o755)
        module = self.modules / 'library_permissions.py'
        module.write_text((MODULES / module.name).read_text())
        module.chmod(0o644)
        self.library = self.root / 'share/library'
        self.library.mkdir(parents=True)
        self.library.parent.chmod(0o755)
        self.library.chmod(0o755)
        # HA bootstrap owns the directory, while CWA creates the DB as root.
        os.chown(self.library, self.account.pw_uid, self.account.pw_gid)
        self.db = self.library / 'metadata.db'
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE books (title TEXT)')
            db.execute("INSERT INTO books VALUES ('Existing book')")
        self.db.chmod(0o644)
        self.link = self.root / 'calibre-library'
        self.link.symlink_to(self.library, target_is_directory=True)

    def run_as_reader(self, library=None, insert=False, check=True):
        script = '''
from pathlib import Path
import sqlite3, sys
sys.path.insert(0, sys.argv[1])
from library_permissions import check_writable
library = Path(sys.argv[2])
if sys.argv[4] == 'True':
    check_writable(library)
if sys.argv[3] == 'True':
    with sqlite3.connect(library / 'metadata.db') as db:
        db.execute("INSERT INTO books VALUES ('Imported book')")
'''
        return subprocess.run(
            [sys.executable, '-c', script, str(self.modules), str(library or self.library),
             str(insert), str(check)],
            user=self.account.pw_uid, group=self.account.pw_gid, extra_groups=[],
            capture_output=True, text=True)

    def test_original_recursive_chown_leaves_symlink_database_readonly(self):
        subprocess.run(['chown', '-R', self.owner, str(self.link)], check=True)
        self.assertEqual(self.db.stat().st_uid, 0)
        result = self.run_as_reader(insert=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('readonly database', result.stderr)
        self.assertNotEqual(self.run_as_reader().returncode, 0)

    def test_repair_allows_import_and_preserves_existing_books(self):
        prepare_library(self.link, False, self.owner)
        result = self.run_as_reader(insert=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.db.stat().st_uid, self.account.pw_uid)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT title FROM books').fetchall(),
                             [('Existing book',), ('Imported book',)])
        # Restarting with an existing library remains safe.
        prepare_library(self.link, False, self.owner)
        self.assertEqual(self.run_as_reader().returncode, 0)

    def test_nested_library_is_repaired_without_following_internal_symlinks(self):
        nested = self.library / 'nested'
        nested.mkdir()
        self.db.rename(nested / 'metadata.db')
        outside = self.root / 'unrelated'
        outside.mkdir()
        untouched = outside / 'file'
        untouched.write_text('keep')
        (nested / 'external').symlink_to(outside, target_is_directory=True)
        dirs = self.root / 'dirs.json'
        dirs.write_text(json.dumps({'calibre_library_dir': str(self.link / 'nested')}))
        selected = selected_library(dirs, self.link)
        prepare_library(selected, False, self.owner)
        result = self.run_as_reader(nested, insert=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(untouched.stat().st_uid, 0)
        self.assertEqual(outside.stat().st_uid, 0)

    def test_network_share_ownership_is_preserved_and_checked(self):
        prepare_library(self.link, True, self.owner)
        self.assertEqual(self.db.stat().st_uid, 0)
        self.assertNotEqual(self.run_as_reader().returncode, 0)
        os.chown(self.db, self.account.pw_uid, self.account.pw_gid)
        prepare_library(self.link, True, self.owner)
        self.assertEqual(self.run_as_reader().returncode, 0)

    def test_readonly_database_and_directory_fail_the_check(self):
        prepare_library(self.link, False, self.owner)
        self.db.chmod(0o444)
        result = self.run_as_reader()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PermissionError', result.stderr)
        self.db.chmod(0o644)
        self.library.chmod(0o555)
        result = self.run_as_reader()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PermissionError', result.stderr)
        self.library.chmod(0o755)
