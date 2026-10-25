from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StartupOrderTest(unittest.TestCase):
    def test_upstream_initialization_waits_for_ha_storage_bootstrap(self):
        services = ROOT / 'rootfs/etc/s6-overlay/s6-rc.d'
        self.assertTrue((services / 'cwa-init/dependencies.d/legacy-cont-init').is_file())
        for consumer in ('calibre-binaries-setup', 'cwa-auto-library', 'svc-shelfmark'):
            self.assertTrue((services / consumer / 'dependencies.d/cwa-init').is_file())

    def test_manual_admin_ids_are_not_in_the_visible_ha_configuration(self):
        self.assertNotIn('admin_users', (ROOT / 'config.yaml').read_text())
