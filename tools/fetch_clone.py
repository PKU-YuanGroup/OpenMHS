#!/usr/bin/env python3
"""Fetch the upstream clone a driver package needs, at the pinned commit.  Standard library plus ``git``.

The corpus (``labs/``, ``robots/``, ~3,000 repositories) is not part of the open-source repository, but gate G1 to G4 and G7
read the card's ``local_path`` clone at the card's pinned commit.  This fetches just that one repository:

    python3 tools/fetch_clone.py MHS/drivers/labs/tiagocoutinho__julabo          # from a driver directory
    python3 tools/fetch_clone.py gh.tiagocoutinho/julabo                          # or a package id
    python3 tools/fetch_clone.py --exemplars                                      # the four exemplars
    python3 tools/fetch_clone.py <dir> --source /path/to/a/local/clone            # offline: clone from a local path

It makes a shallow clone of ``upstream.repo_url`` (``--source`` replaces the URL) at exactly ``upstream.commit`` into
``<root>/<local_path>``.  An existing directory is left alone if it is already at the pinned commit and has no local changes;
otherwise the command stops (it never deletes or resets anything).  Exit code 0 on success, 1 on a failure, 2 on usage.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "--no-optional-locks", *args], cwd=cwd, capture_output=True, text=True, check=False)


def load_card(root: Path, target: str) -> dict:
    path = Path(target)
    if not path.is_absolute():
        path = root / path
    if path.is_dir() and (path / "task.json").is_file():
        return json.loads((path / "task.json").read_text(encoding="utf-8"))
    if target.startswith("gh."):
        owner_repo = target[3:].replace("/", "__")
        for track in ("labs", "robots"):
            candidate = root / "MHS" / "registry" / "tasks" / track / f"{owner_repo}.json"
            if candidate.is_file():
                return json.loads(candidate.read_text(encoding="utf-8"))
    raise SystemExit(f"error: {target!r} is neither a driver directory with task.json nor a known package id")


def fetch(root: Path, card: dict, source: str | None) -> int:
    url = source or card["upstream"]["repo_url"]
    commit = card["upstream"]["commit"]
    dest = root / card["local_path"]
    if dest.exists():
        head = git("rev-parse", "HEAD", cwd=dest).stdout.strip()
        dirty = git("status", "--porcelain", cwd=dest).stdout.strip()
        if head == commit and not dirty:
            print(f"ok      {card['package_id']}: {card['local_path']} is already at {commit[:12]}")
            return 0
        print(f"error: {card['local_path']} exists (HEAD {head[:12] or '?'}, {'modified' if dirty else 'clean'}) and is not the "
              f"pinned commit {commit[:12]}; remove it yourself if you want a fresh copy", file=sys.stderr)
        return 1
    if not commit:
        print(f"error: {card['package_id']} has no pinned commit (an empty upstream)", file=sys.stderr)
        return 1
    dest.mkdir(parents=True)
    steps = [
        ("init", ["init", "--quiet"]),
        ("remote", ["remote", "add", "origin", url]),
        ("fetch", ["fetch", "--quiet", "--depth", "1", "origin", commit]),
        ("checkout", ["checkout", "--quiet", "--detach", "FETCH_HEAD"]),
    ]
    for name, args in steps:
        result = git(*args, cwd=dest)
        if result.returncode != 0:
            print(f"error: git {name} failed for {card['package_id']}: {result.stderr.strip()[-300:]}", file=sys.stderr)
            return 1
    head = git("rev-parse", "HEAD", cwd=dest).stdout.strip()
    if head != commit:
        print(f"error: fetched {head[:12]}, expected {commit[:12]}", file=sys.stderr)
        return 1
    print(f"fetched {card['package_id']}: {card['local_path']} at {commit[:12]} from {url}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("targets", nargs="*", help="driver directories or package ids (gh.owner/repo)")
    parser.add_argument("--exemplars", action="store_true", help="the packages listed in MHS/drivers/EXEMPLARS.txt")
    parser.add_argument("--source", help="clone from this path or URL instead of the card's repo_url (one target only)")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root (default: found from this file)")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    targets = list(args.targets)
    if args.exemplars:
        listing = root / "MHS" / "drivers" / "EXEMPLARS.txt"
        targets += [line.strip() for line in listing.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not targets:
        parser.error("name a driver directory or a package id, or pass --exemplars")
    if args.source and len(targets) != 1:
        parser.error("--source works with exactly one target")
    status = 0
    for target in targets:
        status |= fetch(root, load_card(root, target), args.source)
    return status


if __name__ == "__main__":
    sys.exit(main())
