import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('images', ROOT / '.github/scripts/calibre_images.py')
images = importlib.util.module_from_spec(spec)
spec.loader.exec_module(images)


class ImageMetadataTest(unittest.TestCase):
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
