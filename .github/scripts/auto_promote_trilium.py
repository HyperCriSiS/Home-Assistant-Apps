#!/usr/bin/env python3
"""Fail-closed gates for promoting bot-only Trilium updates from dev-trilium to main.

Only Trilium version bumps produced by the trusted Update Trilium workflow may
be promoted automatically, 48 hours after the newest one reached dev-trilium.
Anything else on dev-trilium keeps the manual release pull request flow.

Invoked only by the trusted main-branch workflow. Never execute this helper
from a pull request checkout in a privileged job.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

spec = importlib.util.spec_from_file_location(
    "auto_promote_mcphub", Path(__file__).resolve().parent / "auto_promote_mcphub.py"
)
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
Skip, api, ci_state, gh, git, show, wait_for = (
    shared.Skip, shared.api, shared.ci_state, shared.gh, shared.git, shared.show, shared.wait_for
)

DEV, MAIN, APP = "dev-trilium", "main", "TriliumNext Notes"
HOUR = 3600
RELEASE_AGE = 48 * HOUR  # minimum age of a new Trilium release
SOAK = 48 * HOUR  # newest update must have been on dev-trilium this long
WORKFLOW = "validate.yml"
TITLE = "release(trilium): automated update release"
ALLOWED_FILES = frozenset({
    f"{APP}/CHANGELOG.md",
    f"{APP}/Dockerfile",
    f"{APP}/README.md",
    f"{APP}/config.yaml",
})
UPDATE_TITLES = (re.compile(r"chore: update Trilium to v[0-9]+\.[0-9]+\.[0-9]+"),)
SYNC_SUBJECT = f"Merge remote-tracking branch 'origin/{MAIN}' into {DEV}"
UPSTREAM_PIN = re.compile(r"^FROM docker\.io/triliumnext/trilium:(v[0-9]+\.[0-9]+\.[0-9]+)$", re.M)
WRAPPER_VERSION = re.compile(r'^version: "(v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(?:\.[1-9][0-9]*)?)"$', re.M)
CHANGELOG_HEADER = "# Changelog\n\n"
CHANGELOG_LINES = (
    re.compile(r""),
    re.compile(r"## v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(?:\.[1-9][0-9]*)?"),
    re.compile(r"### Changed"),
    re.compile(r"- Updated Trilium from v[0-9]+\.[0-9]+\.[0-9]+ to v[0-9]+\.[0-9]+\.[0-9]+\."),
)


def as_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.removeprefix("v").split("."))


def versions(files: dict[str, str]) -> dict[str, str]:
    return {
        "upstream": shared.single(UPSTREAM_PIN, files[f"{APP}/Dockerfile"], "Trilium version"),
        "wrapper": shared.single(WRAPPER_VERSION, files[f"{APP}/config.yaml"], "App version"),
    }


def check_content(stable: dict[str, str], candidate: dict[str, str]) -> tuple[str, str]:
    """Accept only a pure Trilium version bump plus generated changelog notes."""
    old, new = versions(stable), versions(candidate)
    if as_tuple(new["upstream"]) <= as_tuple(old["upstream"]):
        raise ValueError("Trilium version must increase")
    if as_tuple(new["wrapper"]) <= as_tuple(old["wrapper"]):
        raise ValueError("App version must increase")
    if as_tuple(new["upstream"])[0] != as_tuple(old["upstream"])[0]:
        raise Skip(f"Major Trilium update {old['upstream']} -> {new['upstream']} needs a manual release")

    for path in sorted(ALLOWED_FILES - {f"{APP}/CHANGELOG.md"}):
        expected = stable[path]
        for key in ("upstream", "wrapper"):
            expected = expected.replace(old[key], new[key])
        if expected != candidate[path]:
            raise ValueError(f"{path} changes more than the pinned versions")

    before, after = stable[f"{APP}/CHANGELOG.md"], candidate[f"{APP}/CHANGELOG.md"]
    if not (before.startswith(CHANGELOG_HEADER) and after.startswith(CHANGELOG_HEADER)):
        raise ValueError("Unexpected Trilium changelog header")
    previous = before[len(CHANGELOG_HEADER):]
    if not after.endswith(previous):
        raise ValueError("Changelog history was modified")
    added = after[len(CHANGELOG_HEADER):len(after) - len(previous)]
    if not added.startswith(f"## {new['wrapper']}\n") or any(
        not any(pattern.fullmatch(line) for pattern in CHANGELOG_LINES)
        for line in added.splitlines()
    ):
        raise ValueError("Changelog contains notes beyond the generated update lines")
    return old["upstream"], new["upstream"]


def release_pr(repository: str, dev_sha: str) -> dict | None:
    prs = api(f"repos/{repository}/pulls?state=open&base={MAIN}&per_page=100")
    matching = [pr for pr in prs if pr.get("head", {}).get("ref") == DEV
                and pr.get("head", {}).get("repo", {}).get("full_name") == repository]
    if len(matching) > 1:
        raise ValueError("More than one open Trilium release pull request")
    if not matching:
        return None
    pr = matching[0]
    if any(label.get("name") == "hold" for label in pr.get("labels", [])):
        raise Skip("The Trilium release pull request is labelled 'hold'")
    if pr.get("draft") is not False:
        raise Skip("The Trilium release pull request is a draft")
    if pr.get("head", {}).get("sha") != dev_sha:
        raise Skip("The Trilium release pull request does not point at the gated commit yet")
    return pr


def gate(repository: str, now: float, haos_required: bool) -> dict[str, str]:
    """Decide what the scheduled run does next. Raises Skip when nothing is due."""
    git("fetch", "--no-tags", "origin", MAIN, DEV)
    main_sha, dev_sha = git("rev-parse", f"origin/{MAIN}"), git("rev-parse", f"origin/{DEV}")
    changed = set(git("diff", "--name-only", main_sha, dev_sha).splitlines())
    if not changed:
        raise Skip("dev-trilium has nothing to release")
    if not changed <= ALLOWED_FILES:
        raise Skip("dev-trilium contains changes beyond automated updates; release manually")
    newest = shared.check_history(
        repository, main_sha, dev_sha,
        sync_subject=SYNC_SUBJECT, allowed=ALLOWED_FILES, titles=UPDATE_TITLES, dev=DEV,
    )

    stable = {path: show(main_sha, path) for path in ALLOWED_FILES}
    candidate = {path: show(dev_sha, path) for path in ALLOWED_FILES}
    _, upstream = check_content(stable, candidate)
    shared.check_release(
        api(f"repos/TriliumNext/Trilium/releases/tags/{quote(upstream, safe='')}"),
        now, "Trilium release",
    )
    if now - newest < SOAK:
        raise Skip(f"Newest update has been on dev-trilium for less than {SOAK // HOUR} hours")

    result = {"main_sha": main_sha, "dev_sha": dev_sha, "upstream": upstream, "action": "promote"}
    validation = ci_state(repository, WORKFLOW, shared.validated(dev_sha, DEV))
    if validation == "failed":
        raise ValueError(f"Trilium validation failed for {dev_sha}")
    if validation != "success":
        result["action"] = "validate" if validation == "missing" else "wait"
        return result
    if haos_required:
        # haos-integration.yml tests the dev-trilium branch tip, not an exact commit,
        # so it cannot prove what would be released: keep that path manual.
        raise Skip("The optional HAOS gate is enabled; release Trilium manually")
    return result


def merge(repository: str, main_sha: str, dev_sha: str, upstream: str) -> str:
    # Everything that was gated must still be exactly what will be merged.
    git("fetch", "--no-tags", "origin", MAIN, DEV)
    if git("rev-parse", f"origin/{MAIN}") != main_sha or git("rev-parse", f"origin/{DEV}") != dev_sha:
        raise Skip("main or dev-trilium moved since the gate; the next run re-checks")
    pr = release_pr(repository, dev_sha)
    if pr is None:
        url = gh("pr", "create", "--repo", repository, "--base", MAIN, "--head", DEV,
                 "--title", TITLE, "--body",
                 f"Bot-only Trilium update to {upstream}, merged automatically 48 hours after it "
                 "reached dev-trilium once all gates pass. Label: hold stops it.")
        pr = api(f"repos/{repository}/pulls/{url.rstrip('/').rsplit('/', 1)[-1]}")
        if pr.get("head", {}).get("sha") != dev_sha:
            raise Skip("dev-trilium moved while opening the release pull request")
    number = pr["number"]
    # main only accepts squash merges; the shared release baseline relies on that.
    gh("pr", "merge", str(number), "--repo", repository, "--squash",
       "--match-head-commit", dev_sha,
       "--subject", f"release(trilium): update Trilium to {upstream} (#{number})")
    merged = api(f"repos/{repository}/pulls/{number}")
    if merged.get("merged") is not True:
        raise ValueError("Release pull request was not merged")
    return merged["merge_commit_sha"]


def watch(repository: str, merge_sha: str) -> None:
    """Report a failing stable build and prepare (never merge) a revert."""
    try:
        wait_for(repository, WORKFLOW, shared.validated(merge_sha, MAIN), "Stable validation")
        return
    except (ValueError, TimeoutError) as error:
        reason = str(error)
    branch = f"revert/trilium-{merge_sha[:12]}"
    git("switch", "-c", branch, merge_sha)
    git("revert", "--no-edit", merge_sha)
    git("push", f"https://x-access-token:{os.environ['GH_TOKEN']}@github.com/{repository}.git",
        f"HEAD:refs/heads/{branch}")
    body = (f"Automatic Trilium promotion {merge_sha} failed post-merge validation: {reason}.\n\n"
            "This revert is not merged automatically. Set TRILIUM_AUTO_PROMOTE=false to pause.")
    gh("pr", "create", "--repo", repository, "--base", MAIN, "--head", branch,
       "--title", "revert(trilium): failed automatic promotion", "--body", body)
    gh("issue", "create", "--repo", repository,
       "--title", "Trilium automatic promotion failed after merge", "--body", body)
    raise SystemExit(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("gate", "merge", "watch"))
    parser.add_argument("--main-sha")
    parser.add_argument("--dev-sha")
    parser.add_argument("--upstream")
    parser.add_argument("--merge-sha")
    args = parser.parse_args()
    repository = os.environ["GITHUB_REPOSITORY"]
    output = Path(os.environ.get("GITHUB_OUTPUT", os.devnull))
    if args.mode == "gate":
        try:
            result = gate(repository, time.time(), os.environ.get("HAOS_E2E_ENABLED") == "true")
        except Skip as reason:
            print(f"Not promoting: {reason}")
            result = {"action": "skip"}
        print(json.dumps(result))
        with output.open("a", encoding="utf-8") as handle:
            handle.writelines(f"{key}={value}\n" for key, value in result.items())
    elif args.mode == "merge":
        try:
            merge_sha = merge(repository, args.main_sha, args.dev_sha, args.upstream)
        except Skip as reason:
            print(f"Not promoting: {reason}")
            return
        with output.open("a", encoding="utf-8") as handle:
            handle.write(f"merge_sha={merge_sha}\n")
    else:
        watch(repository, args.merge_sha)


if __name__ == "__main__":
    main()
