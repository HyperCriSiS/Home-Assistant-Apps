import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rootfs/opt/ha-cwa'))
import shelfmark_bypass


class BypassMigrationTest(unittest.TestCase):
    def test_only_real_services_stay_external(self):
        self.assertEqual(shelfmark_bypass.external_url({}), '')
        self.assertEqual(shelfmark_bypass.external_url(
            {'external_bypass_url': 'http://127.0.0.1:8191'}), '')
        self.assertEqual(shelfmark_bypass.external_url(
            {'external_bypass_url': 'http://flaresolverr:8191'}), 'http://flaresolverr:8191')

    def test_retired_settings_are_removed_and_others_kept(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, 'plugins', 'advanced.json')
            path.parent.mkdir()
            path.write_text(json.dumps({'USING_EXTERNAL_BYPASSER': True, 'A': 1,
                                        'EXT_BYPASSER_URL': 'http://127.0.0.1:8191'}))
            other = Path(root, 'settings.json')
            other.write_text(json.dumps({'USING_EXTERNAL_BYPASSER': True,
                                         'EXT_BYPASSER_URL': 'http://flaresolverr:8191'}))
            before = other.read_text()
            shelfmark_bypass.clear_retired_settings(root)
            self.assertEqual(json.loads(path.read_text()), {'A': 1})
            self.assertEqual(other.read_text(), before)


if __name__ == '__main__':
    unittest.main()
