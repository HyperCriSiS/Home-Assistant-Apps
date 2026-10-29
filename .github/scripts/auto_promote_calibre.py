#!/usr/bin/env python3
"""Fail-closed gates for promoting bot-only Calibre AIO updates from dev-calibre to main.

Only CWA/Shelfmark pin updates produced by the trusted Calibre AIO updater may
be promoted automatically, 48 hours after the newest one reached dev-calibre.
Anything else on dev-calibre keeps the manual release pull request flow.

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

SCRIPTS = Path(__file__).resolve().parent


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


shared = load("auto_promote_mcphub", SCRIPTS / "auto_promote_mcphub.py")
upstreams = load("calibre_aio_upstreams", SCRIPTS.parents[1] / "Calibre AIO/scripts/upstreams.py")
Skip, api, ci_state, gh, git, show, wait_for = (
    shared.Skip, shared.api, shared.ci_state, shared.gh, shared.git, shared.show, shared.wait_for
)

DEV, MAIN, APP = "dev-calibre", "main", "Calibre AIO"
HOUR = 3600
SOAK = 48 * HOUR  # newest update must have been on dev-calibre this long
WORKFLOW = "validate-calibre-aio.yml"
TITLE = "release(calibre): automated update release"
COMPONENTS = {"cwa": "CWA", "shelfmark": "Shelfmark"}
ALLOWED_FILES = frozenset({
    f"{APP}/CHANGELOG.md",
    f"{APP}/build.yaml",
    f"{APP}/config.yaml",
    f"{APP}/upstream.json",
})
VERSION = r"v?[0-9]+\.[0-9]+\.[0-9]+"
UPDATE_TITLES = (
    re.compile(rf"chore\(calibre-aio\): update CWA to {VERSION} and Shelfmark to {VERSION}"),
)
SYNC_SUBJECT = f"Merge remote-tracking branch 'origin/{MAIN}' into {DEV}"
WRAPPER_VERSION = re.compile(r'^version: "([0-9]+\.[0-9]+\.[0-9]+)"$', re.M)
CHANGELOG_LINES = (
    re.compile(r""),
    re.compile(r"# [0-9]+\.[0-9]+\.[0-9]+"),
    re.compile(rf"- Update CWA to {VERSION} and Shelfmark to {VERSION}\."),
)


def as_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.removeprefix("v").split("."))


def manifest(text: str) -> dict:
    data = json.loads(text)
    for name, repository in upstreams.REPOSITORIES.items():
        item = data[name]
        if (set(item) != {"repository", "version", "commit", "sha256"}
                or item["repository"] != repository
                or not re.fullmatch(r"[0-9a-f]{40}", item["commit"])
                or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
                or not re.fullmatch(VERSION, item["version"])):
            raise ValueError(f"Invalid upstream pin: {name}")
    return data


def check_content(stable: dict[str, str], candidate: dict[str, str]) -> dict[str, tuple[str, str]]:
    """Accept only CWA/Shelfmark pin bumps, their generated build file and changelog notes."""
    old, new = manifest(stable[f"{APP}/upstream.json"]), manifest(candidate[f"{APP}/upstream.json"])
    if {k: v for k, v in old.items() if k not in COMPONENTS} != \
            {k: v for k, v in new.items() if k not in COMPONENTS}:
        raise ValueError("upstream.json changes more than the CWA and Shelfmark pins")
    bumps = {}
    for name, label in COMPONENTS.items():
        before, after = old[name]["version"], new[name]["version"]
        if before == after:
            if old[name] != new[name]:
                raise ValueError(f"{label} provenance changed without a new version")
            continue
        if as_tuple(after) < as_tuple(before):
            raise ValueError(f"Refusing a {label} downgrade")
        if as_tuple(after)[0] != as_tuple(before)[0]:
            raise Skip(f"Major {label} update {before} -> {after} needs a manual release")
        bumps[name] = (before, after)
    if not bumps:
        raise ValueError("No CWA or Shelfmark version increased")

    if candidate[f"{APP}/build.yaml"] != upstreams.render(new):
        raise ValueError("build.yaml is not generated from upstream.json")

    old_app = shared.single(WRAPPER_VERSION, stable[f"{APP}/config.yaml"], "App version")
    new_app = shared.single(WRAPPER_VERSION, candidate[f"{APP}/config.yaml"], "App version")
    if as_tuple(new_app) <= as_tuple(old_app):
        raise ValueError("App version must increase")
    expected = stable[f"{APP}/config.yaml"].replace(f'version: "{old_app}"', f'version: "{new_app}"', 1)
    if expected != candidate[f"{APP}/config.yaml"]:
        raise ValueError(f"{APP}/config.yaml changes more than the App version")

    before, after = stable[f"{APP}/CHANGELOG.md"], candidate[f"{APP}/CHANGELOG.md"]
    if not after.endswith(before):
        raise ValueError("Changelog history was modified")
    added = after[:len(after) - len(before)]
    if not added.startswith(f"# {new_app}\n") or any(
        not any(pattern.fullmatch(line) for pattern in CHANGELOG_LINES)
        for line in added.splitlines()
    ):
        raise ValueError("Changelog contains notes beyond the generated update lines")
    return bumps


def summary(bumps: dict[str, tuple[str, str]]) -> str:
    return " and ".join(f"{COMPONENTS[name]} to {new}" for name, (_, new) in bumps.items())


def release_pr(repository: str, dev_sha: str) -> dict | None:
    prs = api(f"repos/{repository}/pulls?state=open&base={MAIN}&per_page=100")
    matching = [pr for pr in prs if pr.get("head", {}).get("ref") == DEV
                and pr.get("head", {}).get("repo", {}).get("full_name") == repository]
    if len(matching) > 1:
        raise ValueError("More than one open Calibre AIO release pull request")
    if not matching:
        return None
    pr = matching[0]
    if any(label.get("name") == "hold" for label in pr.get("labels", [])):
        raise Skip("The Calibre AIO release pull request is labelled 'hold'")
    if pr.get("draft") is not False:
        raise Skip("The Calibre AIO release pull request is a draft")
    if pr.get("head", {}).get("sha") != dev_sha:
        raise Skip("The Calibre AIO release pull request does not point at the gated commit yet")
    return pr


def gate(repository: str, now: float) -> dict[str, str]:
    """Decide what the scheduled run does next. Raises Skip when nothing is due."""
    git("fetch", "--no-tags", "origin", MAIN, DEV)
    main_sha, dev_sha = git("rev-parse", f"origin/{MAIN}"), git("rev-parse", f"origin/{DEV}")
    changed = set(git("diff", "--name-only", main_sha, dev_sha).splitlines())
    if not changed:
        raise Skip("dev-calibre has nothing to release")
    if not changed <= ALLOWED_FILES:
        raise Skip("dev-calibre contains changes beyond automated updates; release manually")
    newest = shared.check_history(
        repository, main_sha, dev_sha,
        sync_subject=SYNC_SUBJECT, allowed=ALLOWED_FILES, titles=UPDATE_TITLES, dev=DEV,
    )

    stable = {path: show(main_sha, path) for path in ALLOWED_FILES}
    candidate = {path: show(dev_sha, path) for path in ALLOWED_FILES}
    bumps = check_content(stable, candidate)
    for name, (_, version) in bumps.items():
        shared.check_release(
            api(f"repos/{upstreams.REPOSITORIES[name]}/releases/tags/{quote(version, safe='')}"),
            now, f"{COMPONENTS[name]} release",
        )
    if now - newest < SOAK:
        raise Skip(f"Newest update has been on dev-calibre for less than {SOAK // HOUR} hours")

    result = {"main_sha": main_sha, "dev_sha": dev_sha, "summary": summary(bumps), "action": "promote"}
    validation = ci_state(repository, WORKFLOW, shared.validated(dev_sha, DEV))
    if validation == "failed":
        raise ValueError(f"Calibre AIO validation failed for {dev_sha}")
    if validation != "success":
        result["action"] = "validate" if validation == "missing" else "wait"
    return result


def merge(repository: str, main_sha: str, dev_sha: str, update: str) -> str:
    # Everything that was gated must still be exactly what will be merged.
    git("fetch", "--no-tags", "origin", MAIN, DEV)
    if git("rev-parse", f"origin/{MAIN}") != main_sha or git("rev-parse", f"origin/{DEV}") != dev_sha:
        raise Skip("main or dev-calibre moved since the gate; the next run re-checks")
    pr = release_pr(repository, dev_sha)
    if pr is None:
        url = gh("pr", "create", "--repo", repository, "--base", MAIN, "--head", DEV,
                 "--title", TITLE, "--body",
                 f"Bot-only Calibre AIO update ({update}), merged automatically 48 hours after it "
                 "reached dev-calibre once all gates pass. Label: hold stops it.")
        pr = api(f"repos/{repository}/pulls/{url.rstrip('/').rsplit('/', 1)[-1]}")
        if pr.get("head", {}).get("sha") != dev_sha:
            raise Skip("dev-calibre moved while opening the release pull request")
    number = pr["number"]
    # main only accepts squash merges; the shared release baseline relies on that.
    gh("pr", "merge", str(number), "--repo", repository, "--squash",
       "--match-head-commit", dev_sha,
       "--subject", f"release(calibre): update {update} (#{number})")
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
    branch = f"revert/calibre-{merge_sha[:12]}"
    git("switch", "-c", branch, merge_sha)
    git("revert", "--no-edit", merge_sha)
    git("push", f"https://x-access-token:{os.environ['GH_TOKEN']}@github.com/{repository}.git",
        f"HEAD:refs/heads/{branch}")
    body = (f"Automatic Calibre AIO promotion {merge_sha} failed post-merge validation: {reason}.\n\n"
            "This revert is not merged automatically. Set CALIBRE_AUTO_PROMOTE=false to pause.")
    gh("pr", "create", "--repo", repository, "--base", MAIN, "--head", branch,
       "--title", "revert(calibre): failed automatic promotion", "--body", body)
    gh("issue", "create", "--repo", repository,
       "--title", "Calibre AIO automatic promotion failed after merge", "--body", body)
    raise SystemExit(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("gate", "merge", "watch"))
    parser.add_argument("--main-sha")
    parser.add_argument("--dev-sha")
    parser.add_argument("--summary")
    parser.add_argument("--merge-sha")
    args = parser.parse_args()
    repository = os.environ["GITHUB_REPOSITORY"]
    output = Path(os.environ.get("GITHUB_OUTPUT", os.devnull))
    if args.mode == "gate":
        try:
            result = gate(repository, time.time())
        except Skip as reason:
            print(f"Not promoting: {reason}")
            result = {"action": "skip"}
        print(json.dumps(result))
        with output.open("a", encoding="utf-8") as handle:
            handle.writelines(f"{key}={value}\n" for key, value in result.items())
    elif args.mode == "merge":
        try:
            merge_sha = merge(repository, args.main_sha, args.dev_sha, args.summary)
        except Skip as reason:
            print(f"Not promoting: {reason}")
            return
        with output.open("a", encoding="utf-8") as handle:
            handle.write(f"merge_sha={merge_sha}\n")
    else:
        watch(repository, args.merge_sha)


if __name__ == "__main__":
    main()
