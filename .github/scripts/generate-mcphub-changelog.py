#!/usr/bin/env python3
"""MCPHub development changelog from Git history and consolidated stable notes.

Dev-store builds list their commits. Stable releases get one human-curated
section with every change since the previous stable release and no commits;
`stable` drafts that section and `stable --check` enforces its shape.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

APP = "MCPHub"
CHANGELOG = Path(APP) / "CHANGELOG.md"
HISTORY = Path(".dev-store-mcphub-changes.json")
STATE = Path(".dev-store-revisions.json")
RELATED = (
    "MCPHub",
    ".github/workflows/validate-mcphub.yml",
    ".github/workflows/haos-mcphub.yml",
    ".github/workflows/sync-dev-store.yml",
    ".github/workflows/promote.yml",
    ".github/scripts/haos-e2e-mcphub.sh",
    ".github/scripts/haos-qemu-mcphub.sh",
    ".github/workflows/haos-qemu-mcphub.yml",
    ".github/scripts/integration-test-mcphub.sh",
    ".github/scripts/update-mcphub-upstream.py",
    ".github/scripts/generate-mcphub-changelog.py",
)
BEGIN = "<!-- MCPHUB STABLE AUDIT BEGIN -->"
END = "<!-- MCPHUB STABLE AUDIT END -->"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def commits(previous: str, current: str) -> list[dict[str, str]]:
    output = git(
        "log", "--full-history", "--format=%H%x1f%s%x1e",
        f"{previous}..{current}", "--", *RELATED,
    )
    entries = []
    for entry in output.split("\x1e"):
        entry = entry.strip()
        if not entry:
            continue
        sha, sep, subject = entry.partition("\x1f")
        if not sep:
            raise ValueError("Unexpected git log entry")
        entries.append({"sha": sha.strip(), "subject": subject.strip()})
    return entries


def escape_md(value: str) -> str:
    return value.replace("\\", "\\\\").replace("`", "\\`").replace("[", "\\[").replace("]", "\\]")


def commit_notes(entries: list[dict[str, str]], repository: str) -> str:
    if not entries:
        return "- No MCPHub-related commits in this range.\n"
    lines = []
    for entry in entries:
        sha, subject = entry["sha"], escape_md(entry["subject"])
        lines.append(f"- [\u0060{sha[:7]}\u0060](https://github.com/{repository}/commit/{sha}) {subject}")
    return "\n".join(lines) + "\n"


def version_from_yaml(content: str) -> str:
    match = re.search(r'^version:\s*["\']?([^"\'\n]+)', content, re.M)
    if not match:
        raise ValueError("Missing version in config.yaml")
    return match.group(1).strip()


def stable_version() -> str:
    return version_from_yaml(git("show", "origin/main:MCPHub/config.yaml"))


def dev(repository: str) -> None:
    state = json.loads(STATE.read_text(encoding="utf-8"))["mcphub"]
    revision = int(state["revision"])
    version = version_from_yaml(Path(APP, "config.yaml").read_text(encoding="utf-8"))
    expected = f"-dev.{revision}"
    if not version.endswith(expected):
        raise ValueError(f"Development version {version!r} does not match revision {revision}")
    source_sha = git("rev-parse", "origin/dev-mcphub")
    previous = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    if not isinstance(previous, list):
        raise ValueError("Development changelog history must be an array")
    if previous and previous[0]["revision"] > revision:
        raise ValueError("Development revision moved backwards; refusing to drop history")
    if not previous or previous[0]["revision"] < revision:
        prior_sha = previous[0]["source_sha"] if previous else None
        if prior_sha:
            git("merge-base", "--is-ancestor", prior_sha, source_sha)
        previous.insert(0, {
            "revision": revision,
            "version": version,
            "source_sha": source_sha,
            "baseline": not bool(prior_sha),
            "commits": commits(prior_sha, source_sha) if prior_sha else [],
        })
    HISTORY.write_text(json.dumps(previous, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Only show commits belonging to the current dev-store revision.
    # The JSON history is retained for calculating iteration boundaries, but
    # neither earlier builds nor the stable-release audit belong in this view.
    latest = previous[0]
    head = f"# Changelog\n\n## {version}\n\n### Commits in this Dev build\n\n"
    if latest["baseline"]:
        head += "- Initial development snapshot (no previous Dev build recorded).\n"
    else:
        head += commit_notes(latest["commits"], repository)
    CHANGELOG.write_text(head, encoding="utf-8")


SECTION = re.compile(r"^## (\S+)[ \t]*$", re.M)
COMMIT_LINK = re.compile(r"\[`[0-9a-f]{7,40}`\]\(https://github\.com/[^)\s]+/commit/[0-9a-f]+\)")
CATEGORIES = ("Breaking changes", "Added", "Changed", "Removed", "Fixed", "Security", "Upgrade notes")
BREAKING = re.compile(r"^>\s*\*\*Breaking change:?\*\*:?\s*(.+)$")


def split_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Split a changelog into its preamble and (version, body) sections."""
    matches = list(SECTION.finditer(text))
    if not matches:
        raise ValueError("Changelog has no version sections")
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1), text[match.end():end].strip("\n")))
    return text[:matches[0].start()], sections


