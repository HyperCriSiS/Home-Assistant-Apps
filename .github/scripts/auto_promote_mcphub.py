#!/usr/bin/env python3
"""Fail-closed gates for promoting bot-only MCPHub updates from dev-mcphub to main.

Only MCPHub upstream and OpenAI tunnel-client version bumps made by the trusted
update workflows may be promoted automatically. Anything else on dev-mcphub
keeps the manual release pull request flow.

Invoked only by the trusted main-branch workflow. Never execute this helper
from a pull request checkout in a privileged job.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

DEV, MAIN, RELEASE = "dev-mcphub", "main", "release/mcphub-candidate"
BOT = "github-actions[bot]"
HOUR = 3600
RELEASE_AGE = 48 * HOUR  # minimum age of a new upstream or tunnel-client release
SOAK = 48 * HOUR  # newest update must have been on the development store this long
COOLDOWN = 24 * HOUR  # minimum distance to the previous stable MCPHub release
ALLOWED_FILES = frozenset({
    "MCPHub/CHANGELOG.md",
    "MCPHub/Dockerfile",
    "MCPHub/NOTICE.md",
    "MCPHub/build.yaml",
    "MCPHub/config.yaml",
    "MCPHub/ingress.conf",
    "MCPHub/patch_home_assistant_auth.py",
    "MCPHub/run.sh",
})
UPDATE_TITLES = (
    re.compile(r"chore\(mcphub\): update upstream to [0-9]+\.[0-9]+\.[0-9]+"),
    re.compile(r"chore\(mcphub\): update OpenAI tunnel client"),
)
SQUASH_SUBJECT = re.compile(r"(?P<title>.+) \(#(?P<number>[0-9]+)\)")
SYNC_SUBJECT = f"Merge remote-tracking branch 'origin/{MAIN}' into {DEV}"
UPSTREAM_PIN = re.compile(r"samanhappy/mcphub:([0-9]+\.[0-9]+\.[0-9]+)")
TUNNEL_PIN = re.compile(r"^ARG OPENAI_TUNNEL_VERSION=(v[0-9]+\.[0-9]+\.[0-9]+)$", re.M)
WRAPPER_VERSION = re.compile(
    r'^version: "(v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(?:-[1-9][0-9]*)?)"$', re.M
)
CHANGELOG_HEADER = "# Changelog\n\n"
CHANGELOG_LINES = (
    re.compile(r""),
    re.compile(r"## v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(?:-[1-9][0-9]*)?"),
    re.compile(r"### Changed"),
    re.compile(r"- Updated MCPHub from [0-9]+\.[0-9]+\.[0-9]+ to [0-9]+\.[0-9]+\.[0-9]+\."),
    re.compile(r"- Updated bundled OpenAI tunnel-client v[0-9.]+ to v[0-9.]+\."),
)


class Skip(Exception):
    """Not (yet) eligible; the manual release flow remains available."""


def run(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, check=check, capture_output=True, text=True)


def git(*arguments: str) -> str:
    return run("git", *arguments).stdout.strip()


def gh(*arguments: str) -> str:
    return run("gh", *arguments).stdout.strip()


def api(endpoint: str):
    return json.loads(gh("api", endpoint))


def show(sha: str, path: str) -> str:
    return run("git", "show", f"{sha}:{path}").stdout


def timestamp(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def single(pattern: re.Pattern[str], text: str, label: str) -> str:
    found = set(pattern.findall(text))
    if len(found) != 1:
        raise ValueError(f"Cannot determine {label}: {sorted(found)}")
    return found.pop()


def as_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.removeprefix("v").split("."))


def versions(files: dict[str, str]) -> dict[str, str]:
    return {
        "upstream": single(UPSTREAM_PIN, files["MCPHub/build.yaml"], "MCPHub version"),
        "tunnel": single(TUNNEL_PIN, files["MCPHub/Dockerfile"], "tunnel-client version"),
        "wrapper": single(WRAPPER_VERSION, files["MCPHub/config.yaml"], "App version"),
    }


def check_content(stable: dict[str, str], candidate: dict[str, str]) -> dict[str, tuple[str, str]]:
    """Accept only pure version bumps plus generated changelog notes."""
    old, new = versions(stable), versions(candidate)
    if as_tuple(new["upstream"]) < as_tuple(old["upstream"]) or \
            as_tuple(new["tunnel"]) < as_tuple(old["tunnel"]):
        raise ValueError("Refusing a version downgrade")
    if as_tuple(new["wrapper"].split("-")[0]) < as_tuple(old["wrapper"].split("-")[0]) or \
            new["wrapper"] == old["wrapper"]:
        raise ValueError("App version must increase")
    for name in ("upstream", "tunnel"):
        if as_tuple(new[name])[0] != as_tuple(old[name])[0]:
            raise Skip(f"Major {name} update {old[name]} -> {new[name]} needs a manual release")

    for path in sorted(ALLOWED_FILES - {"MCPHub/CHANGELOG.md"}):
        expected = stable[path]
        for key in ("upstream", "tunnel", "wrapper"):
            if old[key] != new[key]:
                expected = expected.replace(old[key], new[key])
        if expected != candidate[path]:
            raise ValueError(f"{path} changes more than the pinned versions")

    before, after = stable["MCPHub/CHANGELOG.md"], candidate["MCPHub/CHANGELOG.md"]
    if not (before.startswith(CHANGELOG_HEADER) and after.startswith(CHANGELOG_HEADER)):
        raise ValueError("Unexpected MCPHub changelog header")
    previous = before[len(CHANGELOG_HEADER):]
    if not after.endswith(previous):
        raise ValueError("Changelog history was modified")
    added = after[len(CHANGELOG_HEADER):len(after) - len(previous)]
    if not added.startswith(f"## {new['wrapper']}\n") or any(
        not any(pattern.fullmatch(line) for pattern in CHANGELOG_LINES)
        for line in added.splitlines()
    ):
        raise ValueError("Changelog contains notes beyond the generated update lines")
    return {key: (old[key], new[key]) for key in ("upstream", "tunnel") if old[key] != new[key]}


def check_release(release: dict, now: float, label: str) -> None:
    if release.get("draft") is not False or release.get("prerelease") is not False:
        raise ValueError(f"{label} is not a published stable release")
    published = release.get("published_at")
    if not published or now - timestamp(published) < RELEASE_AGE:
        raise Skip(f"{label} was published less than {RELEASE_AGE // HOUR} hours ago")


def check_squash(commit: dict, pr: dict, repository: str, sha: str, subject: str) -> None:
    """A dev-mcphub commit must be GitHub's own squash merge of a bot update PR."""
    match = SQUASH_SUBJECT.fullmatch(subject)
    if not match or not any(t.fullmatch(match["title"]) for t in UPDATE_TITLES):
        raise Skip(f"{sha[:7]} is not an automated update: {subject}")
    if not (
        commit.get("commit", {}).get("verification", {}).get("verified") is True
        and commit.get("committer", {}).get("login") == "web-flow"
    ):
        raise ValueError(f"{sha[:7]} is not a GitHub-signed merge commit")
    if not (
        pr.get("number") == int(match["number"])
        and pr.get("merged") is True
        and pr.get("merge_commit_sha") == sha
        and pr.get("title") == match["title"]
        and pr.get("user", {}).get("login") == BOT
        and pr.get("base", {}).get("ref") == DEV
        and pr.get("head", {}).get("repo", {}).get("full_name") == repository
    ):
        raise ValueError(f"{sha[:7]} does not belong to a merged bot update PR")


