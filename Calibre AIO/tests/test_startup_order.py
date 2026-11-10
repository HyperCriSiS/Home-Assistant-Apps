import os
from pathlib import Path
import shutil
import subprocess
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / 'rootfs/etc/s6-overlay/s6-rc.d'


class StartupOrderTest(unittest.TestCase):
    def test_ingress_streaming_avoids_supervisor_16_mib_upload_buffer(self):
        config = yaml.safe_load((ROOT / 'config.yaml').read_text())
        self.assertIs(config['ingress_stream'], True)
        self.assertEqual(config['ports'], {})

    def test_upstream_initialization_waits_for_ha_storage_bootstrap(self):
        services = ROOT / 'rootfs/etc/s6-overlay/s6-rc.d'
        self.assertTrue((services / 'cwa-init/dependencies.d/legacy-cont-init').is_file())
        for consumer in ('calibre-binaries-setup', 'cwa-auto-library', 'svc-shelfmark'):
            self.assertTrue((services / consumer / 'dependencies.d/cwa-init').is_file())

    def test_shelfmark_waits_for_the_repaired_library_database(self):
        # Shelfmark reads /calibre-library/metadata.db, which cwa-auto-library creates and repairs.
        self.assertTrue((SERVICES / 'svc-shelfmark/dependencies.d/cwa-auto-library').is_file())

    def test_only_the_storage_bootstrap_keeps_the_supervisor_token(self):
        # launch.py drops the token for CWA and Shelfmark; every other service must too.
        for run in sorted(SERVICES.glob('*/run')):
            if run.parent.name in ('svc-calibre-web-automated', 'svc-shelfmark'):
                continue
            with self.subTest(service=run.parent.name):
                self.assertIn('unset SUPERVISOR_TOKEN HASSIO_TOKEN', run.read_text())
        # The upstream ingest script re-executes itself via its with-contenv shebang
        # when it runs as root, which would import the token again.
        self.assertIn('exec s6-setuidgid abc bash /app/calibre-web-automated/root/etc/s6-overlay/s6-rc.d/cwa-ingest-service/run',
                      (SERVICES / 'cwa-ingest-service/run').read_text())

    def test_ingress_proxy_forwards_the_supervisor_scheme(self):
        template = (ROOT / 'rootfs/etc/nginx/cwa-ingress.conf.template').read_text()
        self.assertNotIn('X-Forwarded-Proto $scheme', template)
        self.assertEqual(template.count('X-Forwarded-Proto $forwarded_proto'), 2)
        self.assertIn("map $http_x_forwarded_proto $forwarded_proto { default $http_x_forwarded_proto; '' $scheme; }",
                      template)

    @unittest.skipUnless(shutil.which('bash'), 'requires bash')
    def test_interrupted_ingest_follow_up_is_requeued(self):
        import tempfile
        script = (ROOT / 'rootfs/etc/cont-init.d/calibre-web-automated.sh').read_text()
        start = script.index('requeue_interrupted_follow_up() {')
        function = script[start:script.index(chr(10) + '}' + chr(10), start) + 3]
        stub = 'bashio::log.info() { :; }' + chr(10)
        for present, expected in (({'running'}, {'dirty'}), ({'running', 'dirty'}, {'dirty'}), (set(), set())):
            with self.subTest(present=present), tempfile.TemporaryDirectory() as directory:
                names = {'dirty': 'cwa_ingest_batch_dirty', 'running': 'cwa_ingest_batch_dirty.running'}
                for name in present:
                    (Path(directory) / names[name]).write_text('x')
                subprocess.run([shutil.which('bash'), '-c', stub + function + 'requeue_interrupted_follow_up "$1"',
                                'test', Path(directory).as_posix()], check=True, capture_output=True)
                left = {key for key, name in names.items() if (Path(directory) / name).exists()}
                self.assertEqual(left, expected)

    def test_backups_skip_caches_and_keep_state(self):
        excluded = yaml.safe_load((ROOT / 'config.yaml').read_text())['backup_exclude']
        for pattern in ('config/thumbnails/*', 'shelfmark/covers/*', 'config/cwa_ingest_batch_dirty.running'):
            self.assertIn(pattern, excluded)
        # processed_books is a link into /share; its copies follow the Share folder.
        self.assertFalse(any('processed_books' in pattern for pattern in excluded))
        for kept in ('app.db', 'cwa.db', '.key', 'ha_admin_bindings.db'):
            self.assertFalse(any(Path('config', kept).match(pattern) for pattern in excluded), kept)

    @unittest.skipUnless(shutil.which('bash') and os.name != 'nt', 'requires bash with real symlinks')
    def test_processed_books_move_to_share_once_and_follow_the_option(self):
        import tempfile
        script = (ROOT / 'rootfs/etc/cont-init.d/calibre-web-automated.sh').read_text()
        start = script.index('link_processed_books() {')
        function = script[start:script.index(chr(10) + '}' + chr(10), start) + 3]
        stub = 'bashio::log.info() { :; }' + chr(10)

        def run(config, target):
            subprocess.run([shutil.which('bash'), '-c', stub + function + 'link_processed_books "$1" "$2"',
                            'test', str(config), str(target)], check=True, capture_output=True)

        with tempfile.TemporaryDirectory() as directory:
            config, first, second = (Path(directory) / name for name in ('config', 'first', 'second'))
            for folder in (config / 'processed_books/fixed_originals', first, second):
                folder.mkdir(parents=True)
            (config / 'processed_books/fixed_originals/book.zip').write_text('copy')
            run(config, first)
            link = config / 'processed_books'
            self.assertTrue(link.is_symlink())
            self.assertEqual(os.readlink(link), str(first))
            self.assertEqual((first / 'fixed_originals/book.zip').read_text(), 'copy')
            run(config, first)
            self.assertEqual(os.readlink(link), str(first))
            run(config, second)
            self.assertEqual(os.readlink(link), str(second))
            self.assertTrue((first / 'fixed_originals/book.zip').exists())

    @unittest.skipUnless(shutil.which('bash'), 'requires bash')
    def test_nested_library_and_ingest_folders_are_refused(self):
        script = (ROOT / 'rootfs/etc/cont-init.d/calibre-web-automated.sh').read_text()
        checks = script[script.index('check_share_dir() {'):script.index('CONFIG_TARGET=')]
        stub = 'bashio::log.fatal() { echo "$@" >&2; }' + chr(10)
        def run(library_dir, ingest_dir, processed_dir='calibre-aio/processed'):
            assignments = f'library_dir={library_dir!r}; ingest_dir={ingest_dir!r}; processed_dir={processed_dir!r}'
            return subprocess.run([shutil.which('bash'), '-c', stub + assignments + chr(10) + checks],
                                  capture_output=True, text=True)
        self.assertEqual(run('calibre-aio/library', 'calibre-aio/ingest').returncode, 0)
        for processed_dir in ('calibre-aio/library', 'calibre-aio/library/processed', 'calibre-aio/ingest/processed',
                              'calibre-aio', '', '../processed'):
            with self.subTest(processed_dir=processed_dir):
                self.assertEqual(run('calibre-aio/library', 'calibre-aio/ingest', processed_dir).returncode, 1)
        for library_dir, ingest_dir in (('calibre-aio', 'calibre-aio/ingest'), ('calibre-aio/library', 'calibre-aio'),
                                        ('calibre-aio/library', 'calibre-aio/library/'), ('', 'calibre-aio/ingest'),
                                        ('/share/library', 'calibre-aio/ingest'), ('a/../b', 'calibre-aio/ingest')):
            with self.subTest(library_dir=library_dir, ingest_dir=ingest_dir):
                result = run(library_dir, ingest_dir)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertTrue(result.stderr.strip(), 'expected a fatal message')
        self.assertEqual(run('calibre-aio/library', 'calibre-aio/library-ingest').returncode, 0)

    def test_manual_admin_ids_are_not_in_the_visible_ha_configuration(self):
        self.assertNotIn('admin_users', (ROOT / 'config.yaml').read_text())
