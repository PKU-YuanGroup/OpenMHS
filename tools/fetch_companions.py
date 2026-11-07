#!/usr/bin/env python3
"""Verify, copy or fetch the companion clones a driver package cites (``companions`` with ``lock``).  Standard library
plus ``git``.

A task card may name companion sources fetched at one pinned commit under ``work/companions/`` and listed in its
``LOCK.json`` (a ``lock`` alias such as ``ros-simulation__gazebo_ros_pkgs@2.5.21``).  ``work/`` is not part of the
open-source tree, so an export has the card's pin but no clone: gate G1 then fails ``NO_COMPANION_CLONE`` and
``COMPANION_LOCK``.  This tool puts each clone back, offline first:

    python3 tools/fetch_companions.py MHS/drivers/robots/ethz-asl__rotors_simulator     # the card's lock companions
    python3 tools/fetch_companions.py --lock work/companions/LOCK.json [ALIAS ...]        # entries of a LOCK file
    python3 tools/fetch_companions.py <dir> --from /other/workspace/work/companions        # offline copy
    python3 tools/fetch_companions.py <dir> --network                                       # explicit online fetch
    python3 tools/fetch_companions.py <dir> --companions-root DIR                           # write elsewhere

For each companion, in this order:

1. The destination ``<root>/<owner>__<repo>@<commit12>`` exists: it is verified (``.git/HEAD`` names the commit, ``git
   status --porcelain --untracked-files=all`` is empty, no write bit in the work tree) and left as it is.  A failure is
   reported; an existing directory is never deleted, reset or chmod-ed.
2. ``--from DIR`` (or ``MHS_COMPANIONS_FROM``): ``DIR/<name>`` (a clone) or ``DIR/<name>.bundle`` is copied into a
   temporary sibling and accepted only if its HEAD is the commit, ``git fsck --full --no-dangling`` passes and its work
   tree is clean (no submodule is initialised); it is then renamed into place.
3. Only with ``--network``: ``git init``, one ``git fetch --depth 1 --no-tags`` of the pinned commit and a detached
   checkout, with an empty hooks directory, no credential helper, no terminal prompt, ``GIT_LFS_SKIP_SMUDGE=1``,
   system and global git configuration ignored and no submodule update; then the same verification.  Network use is a
   user-authorised act: the authorisation of 2026-11-05 covered the 17 fetches LOCK.json records; CI never passes
   ``--network`` without a recorded authorisation.

Before any git command in a clone (an existing destination or a copied one) its repository-local configuration is
read without git (``repository_problems``): ``.git`` must be a plain directory without ``commondir`` or
``config.worktree``, and ``.git/config`` may carry only what ``git init``, ``git remote add`` and the authorised fetch
write (``core``: repositoryformatversion, filemode, ``bare`` false, logallrefupdates, ignorecase, precomposeunicode,
symlinks; ``remote.<name>``: url, fetch, tagopt; ``branch.<name>``: remote, merge; an empty ``credential.helper``;
``extensions.objectformat``).  Anything else (``core.fsmonitor``, a ``filter`` driver, ``core.worktree``, an
``include``, ...) could make git run code or read another tree, so the clone is refused and git never runs there.
Every git command also runs with ``core.fsmonitor`` off and an empty hooks directory, and without the caller's
``GIT_DIR``-style variables or environment configuration.

A new clone's work tree is then made read-only (``chmod -R a-w``, ``.git`` left writable) and ``LOCK.json`` in the
companions root is merged: an existing entry with the alias must repeat the repo_url, commit, path, profile and ref
(nothing is ever re-pinned) and must already list the package in ``needed_by`` (widening it is a reviewed LOCK.json
edit); a missing entry is written from the card (``needed_by`` the packages of this run that name it).

Exit code 0 when every companion is verified, 1 on a failure (nothing is removed), 2 on a usage error.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE = "LOCK.json"
_GITHUB_URL = re.compile(r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$")
_LOCK_ALIAS = re.compile(r"^[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+@[A-Za-z0-9_.+-]+$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
#: The LOCK.json fields an existing entry must repeat (no silent re-pin).
_PINNED = ("repo_url", "commit", "path", "profile", "ref")
#: The only repository-local git configuration a companion clone may carry (what git init, git remote add and the
#: authorised fetch write): section -> keys (lower case). Any other key is refused before git runs in the clone
#: (integrator edit I4, Claude Sonnet safety F4: a copied clone's own .git/config must not run code).
_CONFIG_ALLOWED = {
    "core": {"repositoryformatversion", "filemode", "bare", "logallrefupdates", "ignorecase", "precomposeunicode",
             "symlinks"},
    "remote": {"url", "fetch", "tagopt"},
    "branch": {"remote", "merge"},
    "credential": {"helper"},
    "extensions": {"objectformat"},
}
#: The sections that name a subsection (``[remote "origin"]``); the others must not.
_CONFIG_SUBSECTIONS = {"remote", "branch"}
_CONFIG_SECTION = re.compile(r'^\[\s*([A-Za-z0-9-]+)(?:\s+"((?:[^"\\\n]|\\.)*)")?\s*\]\s*(?:[#;].*)?$')
_CONFIG_KEY = re.compile(r"^([A-Za-z][A-Za-z0-9-]*)\s*(?:=\s*(.*))?$")
_FALSE = {"false", "no", "off", "0"}
#: The caller's variables that would point git at another repository or inject configuration.
_CALLER_GIT_ENV = ("GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT", "GIT_CONFIG", "GIT_DIR", "GIT_WORK_TREE",
                   "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                   "GIT_NAMESPACE")


class FetchError(Exception):
    """A companion could not be verified, copied or fetched (nothing was removed)."""


def git(*args: str, cwd: Path | None = None, hooks: Path | None = None) -> subprocess.CompletedProcess:
    """``git --no-optional-locks`` with the hardened environment of every command here (as ``fetch_clone.py``'s git()
    plus: no hooks, no credential helper, no prompt, no LFS smudge, no system or global configuration)."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_LFS_SKIP_SMUDGE="1",
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, LC_ALL="C")
    for name in list(env):
        if name in _CALLER_GIT_ENV or name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            env.pop(name)
    options = ["-c", f"core.hooksPath={hooks or os.devnull}", "-c", "credential.helper=", "-c", "core.fsmonitor=false"]
    return subprocess.run(["git", "--no-optional-locks", *options, *args], cwd=cwd, capture_output=True, text=True,
                          check=False, env=env, stdin=subprocess.DEVNULL)


