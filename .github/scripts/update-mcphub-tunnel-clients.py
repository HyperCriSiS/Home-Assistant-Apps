#!/usr/bin/env python3
"""Strict update and merge gates for the bundled MCPHub OpenAI tunnel-client.

Cloudflare remote access runs in the separate Cloudflared App, so MCPHub no
longer pins a cloudflared binary and this helper only tracks the OpenAI pin.

Invoked only by the trusted main-branch GitHub Actions workflow. Never execute
this helper from a pull request checkout in a privileged job.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote

OPENAI = re.compile(r"v[0-9]+[.][0-9]+[.][0-9]+")
BRANCH = re.compile(r"automation/mcphub-tunnel-clients-(v[0-9]+_[0-9]+_[0-9]+)")
TITLE = "chore(mcphub): update OpenAI tunnel client"
ALLOWED_FILES = {
    "MCPHub/Dockerfile",
    "MCPHub/CHANGELOG.md",
    "MCPHub/NOTICE.md",
    "MCPHub/config.yaml",
}
WRAPPER_VERSION = re.compile(
    r'^version: "(v([0-9]{4})[.]([0-9]{2})[.]([0-9]{2})(?:-([1-9][0-9]*))?)"$', re.M
)


def gh(*arguments: str) -> str:
    return subprocess.check_output(["gh", *arguments], text=True).strip()


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], text=True)


def pin(dockerfile: str) -> str:
    occurrences = re.findall(r"^ARG OPENAI_TUNNEL_VERSION=(\S+)$", dockerfile, re.M)
    if len(occurrences) != 1 or not OPENAI.fullmatch(occurrences[0]):
        raise ValueError("Missing or invalid OPENAI_TUNNEL_VERSION Dockerfile pin")
    return occurrences[0]


def as_tuple(value: str) -> tuple[int, int, int]:
    return tuple(int(x) for x in value.removeprefix("v").split("."))


def branch_for(openai: str) -> str:
    if not OPENAI.fullmatch(openai):
        raise ValueError("Only official stable three-part release tags are supported")
    return "automation/mcphub-tunnel-clients-" + openai.replace(".", "_")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"Expected exactly one {label}")
    return text.replace(old, new, 1)


def bump_version(config: str, today: date) -> tuple[str, str]:
    """Same scheme as the upstream updater: a new date, or -N on the same day."""
    matches = list(WRAPPER_VERSION.finditer(config))
    if len(matches) != 1:
        raise ValueError("Missing or invalid MCPHub App version")
    match = matches[0]
    current = date(int(match[2]), int(match[3]), int(match[4]))
    if today > current:
        version = f"v{today:%Y.%m.%d}"
    else:
        version = f"v{current:%Y.%m.%d}-{int(match[5] or 0) + 1}"
    return config[:match.start(1)] + version + config[match.end(1):], version


def prepare(files: dict[str, str], openai: str, today: date) -> tuple[dict[str, str], bool]:
    """Bump the tunnel pin, its notice and the App version; add a changelog section.

    The App version must change, otherwise Home Assistant never offers the
    rebuilt image as an update.
    """
    if not OPENAI.fullmatch(openai):
        raise ValueError("Rejecting unrecognized, prerelease or floating tunnel image tags")
    current_openai = pin(files["MCPHub/Dockerfile"])
    if as_tuple(openai) < as_tuple(current_openai):
        raise ValueError("Refusing tunnel-client version downgrade")
    if openai == current_openai:
        return files, False

    changelog = files["MCPHub/CHANGELOG.md"]
    header = "# Changelog\n\n"
    if not re.match(r"^# Changelog\n\n## v[0-9]{4}[.][0-9]{2}[.][0-9]{2}(?:-[1-9][0-9]*)?\n", changelog):
        raise ValueError("Unexpected MCPHub source changelog header")
    config, version = bump_version(files["MCPHub/config.yaml"], today)
    entry = (
        f"## {version}\n\n### Changed\n\n"
        f"- Updated bundled OpenAI tunnel-client {current_openai} to {openai}.\n\n"
    )
    updated = {
        "MCPHub/Dockerfile": replace_once(
            files["MCPHub/Dockerfile"],
            f"ARG OPENAI_TUNNEL_VERSION={current_openai}\n",
            f"ARG OPENAI_TUNNEL_VERSION={openai}\n",
            "tunnel-client Dockerfile pin",
        ),
        "MCPHub/NOTICE.md": replace_once(
            files["MCPHub/NOTICE.md"],
            f"- Version currently packaged: {current_openai}\n",
            f"- Version currently packaged: {openai}\n",
            "tunnel-client NOTICE version",
        ),
        "MCPHub/config.yaml": config,
        "MCPHub/CHANGELOG.md": header + entry + changelog[len(header):],
    }
    return updated, True


def api(endpoint: str):
    return json.loads(gh("api", endpoint))


def verify_candidate(repository: str, branch: str, sha: str, openai: str, today: date) -> int:
    if branch != branch_for(openai):
        raise ValueError("Automation branch/tag mismatch")
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("Unrecognized candidate SHA")
    if not BRANCH.fullmatch(branch):
        raise ValueError("Unrecognized automation branch")
    prs = api(f"repos/{repository}/pulls?state=open&base=dev-mcphub&per_page=100")
    matching = [pr for pr in prs if pr.get("head", {}).get("ref") == branch]
    if len(matching) != 1:
        raise ValueError("Expected exactly one open tunnel update pull request")
    pr = matching[0]
    if not (
        pr.get("draft") is False
        and pr.get("title") == TITLE
        and pr.get("head", {}).get("repo", {}).get("full_name") == repository
        and pr.get("base", {}).get("ref") == "dev-mcphub"
        and pr.get("head", {}).get("sha") == sha
        and pr.get("state") == "open"
    ):
        raise ValueError("PR target, identity, branch or HEAD mismatch")
    number = pr["number"]
    files = api(f"repos/{repository}/pulls/{number}/files?per_page=100")
    if (
        len(files) != len(ALLOWED_FILES)
        or {f.get("filename") for f in files} != ALLOWED_FILES
        or any(f.get("status") != "modified" for f in files)
    ):
        raise ValueError("PR modifies unexpected or missing files")

    # Verify every byte of the generated update against the current dev base.
    # A successful build alone is not permission to merge unrelated code.
    git("fetch", "--no-tags", "origin", "dev-mcphub", branch)
    current = {path: git("show", f"origin/dev-mcphub:{path}") for path in ALLOWED_FILES}
    desired, changed = prepare(current, openai, today)
    if not changed:
        raise ValueError("Tunnel update is already on dev-mcphub")
    if any(git("show", f"{sha}:{path}") != desired[path] for path in ALLOWED_FILES):
        raise ValueError("Candidate content differs from trusted version updater")
    git("merge-base", "--is-ancestor", "origin/dev-mcphub", sha)
    return number


def wait_for_ci(repository: str, branch: str, sha: str, attempts: int = 168) -> None:
    url = (
        f"repos/{repository}/actions/workflows/validate-mcphub.yml/runs?"
        f"event=workflow_dispatch&branch={quote(branch, safe='')}&per_page=100"
    )
    for attempt in range(attempts):
        response = api(url)
        runs = response.get("workflow_runs", [])
        matches = [
            r for r in runs if (
                r.get("head_sha") == sha
                and r.get("head_branch") == branch
                and r.get("event") == "workflow_dispatch"
                and r.get("actor", {}).get("login") == "github-actions[bot]"
                and r.get("head_repository", {}).get("full_name") == repository
            )
        ]
        if matches:
            selected = max(matches, key=lambda r: r.get("created_at", ""))
            if selected.get("status") == "completed":
                if selected.get("conclusion") != "success":
                    raise ValueError(f"Tunnel update CI failed: {selected.get('conclusion')}")
                return
        if attempt < attempts - 1:
            time.sleep(15)
    raise TimeoutError("No successful same-SHA validation of tunnel update")


def verify_and_merge(repository: str, branch: str, sha: str, openai: str, today: date):
    number = verify_candidate(repository, branch, sha, openai, today)
    wait_for_ci(repository, branch, sha)
    # Recheck base, candidate contents and SHA immediately before merging.
    if verify_candidate(repository, branch, sha, openai, today) != number:
        raise ValueError("Update PR changed during validation")
    gh("pr", "merge", str(number), "--repo", repository, "--squash",
       "--delete-branch", "--match-head-commit", sha)
    # GITHUB_TOKEN commits do not recursively trigger push workflows.
    gh("workflow", "run", "sync-dev-store.yml", "--repo", repository, "--ref", "main")
    gh("workflow", "run", "validate-mcphub.yml", "--repo", repository, "--ref", "dev-mcphub")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "merge"))
    parser.add_argument("--openai", required=True)
    parser.add_argument("--date", required=True, type=date.fromisoformat,
                        help="UTC date of the prepare run; merge must reuse it")
    parser.add_argument("--branch")
    parser.add_argument("--sha")
    args = parser.parse_args()
    if args.mode == "prepare":
        current = {path: Path(path).read_text(encoding="utf-8") for path in ALLOWED_FILES}
        files, updated = prepare(current, args.openai, args.date)
        if updated:
            for path, text in files.items():
                Path(path).write_text(text, encoding="utf-8")
        print("update=true" if updated else "update=false")
    else:
        verify_and_merge(
            os.environ["GITHUB_REPOSITORY"], args.branch, args.sha, args.openai, args.date
        )


if __name__ == "__main__":
    main()
