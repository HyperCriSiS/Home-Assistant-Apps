from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

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

    def test_empty_name_starts_unprivileged_without_granting_admin(self):
        source = Path(self.temp.name) / 'options.json'
        source.write_text('{"sso":{"enabled":true}}')
        account = SimpleNamespace(pw_name='abc', pw_gid=1000, pw_uid=1000)
        with (patch.dict(sys.modules, {'pwd': SimpleNamespace(getpwnam=lambda _: account)}),
              patch.object(launch.os, 'initgroups', create=True),
              patch.object(launch.os, 'setgid', create=True) as gid,
              patch.object(launch.os, 'setuid', create=True) as uid):
            options = launch.load_options_and_drop_privileges(str(source))
            self.assertEqual(options['admin_username'], '')
            gid.assert_called_once_with(1000)
            uid.assert_called_once_with(1000)
        self.assertFalse(is_configured_admin('a' * 32, 'admin', '', self.path))
