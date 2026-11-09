"""Inbox Zero installs prebuilt images; every path that advertises a tag publishes it first.

main carries this automation before the first release adds the App folder, so
these checks read only the workflows.
"""
from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
IMAGE = 'image: "ghcr.io/hypercrisis/{arch}-inbox-zero"'


def workflow(name):
    text = (ROOT / '.github/workflows' / name).read_text()
    return text, yaml.safe_load(text)


class InboxZeroImagesTest(unittest.TestCase):
    def test_publisher_requires_the_advertised_image_and_a_release_version(self):
        text, publisher = workflow('publish-inbox-zero-images.yml')
        self.assertIn(IMAGE, text)
        version = re.compile(publisher['env']['VERSION_PATTERN'])
        for value in ('v2026.11.09', 'v2026.11.09.2', 'v2026.11.09-dev.162', 'v2026.11.09.2-dev.7'):
            self.assertTrue(version.match(f'version: "{value}"'), value)
        for value in ('latest', 'v2026.11.09;echo bad', 'v2026.11.09-dev.bad', '2.30.0'):
            self.assertFalse(version.match(f'version: "{value}"'), value)

    def test_release_tags_are_gated_by_both_architectures_and_anonymous_pull(self):
        text, publisher = workflow('publish-inbox-zero-images.yml')
        self.assertEqual(publisher['jobs']['publish']['needs'], 'build')
        self.assertEqual(
            sorted(item['arch'] for item in publisher['jobs']['build']['strategy']['matrix']['include']),
            ['aarch64', 'amd64'])
        self.assertIn('DOCKER_CONFIG="$public_config" docker manifest inspect', text)
        self.assertIn('Refusing to replace an existing release', text)
        self.assertIn('Source changed during build', text)
        self.assertIn('cancel-in-progress: false', text)
        self.assertIn('/api/health', text)

    def test_base_image_is_built_once_per_fork_commit_before_the_app_image(self):
        text, base = workflow('build-inbox-zero-base.yml')
        self.assertIn('^[0-9a-f]{40}$', text)
        self.assertEqual(base['jobs']['build']['if'], "needs.check.outputs.exists == 'false'")
        self.assertEqual(
            sorted(item['arch'] for item in base['jobs']['build']['strategy']['matrix']['include']),
            ['amd64', 'arm64'])
        # actions/checkout fails on the fork's submodule path without a URL.
        self.assertNotIn('actions/checkout', text)
        self.assertIn('[[ "$(git rev-parse HEAD)" == "$COMMIT" ]]', text)
        _, validate = workflow('validate-inbox-zero.yml')
        self.assertEqual(validate['jobs']['base']['uses'], './.github/workflows/build-inbox-zero-base.yml')
        self.assertEqual(validate['jobs']['build']['needs'], ['pin', 'base'])
        # main has no App folder before the first release: nothing may run there.
        for name, job in validate['jobs'].items():
            if name != 'pin':
                self.assertEqual(job['if'], "needs.pin.outputs.commit != ''", name)

    def test_dev_store_waits_for_public_tested_images(self):
        text, store = workflow('sync-dev-store.yml')
        self.assertIn('inbox-zero-images', store['jobs']['publish']['needs'])
        self.assertEqual(store['jobs']['inbox-zero-images']['uses'],
                         './.github/workflows/publish-inbox-zero-images.yml')
        self.assertEqual(store['jobs']['inbox-zero-images']['with'], {'bundle': 'calibre-store-candidate'})
        self.assertIn('git checkout origin/dev-inbox-zero -- "Inbox Zero"', text)

    def test_release_paths_publish_before_main_advertises_the_tag(self):
        _, promote = workflow('promote.yml')
        self.assertEqual(promote['jobs']['promote-inbox-zero']['needs'], 'inbox-zero-images')
        self.assertEqual(promote['jobs']['inbox-zero-images']['with'], {'source_ref': 'dev-inbox-zero'})
        text, auto = workflow('auto-promote-inbox-zero.yml')
        self.assertEqual(auto['jobs']['images']['needs'], 'gate')
        self.assertEqual(auto['jobs']['promote']['needs'], ['gate', 'images'])
        self.assertIn('ghcr.io/hypercrisis/${arch}-inbox-zero:${version}', text)
        self.assertIn('Install image is not public', text)
        self.assertEqual(auto['permissions']['packages'], 'write')

    def test_updater_runs_the_trusted_copy_from_main(self):
        text, update = workflow('update-inbox-zero.yml')
        self.assertIn('git show "origin/main:.github/scripts/${script}"', text)
        self.assertIn('--base dev-inbox-zero', text)
        self.assertIn('gh workflow run validate-inbox-zero.yml', text)
        self.assertEqual(update['jobs']['update']['steps'][0]['with']['ref'], 'dev-inbox-zero')


if __name__ == '__main__':
    unittest.main()
