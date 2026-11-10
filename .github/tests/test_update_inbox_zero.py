"""The Inbox Zero updater is a pure function the merge gate can regenerate byte for byte."""
import importlib.util
import unittest
from datetime import date
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts" / "update_inbox_zero.py"
spec = importlib.util.spec_from_file_location("update_inbox_zero", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

APP = "Inbox Zero"
OLD, NEW = "a" * 40, "b" * 40
# main carries this automation before the App folder exists, so the tests use
# a fixture with the lines the updater owns instead of the App files.
FILES = {
    f"{APP}/Dockerfile": f"FROM ghcr.io/hypercrisis/inbox-zero-base:{OLD}\n\nARG BUILD_VERSION\n",
    f"{APP}/config.yaml": '---\nname: "Inbox Zero"\ndescription: >-\n'
                          "  Inbox Zero v2.30.0 (fork aaaaaaa) - AI email assistant\n"
                          'version: "v2026.11.09"\n',
    f"{APP}/README.md": "# Inbox Zero\n\n[![Inbox Zero version](https://img.shields.io/badge/"
                        "Inbox%20Zero-v2.30.0%20(aaaaaaa)-6E56CF)]"
                        f"(https://github.com/HyperCriSiS/inbox-zero/commit/{OLD})\n",
    f"{APP}/NOTICE.md": f"- Version currently packaged: v2.30.0 at fork commit {OLD}\n",
    f"{APP}/CHANGELOG.md": "# Changelog\n\n## v2026.11.09\n\n### Added\n\n- First release.\n",
}


class RenderTests(unittest.TestCase):
    def test_moves_every_file_to_the_new_commit(self):
        updated = mod.render(FILES, "v2.31.0", NEW, date(2026, 11, 12))
        self.assertEqual(set(updated), set(mod.UPDATE_FILES))
        self.assertEqual(mod.pinned(updated), ("v2.31.0", NEW))
        self.assertIn('version: "v2026.11.12"', updated[f"{APP}/config.yaml"])
        self.assertIn("Inbox%20Zero-v2.31.0%20(bbbbbbb)-", updated[f"{APP}/README.md"])
        self.assertIn(f"/commit/{NEW})", updated[f"{APP}/README.md"])
        self.assertIn(f"v2.31.0 at fork commit {NEW}", updated[f"{APP}/NOTICE.md"])
        self.assertTrue(updated[f"{APP}/CHANGELOG.md"].startswith(
            "# Changelog\n\n## v2026.11.12\n\n### Changed\n\n"
            "- Updated Inbox Zero from aaaaaaa to bbbbbbb (v2.31.0).\n\n## v2026.11.09\n"))
        self.assertNotIn("aaaaaaa", "".join(updated[name] for name in updated if "CHANGELOG" not in name))

    def test_is_deterministic_and_keeps_the_base_version_when_unchanged(self):
        first = mod.render(FILES, "v2.30.0", NEW, date(2026, 11, 9))
        self.assertEqual(first, mod.render(FILES, "v2.30.0", NEW, date(2026, 11, 9)))
        self.assertIn('version: "v2026.11.09.1"', first[f"{APP}/config.yaml"])
        self.assertIn("Inbox Zero v2.30.0 (fork bbbbbbb) - ", first[f"{APP}/config.yaml"])

    def test_same_commit_changes_nothing(self):
        self.assertIsNone(mod.render(FILES, "v2.30.0", OLD, date(2026, 11, 12)))

    def test_refuses_unexpected_input(self):
        for base, commit in (("2.31.0", NEW), ("v2.31.0-rc1", NEW), ("v2.31.0", "b" * 7), ("v2.31.0", "main")):
            with self.subTest(base=base, commit=commit), self.assertRaises(SystemExit):
                mod.render(FILES, base, commit, date(2026, 11, 12))

    def test_refuses_files_that_do_not_name_one_commit(self):
        broken = (
            {f"{APP}/Dockerfile": "FROM ghcr.io/hypercrisis/inbox-zero-base:latest\n"},
            {f"{APP}/Dockerfile": FILES[f"{APP}/Dockerfile"].replace(OLD, "c" * 40)},
            {f"{APP}/README.md": "# Inbox Zero\n"},
            {f"{APP}/NOTICE.md": FILES[f"{APP}/NOTICE.md"] * 2},
            {f"{APP}/CHANGELOG.md": "## v2026.11.09\n"},
        )
        for change in broken:
            with self.subTest(file=next(iter(change))), self.assertRaises(SystemExit):
                mod.render({**FILES, **change}, "v2.31.0", NEW, date(2026, 11, 12))


if __name__ == "__main__":
    unittest.main()
