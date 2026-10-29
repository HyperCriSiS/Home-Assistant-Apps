"""Exercise the actual shared-store generator, including independent revisions."""
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]


class DevelopmentStoreTest(unittest.TestCase):
    def test_three_app_generation_and_calibre_revision_isolation(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/sync-dev-store.yml').read_text())
        steps = workflow['jobs']['sync']['steps']
        block = next(step['run'] for step in steps if step['name'] == 'Generate development metadata')
        code = compile('\n'.join(block.splitlines()[1:-1]), '<store-generator>', 'exec')
        trees = {}

        def git_tree(args, **kwargs):
            key = args[-1]
            return SimpleNamespace(stdout=trees.get(key, 'tree:' + key))

        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            for folder in ('Calibre AIO', 'MCPHub', 'TriliumNext Notes'):
                (temp / folder).mkdir()
                shutil.copyfile(ROOT / folder / 'config.yaml', temp / folder / 'config.yaml')
            shutil.copyfile(ROOT / 'repository.json', temp / 'repository.json')
            original = Path.cwd()
            try:
                os.chdir(temp)
                with patch.dict(os.environ, {'DEV_BUILD': '100'}), patch('subprocess.run', side_effect=git_tree):
                    exec(code, {})
                    first = json.loads(Path('.dev-store-revisions.json').read_text())
                    calibre = yaml.safe_load(Path('Calibre AIO/config.yaml').read_text())
                    self.assertEqual(set(first), {'calibre', 'mcphub', 'trilium'})
                    self.assertEqual(calibre['name'], 'Calibre AIO (Dev)')
                    self.assertTrue(calibre['version'].endswith('-dev.100'))
                    self.assertEqual(calibre['options']['library_dir'], 'calibre-aio-dev/library')
                    self.assertEqual(calibre['options']['ingest_dir'], 'calibre-aio-dev/ingest')
                    self.assertEqual(calibre['ports'], {})
                    self.assertNotIn('homeassistant_api', calibre)
                    exec(code, {})
                    self.assertEqual(first, json.loads(Path('.dev-store-revisions.json').read_text()))
                    trees['origin/dev-calibre:Calibre AIO'] = 'new-calibre-tree'
                    exec(code, {})
                    updated = json.loads(Path('.dev-store-revisions.json').read_text())
                    self.assertEqual(updated['calibre']['revision'], 101)
                    self.assertEqual(updated['mcphub'], first['mcphub'])
                    self.assertEqual(updated['trilium'], first['trilium'])
            finally:
                os.chdir(original)

    def test_updater_and_composition_use_calibre_development_branch(self):
        updater = yaml.safe_load((ROOT / '.github/workflows/update-calibre-aio.yml').read_text())
        steps = updater['jobs']['update']['steps']
        self.assertEqual(steps[0]['with']['ref'], 'dev-calibre')
        proposal = next(step for step in steps if step.get('id') == 'proposal')
        self.assertEqual(proposal['with']['base'], 'dev-calibre')
        # Ready for review: merge-due-updates.yml only merges non-draft bot PRs whose
        # branch and title name both upstream versions.
        self.assertNotIn('draft', proposal['with'])
        versions = next(step for step in steps if step.get('id') == 'versions')['run']
        self.assertIn('branch=automation/calibre-aio-cwa-${cwa}-shelfmark-${shelfmark}', versions)
        self.assertIn('title=chore(calibre-aio): update CWA to ${cwa} and Shelfmark to ${shelfmark}', versions)
        workflow = (ROOT / '.github/workflows/sync-dev-store.yml').read_text()
        self.assertIn('git checkout origin/dev-calibre -- "Calibre AIO"', workflow)
        self.assertIn('- dev-calibre', workflow)


if __name__ == '__main__':
    unittest.main()
