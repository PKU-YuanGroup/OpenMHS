#!/usr/bin/env python3
"""Pin every upstream clone of the corpus: ``MHS/registry/corpus.lock.jsonl``.

One JSON object per clone, sorted by ``package_id``::

    {"commit": "<40-hex HEAD or null>", "local_path": "labs/<owner>/<repo>",
     "package_id": "gh.<owner>/<repo>", "repo_url": "<origin remote>"}

The commit and remote come from git itself, read without taking any lock or
touching the clone (``git --no-optional-locks -C <clone> rev-parse HEAD`` and
``remote get-url origin``).  ``repo_url`` is the remote normalised to an
``https://`` URL without a trailing ``.git``; it is the identity of the code
that was analysed, which can differ from the catalogue URL (REGQ-09).  A clone
without a valid HEAD (an empty upstream) gets ``"commit": null``.

Stdlib only and offline.  The upstream clones are never modified.

Run:   python3 MHS/registry/corpus_lock.py            # rewrite the lock
       python3 MHS/registry/corpus_lock.py --check    # exit 1 if it is stale
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.abspath(os.path.join(HERE, "..", ".."))
LOCK_PATH = os.path.join(HERE, "corpus.lock.jsonl")
TRACKS = ("labs", "robots")
GIT_TIMEOUT_S = 30
_SHA = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")


def slugify(text: str, maxlen: int = 120) -> str:
    """Lowercase slug used by registry ids (same rule as ``build_registry.py``)."""
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9_.-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-._")
    return (s or "x")[:maxlen]


def package_id_for(owner: str, repo: str) -> str:
    """``gh.<owner>/<repo>`` for a clone directory (same rule as ``build_registry.py``)."""
    package_id = "gh." + slugify(owner, 60) + "/" + slugify(repo, 80)
    if not re.match(r"^gh\.[a-z0-9_.-]+/[a-z0-9_.-]+$", package_id):
        package_id = "gh." + slugify(f"{owner}-{repo}", 120) + "/" + slugify(repo or "repo", 80)
    return package_id.lower()


def normalise_remote(url: str | None) -> str | None:
    """``git@host:o/r.git`` / ``https://host/o/r.git/`` -> ``https://host/o/r``."""
    if not url:
        return None
    url = url.strip()
    match = re.match(r"^(?:ssh://)?git@([^:/]+)[:/](.+)$", url)
    if match:
        url = f"https://{match.group(1)}/{match.group(2)}"
    url = re.sub(r"^http://", "https://", url)
    url = re.sub(r"//[^/@]+@", "//", url)  # never keep credentials embedded in a remote
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url or None


def iter_clones(workspace: str = WORKSPACE, tracks: Iterable[str] = TRACKS) -> list[tuple[str, str, str]]:
    """(track, owner, repo) for every clone directory, in sorted order."""
    out = []
    for track in tracks:
        track_dir = os.path.join(workspace, track)
        if not os.path.isdir(track_dir):
            continue
        for owner in sorted(os.listdir(track_dir)):
            owner_dir = os.path.join(track_dir, owner)
            if not os.path.isdir(owner_dir) or owner.startswith("."):
                continue
            for repo in sorted(os.listdir(owner_dir)):
                if os.path.isdir(os.path.join(owner_dir, repo)) and not repo.startswith("."):
                    out.append((track, owner, repo))
    return out


def _git(clone: str, *args: str) -> str | None:
    """Run a read-only git command in ``clone`` itself.

    A directory without its own ``.git`` is not a clone: git would otherwise walk up into a parent work tree
    (the workspace, if it is a git checkout) and report that tree's HEAD and remote for every such directory,
    which rule 5 would then read as duplicates. ``GIT_CEILING_DIRECTORIES`` stops the walk at the clone's parent
    as a second guard.
    """
    if not os.path.exists(os.path.join(clone, ".git")):
        return None
    parent = os.path.dirname(os.path.realpath(clone))
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", LC_ALL="C",
               GIT_CEILING_DIRECTORIES=parent)
    try:
        proc = subprocess.run(
            ["git", "--no-optional-locks", "-C", clone, *args],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_S, env=env, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def read_clone(workspace: str, track: str, owner: str, repo: str) -> dict:
    """Lock entry of one clone (git is read, never written)."""
    local_path = f"{track}/{owner}/{repo}"
    clone = os.path.join(workspace, local_path)
    commit = _git(clone, "rev-parse", "HEAD")
    if commit is not None and not _SHA.match(commit):
        commit = None
    return {
        "commit": commit,
        "local_path": local_path,
        "package_id": package_id_for(owner, repo),
        "repo_url": normalise_remote(_git(clone, "remote", "get-url", "origin")),
    }


def build_lock(workspace: str = WORKSPACE, jobs: int = 8) -> list[dict]:
    clones = iter_clones(workspace)
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        entries = list(pool.map(lambda c: read_clone(workspace, *c), clones))
    entries.sort(key=lambda e: (e["package_id"], e["local_path"]))
    seen: dict[str, int] = {}
    for entry in entries:  # same deterministic collision rule as build_registry.py
        pid = entry["package_id"]
        if pid in seen:
            seen[pid] += 1
            entry["package_id"] = f"{pid}-{seen[pid]}"
        else:
            seen[pid] = 1
    return entries


def dumps(entries: list[dict]) -> str:
    return "".join(json.dumps(e, sort_keys=True, ensure_ascii=False) + "\n" for e in entries)


def load_lock(path: str = LOCK_PATH) -> dict[str, dict]:
    """``{local_path: entry}`` from a lock file; empty when the file is absent."""
    out: dict[str, dict] = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entry = json.loads(line)
                out[entry["local_path"]] = entry
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    check = "--check" in argv
    entries = build_lock()
    if not entries:
        print("[corpus-lock] no clones under labs/ or robots/; nothing to lock", file=sys.stderr)
        return 2
    text = dumps(entries)
    pinned = sum(1 for e in entries if e["commit"])
    if check:
        try:
            with open(LOCK_PATH, encoding="utf-8") as fh:
                current = fh.read()
        except OSError:
            current = None
        if current != text:
            print(f"[corpus-lock] STALE: {os.path.relpath(LOCK_PATH, WORKSPACE)} differs from the clones")
            return 1
        print(f"[corpus-lock] OK: {len(entries)} clones, {pinned} pinned commits")
        return 0
    with open(LOCK_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"[corpus-lock] wrote {os.path.relpath(LOCK_PATH, WORKSPACE)}: {len(entries)} clones, "
          f"{pinned} pinned commits, {len(entries) - pinned} without HEAD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
