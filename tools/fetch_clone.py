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

Git submodules.  The gates read a path inside a git submodule from the submodule's own checkout at the commit the pinned
tree records (``mhs.driver.upstream``, SUBMODULES), so a package that names such a path (a MuJoCo model, a cited source
line) needs that submodule too.  After the clone this fetches every submodule whose path the driver package's files
name (``--submodules cited``, the default), every submodule (``all``) or none (``none``), each shallow and at its
gitlink commit, with ``git@github.com:`` URLs read over https; a submodule of such a submodule too, the way the gates
follow two levels.  With ``--source`` a submodule comes from the source
clone's own checkout of it.  A submodule that cannot be fetched is an error: the gate would refuse the paths in it.
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


#: ssh forms of a GitHub URL that an anonymous fetch (CI, a reader without keys) cannot use, and their https form
HTTPS_FOR = {"git@github.com:": "https://github.com/", "ssh://git@github.com/": "https://github.com/"}
#: package files whose text may name a path of the upstream tree
PACKAGE_TEXT = (".py", ".md", ".json", ".txt", ".yaml", ".yml", ".toml")
#: how deep the gates follow submodules (``mhs.driver.upstream``): a submodule of a submodule is depth 2
MAX_DEPTH = 2


def gitlinks(clone: Path) -> list[str]:
    """Paths of the git submodules the checked-out tree records (mode 160000 entries of the index)."""
    listing = git("ls-files", "--stage", cwd=clone).stdout
    return sorted(line.split("\t", 1)[1] for line in listing.splitlines() if line.startswith("160000 ") and "\t" in line)


def package_text(root: Path, card: dict) -> str:
    """The text of the driver package's files, where a path of the upstream tree may be named."""
    directory = root / (card.get("driver_dir") or "")
    if not card.get("driver_dir") or not directory.is_dir():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in sorted(directory.iterdir())
                     if path.is_file() and path.suffix in PACKAGE_TEXT)


def fetch_submodules(root: Path, card: dict, source: str | None, mode: str) -> int:
    """Check out the submodules the package needs at their gitlink commits, and the submodules of those submodules
    (the gates follow two levels, ``mhs.driver.upstream``).  0 when all of them are in place."""
    text = package_text(root, card) if mode == "cited" else ""
    return _fetch_level(root / card["local_path"], "", Path(source) if source else None, mode, text, card, 1)


def _fetch_level(clone: Path, prefix: str, source: Path | None, mode: str, text: str, card: dict, depth: int) -> int:
    status = 0
    for link in gitlinks(clone):
        full = prefix + link   # the path from the outer clone's root, as the package names it
        if mode != "all" and full + "/" not in text:
            continue
        gitlink = git("ls-files", "--stage", "--", link, cwd=clone).stdout.split()[1]
        head = git("rev-parse", "HEAD", cwd=clone / link).stdout.strip() if (clone / link / ".git").exists() else ""
        if head == gitlink:
            print(f"ok      {card['package_id']}: submodule {full} is already at {gitlink[:12]}")
        else:
            config = ["-c", "protocol.file.allow=always"]
            for ssh, https in HTTPS_FOR.items():
                config += ["-c", f"url.{https}.insteadOf={ssh}"]
            if source is not None:  # offline: the source clone's own checkout of the submodule, if it has one
                local = source / link
                if not (local / ".git").exists():
                    print(f"error: {card['package_id']}: the source clone has no checkout of submodule {full}",
                          file=sys.stderr)
                    status = 1
                    continue
                listing = git("config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$", cwd=clone).stdout
                names = [line.split()[0][len("submodule."):-len(".path")] for line in listing.splitlines()
                         if line.split(None, 1)[1:] == [link]]
                if len(names) != 1:
                    print(f"error: {card['package_id']}: .gitmodules does not name submodule {full} once",
                          file=sys.stderr)
                    status = 1
                    continue
                config += ["-c", f"submodule.{names[0]}.url={local}"]
            result = git(*config, "submodule", "update", "--init", "--depth", "1", "--", link, cwd=clone)
            head = git("rev-parse", "HEAD", cwd=clone / link).stdout.strip() if result.returncode == 0 else ""
            if head != gitlink:
                print(f"error: submodule {full} of {card['package_id']} is not at {gitlink[:12]}: "
                      f"{result.stderr.strip()[-300:] or 'HEAD ' + (head[:12] or '?')}", file=sys.stderr)
                status = 1
                continue
            print(f"fetched {card['package_id']}: submodule {full} at {gitlink[:12]}")
        if depth < MAX_DEPTH:
            status |= _fetch_level(clone / link, full + "/", source / link if source is not None else None, mode,
                                   text, card, depth + 1)
    return status


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


def fetch(root: Path, card: dict, source: str | None, submodules: str = "cited") -> int:
    url = source or card["upstream"]["repo_url"]
    commit = card["upstream"]["commit"]
    dest = root / card["local_path"]
    if dest.exists():
        head = git("rev-parse", "HEAD", cwd=dest).stdout.strip()
        dirty = git("status", "--porcelain", cwd=dest).stdout.strip()
        if head == commit and not dirty:
            print(f"ok      {card['package_id']}: {card['local_path']} is already at {commit[:12]}")
            return 0 if submodules == "none" else fetch_submodules(root, card, source, submodules)
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
    return 0 if submodules == "none" else fetch_submodules(root, card, source, submodules)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("targets", nargs="*", help="driver directories or package ids (gh.owner/repo)")
    parser.add_argument("--exemplars", action="store_true", help="the packages listed in MHS/drivers/EXEMPLARS.txt")
    parser.add_argument("--source", help="clone from this path or URL instead of the card's repo_url (one target only)")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root (default: found from this file)")
    parser.add_argument("--submodules", choices=("cited", "all", "none"), default="cited",
                        help="git submodules to fetch at their gitlink commits: those whose path the driver package "
                             "names (default), all, or none")
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
        status |= fetch(root, load_card(root, target), args.source, args.submodules)
    return status


if __name__ == "__main__":
    sys.exit(main())
