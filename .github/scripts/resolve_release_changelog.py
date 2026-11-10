#!/usr/bin/env python3
"""Resolve the changelog conflict a squashed release leaves on a dev branch.

A release reaches main as one squashed commit whose changelog was curated on
the release pull request, so merging main back conflicts with the development
branch's own wording of the same sections. main holds the released text. The
development branch keeps only the sections it added above the released version.

Run inside a conflicted `git merge origin/main`. Exits non-zero without
touching the tree when anything but an App changelog conflicts.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SECTION = re.compile(r"^## (\S+)[ \t]*$", re.M)
VERSION = re.compile(r'^version:\s*["\']?([^"\'\n]+)', re.M)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8")


def resolve(dev: str, main: str, released: str) -> str:
    """main's changelog below the sections dev added above `released`."""
    main_top = SECTION.search(main)
    if not main_top or main_top.group(1) != released:
        raise ValueError(f"main's changelog does not start with {released}")
    dev_sections = list(SECTION.finditer(dev))
    for section in dev_sections:
        if section.group(1) == released:
            newer = dev[dev_sections[0].start():section.start()]
            return main[:main_top.start()] + newer + main[main_top.start():]
    raise ValueError(f"The development changelog has no section {released}")


def main() -> None:
    paths = [path for path in git("diff", "--name-only", "--diff-filter=U", "-z").split("\0") if path]
    if not paths:
        sys.exit("No conflicted files to resolve")
    resolved = {}
    for path in paths:
        app, _, name = path.rpartition("/")
        if not app or name != "CHANGELOG.md":
            sys.exit(f"Cannot resolve the conflict in {path}")
        released = VERSION.search(git("show", f"origin/main:{app}/config.yaml"))
        if not released:
            sys.exit(f"{app}/config.yaml on main has no version")
        resolved[path] = resolve(
            git("show", f":2:{path}"), git("show", f":3:{path}"), released.group(1).strip())
    for path, text in resolved.items():
        Path(path).write_text(text, encoding="utf-8", newline="\n")
        git("add", "--", path)


if __name__ == "__main__":
    main()
