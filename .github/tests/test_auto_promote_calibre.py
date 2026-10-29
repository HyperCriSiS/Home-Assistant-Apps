"""Regression checks for the fail-closed Calibre AIO auto-promotion gates."""
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "scripts" / "auto_promote_calibre.py"
spec = importlib.util.spec_from_file_location("auto_promote_calibre", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REPO = "x/y"
NOW = 1_800_000_000.0
APP = "Calibre AIO"
MANIFEST = {
    "cwa": {"repository": "crocodilestick/Calibre-Web-Automated", "version": "v4.0.8",
            "commit": "a" * 40, "sha256": "b" * 64},
    "shelfmark": {"repository": "calibrain/shelfmark", "version": "v1.5.1",
                  "commit": "c" * 40, "sha256": "d" * 64},
    "calibre": "9.1.0", "kepubify": "v4.0.4", "shelfmark_python": "3.14.7",
}
CONFIG = 'name: "Calibre AIO"\nversion: "1.0.0"\nslug: "calibre-aio"\n'
NOTES = "# 1.0.0\n\n- Stable release.\n"


def files(manifest, config=CONFIG, notes=NOTES):
    return {
        f"{APP}/upstream.json": json.dumps(manifest, indent=2) + "\n",
        f"{APP}/build.yaml": mod.upstreams.render(manifest),
        f"{APP}/config.yaml": config,
        f"{APP}/CHANGELOG.md": notes,
    }


STABLE = files(MANIFEST)


def bumped(cwa="v4.0.10", shelfmark="v1.6.0", **overrides):
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["cwa"].update(version=cwa, commit="e" * 40, sha256="f" * 64)
    manifest["shelfmark"].update(version=shelfmark, commit="1" * 40, sha256="2" * 64)
    result = files(
        manifest, CONFIG.replace('"1.0.0"', '"1.0.2"'),
        f"# 1.0.2\n\n- Update CWA to {cwa} and Shelfmark to {shelfmark}.\n\n"
        f"# 1.0.1\n\n- Update CWA to v4.0.9 and Shelfmark to v1.5.1.\n\n" + NOTES,
    )
    result.update(overrides)
    return result


class ContentTests(unittest.TestCase):
    def test_accepts_pure_pin_bumps(self):
        self.assertEqual(mod.check_content(STABLE, bumped()),
                         {"cwa": ("v4.0.8", "v4.0.10"), "shelfmark": ("v1.5.1", "v1.6.0")})
        self.assertEqual(mod.summary(mod.check_content(STABLE, bumped())),
                         "CWA to v4.0.10 and Shelfmark to v1.6.0")

    def test_rejects_any_other_change(self):
        cases = {
            f"{APP}/build.yaml": bumped()[f"{APP}/build.yaml"] + "  EXTRA: \"1\"\n",
            f"{APP}/config.yaml": bumped()[f"{APP}/config.yaml"] + "privileged: [SYS_ADMIN]\n",
        }
        for name, text in cases.items():
            with self.subTest(file=name), self.assertRaises(ValueError):
                mod.check_content(STABLE, bumped(**{name: text}))

    def test_rejects_other_manifest_changes_and_redirected_sources(self):
        for change in ({"calibre": "9.9.9"}, {"cwa": dict(MANIFEST["cwa"], repository="evil/cwa")}):
            manifest = dict(json.loads(bumped()[f"{APP}/upstream.json"]), **change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                mod.check_content(STABLE, bumped(**{f"{APP}/upstream.json": json.dumps(manifest)}))

    def test_rejects_changed_provenance_of_an_unchanged_version(self):
        manifest = json.loads(bumped(shelfmark="v1.5.1")[f"{APP}/upstream.json"])
        with self.assertRaisesRegex(ValueError, "provenance"):
            mod.check_content(STABLE, files(manifest, bumped()[f"{APP}/config.yaml"],
                                            bumped(shelfmark="v1.5.1")[f"{APP}/CHANGELOG.md"]))

    def test_rejects_changelog_edits(self):
        notes = bumped()[f"{APP}/CHANGELOG.md"]
        for text in (notes.replace("- Stable release.", "- Rewritten."),
                     notes.replace("v1.6.0.\n", "v1.6.0.\n- Also something manual.\n", 1)):
            with self.subTest(text=text[:60]), self.assertRaises(ValueError):
                mod.check_content(STABLE, bumped(**{f"{APP}/CHANGELOG.md": text}))

    def test_rejects_downgrade_and_unchanged_app_version(self):
        with self.assertRaises(ValueError):
            mod.check_content(bumped(), STABLE)
        same = bumped(**{f"{APP}/config.yaml": CONFIG})
        with self.assertRaisesRegex(ValueError, "App version"):
            mod.check_content(STABLE, same)

    def test_major_update_stays_manual(self):
        with self.assertRaisesRegex(mod.Skip, "Major"):
            mod.check_content(STABLE, bumped(cwa="v5.0.0"))


class GateTests(unittest.TestCase):
    def run_gate(self, state, newest=NOW - 49 * 3600, changed=None):
        with patch.object(mod, "git") as git, \
             patch.object(mod.shared, "check_history", return_value=newest), \
             patch.object(mod, "show", side_effect=lambda sha, name: (STABLE if sha == "m" else bumped())[name]), \
             patch.object(mod.shared, "check_release") as release, \
             patch.object(mod, "api", return_value={}), \
             patch.object(mod, "ci_state", return_value=state):
            git.side_effect = lambda *a: {
                ("rev-parse", "origin/main"): "m", ("rev-parse", "origin/dev-calibre"): "d",
                ("diff", "--name-only", "m", "d"): "\n".join(changed or mod.ALLOWED_FILES),
            }.get(a, "")
            result = mod.gate(REPO, NOW)
            self.assertEqual(release.call_count, 2)
            return result

    def test_validation_is_mandatory(self):
        self.assertEqual(self.run_gate("missing")["action"], "validate")
        self.assertEqual(self.run_gate("running")["action"], "wait")
        with self.assertRaisesRegex(ValueError, "validation failed"):
            self.run_gate("failed")
        self.assertEqual(self.run_gate("success")["action"], "promote")

    def test_soak_of_48_hours(self):
        with self.assertRaisesRegex(mod.Skip, "36 hours"):
            self.run_gate("success", newest=NOW - 35 * 3600)

    def test_other_files_keep_the_release_manual(self):
        with self.assertRaisesRegex(mod.Skip, "manually"):
            self.run_gate("success", changed=[*mod.ALLOWED_FILES, f"{APP}/Dockerfile"])


class ReleasePrTests(unittest.TestCase):
    pr = {"head": {"ref": "dev-calibre", "sha": "d", "repo": {"full_name": REPO}},
          "draft": False, "labels": [], "number": 7}

    def test_hold_and_stale_heads_are_never_merged(self):
        cases = ({"labels": [{"name": "hold"}]}, {"draft": True},
                 {"head": {"ref": "dev-calibre", "sha": "old", "repo": {"full_name": REPO}}})
        for change in cases:
            with self.subTest(change=change), \
                 patch.object(mod, "api", return_value=[{**self.pr, **change}]), \
                 self.assertRaises(mod.Skip):
                mod.release_pr(REPO, "d")

    def test_existing_release_pr_is_reused(self):
        with patch.object(mod, "api", return_value=[self.pr]):
            self.assertEqual(mod.release_pr(REPO, "d")["number"], 7)


class UpdaterContractTests(unittest.TestCase):
    def test_gate_accepts_the_updater_title(self):
        title = "chore(calibre-aio): update CWA to v4.0.10 and Shelfmark to v1.6.0"
        self.assertTrue(any(pattern.fullmatch(title) for pattern in mod.UPDATE_TITLES))


if __name__ == "__main__":
    unittest.main()
