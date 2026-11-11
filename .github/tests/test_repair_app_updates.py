"""Guards of the repair workflow and the per-App promotion queues."""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"


class RepairWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = (WORKFLOWS / "repair-app-updates.yml").read_text()
        self.workflow = yaml.safe_load(self.text)

    def test_only_first_failures_of_this_repository_outside_pull_requests(self):
        condition = self.workflow["jobs"]["find"]["if"]
        for guard in ("workflow_run.event != 'pull_request'",
                      "head_repository.full_name == github.repository",
                      "run_attempt == 1"):
            self.assertIn(guard, condition)

    def test_a_hold_set_by_a_person_is_left_alone(self):
        self.assertIn('[[ "${setter}" == "github-actions[bot]" ]] || continue', self.text)

    def test_own_queue_so_merge_due_updates_is_never_dropped(self):
        merge_due = yaml.safe_load((WORKFLOWS / "merge-due-updates.yml").read_text())
        self.assertNotEqual(self.workflow["concurrency"]["group"], merge_due["concurrency"]["group"])

    def test_release_requests_compare_trees_not_the_merge_base(self):
        self.assertIn(".commit.tree.sha", self.text)
        self.assertNotIn("--jq '.files | length'", self.text)

    def test_half_done_releases_cover_only_bot_commits(self):
        self.assertIn('all(\$own[]; .author.login == \\"github-actions[bot]\\")', self.text)

    def test_release_merge_requires_images_validation_and_haos(self):
        for needed in ("docker manifest inspect", "haos-qemu-mcphub.yml", "--match-head-commit",
                       "validate-mcphub.yml"):
            self.assertIn(needed, self.text)

    def test_listed_workflows_exist(self):
        names = {yaml.safe_load(path.read_text())["name"] for path in WORKFLOWS.glob("*.yml")}
        self.assertLessEqual(set(self.workflow[True]["workflow_run"]["workflows"]), names)

    def test_due_releases_go_to_the_release_agent(self):
        for app in ("mcphub", "trilium", "calibre"):
            text = (WORKFLOWS / f"auto-promote-{app}.yml").read_text()
            self.assertIn(f"repair-app-updates.yml --repo \"$GITHUB_REPOSITORY\" --ref main -f app={app}", text)
            # The built-in merge only runs while the agent is switched off.
            gated = [line for line in text.splitlines() if "== 'promote'" in line]
            self.assertTrue(gated)
            self.assertTrue(all("vars.APP_REPAIR" in line for line in gated))
        self.assertIn('report+="Release due: ${RELEASE_APP}', self.text)

    def test_each_app_has_its_own_promotion_queue(self):
        groups = [yaml.safe_load(path.read_text())["concurrency"]["group"]
                  for path in WORKFLOWS.glob("auto-promote-*.yml")]
        self.assertEqual(len(groups), len(set(groups)))


if __name__ == "__main__":
    unittest.main()
