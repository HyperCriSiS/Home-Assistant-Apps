import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rootfs/opt/ha-cwa'))
import start_shelfmark


class ShelfmarkStartTest(unittest.TestCase):
    def test_gunicorn_starts_only_after_privilege_drop(self):
        options = {'enabled': True, 'admin_users': []}
        with (patch.object(start_shelfmark, 'load_options_and_drop_privileges', return_value=options) as load,
              patch.object(os, 'execv') as execute, patch.dict(os.environ, {}, clear=True)):
            start_shelfmark.main()
            load.assert_called_once_with()
            self.assertEqual(json.loads(os.environ['AIO_SSO_OPTIONS']), options)
            self.assertEqual(execute.call_args.args[0], '/app/shelfmark/.venv/bin/gunicorn')

    def test_failed_drop_cannot_start_gunicorn(self):
        with (patch.object(start_shelfmark, 'load_options_and_drop_privileges', side_effect=PermissionError),
              patch.object(os, 'execv') as execute, self.assertRaises(PermissionError)):
            start_shelfmark.main()
        execute.assert_not_called()
