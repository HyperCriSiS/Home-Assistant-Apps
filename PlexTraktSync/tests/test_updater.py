import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pts_upstream", ROOT / "scripts/upstream.py")
upstream = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upstream)


class UpdaterTests(unittest.TestCase):
    def test_major_and_pre_one_minor_changes_stay_manual(self):
        for old, new, allowed in (("0.35.21", "0.35.22", True),
                                  ("0.35.21", "0.36.0", False),
                                  ("0.35.21", "1.0.0", False),
                                  ("1.2.0", "1.3.0", True),
                                  ("1.2.0", "2.0.0", False),
                                  ("0.35.21", "0.35.20", False)):
            with self.subTest(old=old, new=new):
                self.assertEqual(upstream.automatic_update_allowed(old, new), allowed)
        with self.assertRaises(ValueError):
            upstream.automatic_update_allowed("0.35.21", "0.35.22rc1")

    def test_manifest_matches_every_generated_pin(self):
        manifest = json.loads((ROOT / "upstream.json").read_text())
        for path, generated in upstream.generate(manifest).items():
            self.assertEqual(path.read_text(), generated)

    def test_new_version_changes_both_docker_and_ha_build_arguments(self):
        manifest = json.loads((ROOT / "upstream.json").read_text())
        manifest.update(version="0.35.22", sha256="a" * 64)
        files = upstream.generate(manifest)
        for text in files.values():
            self.assertIn("0.35.22", text)
            self.assertIn("a" * 64, text)
            self.assertNotIn("0.35.21", text)


if __name__ == "__main__":
    unittest.main()
