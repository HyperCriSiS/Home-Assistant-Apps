"""Regression checks for the 12-hour development merge of bot update PRs."""
import importlib.util
import os
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
path = ROOT / ".github" / "scripts" / "merge_due_updates.py"
spec = importlib.util.spec_from_file_location("merge_due_updates", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REPO = "x/y"
HOUR = 3600


def pr(branch, base, **overrides):
    data = {
        "number": 5, "state": "open", "draft": False, "labels": [],
        "user": {"login": mod.BOT}, "created_at": "2026-10-24T04:20:00Z",
        "base": {"ref": base},
        "head": {"ref": branch, "sha": "a" * 40, "repo": {"full_name": REPO}},
    }
    data.update(overrides)
    return data


class ClassifyTests(unittest.TestCase):
    def test_known_update_branches(self):
        cases = {
            ("automation/mcphub-1.1.10", "dev-mcphub"): ("mcphub-upstream", "1.1.10"),
            ("automation/mcphub-tunnel-clients-v0_0_17", "dev-mcphub"): ("mcphub-tunnel", "v0.0.17"),
            ("automation/trilium-v0.106.1", "dev-trilium"): ("trilium", "v0.106.1"),
        }
        for (branch, base), expected in cases.items():
            with self.subTest(branch=branch):
                kind, version = mod.classify(pr(branch, base), REPO)
                self.assertEqual((kind.name, version), expected)

    def test_everything_else_is_ignored(self):
        cases = [
            pr("automation/trilium-v0.106.1", "main"),
            pr("automation/trilium-v0.106.1", "dev-mcphub"),
            pr("automation/trilium-v0.107.0-beta", "dev-trilium"),
            pr("feature/x", "dev-trilium"),
            pr("automation/trilium-v0.106.1", "dev-trilium", user={"login": "someone"}),
            pr("automation/trilium-v0.106.1", "dev-trilium",
               head={"ref": "automation/trilium-v0.106.1", "sha": "a" * 40,
                     "repo": {"full_name": "fork/y"}}),
        ]
        for item in cases:
            with self.subTest(pr=item["head"]["ref"]):
                self.assertIsNone(mod.classify(item, REPO))

    def test_identity_requires_expected_title(self):
        kind, version = mod.classify(pr("automation/trilium-v0.106.1", "dev-trilium"), REPO)
        good = pr("automation/trilium-v0.106.1", "dev-trilium", title="chore: update Trilium to v0.106.1")
        mod.check_identity(good, kind, version)
        for change in ({"title": "chore: update Trilium to v9.9.9"}, {"draft": True}):
            with self.subTest(change=change), self.assertRaises(mod.Hold):
                mod.check_identity({**good, **change}, kind, version)


class DecisionTests(unittest.TestCase):
    def test_twelve_hour_delay(self):
        self.assertEqual(mod.decide(behind=False, tree_matches=True, ci="success", age=11.9 * HOUR), "wait")
        self.assertEqual(mod.decide(behind=False, tree_matches=True, ci="success", age=12 * HOUR), "merge")

    def test_fail_closed(self):
        self.assertEqual(mod.decide(behind=False, tree_matches=False, ci="success", age=99 * HOUR), "hold")
        self.assertEqual(mod.decide(behind=False, tree_matches=True, ci="failed", age=99 * HOUR), "hold")
        self.assertEqual(mod.decide(behind=False, tree_matches=True, ci="missing", age=99 * HOUR), "validate")
        self.assertEqual(mod.decide(behind=False, tree_matches=True, ci="running", age=99 * HOUR), "wait")
        self.assertEqual(mod.decide(behind=True, tree_matches=False, ci="success", age=99 * HOUR), "refresh")

    def test_pr_date_is_utc(self):
        self.assertEqual(mod.pr_date({"created_at": "2026-10-24T23:59:00Z"}), date(2026, 10, 24))


class GenerateTests(unittest.TestCase):
    """Regenerates real update content in a throw-away repository."""

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
        for name in {*mod.trilium.UPDATE_FILES, *mod.tunnel.ALLOWED_FILES, *mod.MCPHUB_UPSTREAM_FILES}:
            target = Path(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((ROOT / name).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.base = self.git("rev-parse", "HEAD")

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], check=True, capture_output=True,
                              text=True).stdout.strip()

    def generate(self, kind_name, version):
        kind = next(kind for kind in mod.KINDS if kind.name == kind_name)
        worktree = str(Path(self.tmp.name, f"wt-{kind_name}"))
        try:
            return kind, mod.generate(kind, version, date(2026, 10, 24), self.base, worktree)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", worktree], capture_output=True)

    def test_trilium_update_is_deterministic(self):
        kind, first = self.generate("trilium", "v999.0.0")
        _, second = self.generate("trilium", "v999.0.0")
        self.assertEqual(self.git("rev-parse", f"{first}^{{tree}}"), self.git("rev-parse", f"{second}^{{tree}}"))
        changed = set(self.git("diff", "--name-only", self.base, first).splitlines())
        self.assertEqual(changed, set(kind.files))
        self.assertEqual(self.git("log", "-1", "--format=%s", first), "chore: update Trilium to v999.0.0")

    def test_tunnel_update_touches_only_its_files(self):
        kind, commit = self.generate("mcphub-tunnel", "v99.0.0")
        changed = set(self.git("diff", "--name-only", self.base, commit).splitlines())
        self.assertEqual(changed, set(kind.files))

    def test_mcphub_upstream_update_uses_trusted_updater(self):
        kind, commit = self.generate("mcphub-upstream", "99.0.0")
        changed = set(self.git("diff", "--name-only", self.base, commit).splitlines())
        self.assertEqual(changed, set(kind.files))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_update_already_on_base_is_held(self):
        current = mod.trilium.pinned_upstream(Path(mod.trilium.UPDATE_FILES[0]).read_text(encoding="utf-8"))
        with self.assertRaises(mod.Hold):
            self.generate("trilium", current)


if __name__ == "__main__":
    unittest.main()