def check_history(repository: str, main_sha: str, dev_sha: str) -> float:
    """Validate every dev-only commit; return the newest update's commit time."""
    git("merge-base", "--is-ancestor", main_sha, dev_sha)
    log = git("log", "--format=%H%x1f%P%x1f%ct%x1f%s", f"{main_sha}..{dev_sha}")
    newest = None
    for line in filter(None, log.splitlines()):
        sha, parents, committed, subject = line.split("\x1f", 3)
        parents = parents.split()
        if len(parents) == 2:
            # Only clean, unedited merges of stable main are allowed.
            if subject != SYNC_SUBJECT:
                raise Skip(f"{sha[:7]} is not an automatic main sync: {subject}")
            git("merge-base", "--is-ancestor", parents[1], main_sha)
            merged = run("git", "merge-tree", "--write-tree", *parents, check=False)
            if merged.returncode or merged.stdout.split()[0] != git("rev-parse", f"{sha}^{{tree}}"):
                raise ValueError(f"{sha[:7]} is not a clean merge of main")
            continue
        if len(parents) != 1:
            raise ValueError(f"{sha[:7]} has an unexpected parent count")
        changed = set(git("diff-tree", "--no-commit-id", "--name-only", "-r", sha).splitlines())
        if not changed <= ALLOWED_FILES:
            raise Skip(f"{sha[:7]} changes files outside the update set")
        match = SQUASH_SUBJECT.fullmatch(subject)
        number = match["number"] if match else "0"
        pr = api(f"repos/{repository}/pulls/{number}") if match else {}
        check_squash(api(f"repos/{repository}/commits/{sha}"), pr, repository, sha, subject)
        newest = max(newest or 0, float(committed))
    if newest is None:
        raise Skip("No automated MCPHub update is waiting on dev-mcphub")
    return newest


