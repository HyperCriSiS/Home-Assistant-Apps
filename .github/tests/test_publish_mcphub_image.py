"""Regression tests for prebuilt MCPHub installation and publication ordering."""
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "publisher", ROOT / ".github/scripts/publish-mcphub-image.py",
)
PUB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PUB)
REVISION = "a" * 40


class PublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.source = Path(temporary.name) / "MCPHub"
        shutil.copytree(ROOT / "MCPHub", self.source,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.version, _ = PUB.metadata(self.source)
        self.script = ROOT / ".github/scripts/integration-test-mcphub.sh"
        self.fingerprint = PUB.source_hash(self.source)

    def test_metadata_accepts_development_tag_and_rejects_other_registry(self):
        path = self.source / "config.yaml"
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace(self.version, self.version + "-dev.123"), encoding="utf-8")
        self.assertEqual(PUB.metadata(self.source)[0], self.version + "-dev.123")
        path.write_text(original.replace(PUB.IMAGE, "ghcr.io/other/image"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Unexpected MCPHub image"):
            PUB.metadata(self.source)

    def test_hash_tracks_packaged_code_but_ignores_release_notes_and_commit_id(self):
        (self.source / ".haos-source-revision").write_text("b" * 40, encoding="utf-8")
        (self.source / "CHANGELOG.md").write_text("Edited release notes", encoding="utf-8")
        self.assertEqual(PUB.source_hash(self.source), self.fingerprint)
        with (self.source / "run.sh").open("a", encoding="utf-8") as handle:
            handle.write("\n# Runtime change\n")
        self.assertNotEqual(PUB.source_hash(self.source), self.fingerprint)

    def test_hash_includes_new_copy_inputs_and_rejects_unhandled_forms(self):
        dockerfile = self.source / "Dockerfile"
        original = dockerfile.read_text(encoding="utf-8")
        dockerfile.write_text(original + "\nCOPY extra.txt /extra.txt\n", encoding="utf-8")
        (self.source / "extra.txt").write_text("first", encoding="utf-8")
        first = PUB.source_hash(self.source)
        (self.source / "extra.txt").write_text("second", encoding="utf-8")
        self.assertNotEqual(PUB.source_hash(self.source), first)
        dockerfile.write_text(original + "\nCOPY extra/ /extra/\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Unsupported COPY"):
            PUB.source_hash(self.source)

    def test_existing_tag_is_verified_without_build_or_push(self):
        with patch.object(PUB, "existing_manifest", return_value={}), \
                patch.object(PUB, "verify_public") as verify, patch.object(PUB, "run") as run:
            PUB.publish(self.source, REVISION, self.script)
        verify.assert_called_once_with(self.version, self.fingerprint)
        run.assert_not_called()

    def test_different_existing_tag_is_never_overwritten(self):
        with patch.object(PUB, "existing_manifest", return_value={}), \
                patch.object(PUB, "verify_public", side_effect=ValueError("bump the App version")), \
                patch.object(PUB, "run") as run:
            with self.assertRaisesRegex(ValueError, "bump the App version"):
                PUB.publish(self.source, REVISION, self.script)
        run.assert_not_called()

    def test_both_architectures_are_tested_before_any_push(self):
        commands = []

        def record(*args):
            commands.append(args)
            if args[:3] == ("docker", "buildx", "build"):
                context = Path(args[-1])
                self.assertEqual((context / ".haos-source-revision").read_text().strip(), REVISION)

        with patch.object(PUB, "existing_manifest", return_value=None), \
                patch.object(PUB, "run", side_effect=record), \
                patch.object(PUB, "verify_public") as verify:
            PUB.publish(self.source, REVISION, self.script)
        builds = [args for args in commands if args[:3] == ("docker", "buildx", "build")]
        self.assertEqual([args[args.index("--platform") + 1] for args in builds],
                         ["linux/amd64", "linux/arm64"])
        tests = [i for i, args in enumerate(commands) if args[0] == "bash"]
        pushes = [i for i, args in enumerate(commands) if args[:2] == ("docker", "push")]
        self.assertEqual(len(tests), 2)
        self.assertEqual(len(pushes), 2)
        self.assertLess(max(tests), min(pushes))
        self.assertEqual(commands[-1][:4], ("docker", "buildx", "imagetools", "create"))
        verify.assert_called_once_with(self.version, self.fingerprint)
        self.assertEqual((self.source / ".haos-source-revision").read_text().strip(), "unidentified")

    def test_arm64_failure_publishes_no_images(self):
        commands = []

        def fail_second_test(*args):
            commands.append(args)
            if args[0] == "bash" and args[-1].endswith("-aarch64"):
                raise subprocess.CalledProcessError(1, args)

        with patch.object(PUB, "existing_manifest", return_value=None), \
                patch.object(PUB, "run", side_effect=fail_second_test), \
                patch.object(PUB, "verify_public") as verify:
            with self.assertRaises(subprocess.CalledProcessError):
                PUB.publish(self.source, REVISION, self.script)
        self.assertFalse(any(args[:2] == ("docker", "push") for args in commands))
        self.assertFalse(any(args[:4] == ("docker", "buildx", "imagetools", "create") for args in commands))
        verify.assert_not_called()

    def test_registry_auth_errors_do_not_get_treated_as_missing_tags(self):
        for message in ("unauthorized", "connection refused", "credential helper executable file not found"):
            with self.subTest(message=message), patch.object(
                PUB.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", message),
            ):
                with self.assertRaisesRegex(RuntimeError, "Cannot inspect"):
                    PUB.existing_manifest("example:test")
        with patch.object(PUB.subprocess, "run", return_value=subprocess.CompletedProcess(
            [], 1, "", "ERROR: example:test: not found",
        )):
            self.assertIsNone(PUB.existing_manifest("example:test"))

    def registry(self, bad_arch=None, platforms=("amd64", "arm64")):
        def response(url, token=""):
            if "/token?" in url:
                self.assertEqual(token, "")
                return {"token": "anonymous-pull-token"}
            self.assertEqual(token, "anonymous-pull-token")
            if url.endswith("/manifests/" + self.version):
                return {"manifests": [
                    {"platform": {"os": "linux", "architecture": arch}, "digest": f"sha256:{arch}"}
                    for arch in platforms
                ]}
            arch = url.rsplit(":", 1)[-1]
            if "/manifests/" in url:
                return {"config": {"digest": f"sha256:{arch}"}}
            return {"os": "linux", "architecture": arch, "config": {"Labels": {
                PUB.SOURCE_LABEL: "wrong" if arch == bad_arch else self.fingerprint,
                "io.hass.version": self.version,
                "io.hass.arch": "aarch64" if arch == "arm64" else arch,
            }}}
        return response

    def test_anonymous_check_verifies_both_actual_image_configurations(self):
        with patch.object(PUB, "public_json", side_effect=self.registry()) as request:
            PUB.verify_public(self.version, self.fingerprint)
        self.assertEqual(request.call_count, 6)
        with patch.object(PUB, "public_json", side_effect=self.registry(bad_arch="arm64")):
            with self.assertRaisesRegex(ValueError, "bump the App version"):
                PUB.verify_public(self.version, self.fingerprint)

    def test_incomplete_manifest_and_private_package_are_rejected(self):
        with patch.object(PUB, "public_json", side_effect=self.registry(platforms=("amd64",))):
            with self.assertRaisesRegex(ValueError, "linux/amd64 and linux/arm64"):
                PUB.verify_public(self.version, self.fingerprint)
        with patch.object(PUB, "public_json", side_effect=HTTPError("registry", 403, "private", {}, None)):
            with self.assertRaisesRegex(RuntimeError, "visibility to Public"):
                PUB.verify_public(self.version, self.fingerprint)


class WorkflowTests(unittest.TestCase):
    def test_dev_store_is_exposed_only_after_successful_publication(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/sync-dev-store.yml").read_text())
        self.assertIs(workflow["concurrency"]["cancel-in-progress"], False)
        jobs = workflow["jobs"]
        self.assertEqual(set(jobs["publish"]["needs"]), {"images", "mcphub-images", "trilium-images"})
        self.assertEqual(jobs["mcphub-images"]["needs"], "sync")
        self.assertEqual(jobs["mcphub-images"]["with"]["bundle"], jobs["images"]["with"]["bundle"])
        self.assertNotIn("continue-on-error", jobs["mcphub-images"])
        self.assertNotIn("if", jobs["publish"])

    def test_metadata_reserves_new_run_tags_but_retains_unchanged_versions(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/sync-dev-store.yml").read_text())
        step = next(step for step in workflow["jobs"]["sync"]["steps"]
                    if step["name"] == "Generate development metadata")
        code = step["run"].split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary:
            os.chdir(temporary)
            try:
                Path("repository.json").write_text('{"name": "test"}')
                for app in ("MCPHub", "TriliumNext Notes", "Calibre AIO"):
                    Path(app).mkdir()
                    Path(app, "config.yaml").write_text(
                        'name: "test"\nversion: "v2026.11.02"\npanel_title: "test"\nurl: "test"\ninit: false\n'
                        '  library_dir: "calibre-aio/library"\n  ingest_dir: "calibre-aio/ingest"\n'
                        '  processed_dir: "calibre-aio/processed"\n',
                    )
                def generate(run_number, source):
                    with patch.dict(os.environ, {"DEV_BUILD": str(run_number)}), \
                            patch.object(subprocess, "run", return_value=subprocess.CompletedProcess(
                                [], 0, source + "\n", "",
                            )):
                        exec(compile(code, "dev-store-metadata", "exec"), {})
                    return json.loads(Path(".dev-store-revisions.json").read_text())
                first = generate(100, "first-source")
                self.assertEqual(first["mcphub"]["revision"], 100)
                same = generate(101, "first-source")
                self.assertEqual(same["mcphub"]["revision"], 100)
                # Run 102 might have published images but failed before git push.
                # The next run must not reuse 101 or 102 for a different source.
                changed = generate(103, "changed-source")
                self.assertEqual(changed["mcphub"]["revision"], 103)
                # Trilium publishes images too, so it reserves the run tag as well.
                self.assertEqual(changed["trilium"]["revision"], 103)
                self.assertEqual(changed["calibre"]["revision"], 101)
                self.assertIn("-dev.103", Path("MCPHub/config.yaml").read_text())
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
