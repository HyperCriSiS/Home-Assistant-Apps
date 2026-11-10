"""A squashed release must not leave a development branch unable to take main."""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.github/scripts/resolve_release_changelog.py'
spec = importlib.util.spec_from_file_location('resolve_release_changelog', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

BASE = '# Changelog\n\n## v1\n\n- First.\n'
DEV = '# Changelog\n\n## v3\n\n- Third.\n\n## v2\n\n- Second,\n  wrapped.\n\n## v1\n\n- First.\n'
RELEASED = '# Changelog\n\n## v3\n\n- Second, wrapped.\n- Third.\n\n## v1\n\n- First.\n'


class ResolveTest(unittest.TestCase):
    def test_released_text_wins_when_the_branch_has_nothing_newer(self):
        self.assertEqual(module.resolve(DEV, RELEASED, 'v3'), RELEASED)

    def test_sections_above_the_released_version_are_kept(self):
        newer = DEV.replace('# Changelog\n\n', '# Changelog\n\n## v4\n\n- Fourth.\n\n')
        self.assertEqual(
            module.resolve(newer, RELEASED, 'v3'),
            RELEASED.replace('# Changelog\n\n', '# Changelog\n\n## v4\n\n- Fourth.\n\n'))

    def test_unknown_shapes_are_refused(self):
        with self.assertRaises(ValueError):
            module.resolve(BASE, RELEASED, 'v3')
        with self.assertRaises(ValueError):
            module.resolve(DEV, RELEASED, 'v2')


class MergeTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.repo = Path(directory.name)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('commit', '-q', '--allow-empty', '-m', 'root')
        self.commit('main', BASE, 'v1')
        self.git('branch', 'dev')
        self.commit('dev', DEV, 'v3')
        self.commit('main', RELEASED, 'v3')
        self.git('update-ref', 'refs/remotes/origin/main', 'main')
        self.git('checkout', '-q', 'dev')

    def git(self, *args, check=True):
        return subprocess.run(
            ['git', *args], cwd=self.repo, check=check, capture_output=True, text=True)

    def commit(self, branch, changelog, version, other=None):
        self.git('checkout', '-q', branch)
        (self.repo / 'My App').mkdir(exist_ok=True)
        (self.repo / 'My App/CHANGELOG.md').write_text(changelog, encoding='utf-8', newline='\n')
        (self.repo / 'My App/config.yaml').write_text(f'version: "{version}"\n', encoding='utf-8')
        if other:
            (self.repo / 'other.txt').write_text(other, encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', f'{branch} {version}')

    def resolve(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=self.repo, capture_output=True, text=True,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})

    def test_conflicted_merge_is_resolved_and_can_be_committed(self):
        self.assertNotEqual(self.git('merge', '--no-ff', '--no-edit', 'origin/main', check=False).returncode, 0)
        self.assertEqual(self.resolve().returncode, 0)
        self.git('commit', '--no-edit')
        self.assertEqual((self.repo / 'My App/CHANGELOG.md').read_bytes(), RELEASED.encode())
        self.git('merge-base', '--is-ancestor', 'origin/main', 'HEAD')

    def test_other_conflicts_are_left_untouched(self):
        self.commit('dev', DEV, 'v3', other='dev\n')
        self.commit('main', RELEASED, 'v3', other='main\n')
        self.git('update-ref', 'refs/remotes/origin/main', 'main')
        self.git('checkout', '-q', 'dev')
        self.git('merge', '--no-ff', '--no-edit', 'origin/main', check=False)
        before = self.git('status', '--porcelain').stdout
        self.assertNotEqual(self.resolve().returncode, 0)
        self.assertEqual(self.git('status', '--porcelain').stdout, before)


class WorkflowTest(unittest.TestCase):
    def test_one_failing_branch_does_not_block_the_others(self):
        text = (ROOT / '.github/workflows/sync-dev-bases.yml').read_text(encoding='utf-8')
        self.assertIn('cp .github/scripts/resolve_release_changelog.py "${RUNNER_TEMP}/"', text)
        self.assertIn('if ! merge_main || ! git push origin "HEAD:${branch}"; then', text)
        self.assertIn('failed+=" ${branch}"', text)
        self.assertIn('if: ${{ !cancelled() }}', text)


if __name__ == '__main__':
    unittest.main()