def latest_run(repository: str, workflow: str, predicate) -> dict | None:
    runs = api(
        f"repos/{repository}/actions/workflows/{workflow}/runs?per_page=100"
    ).get("workflow_runs", [])
    # Skipped or cancelled runs say nothing about the commit; they never count.
    matching = [
        r for r in runs
        if predicate(r) and r.get("conclusion") not in {"skipped", "cancelled"}
    ]
    return max(matching, key=lambda r: r.get("created_at", ""), default=None)


def ci_state(repository: str, workflow: str, predicate) -> str:
    selected = latest_run(repository, workflow, predicate)
    if selected is None:
        return "missing"
    if selected.get("status") != "completed":
        return "running"
    return "success" if selected.get("conclusion") == "success" else "failed"


def validated(sha: str, branch: str):
    return lambda r: (
        r.get("head_sha") == sha and r.get("head_branch") == branch
        and r.get("head_repository", {}).get("full_name") == os.environ.get("GITHUB_REPOSITORY")
    )


def haos_title(sha: str) -> str:
    return f"HAOS MCPHub integration {sha}"


def gate(repository: str, now: float) -> dict[str, str]:
    """Decide what the scheduled run does next. Raises Skip when nothing is due."""
    git("fetch", "--no-tags", "origin", MAIN, DEV)
    main_sha, dev_sha = git("rev-parse", f"origin/{MAIN}"), git("rev-parse", f"origin/{DEV}")
    held = api(f"repos/{repository}/pulls?state=open&base={MAIN}&per_page=100")
    if any(
        pr.get("head", {}).get("ref") == RELEASE
        and any(label.get("name") == "hold" for label in pr.get("labels", []))
        for pr in held
    ):
        raise Skip("The MCPHub release pull request is labelled 'hold'")

    changed = set(git("diff", "--name-only", main_sha, dev_sha).splitlines())
    if not changed:
        raise Skip("dev-mcphub has nothing to release")
    if not changed <= ALLOWED_FILES:
        raise Skip("dev-mcphub contains changes beyond automated updates; release manually")
    newest = check_history(repository, main_sha, dev_sha)

    stable = {path: show(main_sha, path) for path in ALLOWED_FILES}
    candidate = {path: show(dev_sha, path) for path in ALLOWED_FILES}
    bumps = check_content(stable, candidate)
    if "upstream" in bumps:
        tag = quote("v" + bumps["upstream"][1], safe="")
        check_release(api(f"repos/samanhappy/mcphub/releases/tags/{tag}"), now, "MCPHub release")
    if "tunnel" in bumps:
        tag = quote(bumps["tunnel"][1], safe="")
        check_release(api(f"repos/openai/tunnel-client/releases/tags/{tag}"), now, "Tunnel-client release")

    if now - newest < SOAK:
        raise Skip(f"Newest update has been on dev-mcphub for less than {SOAK // HOUR} hours")
    last_stable = float(git(
        "log", "-1", "--first-parent", "--format=%ct", main_sha, "--", "MCPHub/config.yaml"
    ) or 0)
    if now - last_stable < COOLDOWN:
        raise Skip(f"Previous stable MCPHub release is younger than {COOLDOWN // HOUR} hours")

    result = {"main_sha": main_sha, "dev_sha": dev_sha, "action": "promote"}
    validation = ci_state(repository, "validate-mcphub.yml", validated(dev_sha, DEV))
    if validation == "failed":
        raise ValueError(f"MCPHub validation failed for {dev_sha}")
    if validation != "success":
        result["action"] = "validate" if validation == "missing" else "wait"
        return result
    if os.environ.get("HAOS_E2E_ENABLED") != "true":
        raise Skip("The Home Assistant OS test is disabled (HAOS_E2E_ENABLED)")
    haos = ci_state(repository, "haos-mcphub.yml", lambda r: r.get("display_title") == haos_title(dev_sha))
    if haos == "failed":
        raise ValueError(f"Home Assistant OS test failed for {dev_sha}")
    if haos != "success":
        result["action"] = "haos" if haos == "missing" else "wait"
    return result


