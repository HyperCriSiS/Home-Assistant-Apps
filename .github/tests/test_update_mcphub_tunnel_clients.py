"""Regression checks for trusted OpenAI tunnel-client updates."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "scripts" / "update-mcphub-tunnel-clients.py"
spec = importlib.util.spec_from_file_location("tunnel_update", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

DOCKER = "ARG OPENAI_TUNNEL_VERSION=v0.0.16\nARG BUILD_ARCH=amd64\n"
NOTES = "# Changelog\n\n## v2026.10.17-1\n\n- Existing notes.\n\n## v2026.10.16\n\n- Previous.\n"


class UpdateTests(unittest.TestCase):
    def test_no_update(self):
        self.assertEqual(mod.prepare(DOCKER, NOTES, "v0.0.16"), (DOCKER, NOTES, False))

    def test_update(self):
        docker, notes, changed = mod.prepare(DOCKER, NOTES, "v0.0.17")
        self.assertTrue(changed)
        self.assertEqual(mod.pin(docker), "v0.0.17")
        self.assertEqual(docker, DOCKER.replace("v0.0.16", "v0.0.17"))
        self.assertIn("- Updated bundled OpenAI tunnel-client v0.0.16 to v0.0.17.\n", notes)
        self.assertNotIn("cloudflared", notes)
        self.assertIn("## v2026.10.16\n\n- Previous.", notes)

    def test_cloudflared_pin_not_required(self):
        # MCPHub no longer bundles cloudflared; a legacy pin is left untouched.
        legacy = DOCKER + "ARG CLOUDFLARED_VERSION=2026.10.1\n"
        docker, _, changed = mod.prepare(legacy, NOTES, "v0.0.17")
        self.assertTrue(changed)
        self.assertIn("ARG CLOUDFLARED_VERSION=2026.10.1\n", docker)

    def test_reject_downgrades_prereleases_and_malformed_data(self):
        for version in ("v0.0.15", "v0.0.17-rc1", "latest", "0.0.17"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                mod.prepare(DOCKER, NOTES, version)
        with self.assertRaises(ValueError):
            mod.prepare(DOCKER, "wrong header", "v0.0.17")
        for docker in ("", DOCKER + DOCKER, "ARG OPENAI_TUNNEL_VERSION=latest\n"):
            with self.subTest(docker=docker), self.assertRaises(ValueError):
                mod.prepare(docker, NOTES, "v0.0.17")

    def test_unique_stable_branch_name(self):
        branch = mod.branch_for("v0.0.17")
        self.assertEqual(branch, "automation/mcphub-tunnel-clients-v0_0_17")
        self.assertIsNotNone(mod.BRANCH.fullmatch(branch))
        self.assertIsNone(mod.BRANCH.fullmatch(branch + "-2026_10_2"))
        with self.assertRaises(ValueError):
            mod.branch_for("v0.0.17-rc")

    def test_reject_branch_tag_mismatch(self):
        with patch.object(mod, "api") as api, self.assertRaisesRegex(ValueError, "mismatch"):
            mod.verify_candidate("x/y", mod.branch_for("v0.0.17"), "a" * 40, "v0.0.18")
        api.assert_not_called()

    def test_reject_unrelated_changes_before_reading_sources(self):
        branch = mod.branch_for("v0.0.17")
        sha = "a" * 40
        pr = {"number": 84, "title": mod.TITLE, "draft": False, "state": "open",
              "head": {"sha": sha, "ref": branch, "repo": {"full_name": "x/y"}},
              "base": {"ref": "dev-mcphub"}}
        files = [{"filename": p, "status": "modified"} for p in
                 ("MCPHub/Dockerfile", "MCPHub/CHANGELOG.md", "MCPHub/run.sh")]
        with patch.object(mod, "api", side_effect=[[pr], files]), \
             patch.object(mod, "git") as git:
            with self.assertRaisesRegex(ValueError, "unexpected or missing"):
                mod.verify_candidate("x/y", branch, sha, "v0.0.17")
            git.assert_not_called()

    def test_reject_pr_head_mismatch(self):
        branch = mod.branch_for("v0.0.17")
        pr = {"number": 84, "title": mod.TITLE, "draft": False, "state": "open",
              "head": {"sha": "b" * 40, "ref": branch, "repo": {"full_name": "x/y"}},
              "base": {"ref": "dev-mcphub"}}
        with patch.object(mod, "api", side_effect=[[pr]]), \
             patch.object(mod, "git") as git:
            with self.assertRaisesRegex(ValueError, "HEAD mismatch"):
                mod.verify_candidate("x/y", branch, "a" * 40, "v0.0.17")
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
