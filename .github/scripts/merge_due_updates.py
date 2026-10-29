#!/usr/bin/env python3
"""Merge automated App update pull requests into their development branch.

Bot update PRs (MCPHub upstream, MCPHub OpenAI tunnel-client, Trilium, Calibre
AIO upstreams) are merged into dev-mcphub / dev-trilium / dev-calibre only when
all of the following hold:

* the PR was opened by github-actions[bot] from this repository for a known
  automation branch, carries the expected title and is not labelled "hold";
* its HEAD tree is exactly what the trusted updater on main produces from the
  current development branch (no other file or byte may differ);
* the full App validation passed for that exact HEAD commit;
* the PR has been open for at least DELAY.

A PR that fell behind its base is regenerated from the current base with the
original PR date and validated again. Merging stays fail-closed: anything
unexpected labels the PR "hold" and leaves it for a human.

Invoked only by the trusted main-branch workflow. Never execute this helper
from a pull request checkout in a privileged job.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote

HOUR = 3600
DELAY = 12 * HOUR  # minimum time an update PR stays open before it reaches dev
BOT = "github-actions[bot]"
HOLD = "hold"
SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[1]


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tunnel = load("update_mcphub_tunnel_clients", "update-mcphub-tunnel-clients.py")
trilium = load("update_trilium", "update_trilium.py")


class Kind(NamedTuple):
    name: str
    base: str
    branch: re.Pattern[str]
    workflow: str
    files: tuple[str, ...]

    def title(self, version: str) -> str:
        if self.name == "calibre":
            cwa, shelfmark = version.split(" ")
            return f"chore(calibre-aio): update CWA to {cwa} and Shelfmark to {shelfmark}"
        return {
            "mcphub-upstream": f"chore(mcphub): update upstream to {version}",
            "mcphub-tunnel": tunnel.TITLE,
            "trilium": f"chore: update Trilium to {version}",
        }[self.name]

    def version(self, branch: str) -> str | None:
        match = self.branch.fullmatch(branch)
        if not match:
            return None
        if self.name == "calibre":
            return " ".join(match.groups())  # "<CWA version> <Shelfmark version>"
        return match.group(1).replace("_", ".") if self.name == "mcphub-tunnel" else match.group(1)


MCPHUB_UPSTREAM_FILES = (
    "MCPHub/CHANGELOG.md",
    "MCPHub/Dockerfile",
    "MCPHub/NOTICE.md",
    "MCPHub/build.yaml",
    "MCPHub/config.yaml",
    "MCPHub/ingress.conf",
    "MCPHub/patch_home_assistant_auth.py",
    "MCPHub/run.sh",
)
CALIBRE_FILES = (
    "Calibre AIO/CHANGELOG.md",
    "Calibre AIO/build.yaml",
    "Calibre AIO/config.yaml",
    "Calibre AIO/upstream.json",
)
CALIBRE_VERSION = r"(v?[0-9]+\.[0-9]+\.[0-9]+)"
KINDS = (
    Kind("mcphub-upstream", "dev-mcphub", re.compile(r"automation/mcphub-([0-9]+\.[0-9]+\.[0-9]+)"),
         "validate-mcphub.yml", MCPHUB_UPSTREAM_FILES),
    Kind("mcphub-tunnel", "dev-mcphub", tunnel.BRANCH, "validate-mcphub.yml",
         tuple(sorted(tunnel.ALLOWED_FILES))),
    Kind("trilium", "dev-trilium", re.compile(r"automation/trilium-(v[0-9]+\.[0-9]+\.[0-9]+)"),
         "validate.yml", trilium.UPDATE_FILES),
    Kind("calibre", "dev-calibre",
         re.compile(rf"automation/calibre-aio-cwa-{CALIBRE_VERSION}-shelfmark-{CALIBRE_VERSION}"),
         "validate-calibre-aio.yml", CALIBRE_FILES),
)


class Hold(Exception):
    """The PR needs a human; it is labelled and skipped from now on."""


def run(*arguments: str, cwd: str | None = None, env: dict | None = None) -> str:
    return subprocess.run(
        arguments, check=True, capture_output=True, text=True, cwd=cwd,
        env={**os.environ, **(env or {})},
    ).stdout.strip()


def git(*arguments: str, cwd: str | None = None, env: dict | None = None) -> str:
    return run("git", *arguments, cwd=cwd, env=env)


def gh(*arguments: str) -> str:
    return run("gh", *arguments)


def api(endpoint: str):
    return json.loads(gh("api", endpoint))


def timestamp(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def classify(pr: dict, repository: str) -> tuple[Kind, str] | None:
    """Return the update kind and version of a bot update PR, else None."""
    head = pr.get("head", {})
    if (
        pr.get("user", {}).get("login") != BOT
        or head.get("repo", {}).get("full_name") != repository
    ):
        return None
    for kind in KINDS:
        version = kind.version(head.get("ref", ""))
        if version and pr.get("base", {}).get("ref") == kind.base:
            return kind, version
    return None


def check_identity(pr: dict, kind: Kind, version: str) -> None:
    if pr.get("draft") is not False or pr.get("state") != "open":
        raise Hold("PR is a draft or not open")
    if pr.get("title") != kind.title(version):
        raise Hold(f"Unexpected PR title: {pr.get('title')!r}")
    if not re.fullmatch(r"[0-9a-f]{40}", pr.get("head", {}).get("sha", "")):
        raise Hold("Unrecognized PR HEAD")


def pr_date(pr: dict) -> date:
    """UTC day the updater ran; it determines the generated App version."""
    return datetime.fromtimestamp(timestamp(pr["created_at"]), timezone.utc).date()


def generate(kind: Kind, version: str, today: date, base_sha: str, worktree: str) -> str:
    """Commit the trusted updater's output on top of base_sha; return the commit."""
    git("worktree", "add", "--detach", worktree, base_sha)
    try:
        write_update(kind, version, today, worktree)
    except (ValueError, SystemExit, subprocess.CalledProcessError) as error:
        raise Hold(f"the trusted updater rejected {version}: {error}") from error
    git("add", "--", *kind.files, cwd=worktree)
    if not git("diff", "--cached", "--name-only", cwd=worktree):
        raise Hold(f"{version} is already on {kind.base}")
    identity = {
        "GIT_AUTHOR_NAME": BOT, "GIT_COMMITTER_NAME": BOT,
        "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
        "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
    }
    git("commit", "-q", "-m", kind.title(version), cwd=worktree, env=identity)
    return git("rev-parse", "HEAD", cwd=worktree)