def check_candidate(dev_sha: str, candidate_sha: str) -> None:
    """The release commit may only consolidate the changelog of the gated dev commit."""
    if candidate_sha != dev_sha:
        if git("rev-parse", f"{candidate_sha}^@").split() != [dev_sha]:
            raise ValueError("Release candidate is not a single commit on the gated dev commit")
        changed = git("diff", "--name-only", dev_sha, candidate_sha).splitlines()
        if changed not in ([], ["MCPHub/CHANGELOG.md"]):
            raise ValueError("Release candidate changes more than the changelog")


def wait_for(repository: str, workflow: str, predicate, label: str, attempts: int = 200) -> None:
    for attempt in range(attempts):
        state = ci_state(repository, workflow, predicate)
        if state == "success":
            return
        if state == "failed":
            raise ValueError(f"{label} failed")
        if attempt < attempts - 1:
            time.sleep(15)
    raise TimeoutError(f"{label} did not finish successfully")


def release_pr(repository: str, candidate_sha: str) -> int:
    prs = api(f"repos/{repository}/pulls?state=open&base={MAIN}&per_page=100")
    matching = [pr for pr in prs if pr.get("head", {}).get("ref") == RELEASE]
    if len(matching) != 1:
        raise ValueError("Expected exactly one open MCPHub release pull request")
    pr = matching[0]
    if not (
        pr.get("draft") is False
        and pr.get("head", {}).get("sha") == candidate_sha
        and pr.get("head", {}).get("repo", {}).get("full_name") == repository
        and not any(label.get("name") == "hold" for label in pr.get("labels", []))
    ):
        raise ValueError("Release pull request identity, HEAD or hold label mismatch")
    return pr["number"]


def merge(repository: str, main_sha: str, dev_sha: str, candidate_sha: str) -> str:
    check_candidate(dev_sha, candidate_sha)
    wait_for(repository, "validate-mcphub.yml", validated(candidate_sha, RELEASE),
             "Release candidate validation")
    # Everything that was gated must still be exactly what will be merged.
    git("fetch", "--no-tags", "origin", MAIN, DEV)
    if git("rev-parse", f"origin/{MAIN}") != main_sha or git("rev-parse", f"origin/{DEV}") != dev_sha:
        raise Skip("main or dev-mcphub moved during validation; the next run re-checks")
    number = release_pr(repository, candidate_sha)
    gh("pr", "merge", str(number), "--repo", repository, "--merge", "--match-head-commit", candidate_sha)
    merged = api(f"repos/{repository}/pulls/{number}")
    if merged.get("merged") is not True:
        raise ValueError("Release pull request was not merged")
    return merged["merge_commit_sha"]


def watch(repository: str, merge_sha: str) -> None:
    """Report a failing stable build and prepare (never merge) a revert."""
    try:
        wait_for(repository, "validate-mcphub.yml", validated(merge_sha, MAIN), "Stable validation")
        return
    except (ValueError, TimeoutError) as error:
        reason = str(error)
    branch = f"revert/mcphub-{merge_sha[:12]}"
    git("switch", "-c", branch, merge_sha)
    git("revert", "--no-edit", "-m", "1", merge_sha)
    git("push", f"https://x-access-token:{os.environ['GH_TOKEN']}@github.com/{repository}.git",
        f"HEAD:refs/heads/{branch}")
    body = (f"Automatic MCPHub promotion {merge_sha} failed post-merge validation: {reason}.\n\n"
            "This revert is not merged automatically. Set MCPHUB_AUTO_PROMOTE=false to pause.")
    gh("pr", "create", "--repo", repository, "--base", MAIN, "--head", branch,
       "--title", "revert(mcphub): failed automatic promotion", "--body", body)
    gh("issue", "create", "--repo", repository,
       "--title", "MCPHub automatic promotion failed after merge", "--body", body)
    raise SystemExit(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("gate", "check-candidate", "merge", "watch"))
    parser.add_argument("--main-sha")
    parser.add_argument("--dev-sha")
    parser.add_argument("--candidate-sha")
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
    elif args.mode == "check-candidate":
        check_candidate(args.dev_sha, args.candidate_sha)
    elif args.mode == "merge":
        try:
            merge_sha = merge(repository, args.main_sha, args.dev_sha, args.candidate_sha)
        except Skip as reason:
            print(f"Not promoting: {reason}")
            return
        with output.open("a", encoding="utf-8") as handle:
            handle.write(f"merge_sha={merge_sha}\n")
    else:
        watch(repository, args.merge_sha)


if __name__ == "__main__":
    main()
