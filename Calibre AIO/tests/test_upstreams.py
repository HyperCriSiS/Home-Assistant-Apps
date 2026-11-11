import importlib.util
import io
import json
import re
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('aio_upstreams', ROOT / 'scripts/upstreams.py')
upstreams = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upstreams)


class UpstreamUpdateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ('upstream.json', 'build.yaml', 'config.yaml', 'CHANGELOG.md', 'README.md', 'NOTICE.md'):
            (self.root / name).write_bytes((ROOT / name).read_bytes())
        self.root_patch = patch.object(upstreams, 'ROOT', self.root)
        self.root_patch.start()
        self.before = {p.name: p.read_bytes() for p in self.root.iterdir()}

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def test_update_regenerates_both_pins_build_and_revision(self):
        data = upstreams.load_manifest()
        def latest(name, known=None):
            return dict(data[name], version='v9.0.0', commit='f' * 40, sha256='e' * 64)
        with (patch.object(upstreams, 'latest', latest), patch.object(upstreams, 'check_chromium'),
              patch.object(sys, 'argv', ['upstreams', 'update'])):
            upstreams.main()
        updated = upstreams.load_manifest()
        self.assertEqual(updated['cwa']['version'], 'v9.0.0')
        self.assertEqual(updated['shelfmark']['version'], 'v9.0.0')
        previous = upstreams.app_version(self.before['config.yaml'].decode())
        expected = upstreams.next_version(previous)
        self.assertNotEqual(expected, previous)
        config = (self.root / 'config.yaml').read_text()
        self.assertIn(f'version: "{expected}"', config)
        self.assertIn('description: "CWA v9.0.0 and Shelfmark v9.0.0 - ', config)
        self.assertIn('/badge/CWA-v9.0.0-', (self.root / 'README.md').read_text())
        self.assertIn('- Version currently packaged: v9.0.0', (self.root / 'NOTICE.md').read_text())
        self.assertEqual((self.root / 'build.yaml').read_text(), upstreams.render(updated))

    def test_chromium_pin_must_match_shelfmark(self):
        pins = 'ARG CHROMIUM_VERSION=1\nARG CHROMIUM_SNAPSHOT=2\n'
        (self.root / 'Dockerfile').write_text(pins)
        def serve(text):
            return patch.object(upstreams, 'request', return_value=io.BytesIO(text.encode()))
        with serve(pins):
            upstreams.check_chromium('f' * 40)
        for text in (pins.replace('=1', '=3'), ''):
            with self.subTest(text=text), serve(text), self.assertRaises(ValueError):
                upstreams.check_chromium('f' * 40)

    def test_pinned_versions_reproduce_a_proposal(self):
        data = upstreams.load_manifest()
        def release(name, tag, known=None):
            return dict(data[name], version=tag, commit='f' * 40, sha256='e' * 64)
        argv = ['upstreams', 'update', '--cwa-version', 'v9.0.0',
                '--shelfmark-version', data['shelfmark']['version']]
        with (patch.object(upstreams, 'release', release), patch.object(sys, 'argv', argv),
              self.assertRaisesRegex(ValueError, 'provenance')):
            upstreams.main()
        with (patch.object(upstreams, 'release', lambda name, tag, known=None: dict(data[name], version=tag)
                           if tag != data[name]['version'] else data[name]),
              patch.object(sys, 'argv', argv)):
            upstreams.main()
        updated = upstreams.load_manifest()
        self.assertEqual(updated['cwa']['version'], 'v9.0.0')
        self.assertEqual(updated['shelfmark'], data['shelfmark'])
        version = re.search(r'^version: "(.+)"$', (self.root / 'config.yaml').read_text(), re.M)[1]
        self.assertTrue((self.root / 'CHANGELOG.md').read_text().startswith(
            f'# Changelog\n\n## {version}\n\n### Changed\n\n- Update CWA to v9.0.0 and Shelfmark to '
            f'{data["shelfmark"]["version"]}.\n\n'))

    def test_unchanged_release_provenance_must_match_without_file_changes(self):
        data = upstreams.load_manifest()
        with (patch.object(upstreams, 'latest', lambda name, known=None: dict(data[name], sha256='e' * 64)),
              patch.object(sys, 'argv', ['upstreams', 'update']), self.assertRaises(ValueError)):
            upstreams.main()
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, self.before)

    def test_unchanged_pin_skips_the_archive_download(self):
        known = upstreams.load_manifest()['cwa']
        answers = [io.BytesIO(json.dumps({'tag_name': known['version']}).encode()),
                   io.BytesIO(json.dumps({'sha': known['commit']}).encode())]
        with patch.object(upstreams, 'request', side_effect=answers) as request:
            self.assertEqual(upstreams.latest('cwa', known), known)
        self.assertEqual(request.call_count, 2)

    def test_downgrade_is_rejected_without_file_changes(self):
        data = upstreams.load_manifest()
        with (patch.object(upstreams, 'latest', lambda name, known=None: dict(data[name], version='v0.0.1')),
              patch.object(sys, 'argv', ['upstreams', 'update']), self.assertRaises(ValueError)):
            upstreams.main()
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, self.before)

    def test_manifest_repository_cannot_redirect_update_source(self):
        data = upstreams.load_manifest()
        data['shelfmark']['repository'] = 'untrusted/other'
        (self.root / 'upstream.json').write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            upstreams.load_manifest()