def write_update(kind: Kind, version: str, today: date, worktree: str) -> None:
    if kind.name == "mcphub-upstream":
        # Run main's trusted updater against the worktree (it edits files under ROOT).
        target = Path(worktree, ".github/scripts/_trusted_update_mcphub.py")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SCRIPTS / "update-mcphub-upstream.py", target)
        try:
            run(sys.executable, str(target), "--version", version,
                "--release-url", f"https://github.com/samanhappy/mcphub/releases/tag/v{version}",
                "--date", today.isoformat(), cwd=worktree)
        finally:
            target.unlink()
    elif kind.name == "calibre":
        # Main's trusted updater resolves exactly these releases (commit and
        # archive checksum) again; it rejects downgrades and changed provenance.
        cwa, shelfmark = version.split(" ")
        target = Path(worktree, "Calibre AIO/scripts/_trusted_upstreams.py")
        shutil.copyfile(ROOT / "Calibre AIO/scripts/upstreams.py", target)
        try:
            run(sys.executable, str(target), "update",
                "--cwa-version", cwa, "--shelfmark-version", shelfmark, cwd=worktree)
        finally:
            target.unlink()
    else:
        current = {path: Path(worktree, path).read_text(encoding="utf-8") for path in kind.files}
        if kind.name == "mcphub-tunnel":
            updated, changed = tunnel.prepare(current, version, today)
            updated = updated if changed else None
        else:
            updated = trilium.render(current, version, today)
        if updated is None:
            raise Hold(f"{version} is already on {kind.base}")
        for path, text in updated.items():
            Path(worktree, path).write_text(text, encoding="utf-8", newline="\n")


def validation_state(repository: str, kind: Kind, branch: str, sha: str) -> str:
    runs = api(
        f"repos/{repository}/actions/workflows/{kind.workflow}/runs?"
        f"event=workflow_dispatch&branch={quote(branch, safe='')}&per_page=100"
    ).get("workflow_runs", [])
    matching = [
        r for r in runs
        if r.get("head_sha") == sha
        and r.get("head_branch") == branch
        and r.get("actor", {}).get("login") == BOT
        and r.get("head_repository", {}).get("full_name") == repository
        # Skipped or cancelled runs say nothing about the commit.
        and r.get("conclusion") not in {"skipped", "cancelled"}
    ]
    if not matching:
        return "missing"
    latest = max(matching, key=lambda r: r.get("created_at", ""))
    if latest.get("status") != "completed":
        return "running"
    return "success" if latest.get("conclusion") == "success" else "failed"


def decide(*, behind: bool, tree_matches: bool, ci: str, age: float) -> str:
    """Pure decision for one PR (see module docstring)."""
    if behind:
        return "refresh"
    if not tree_matches:
        return "hold"
    if ci == "failed":
        return "hold"
    if ci == "missing":
        return "validate"
    if ci == "running":
        return "wait"
    return "merge" if age >= DELAY else "wait"


