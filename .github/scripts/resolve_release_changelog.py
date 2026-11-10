#!/usr/bin/env python3
"""Resolve the changelog conflict a squashed release leaves on a dev branch.

A release reaches main as one squashed commit whose changelog was curated on
the release pull request, so merging main back conflicts with the development
branch's own wording of the same entries. When the App is otherwise identical
on both sides, the branch has nothing unreleased and main's text is taken.

Run inside a conflicted `git merge origin/main`. Exits non-zero when anything
but an App changelog conflicts or when the App differs from main, because an
unreleased change would lose its changelog entry.
"""
from __future__ import annotations

import subprocess
import sys


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8")


def main() -> None:
    paths = [path for path in git("diff", "--name-only", "--diff-filter=U", "-z").split("\0") if path]
    if not paths:
        sys.exit("No conflicted files to resolve")
    for path in paths:
        app, _, name = path.rpartition("/")
        if not app or name != "CHANGELOG.md":
            sys.exit(f"Cannot resolve the conflict in {path}")
        if subprocess.call(["git", "diff", "--quiet", "HEAD", "origin/main", "--",
                            f":(literal){app}", f":(exclude,literal){path}"]):
            sys.exit(f"{app} has changes that main does not; resolve {path} by hand")
    for path in paths:
        git("checkout", "--theirs", "--", path)
        git("add", "--", path)


if __name__ == "__main__":
    main()
