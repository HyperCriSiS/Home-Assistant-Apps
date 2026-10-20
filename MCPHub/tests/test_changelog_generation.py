"""Integration regression tests for MCPHub Dev and Stable changelog generation."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GENERATOR = Path(__file__).resolve().parents[2] / ".github/scripts/generate-mcphub-changelog.py"


class ChangelogGenerationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.command("git", "init", "-q")
        self.command("git", "config", "user.name", "Changelog CI")
        self.command("git", "config", "user.email", "ci@example.invalid")
        self.write("MCPHub/config.yaml", 'version: "v2026.10.07-4"\n')
        self.write("MCPHub/CHANGELOG.md", "# Changelog\n\n## v2026.10.07-4\n\n- Existing stable notes.\n")
        self.commit("stable")
        self.command("git", "branch", "-M", "main")
        self.command("git", "update-ref", "refs/remotes/origin/main", "HEAD")
        self.command("git", "switch", "-q", "-c", "dev-mcphub")
        self.write("MCPHub/config.yaml", 'version: "v2026.10.12-1"\n')
        self.write("MCPHub/CHANGELOG.md", "# Changelog\n\n## v2026.10.12-1\n\n- Curated fix notes.\n\n## v2026.10.07-4\n\n- Existing stable notes.\n")
        self.write("MCPHub/README.md", "Initial feature.\n")
        self.commit("feat(mcphub): first dev feature (#1)")
        self.command("git", "update-ref", "refs/remotes/origin/dev-mcphub", "HEAD")
        self.command("git", "switch", "-q", "-c", "dev-store")
        self.write("MCPHub/config.yaml", 'version: "v2026.10.12-1-dev.42"\n')
        self.state(42)
        self.commit("prepare dev-store snapshot")

    def command(self, *args, ok=True):
        result = subprocess.run(args, cwd=self.root, capture_output=True, text=True)
        if ok and result.returncode:
            self.fail(f"{args}: {result.stderr}")
        return result

    def generate(self, *args, ok=True):
        return self.command(sys.executable, str(GENERATOR), *args, ok=ok)

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def commit(self, title):
        self.command("git", "add", ".")
        self.command("git", "commit", "-qm", title)

    def state(self, revision):
        self.write(".dev-store-revisions.json", json.dumps({"mcphub": {"revision": revision}}))

    def test_dev_history_is_complete_and_idempotent(self):
        self.generate("dev")
        first = (self.root / "MCPHub/CHANGELOG.md").read_text()
        self.assertIn("## v2026.10.12-1-dev.42", first)
        self.assertIn("## v2026.10.12-1-dev.42", first)
        self.assertIn("Initial development snapshot", first)
        self.assertNotIn("feat(mcphub): first dev feature", first)
        self.assertNotIn("Curated fix notes.", first)
        self.assertNotIn("Complete changes since stable", first)
        self.generate("dev")
        self.assertEqual(first, (self.root / "MCPHub/CHANGELOG.md").read_text())
        self.commit("compose initial dev-store")
        self.command("git", "switch", "-q", "dev-mcphub")
        self.write("MCPHub/README.md", "Updated feature.\n")
        self.commit("fix(mcphub): next individual fix (#2)")
        self.command("git", "update-ref", "refs/remotes/origin/dev-mcphub", "HEAD")
        self.command("git", "switch", "-q", "dev-store")
        self.command("git", "checkout", "origin/dev-mcphub", "--", "MCPHub")
        self.write("MCPHub/config.yaml", 'version: "v2026.10.12-1-dev.43"\n')
        self.state(43)
        self.generate("dev")
        latest = (self.root / "MCPHub/CHANGELOG.md").read_text()
        self.assertIn("## v2026.10.12-1-dev.43", latest)
        self.assertIn("fix(mcphub): next individual fix", latest)
        self.assertNotIn("## v2026.10.12-1-dev.42", latest)
        self.assertNotIn("feat(mcphub): first dev feature", latest)
        self.assertNotIn("Curated fix notes.", latest)
        self.assertNotIn("Existing stable notes.", latest)
        self.assertNotIn("Complete changes since stable", latest)
        history = json.loads((self.root / ".dev-store-mcphub-changes.json").read_text())
        self.assertEqual([entry["revision"] for entry in history], [43, 42])
        self.assertNotIn("#### Changed files", latest)
        self.assertNotIn("MCPHub/README.md", latest)
        self.assertNotIn("files", history[0])
        self.generate("dev")
        self.assertEqual(latest, (self.root / "MCPHub/CHANGELOG.md").read_text())


    def test_stable_notes_are_consolidated_without_commits(self):
        self.command("git", "switch", "-q", "dev-mcphub")
        self.write("MCPHub/CHANGELOG.md", (
            "# Changelog\n\n## v2026.10.12-1\n\n### Fixed\n\n- Curated fix notes.\n\n"
            "## v2026.10.12\n\n> **Breaking change:** Old tunnel removed.\n\n"
            "### Added\n\n- New bridge\n  with a wrapped line.\n\n### Fixed\n\n- Curated fix notes.\n\n"
            "## v2026.10.07-4\n\n- Existing stable notes.\n"
        ))
        self.assertNotEqual(self.generate("stable", "--check", ok=False).returncode, 0)
        self.generate("stable")
        drafted = (self.root / "MCPHub/CHANGELOG.md").read_text()
        self.assertTrue(drafted.startswith(
            "# Changelog\n\n## v2026.10.12-1\n\n### Breaking changes\n\n- Old tunnel removed."))
        self.assertIn("### Added\n\n- New bridge with a wrapped line.", drafted)
        self.assertEqual(drafted.count("Curated fix notes."), 1)
        self.assertNotIn("## v2026.10.12\n", drafted)
        self.assertIn("## v2026.10.07-4\n\n- Existing stable notes.\n", drafted)
        self.assertNotIn("feat(mcphub): first dev feature", drafted)
        self.generate("stable", "--check")
        self.generate("stable")
        self.assertEqual(drafted, (self.root / "MCPHub/CHANGELOG.md").read_text())

    def test_stable_gate_rejects_commit_lists(self):
        self.command("git", "switch", "-q", "dev-mcphub")
        self.generate("stable", "--check")
        notes = (self.root / "MCPHub/CHANGELOG.md").read_text()
        commit = "- [`0123abc`](https://github.com/o/r/commit/0123abc) fix(mcphub): something\n"
        self.write("MCPHub/CHANGELOG.md", notes.replace(
            "- Curated fix notes.\n", "- Curated fix notes.\n" + commit))
        self.assertNotEqual(self.generate("stable", "--check", ok=False).returncode, 0)


if __name__ == "__main__":
    unittest.main()
