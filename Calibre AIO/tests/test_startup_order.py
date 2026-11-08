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
    def test_nested_library_and_ingest_folders_are_refused(self):
        script = (ROOT / 'rootfs/etc/cont-init.d/calibre-web-automated.sh').read_text()
        checks = script[script.index('check_share_dir() {'):script.index('CONFIG_TARGET=')]
        stub = 'bashio::log.fatal() { echo "$@" >&2; }' + chr(10)
        def run(library_dir, ingest_dir):
            return subprocess.run([shutil.which('bash'), '-c', stub + f'library_dir={library_dir!r}; ingest_dir={ingest_dir!r}' + chr(10) + checks],
                                  capture_output=True, text=True)
        self.assertEqual(run('calibre-aio/library', 'calibre-aio/ingest').returncode, 0)
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
