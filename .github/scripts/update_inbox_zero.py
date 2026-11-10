#!/usr/bin/env python3
"""Move the Inbox Zero App to another commit of the packaged fork."""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import pathlib
import re

SCRIPTS = pathlib.Path(__file__).resolve().parent
APP_PATH = "Inbox Zero"
UPDATE_FILES = (
    f"{APP_PATH}/Dockerfile",
    f"{APP_PATH}/config.yaml",
    f"{APP_PATH}/README.md",
    f"{APP_PATH}/NOTICE.md",
    f"{APP_PATH}/CHANGELOG.md",
)
BASE_VERSION = re.compile(r"v\d+\.\d+\.\d+")
COMMIT = re.compile(r"[0-9a-f]{40}")
PINNED_IMAGE = re.compile(r"^FROM ghcr\.io/hypercrisis/inbox-zero-base:([0-9a-f]{40})$", re.MULTILINE)
DESCRIPTION = re.compile(r"^  Inbox Zero (v\d+\.\d+\.\d+) \(fork ([0-9a-f]{7})\) - ", re.MULTILINE)

_spec = importlib.util.spec_from_file_location("update_trilium", SCRIPTS / "update_trilium.py")
_trilium = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_trilium)
next_addon_version = _trilium.next_addon_version


def pinned(files: dict[str, str]) -> tuple[str, str]:
    """Return the packaged upstream base version and fork commit."""
    image = PINNED_IMAGE.search(files[f"{APP_PATH}/Dockerfile"])
    description = DESCRIPTION.search(files[f"{APP_PATH}/config.yaml"])
    if not image or not description or not image.group(1).startswith(description.group(2)):
        raise SystemExit("Dockerfile and config.yaml do not name one packaged commit")
    return description.group(1), image.group(1)


def swap(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"Expected exactly one {old!r}")
    return text.replace(old, new)


def render(files: dict[str, str], base: str, commit: str, today: dt.date) -> dict[str, str] | None:
    """Return the updated UPDATE_FILES, or None when already on ``commit``.

    Pure function of its inputs, so the merge gate can regenerate a bot pull
    request byte for byte and refuse anything the updater would not produce.
    """
    if not BASE_VERSION.fullmatch(base) or not COMMIT.fullmatch(commit):
        raise SystemExit(f"Refusing unexpected version: {base} {commit}")
    old_base, old_commit = pinned(files)
    if old_commit == commit:
        return None

    config = files[f"{APP_PATH}/config.yaml"]
    version = re.search(r'^version: "([^"]+)"$', config, re.MULTILINE)
    if not version:
        raise SystemExit("Could not find the App version in config.yaml")
    new_version = next_addon_version(version.group(1), today)
    config = swap(config, version.group(0), f'version: "{new_version}"')
    config = swap(
        config, f"Inbox Zero {old_base} (fork {old_commit[:7]})", f"Inbox Zero {base} (fork {commit[:7]})"
    )

    readme = swap(
        files[f"{APP_PATH}/README.md"],
        f"badge/Inbox%20Zero-{old_base}%20({old_commit[:7]})-",
        f"badge/Inbox%20Zero-{base}%20({commit[:7]})-",
    )
    marker = "# Changelog\n\n"
    changelog = files[f"{APP_PATH}/CHANGELOG.md"]
    if not changelog.startswith(marker):
        raise SystemExit("Unexpected CHANGELOG.md format")
    entry = (
        f"## {new_version}\n\n"
        "### Changed\n\n"
        f"- Updated Inbox Zero from {old_commit[:7]} to {commit[:7]} ({base}).\n\n"
    )
    return {
        f"{APP_PATH}/Dockerfile": swap(
            files[f"{APP_PATH}/Dockerfile"], f"inbox-zero-base:{old_commit}", f"inbox-zero-base:{commit}"
        ),
        f"{APP_PATH}/config.yaml": config,
        f"{APP_PATH}/README.md": swap(readme, f"/commit/{old_commit})", f"/commit/{commit})"),
        f"{APP_PATH}/NOTICE.md": swap(
            files[f"{APP_PATH}/NOTICE.md"],
            f"{old_base} at fork commit {old_commit}",
            f"{base} at fork commit {commit}",
        ),
        f"{APP_PATH}/CHANGELOG.md": marker + entry + changelog[len(marker):],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="Upstream release the commit is based on")
    parser.add_argument("--commit", required=True, help="Full commit SHA of the fork")
    parser.add_argument("--date", type=dt.date.fromisoformat, default=None,
                        help="UTC date for the App version (default: today)")
    parser.add_argument("--root", type=pathlib.Path, default=SCRIPTS.parents[1],
                        help="Repository checkout to update (default: this script's repository)")
    args = parser.parse_args()

    current = {path: (args.root / path).read_text(encoding="utf-8") for path in UPDATE_FILES}
    # Compute every change first so a failure never leaves half-updated files behind.
    updated = render(current, args.base, args.commit, args.date or dt.datetime.now(dt.timezone.utc).date())
    if updated is None:
        print(f"Already on {args.commit}")
        return
    for path, text in updated.items():
        (args.root / path).write_text(text, encoding="utf-8", newline="\n")
    print(f"Updated Inbox Zero {pinned(current)[1]} -> {args.commit}")


if __name__ == "__main__":
    main()