def hold(repository: str, number: int, reason: str) -> None:
    print(f"::warning::PR #{number} put on hold: {reason}")
    gh("label", "create", HOLD, "--repo", repository, "--force",
       "--color", "B60205", "--description", "Stops automated merging and promotion")
    gh("pr", "edit", str(number), "--repo", repository, "--add-label", HOLD)
    gh("pr", "comment", str(number), "--repo", repository, "--body",
       f"Automated merge stopped: {reason}\n\nRemove the `{HOLD}` label after fixing it "
       "to let the automation continue.")


def process(repository: str, pr: dict, kind: Kind, version: str, now: float) -> str:
    number, branch, sha = pr["number"], pr["head"]["ref"], pr["head"]["sha"]
    check_identity(pr, kind, version)
    git("fetch", "--no-tags", "origin",
        f"+refs/heads/{kind.base}:refs/remotes/origin/{kind.base}",
        f"+refs/heads/{branch}:refs/remotes/origin/{branch}")
    if git("rev-parse", f"origin/{branch}") != sha:
        return "wait"  # The branch moved after GitHub listed the PR; re-check next run.
    base_sha = git("rev-parse", f"origin/{kind.base}")
    behind = subprocess.run(["git", "merge-base", "--is-ancestor", base_sha, sha]).returncode != 0

    with tempfile.TemporaryDirectory() as scratch:
        worktree = str(Path(scratch, "wt"))
        try:
            expected = generate(kind, version, pr_date(pr), base_sha, worktree)
            tree_matches = git("rev-parse", f"{expected}^{{tree}}") == git("rev-parse", f"{sha}^{{tree}}")
            ci = validation_state(repository, kind, branch, sha)
            action = decide(
                behind=behind, tree_matches=tree_matches, ci=ci,
                age=now - timestamp(pr["created_at"]),
            )
            if action == "refresh":
                remote = f"https://x-access-token:{os.environ['GH_TOKEN']}@github.com/{repository}.git"
                git("push", f"--force-with-lease=refs/heads/{branch}:{sha}", remote,
                    f"{expected}:refs/heads/{branch}")
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", worktree], capture_output=True)

    if action == "refresh":
        print(f"PR #{number}: regenerated on current {kind.base}; validating again")
        gh("workflow", "run", kind.workflow, "--repo", repository, "--ref", branch)
    elif action == "hold":
        raise Hold(
            f"validation failed for {sha}" if tree_matches
            else "the PR content differs from what the trusted updater produces"
        )
    elif action == "validate":
        gh("workflow", "run", kind.workflow, "--repo", repository, "--ref", branch)
    elif action == "merge":
        # Re-read the PR so a push after listing can never be merged untested.
        latest = api(f"repos/{repository}/pulls/{number}")
        if latest.get("head", {}).get("sha") != sha or any(
            label.get("name") == HOLD for label in latest.get("labels", [])
        ):
            return "wait"
        gh("pr", "merge", str(number), "--repo", repository, "--squash",
           "--delete-branch", "--match-head-commit", sha)
        # GITHUB_TOKEN merges do not start push workflows; request them explicitly.
        gh("workflow", "run", "sync-dev-store.yml", "--repo", repository, "--ref", "main")
        gh("workflow", "run", kind.workflow, "--repo", repository, "--ref", kind.base)
    print(f"PR #{number} ({kind.name} {version}): {action}")
    return action


def main() -> None:
    repository = os.environ["GITHUB_REPOSITORY"]
    now = time.time()
    prs = api(f"repos/{repository}/pulls?state=open&per_page=100")
    merged_bases: set[str] = set()
    errors = 0
    # Oldest first, so the update that has waited longest reaches dev first.
    for pr in sorted(prs, key=lambda item: item.get("created_at", "")):
        found = classify(pr, repository)
        if found is None or any(label.get("name") == HOLD for label in pr.get("labels", [])):
            continue
        kind, version = found
        if kind.base in merged_bases:
            continue  # The base just moved; the next run refreshes this PR.
        try:
            if process(repository, pr, kind, version, now) == "merge":
                merged_bases.add(kind.base)
        except Hold as reason:
            hold(repository, pr["number"], str(reason))
        except (subprocess.CalledProcessError, KeyError, ValueError) as error:
            # Transient GitHub or git failures: report, keep the PR, retry next run.
            errors += 1
            detail = getattr(error, "stderr", "") or error
            print(f"::error::PR #{pr['number']}: {detail}")
    if errors:
        raise SystemExit(f"{errors} update PR(s) could not be processed")


if __name__ == "__main__":
    main()
