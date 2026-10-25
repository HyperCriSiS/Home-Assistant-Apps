from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rootfs/opt/ha-cwa'))
from ha_admin import is_configured_admin, AdminBindingUnavailable
import launch


class AdminNameTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'bindings.db'
        self.addCleanup(self.temp.cleanup)

    def test_exact_login_name_binds_once_and_survives_reopen(self):
        self.assertFalse(is_configured_admin('a' * 32, 'Admin', 'admin', self.path))
        self.assertFalse(self.path.exists())
        self.assertTrue(is_configured_admin('a' * 32, 'admin', 'admin', self.path))
        self.assertTrue(is_configured_admin('a' * 32, 'admin', 'admin', self.path))
        self.assertFalse(is_configured_admin('b' * 32, 'admin', 'admin', self.path))
        self.assertFalse(is_configured_admin('a' * 32, 'reader', 'admin', self.path))

    def test_parallel_first_requests_share_the_same_binding(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            values = list(pool.map(lambda _: is_configured_admin(
                'a' * 32, 'admin', 'admin', self.path), range(8)))
        self.assertEqual(values, [True] * 8)

    def test_explicit_configuration_change_selects_new_admin(self):
        self.assertTrue(is_configured_admin('a' * 32, 'admin', 'admin', self.path))
        self.assertTrue(is_configured_admin('b' * 32, 'new_admin', 'new_admin', self.path))
        self.assertFalse(is_configured_admin('a' * 32, 'admin', 'new_admin', self.path))

    def test_storage_failure_never_grants_admin(self):
        with self.assertRaises(AdminBindingUnavailable):
            is_configured_admin('a' * 32, 'admin', 'admin', self.path / 'missing.db')

    def test_aio_requires_a_name_before_privilege_drop_or_app_import(self):
        source = Path(self.temp.name) / 'options.json'
        source.write_text('{"sso":{"enabled":true}}')
        with self.assertRaisesRegex(ValueError, 'sso.admin_username'):
            launch.load_options_and_drop_privileges(str(source))
