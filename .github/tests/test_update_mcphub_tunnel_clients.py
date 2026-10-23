"""Regression checks for trusted OpenAI tunnel-client updates."""
import importlib.util
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "scripts" / "update-mcphub-tunnel-clients.py"
spec = importlib.util.spec_from_file_location("tunnel_update", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

TODAY = date(2026, 10, 22)
FILES = {
    "MCPHub/Dockerfile": "ARG OPENAI_TUNNEL_VERSION=v0.0.16\nARG BUILD_FROM=samanhappy/mcphub:1.1.8\n",
    "MCPHub/NOTICE.md": "## OpenAI\n\n- Version currently packaged: v0.0.16\n- License: MIT\n",
    "MCPHub/config.yaml": '---\nname: "MCPHub"\nversion: "v2026.10.20-1"\nslug: mcphub\n',
    "MCPHub/CHANGELOG.md": "# Changelog\n\n## v2026.10.20-1\n\n- Existing notes.\n\n## v2026.10.16\n\n- Previous.\n",
}


class UpdateTests(unittest.TestCase):
    def test_no_update(self):
        self.assertEqual(mod.prepare(FILES, "v0.0.16", TODAY), (FILES, False))

    def test_update_bumps_pin_notice_version_and_changelog(self):
        files, changed = mod.prepare(FILES, "v0.0.17", TODAY)
        self.assertTrue(changed)
        self.assertEqual(set(files), mod.ALLOWED_FILES)
        self.assertEqual(mod.pin(files["MCPHub/Dockerfile"]), "v0.0.17")
        self.assertIn("ARG BUILD_FROM=samanhappy/mcphub:1.1.8\n", files["MCPHub/Dockerfile"])
        self.assertIn("- Version currently packaged: v0.0.17\n", files["MCPHub/NOTICE.md"])
        self.assertIn('version: "v2026.10.22"\n', files["MCPHub/config.yaml"])
        self.assertTrue(files["MCPHub/CHANGELOG.md"].startswith(
            "# Changelog\n\n## v2026.10.22\n\n### Changed\n\n"
            "- Updated bundled OpenAI tunnel-client v0.0.16 to v0.0.17.\n\n"
            "## v2026.10.20-1\n\n- Existing notes.\n"
        ))
        self.assertNotIn("cloudflared", files["MCPHub/CHANGELOG.md"])

    def test_same_day_release_gets_suffix(self):
        files, _ = mod.prepare(FILES, "v0.0.17", date(2026, 10, 20))
        self.assertIn('version: "v2026.10.20-2"\n', files["MCPHub/config.yaml"])

    def test_cloudflared_pin_not_required(self):
        # MCPHub no longer bundles cloudflared; a legacy pin is left untouched.
        legacy = dict(FILES)
        legacy["MCPHub/Dockerfile"] += "ARG CLOUDFLARED_VERSION=2026.10.1\n"
        files, changed = mod.prepare(legacy, "v0.0.17", TODAY)
        self.assertTrue(changed)
        self.assertIn("ARG CLOUDFLARED_VERSION=2026.10.1\n", files["MCPHub/Dockerfile"])

    def test_reject_downgrades_prereleases_and_malformed_data(self):
        for version in ("v0.0.15", "v0.0.17-rc1", "latest", "0.0.17"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                mod.prepare(FILES, version, TODAY)
        broken = {
            "MCPHub/CHANGELOG.md": "wrong header",
            "MCPHub/NOTICE.md": "no version line\n",
            "MCPHub/config.yaml": "version: latest\n",
            "MCPHub/Dockerfile": FILES["MCPHub/Dockerfile"] * 2,
        }
        for name, text in broken.items():
            with self.subTest(file=name), self.assertRaises(ValueError):
                mod.prepare({**FILES, name: text}, "v0.0.17", TODAY)

    def test_unique_stable_branch_name(self):
        branch = mod.branch_for("v0.0.17")
        self.assertEqual(branch, "automation/mcphub-tunnel-clients-v0_0_17")
        self.assertIsNotNone(mod.BRANCH.fullmatch(branch))
        self.assertIsNone(mod.BRANCH.fullmatch(branch + "-2026_10_2"))
        with self.assertRaises(ValueError):
            mod.branch_for("v0.0.17-rc")

    def test_reject_branch_tag_mismatch(self):
        with patch.object(mod, "api") as api, self.assertRaisesRegex(ValueError, "mismatch"):
            mod.verify_candidate("x/y", mod.branch_for("v0.0.17"), "a" * 40, "v0.0.18", TODAY)
        api.assert_not_called()

    def test_reject_unrelated_changes_before_reading_sources(self):
        branch = mod.branch_for("v0.0.17")
        sha = "a" * 40
        pr = {"number": 84, "title": mod.TITLE, "draft": False, "state": "open",
              "head": {"sha": sha, "ref": branch, "repo": {"full_name": "x/y"}},
              "base": {"ref": "dev-mcphub"}}
        files = [{"filename": p, "status": "modified"} for p in
                 sorted(mod.ALLOWED_FILES) + ["MCPHub/run.sh"]]
        with patch.object(mod, "api", side_effect=[[pr], files]), \
             patch.object(mod, "git") as git:
            with self.assertRaisesRegex(ValueError, "unexpected or missing"):
                mod.verify_candidate("x/y", branch, sha, "v0.0.17", TODAY)
            git.assert_not_called()

    def test_candidate_content_must_match_trusted_updater(self):
        branch = mod.branch_for("v0.0.17")
        sha = "a" * 40
        pr = {"number": 84, "title": mod.TITLE, "draft": False, "state": "open",
              "head": {"sha": sha, "ref": branch, "repo": {"full_name": "x/y"}},
              "base": {"ref": "dev-mcphub"}}
        files = [{"filename": p, "status": "modified"} for p in sorted(mod.ALLOWED_FILES)]
        desired, _ = mod.prepare(FILES, "v0.0.17", TODAY)

        def fake_git(*arguments):
            if arguments[0] != "show":
                return ""
            ref, name = arguments[1].split(":", 1)
            if ref == "origin/dev-mcphub":
                return FILES[name]
            return desired[name] + ("tampered\n" if name == "MCPHub/NOTICE.md" else "")

        with patch.object(mod, "api", side_effect=[[pr], files]), \
             patch.object(mod, "git", side_effect=fake_git):
            with self.assertRaisesRegex(ValueError, "differs"):
                mod.verify_candidate("x/y", branch, sha, "v0.0.17", TODAY)

    def test_reject_pr_head_mismatch(self):
        branch = mod.branch_for("v0.0.17")
        pr = {"number": 84, "title": mod.TITLE, "draft": False, "state": "open",
              "head": {"sha": "b" * 40, "ref": branch, "repo": {"full_name": "x/y"}},
              "base": {"ref": "dev-mcphub"}}
        with patch.object(mod, "api", side_effect=[[pr]]), \
             patch.object(mod, "git") as git:
            with self.assertRaisesRegex(ValueError, "HEAD mismatch"):
                mod.verify_candidate("x/y", branch, "a" * 40, "v0.0.17", TODAY)
            git.assert_not_called()

    def test_failed_ci_cannot_merge(self):
        branch = mod.branch_for("v0.0.17")
        sha = "a" * 40
        run = {"head_sha": sha, "head_branch": branch, "event": "workflow_dispatch",
               "head_repository": {"full_name": "x/y"},
               "actor": {"login": "github-actions[bot]"},
               "status": "completed", "conclusion": "failure"}
        with patch.object(mod, "api", return_value={"workflow_runs": [run]}):
            with self.assertRaisesRegex(ValueError, "CI failed"):
                mod.wait_for_ci("x/y", branch, sha, attempts=1)


if __name__ == "__main__":
    unittest.main()