def drop_audit(text: str) -> str:
    """Remove the commit audit block written by earlier generator versions."""
    start, end = text.find(BEGIN), text.find(END)
    if start < 0 and end < 0:
        return text
    if start < 0 or end < start:
        raise ValueError("Inconsistent stable audit markers")
    return text[:start] + text[end + len(END):].lstrip("\n")


def merge_notes(bodies: list[str]) -> str:
    """Group the bullet points of several sections by category, oldest first."""
    groups: dict[str, list[str]] = {}
    for body in bodies:
        category, item = "Changed", None
        for line in body.splitlines():
            stripped = line.strip()
            heading = re.match(r"^###\s+(.+)$", stripped)
            breaking = BREAKING.match(stripped)
            if heading:
                category, item = heading.group(1).strip(), None
            elif breaking:
                groups.setdefault("Breaking changes", []).append("- " + breaking.group(1).strip())
                item = None
            elif stripped.startswith("- "):
                groups.setdefault(category, []).append(stripped)
                item = len(groups[category]) - 1
            elif stripped and item is not None:
                groups[category][item] += " " + stripped
            elif not stripped:
                item = None
    order = list(CATEGORIES) + [name for name in groups if name not in CATEGORIES]
    parts = []
    for name in order:
        items = list(dict.fromkeys(groups.get(name, [])))
        if items:
            parts.append(f"### {name}\n\n" + "\n".join(items))
    return "\n\n".join(parts)


def consolidate(text: str, current: str, previous: str) -> str:
    """One section for every change since the previous stable release, no commits."""
    preamble, sections = split_sections(drop_audit(text))
    versions = [version for version, _ in sections]
    if previous not in versions:
        raise ValueError(f"Previous stable section {previous} is missing from the changelog")
    pending = sections[:versions.index(previous)]
    if len(pending) <= 1:
        return text
    body = merge_notes([body for _, body in reversed(pending)])
    rest = sections[len(pending):]
    rendered = [f"## {current}\n\n{body}"] + [f"## {version}\n\n{body}".rstrip() for version, body in rest]
    return preamble + "\n\n".join(rendered) + "\n"


def stable(repository: str, check: bool = False) -> None:
    del repository  # Stable notes are human-curated and never list commits.
    source = CHANGELOG.read_text(encoding="utf-8")
    current = version_from_yaml(Path(APP, "config.yaml").read_text(encoding="utf-8"))
    previous = stable_version()
    if not source.startswith(f"# Changelog\n\n## {current}\n\n"):
        raise ValueError("Stable candidate's first changelog header does not match its version")
    if not check:
        drafted = consolidate(source, current, previous)
        if drafted != source:
            CHANGELOG.write_text(drafted, encoding="utf-8", newline="\n")
        return
    problems = []
    if BEGIN in source or END in source or COMMIT_LINK.search(source):
        problems.append("contains commit lists")
    versions = [version for version, _ in split_sections(source)[1]]
    if current != previous and (len(versions) < 2 or versions[1] != previous):
        problems.append(f"must have exactly one section above the previous stable {previous}")
    if problems:
        raise SystemExit(
            "Stable changelog " + "; ".join(problems)
            + ". Run generate-mcphub-changelog.py stable to draft one consolidated section, then edit it."
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("dev", "stable"))
    parser.add_argument("--repository", default="HyperCriSiS/Home-Assistant-Apps")
    parser.add_argument("--check", action="store_true", help="Fail if stable digest is missing/outdated")
    options = parser.parse_args()
    if options.mode == "dev":
        dev(options.repository)
    else:
        stable(options.repository, options.check)


if __name__ == "__main__":
    main()
