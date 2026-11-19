#!/usr/bin/env python3
"""List the driver packages a branch changes in a way a gate can see.  Standard library plus ``git``.

    python3 tools/changed_packages.py origin/main        # one package directory per line, sorted

A package counts when any file under ``MHS/drivers/<track>/<owner>__<repo>/`` differs between the merge base of
``<base>`` and ``HEAD``.  One difference does not count: a ``task.json`` whose only change is ``rank``.  The rank is the
card's place in the dispatch order; it moves in hundreds of cards whenever the registry gains some, and no gate reads
it.  (``prepare.py --sync --check`` proves separately that every ``task.json`` is still its registry card.)  CI runs
the gate on the packages this prints, so a registry rebuild does not make it fetch every upstream repository.

Exit code 0, or 2 when git cannot compare the two commits.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
#: card fields whose change no gate can see
UNGATED = ("rank",)


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args], capture_output=True, text=True, check=False)


def card_at(root: Path, rev: str, path: str) -> dict | None:
    shown = git(root, "show", f"{rev}:{path}")
    if shown.returncode != 0:
        return None
    try:
        doc = json.loads(shown.stdout)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def only_ungated(root: Path, old_rev: str, path: str) -> bool:
    """Whether ``path`` (a task.json) differs between ``old_rev`` and HEAD in nothing but the ungated fields."""
    old, new = card_at(root, old_rev, path), card_at(root, "HEAD", path)
    if old is None or new is None:
        return False
    for field in UNGATED:
        old.pop(field, None)
        new.pop(field, None)
    return old == new


def changed_packages(root: Path, base: str) -> list[str] | None:
    merge_base = git(root, "merge-base", base, "HEAD")
    names = git(root, "diff", "--name-only", f"{base}...HEAD", "--", "MHS/drivers")
    if merge_base.returncode != 0 or names.returncode != 0:
        print(f"error: cannot compare {base} with HEAD: {(merge_base.stderr or names.stderr).strip()[-300:]}", file=sys.stderr)
        return None
    by_package: dict[str, list[str]] = {}
    for name in names.stdout.splitlines():
        parts = name.split("/")
        if len(parts) >= 5:
            by_package.setdefault("/".join(parts[:4]), []).append(name)
    found = []
    for package, files in sorted(by_package.items()):
        if files == [f"{package}/task.json"] and only_ungated(root, merge_base.stdout.strip(), files[0]):
            continue
        found.append(package)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("base", help="the commit or branch the change is measured against, for example origin/main")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root (default: found from this file)")
    args = parser.parse_args(argv)
    found = changed_packages(args.root.resolve(), args.base)
    if found is None:
        return 2
    for package in found:
        print(package)
    return 0


if __name__ == "__main__":
    sys.exit(main())