def _config_value(raw: str | None) -> str:
    """A git config value as this check compares it: ``None`` (a bare key) is true, an inline comment and the quotes
    are dropped (a value with an escape is returned as it is and never matches a compared value)."""
    if raw is None:
        return "true"
    out, quoted = [], False
    for char in raw:
        if char == '"':
            quoted = not quoted
            continue
        if char in "#;" and not quoted:
            break
        out.append(char)
    return "".join(out).strip()


def repository_problems(clone: Path) -> list[str]:
    """Why git must not run in ``clone`` (read without git, before any git command there; empty when it may).

    ``.git`` must be a plain directory (no symbolic link, no ``gitdir:`` file), without ``commondir`` or
    ``config.worktree`` (git would read configuration elsewhere), and ``.git/config`` a regular file whose every key is
    in :data:`_CONFIG_ALLOWED`, with ``core.bare`` false, an empty ``credential.helper``, ``core.repositoryformatversion``
    0 or 1 and ``extensions.objectformat`` sha1 or sha256.  A line this reader does not follow (a continued line, a
    malformed section or key) is a problem too: the clone is refused, never repaired.
    """
    git_dir = clone / ".git"
    if git_dir.is_symlink() or not git_dir.is_dir():
        return [f"{clone}: .git is not a plain directory"]
    problems = [f"{clone}: .git/{name} exists (git would read configuration outside .git/config)"
                for name in ("commondir", "config.worktree") if os.path.lexists(git_dir / name)]
    config = git_dir / "config"
    if config.is_symlink() or not config.is_file():
        return problems + [f"{clone}: .git/config is not a regular file"]
    section: str | None = None
    for number, raw in enumerate(config.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        where = f"{clone}: .git/config:{number}"
        if line.endswith("\\"):
            problems.append(f"{where} continues a line, which this check does not follow")
            section = None
            continue
        if line.startswith("["):
            header = _CONFIG_SECTION.match(line)
            name = header.group(1).lower() if header else None
            if header is None or name not in _CONFIG_ALLOWED or \
                    (name in _CONFIG_SUBSECTIONS) != (header.group(2) is not None):
                problems.append(f"{where}: section {line[:80]!r} is not allowed in a companion clone")
                section = None
            else:
                section = name
            continue
        match = _CONFIG_KEY.match(line)
        if match is None or section is None or match.group(1).lower() not in _CONFIG_ALLOWED[section]:
            problems.append(f"{where}: {line[:80]!r} is not allowed in a companion clone (git could run code or read "
                            "another tree)")
            continue
        key, value = f"{section}.{match.group(1).lower()}", _config_value(match.group(2))
        if (key == "core.bare" and value.lower() not in _FALSE) or (key == "credential.helper" and value) or \
                (key == "core.repositoryformatversion" and value not in ("0", "1")) or \
                (key == "extensions.objectformat" and value.lower() not in ("sha1", "sha256")):
            problems.append(f"{where}: {key} = {value[:40]!r} is not allowed in a companion clone")
    return problems


def head_of(clone: Path) -> str | None:
    """The commit ``.git/HEAD`` names (a detached HEAD holds it; a symbolic one through its ref file or packed-refs)."""
    git_dir = clone / ".git"
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if _COMMIT.match(head):
        return head
    if not head.startswith("ref: ") or ".." in head[5:].split("/"):
        return None
    ref = head[5:].strip()
    try:
        value = (git_dir / ref).read_text(encoding="utf-8").strip()
        return value if _COMMIT.match(value) else None
    except OSError:
        pass
    try:
        for line in (git_dir / "packed-refs").read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == ref and _COMMIT.match(parts[0]):
                return parts[0]
    except OSError:
        pass
    return None


def writable_entries(clone: Path, limit: int = 5) -> list[str]:
    """Up to ``limit`` work-tree entries with a write bit (``.git`` excluded, symlinks not followed)."""
    found = ["."] if stat.S_IMODE(os.lstat(clone).st_mode) & 0o222 else []
    for directory, dirs, names in os.walk(clone):
        if Path(directory) == clone:
            dirs[:] = [item for item in dirs if item != ".git"]
        dirs.sort()
        for name in sorted(dirs) + sorted(names):
            info = os.lstat(os.path.join(directory, name))
            if not stat.S_ISLNK(info.st_mode) and stat.S_IMODE(info.st_mode) & 0o222:
                found.append(os.path.relpath(os.path.join(directory, name), clone))
            if len(found) >= limit:
                return found
    return found


def make_read_only(clone: Path, *, top: bool = True) -> None:
    """``chmod -R a-w`` of the work tree, ``.git`` left writable (the LOCK.json contract); symlinks are not followed.
    ``top=False`` leaves the clone directory itself writable (it still has to be renamed into place)."""
    for directory, dirs, names in os.walk(clone, topdown=False):
        if Path(directory).relative_to(clone).parts[:1] == (".git",):
            continue
        for name in names + dirs:
            full = os.path.join(directory, name)
            if Path(directory) == clone and name == ".git":
                continue
            info = os.lstat(full)
            if not stat.S_ISLNK(info.st_mode):
                os.chmod(full, stat.S_IMODE(info.st_mode) & ~0o222)
    if top:
        os.chmod(clone, stat.S_IMODE(os.lstat(clone).st_mode) & ~0o222)


def verify(clone: Path, commit: str, hooks: Path, *, fsck: bool = False, read_only: bool = True) -> list[str]:
    """What is wrong with ``clone`` as the pinned, clean (and read-only) checkout of ``commit``."""
    problems = []
    if not (clone / ".git").is_dir():
        return [f"{clone} is not a git checkout (no .git directory)"]
    unsafe = repository_problems(clone)
    if unsafe:
        # never run git where the repository's own configuration could run code (Claude Sonnet safety F4)
        return unsafe + [f"{clone}: git was not run there"]
    head = head_of(clone)
    if head != commit:
        problems.append(f"{clone}: HEAD is {str(head)[:12]}, not the pinned {commit[:12]}")
    status = git("status", "--porcelain", "--untracked-files=all", cwd=clone, hooks=hooks)
    if status.returncode != 0:
        problems.append(f"{clone}: git status failed: {status.stderr.strip()[-200:]}")
    elif status.stdout.strip():
        problems.append(f"{clone}: the work tree is not clean: {status.stdout.splitlines()[:3]}")
    if (clone / ".git" / "modules").exists():
        problems.append(f"{clone}: a submodule is initialised (.git/modules)")
    if fsck:
        checked = git("fsck", "--full", "--no-dangling", cwd=clone, hooks=hooks)
        if checked.returncode != 0:
            problems.append(f"{clone}: git fsck failed: {(checked.stderr or checked.stdout).strip()[-300:]}")
    if read_only:
        writable = writable_entries(clone)
        if writable:
            problems.append(f"{clone}: write bits in the work tree: {writable}")
    return problems


def copy_from(source_dir: Path, name: str, commit: str, dest: Path, hooks: Path) -> str:
    """Copy ``source_dir/<name>`` (a clone) or ``source_dir/<name>.bundle`` into place through a temporary sibling."""
    clone, bundle = source_dir / name, source_dir / f"{name}.bundle"
    if not clone.is_dir() and not bundle.is_file():
        raise FetchError(f"--from {source_dir}: neither {name}/ nor {name}.bundle exists")
    holder = Path(tempfile.mkdtemp(prefix=f".{name}.", dir=dest.parent))
    staged = holder / name
    if clone.is_dir():
        shutil.copytree(clone, staged, symlinks=True)
        for directory, dirs, names in os.walk(staged):
            for item in dirs + names:  # the source may be read-only; the staged copy must be checkable and movable
                full = os.path.join(directory, item)
                if not os.path.islink(full):
                    os.chmod(full, stat.S_IMODE(os.lstat(full).st_mode) | 0o200)
        os.chmod(staged, stat.S_IMODE(os.lstat(staged).st_mode) | 0o200)
        origin = f"from:{clone}"
    else:
        staged.mkdir()
        for step in (["init", "--quiet", "--template="], ["fetch", "--quiet", "--no-tags", str(bundle),
                                                           "+refs/*:refs/remotes/bundle/*"],
                     ["checkout", "--quiet", "--detach", commit]):
            done = git(*step, cwd=staged, hooks=hooks)
            if done.returncode != 0:
                raise FetchError(f"git {step[0]} of {bundle} failed: {done.stderr.strip()[-300:]} (the staged copy "
                                 f"stays in {holder})")
        origin = f"from:{bundle}"
    problems = verify(staged, commit, hooks, fsck=True, read_only=False)
    if problems:
        raise FetchError("; ".join(problems) + f" (the staged copy stays in {holder})")
    make_read_only(staged, top=False)
    os.rename(staged, dest)
    os.chmod(dest, stat.S_IMODE(os.lstat(dest).st_mode) & ~0o222)
    holder.rmdir()
    return origin


def fetch_network(repo_url: str, commit: str, dest: Path, hooks: Path) -> str:
    """One depth-1 fetch of ``commit`` from ``repo_url`` into a temporary sibling, verified, then renamed into place."""
    holder = Path(tempfile.mkdtemp(prefix=f".{dest.name}.", dir=dest.parent))
    staged = holder / dest.name
    staged.mkdir()
    for step in (["init", "--quiet", "--template="], ["remote", "add", "origin", repo_url],
                 ["fetch", "--quiet", "--depth", "1", "--no-tags", "origin", commit],
                 ["checkout", "--quiet", "--detach", "FETCH_HEAD"]):
        done = git(*step, cwd=staged, hooks=hooks)
        if done.returncode != 0:
            raise FetchError(f"git {step[0]} failed for {repo_url}: {done.stderr.strip()[-300:]} (the staged copy "
                             f"stays in {holder})")
    problems = verify(staged, commit, hooks, fsck=True, read_only=False)
    if problems:
        raise FetchError("; ".join(problems) + f" (the staged copy stays in {holder})")
    make_read_only(staged, top=False)
    os.rename(staged, dest)
    os.chmod(dest, stat.S_IMODE(os.lstat(dest).st_mode) & ~0o222)
    holder.rmdir()
    return repo_url


def lock_entries(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    clones = document.get("clones") if isinstance(document, dict) else None
    if not isinstance(clones, list):
        raise FetchError(f"{path}: clones is not a list")
    return {str(item.get("alias")): item for item in clones if isinstance(item, dict)}


def write_lock(path: Path, added: list[dict]) -> None:
    """Append ``added`` to ``path`` (created when missing); existing entries are never rewritten."""
    if path.is_file():
        document = json.loads(path.read_text(encoding="utf-8"))
    else:
        document = {"statement": "OpenMHS is an independent open-source project, not affiliated with or endorsed by "
                                 "Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS "
                                 "research preview.",
                    "title": "Companion source clones (read-only, one pinned commit each)",
                    "author": "tools/fetch_companions.py", "clones": []}
    document["clones"] = list(document.get("clones") or []) + added
    document["count"] = len(document["clones"])
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def card_wants(root: Path, target: str) -> list[dict]:
    """The lock companions of a driver directory's ``task.json`` (or a package id's registry card)."""
    path = Path(target) if Path(target).is_absolute() else root / target
    if path.is_dir() and (path / "task.json").is_file():
        card = json.loads((path / "task.json").read_text(encoding="utf-8"))
    elif target.startswith("gh."):
        name = target[3:].replace("/", "__")
        found = [root / "MHS" / "registry" / "tasks" / track / f"{name}.json" for track in ("labs", "robots")]
        found = [item for item in found if item.is_file()]
        if not found:
            raise FetchError(f"{target!r}: no registry card")
        card = json.loads(found[0].read_text(encoding="utf-8"))
    else:
        raise FetchError(f"{target!r} is neither a driver directory with task.json nor a package id")
    wants = []
    for item in card.get("companions") or []:
        if isinstance(item, dict) and "lock" in item:
            wants.append({"alias": item["lock"], "repo_url": item.get("repo_url"), "ref": item.get("ref"),
                          "commit": item.get("commit"), "path": item.get("local_path"), "profile": item.get("profile"),
                          "licence": item.get("licence_note") or item.get("license_spdx"),
                          "needed_by": [card.get("package_id")]})
    return wants


def check_want(want: dict) -> None:
    alias, commit, path = str(want.get("alias")), str(want.get("commit")), str(want.get("path"))
    match = _GITHUB_URL.match(str(want.get("repo_url")))
    if not _LOCK_ALIAS.match(alias) or not _COMMIT.match(commit) or match is None:
        raise FetchError(f"{alias}: needs a LOCK.json alias, a 40-hex commit and a https://github.com repo_url")
    expected = f"work/companions/{match.group('owner')}__{match.group('repo')}@{commit[:12]}"
    if path != expected:
        raise FetchError(f"{alias}: path {path!r} is not {expected!r}")


def run(wants: list[dict], companions_root: Path, source: Path | None, network: bool) -> int:
    companions_root.mkdir(parents=True, exist_ok=True)
    lock_path = companions_root / LOCK_FILE
    status = 0
    merged: dict[str, dict] = {}
    for want in wants:  # one entry per alias; needed_by is the union of this run's packages
        alias = str(want.get("alias"))
        if alias in merged:
            merged[alias]["needed_by"] = sorted(set(merged[alias]["needed_by"]) | set(want["needed_by"]))
        else:
            merged[alias] = dict(want)
    hooks = Path(tempfile.mkdtemp(prefix="mhs-fetch-companions-hooks-"))
    added: list[dict] = []
    try:
        existing = lock_entries(lock_path)
        for alias, want in merged.items():
            try:
                check_want(want)
                old = existing.get(alias)
                if old is not None:
                    differ = [key for key in _PINNED if old.get(key) != want.get(key)]
                    if differ:
                        raise FetchError(f"{alias}: {lock_path} already pins {', '.join(differ)} differently; this "
                                         "tool never re-pins (a reviewed LOCK.json edit)")
                    if not isinstance(old.get("needed_by"), list):
                        raise FetchError(f"{alias}: {lock_path} needed_by {old.get('needed_by')!r} is not a list (the "
                                         "gate refuses such an entry; correcting it is a reviewed LOCK.json edit)")
                    missing = [pid for pid in want["needed_by"] if pid not in old["needed_by"]]
                    if missing:
                        raise FetchError(f"{alias}: {lock_path} needed_by does not list {missing}; widening it is a "
                                         "reviewed LOCK.json edit")
                dest = companions_root / Path(str(want["path"])).name
                if dest.exists() or dest.is_symlink():
                    problems = verify(dest, str(want["commit"]), hooks)
                    if problems:
                        raise FetchError("; ".join(problems) + " (the existing directory is left as it is)")
                    origin = None
                    print(f"ok      {alias}: {dest} is at {str(want['commit'])[:12]}, clean and read-only")
                elif source is not None:
                    origin = copy_from(source, dest.name, str(want["commit"]), dest, hooks)
                    print(f"copied  {alias}: {dest} {origin}")
                elif network:
                    origin = fetch_network(str(want["repo_url"]), str(want["commit"]), dest, hooks)
                    print(f"fetched {alias}: {dest} from {origin}")
                else:
                    raise FetchError(f"{alias}: {dest} is missing; pass --from DIR (another workspace's "
                                     "work/companions or a <name>.bundle) or, with a recorded authorisation, --network")
                if old is None:
                    entry = {key: want.get(key) for key in ("alias", "repo_url", "ref", "commit", "path", "profile",
                                                            "licence", "needed_by")}
                    entry.update({"fetched_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                  "source": origin or f"existing:{dest}", "worktree_read_only": True})
                    added.append(entry)
            except FetchError as exc:
                print(f"error: {exc}", file=sys.stderr)
                status = 1
        if added:
            write_lock(lock_path, added)
            print(f"LOCK.json: {len(added)} entr{'y' if len(added) == 1 else 'ies'} added to {lock_path}")
    finally:
        shutil.rmtree(hooks, ignore_errors=True)
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("targets", nargs="*", help="driver directories or package ids (gh.owner/repo)")
    parser.add_argument("--lock", type=Path, help="a LOCK.json whose entries (all, or the ALIAS targets) are wanted")
    parser.add_argument("--from", dest="source", type=Path, help="another workspace's work/companions (or a directory "
                        "of <name>.bundle files) to copy from, offline (also MHS_COMPANIONS_FROM)")
    parser.add_argument("--network", action="store_true", help="fetch a missing clone from its repo_url (a "
                        "user-authorised act; never without a recorded authorisation)")
    parser.add_argument("--companions-root", type=Path, help="where the clones and LOCK.json live (default: "
                        "work/companions under --root)")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root (default: found from this file)")
    args = parser.parse_args(argv)
    if shutil.which("git") is None:
        print("error: git is required", file=sys.stderr)
        return 2
    root = args.root.resolve()
    companions_root = (args.companions_root or root / "work" / "companions").resolve()
    source = args.source or (Path(os.environ["MHS_COMPANIONS_FROM"]) if os.environ.get("MHS_COMPANIONS_FROM") else None)
    try:
        if args.lock is not None:
            entries = lock_entries(args.lock)
            names = args.targets or sorted(entries)
            unknown = [name for name in names if name not in entries]
            if unknown:
                parser.error(f"{args.lock} has no entries {unknown}")
            scopeless = [name for name in names if not isinstance(entries[name].get("needed_by"), list)]
            if scopeless:
                raise FetchError(f"{args.lock}: needed_by of {scopeless} is not a list (the gate refuses such an "
                                 "entry; correcting it is a reviewed LOCK.json edit)")
            wants = [dict(entries[name], needed_by=list(entries[name]["needed_by"])) for name in names]
        else:
            if not args.targets:
                parser.error("name a driver directory or a package id, or pass --lock FILE")
            wants = [want for target in args.targets for want in card_wants(root, target)]
            if not wants:
                print("nothing to do: the cards declare no fetched (lock) companion")
                return 0
    except (FetchError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return run(wants, companions_root, source.resolve() if source else None, args.network)


if __name__ == "__main__":
    sys.exit(main())
