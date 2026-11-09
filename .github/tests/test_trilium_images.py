"""Trilium installs prebuilt images; every path that advertises a tag publishes it first."""
from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
IMAGE = 'image: "ghcr.io/hypercrisis/{arch}-trilium"'


def workflow(name):
    text = (ROOT / '.github/workflows' / name).read_text()
    return text, yaml.safe_load(text)


class TriliumImagesTest(unittest.TestCase):
    def test_app_metadata_advertises_the_published_image(self):
        config = (ROOT / 'TriliumNext Notes/config.yaml').read_text()
        self.assertIn(IMAGE, config)
        text, publisher = workflow('publish-trilium-images.yml')
        self.assertIn(IMAGE, text)
        version = re.compile(publisher['env']['VERSION_PATTERN'])
        for value in ('v2026.11.05', 'v2026.11.05.2', 'v2026.11.05-dev.162', 'v2026.11.05.2-dev.7'):
            self.assertTrue(version.match(f'version: "{value}"'), value)
        for value in ('latest', 'v2026.11.05;echo bad', 'v2026.11.05-dev.bad', '1.2.0'):
            self.assertFalse(version.match(f'version: "{value}"'), value)

    def test_release_tags_are_gated_by_both_architectures_and_anonymous_pull(self):
        text, publisher = workflow('publish-trilium-images.yml')
        self.assertEqual(publisher['jobs']['publish']['needs'], 'build')
        self.assertEqual(
            sorted(item['arch'] for item in publisher['jobs']['build']['strategy']['matrix']['include']),
            ['aarch64', 'amd64'])
        self.assertIn('DOCKER_CONFIG="$public_config" docker manifest inspect', text)
        self.assertIn('Refusing to replace an existing release', text)
        self.assertIn('Source changed during build', text)
        self.assertIn('cancel-in-progress: false', text)

    def test_dev_store_waits_for_public_tested_images(self):
        text, store = workflow('sync-dev-store.yml')
        self.assertIn('trilium-images', store['jobs']['publish']['needs'])
        self.assertEqual(store['jobs']['trilium-images']['uses'], './.github/workflows/publish-trilium-images.yml')
        self.assertEqual(store['jobs']['trilium-images']['with'], {'bundle': 'calibre-store-candidate'})
        self.assertIn('if key in ("mcphub", "trilium"):', text)

    def test_release_paths_publish_before_main_advertises_the_tag(self):
        _, promote = workflow('promote.yml')
        self.assertEqual(promote['jobs']['promote-trilium']['needs'], 'trilium-images')
        self.assertEqual(promote['jobs']['trilium-images']['with'], {'source_ref': 'dev-trilium'})
        text, auto = workflow('auto-promote-trilium.yml')
        self.assertEqual(auto['jobs']['images']['needs'], 'gate')
        self.assertEqual(auto['jobs']['promote']['needs'], ['gate', 'images'])
        self.assertIn('ghcr.io/hypercrisis/${arch}-trilium:${version}', text)
        self.assertIn('Install image is not public', text)
        self.assertEqual(auto['permissions']['packages'], 'write')

    def test_haos_source_test_still_builds_unreleased_commits(self):
        script = (ROOT / '.github/scripts/haos-e2e.sh').read_text()
        self.assertIn('sed -i \'/^image:/d\' "${TARGET_DIR}/config.yaml"', script)


if __name__ == '__main__':
    unittest.main()
