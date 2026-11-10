"""A squashed release must not leave a development branch unable to take main."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.github/scripts/resolve_release_changelog.py'

BASE = '# Changelog\n\n## v1\n\n- First.\n'
DEV = '# Changelog\n\n## v3\n\n- Third.\n\n## v2\n\n- Second,\n  wrapped.\n\n## v1\n\n- First.\n'
RELEASED = '# Changelog\n\n## v3\n\n- Second, wrapped.\n- Third.\n\n## v1\n\n- First.\n'


class MergeTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.repo = Path(directory.name)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        self.git('commit', '-q', '--allow-empty', '-m', 'root')
        self.commit('main', BASE, 'v1')
        self.git('branch', 'dev')
        self.commit('dev', DEV, 'v3')

    def git(self, *args, check=True):
        return subprocess.run(
            ['git', *args], cwd=self.repo, check=check, capture_output=True, text=True)

    def commit(self, branch, changelog, version, files=None):
        self.git('checkout', '-q', branch)
        files = {'My App/CHANGELOG.md': changelog, 'My App/config.yaml': f'version: "{version}"\n',
                 **(files or {})}
        for name, text in files.items():
            path = self.repo / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(text, encoding='utf-8', newline='\n')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', f'{branch} {version}')

    def merge_and_resolve(self):
        self.git('update-ref', 'refs/remotes/origin/main', 'main')
        self.git('checkout', '-q', 'dev')
        self.assertNotEqual(self.git('merge', '--no-ff', '--no-edit', 'origin/main', check=False).returncode, 0)
        before = self.git('status', '--porcelain').stdout
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=self.repo, capture_output=True, text=True,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        return result.returncode, before == self.git('status', '--porcelain').stdout

    def test_released_changelog_wins_and_the_merge_can_be_committed(self):
        self.commit('main', RELEASED, 'v3')
        self.assertEqual(self.merge_and_resolve(), (0, False))
        self.git('commit', '--no-edit')
        self.assertEqual((self.repo / 'My App/CHANGELOG.md').read_bytes(), RELEASED.encode())
        self.git('merge-base', '--is-ancestor', 'origin/main', 'HEAD')

    def test_unreleased_app_change_is_left_for_a_human(self):
        self.commit('dev', DEV.replace('- Third.', '- Third.\n- Unreleased fix.'), 'v3',
                    {'My App/run.sh': 'fix\n'})
        self.commit('main', RELEASED, 'v3')
        self.assertEqual(self.merge_and_resolve(), (1, True))

    def test_other_conflicts_are_left_untouched(self):
        self.commit('dev', DEV, 'v3', {'other.txt': 'dev\n'})
        self.commit('main', RELEASED, 'v3', {'other.txt': 'main\n'})
        self.assertEqual(self.merge_and_resolve(), (1, True))


class WorkflowTest(unittest.TestCase):
    def test_one_failing_branch_does_not_block_the_others(self):
        text = (ROOT / '.github/workflows/sync-dev-bases.yml').read_text(encoding='utf-8')
        self.assertIn('cp .github/scripts/resolve_release_changelog.py "${RUNNER_TEMP}/"', text)
        self.assertIn('if ! merge_main || ! git push origin "HEAD:${branch}"; then', text)
        self.assertIn('failed+=" ${branch}"', text)
        self.assertIn('if: ${{ !cancelled() }}', text)


if __name__ == '__main__':
    unittest.main()
