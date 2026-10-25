import importlib.util
import json
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
        for name in ('upstream.json', 'build.yaml', 'config.yaml', 'CHANGELOG.md'):
            (self.root / name).write_bytes((ROOT / name).read_bytes())
        self.root_patch = patch.object(upstreams, 'ROOT', self.root)
        self.root_patch.start()
        self.before = {p.name: p.read_bytes() for p in self.root.iterdir()}

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def test_update_regenerates_both_pins_build_and_revision(self):
        data = upstreams.load_manifest()
        def latest(name):
            return dict(data[name], version='v9.0.0', commit='f' * 40, sha256='e' * 64)
        with patch.object(upstreams, 'latest', latest), patch.object(sys, 'argv', ['upstreams', 'update']):
            upstreams.main()
        updated = upstreams.load_manifest()
        self.assertEqual(updated['cwa']['version'], 'v9.0.0')
        self.assertEqual(updated['shelfmark']['version'], 'v9.0.0')
        self.assertIn('version: "0.1.1"', (self.root / 'config.yaml').read_text())
        self.assertEqual((self.root / 'build.yaml').read_text(), upstreams.render(updated))

    def test_unchanged_release_provenance_must_match_without_file_changes(self):
        data = upstreams.load_manifest()
        with (patch.object(upstreams, 'latest', lambda name: dict(data[name], sha256='e' * 64)),
              patch.object(sys, 'argv', ['upstreams', 'update']), self.assertRaises(ValueError)):
            upstreams.main()
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, self.before)

    def test_downgrade_is_rejected_without_file_changes(self):
        data = upstreams.load_manifest()
        with (patch.object(upstreams, 'latest', lambda name: dict(data[name], version='v0.0.1')),
              patch.object(sys, 'argv', ['upstreams', 'update']), self.assertRaises(ValueError)):
            upstreams.main()
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, self.before)

    def test_manifest_repository_cannot_redirect_update_source(self):
        data = upstreams.load_manifest()
        data['shelfmark']['repository'] = 'untrusted/other'
        (self.root / 'upstream.json').write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            upstreams.load_manifest()
