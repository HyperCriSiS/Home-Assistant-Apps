import importlib.util
from pathlib import Path
import unittest
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('images', ROOT / '.github/scripts/calibre_images.py')
images = importlib.util.module_from_spec(spec)
spec.loader.exec_module(images)


class ImageMetadataTest(unittest.TestCase):
    def test_source_and_enabled_store_share_the_same_content_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / 'Calibre AIO'
            app.mkdir()
            config = app / 'config.yaml'
            config.write_text('version: "1.2.0"\n')
            for arguments in (['init', '-q'], ['config', 'user.name', 'Test'],
                              ['config', 'user.email', 'test@localhost'],
                              ['add', '.'], ['commit', '-qm', 'Initial source']):
                subprocess.run(['git', *arguments], cwd=root, check=True, capture_output=True)
            command = [sys.executable, str(ROOT / '.github/scripts/calibre_images.py'), 'metadata']
            source = subprocess.check_output(command, cwd=root, text=True)
            self.assertIn(images.IMAGE, config.read_text())
            subprocess.run(['git', 'commit', '-qm', 'Enable store pulls'], cwd=root, check=True)
            store = subprocess.check_output(command, cwd=root, text=True)
            self.assertEqual(source, store)
            config.write_text(config.read_text().replace('1.2.0', '1.2.1'))
            self.assertNotEqual(source, subprocess.check_output(command, cwd=root, text=True))

    def test_stable_and_generated_dev_versions_match_supervisor_tags(self):
        for version in ('0.1.2', '1.2.0', '1.2.0-dev.162'):
            text = f'name: Calibre\nversion: "{version}"\n'
            enabled = images.enable(text)
            self.assertEqual(images.read_version(enabled), version)
            self.assertEqual(images.enable(enabled), enabled)
            self.assertEqual(enabled.count('image:'), 1)

    def test_invalid_or_foreign_metadata_fails_closed(self):
        for version in ('latest', '1.2.0;echo bad', '1.2.0-dev.bad', '../1.2.0'):
            with self.assertRaises(ValueError):
                images.enable(f'version: "{version}"\n')
        with self.assertRaises(ValueError):
            images.enable('version: "1.2.0"\nimage: "unrelated/image"\n')

    def test_dev_store_waits_for_public_tested_images(self):
        text = (ROOT / '.github/workflows/sync-dev-store.yml').read_text()
        self.assertIn('needs: images', text)
        self.assertLess(text.index('Prepare immutable store candidate'), text.index('  images:'))
        self.assertGreater(text.index('HEAD:refs/heads/dev-store'), text.index('needs: images'))
        self.assertIn('cancel-in-progress: false', text)

    def test_release_tags_are_gated_by_both_architectures_and_anonymous_pull(self):
        text = (ROOT / '.github/workflows/publish-calibre-images.yml').read_text()
        self.assertIn('needs: build', text)
        self.assertIn('DOCKER_CONFIG="$public_config" docker manifest inspect', text)
        self.assertIn('Refusing to replace an existing release', text)
        self.assertIn('Source changed during build', text)
