#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
ADDON_DIR = ROOT / "TriliumNext Notes"
APP_PATH = "TriliumNext Notes"
UPDATE_FILES = (
    f"{APP_PATH}/Dockerfile",
    f"{APP_PATH}/config.yaml",
    f"{APP_PATH}/README.md",
    f"{APP_PATH}/CHANGELOG.md",
)
UPSTREAM_TAG = re.compile(r"v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")
PINNED_IMAGE = re.compile(r"^FROM docker\.io/triliumnext/trilium:(v[^\s]+)$", re.MULTILINE)


def next_addon_version(current: str, today: dt.date | None = None) -> str:
    today = today or dt.datetime.now(dt.timezone.utc).date()
    base = f"v{today:%Y.%m.%d}"
    if current == base:
        return f"{base}.1"
    match = re.fullmatch(re.escape(base) + r"\.(\d+)", current)
    if match:
        return f"{base}.{int(match.group(1)) + 1}"
    return base


def pinned_upstream(dockerfile: str) -> str:
    match = PINNED_IMAGE.search(dockerfile)
    if not match:
        raise SystemExit("Could not find the pinned Trilium image in Dockerfile")
    return match.group(1)


def render(files: dict[str, str], upstream: str, today: dt.date) -> dict[str, str] | None:
    """Return the updated UPDATE_FILES, or None when already on ``upstream``.

    Pure function of its inputs, so the merge gate can regenerate a bot pull
    request byte for byte and refuse anything the updater would not produce.
    """
    if not UPSTREAM_TAG.fullmatch(upstream):
        raise SystemExit(f"Refusing unexpected upstream tag: {upstream}")

    dockerfile = files[f"{APP_PATH}/Dockerfile"]
    current_upstream = pinned_upstream(dockerfile)
    if current_upstream == upstream:
        return None

    dockerfile = dockerfile.replace(
        f"docker.io/triliumnext/trilium:{current_upstream}",
        f"docker.io/triliumnext/trilium:{upstream}",
        1,
    )

    config = files[f"{APP_PATH}/config.yaml"]
    version_match = re.search(r'^version:\s*"([^"]+)"$', config, re.MULTILINE)
    if not version_match:
        raise SystemExit("Could not find add-on version in config.yaml")
    current_addon_version = version_match.group(1)
    new_addon_version = next_addon_version(current_addon_version, today)
    config = config.replace(
        f'version: "{current_addon_version}"',
        f'version: "{new_addon_version}"',
        1,
    )

    description = (
        f"description: >-\n"
        f"  Trilium {upstream} - hierarchical note-taking and personal knowledge base."
    )
    config, count = re.subn(
        r"^description:\s*>-\n(?:^[ \t]+.*(?:\n|$))+?(?=^[A-Za-z_])",
        description + "\n",
        config,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise SystemExit("Could not update Trilium version in config description")

    # Shields.io escapes a literal dash in badge text as a double dash.
    readme, count = re.subn(
        r"badge/Trilium-v(?:[^-)\s]|--)+-(\w+)\)\]"
        r"\(https://github\.com/TriliumNext/Trilium/releases/tag/v[^)\s]+\)",
        lambda match: (
            f"badge/Trilium-{upstream.replace('-', '--')}-{match.group(1)})]"
            f"(https://github.com/TriliumNext/Trilium/releases/tag/{upstream})"
        ),
        files[f"{APP_PATH}/README.md"],
        count=1,
    )
    if count != 1:
        raise SystemExit("Could not update the Trilium version badge in README.md")

    changelog = files[f"{APP_PATH}/CHANGELOG.md"]
    entry = (
        f"## {new_addon_version}\n\n"
        "### Changed\n\n"
        f"- Updated Trilium from {current_upstream} to {upstream}.\n\n"
    )
    marker = "# Changelog\n\n"
    if not changelog.startswith(marker):
        raise SystemExit("Unexpected CHANGELOG.md format")

    return {
        f"{APP_PATH}/Dockerfile": dockerfile,
        f"{APP_PATH}/config.yaml": config,
        f"{APP_PATH}/README.md": readme,
        f"{APP_PATH}/CHANGELOG.md": marker + entry + changelog[len(marker):],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", required=True)
    parser.add_argument(
        "--date",
        type=dt.date.fromisoformat,
        default=None,
        help="UTC date for the App version (default: today)",
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=ADDON_DIR.parent,
        help="Repository checkout to update (default: this script's repository)",
    )
    args = parser.parse_args()
    today = args.date or dt.datetime.now(dt.timezone.utc).date()

    root = args.root
    current = {path: (root / path).read_text(encoding="utf-8") for path in UPDATE_FILES}
    # Compute every change first so a failure never leaves half-updated files behind.
    updated = render(current, args.upstream, today)
    if updated is None:
        print(f"Already on {args.upstream}")
        return
    for path, text in updated.items():
        (root / path).write_text(text, encoding="utf-8", newline="\n")

    print(f"Updated Trilium {pinned_upstream(current[UPDATE_FILES[0]])} -> {args.upstream}")


if __name__ == "__main__":
    main()
