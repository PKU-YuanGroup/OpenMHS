"""Read-only access to a driver's upstream clone at its pinned commit (gates G1, G2, G4, G7).

A task card may also declare companion sources (``companions``, user decision
of 2026-11-05): other corpus clones at their pinned commits, which only a
simulator package's stop, its read-back, its re-enable and its facts may cite,
as ``companion:<alias>/<path>:<LINE>`` (:func:`parse_source_ref`,
:func:`companion_sources`).  A companion entry that names ``lock`` is a clone
fetched at one pinned commit under ``work/companions/`` and listed in its
``LOCK.json`` (user authorisation of 2026-11-05; :func:`read_companion_lock`,
:func:`lock_entry_problems`), not a corpus record.  One further case, and only
when the user decided so for that package (decision 4, 2026-11-05): an entry
with ``hardware_stop`` true and ``lock`` may be cited by that hardware
package's stop and its fresh read-back.  Its profile is not a ROS profile, and
its ``ref`` is the full commit while the alias's text after ``@`` is that
commit's first 12 hex digits.

Nothing here imports or runs upstream code.  :class:`UpstreamTree` reads
files either from the git object store at the pinned commit (``git
cat-file`` / ``git grep`` / ``git ls-tree``, never a checkout, never a
write: ``--no-optional-locks``, and a hooks directory of its own, so that
the git-lfs a clone's filter starts installs no hook into the clone) or,
when the clone is not a git checkout (a
sandbox copy, the synthetic tutorial's ``vendor/`` directory), from the
working tree.  :func:`class_surface` parses the upstream class with
:mod:`ast` and lists every attribute it (and the bases it can follow inside
the clone) defines.  Python 2 source, which :mod:`ast` rejects, is read
leniently: the lines Python 3 cannot parse are left out and the surface
names the files read that way (:attr:`Surface.legacy`).

Git submodules (``SUBMODULES``, 2026-11-05).  A path that crosses a gitlink of
the pinned tree (``<submodule path>/...``) is read from the submodule's own
object store at the commit that gitlink records, and only when the submodule
is declared in the pinned ``.gitmodules``, checked out (its ``.git`` file names
``.git/modules/<name>``, or its ``.git`` is a directory), its ``HEAD`` (read
from the file, not by git) equals the gitlink and its store holds that
commit.  Anything else fails closed: the read returns ``None`` and
:attr:`UpstreamTree.submodule_refusals` says why.  :attr:`UpstreamTree.submodules`
lists every submodule a read went into.  :meth:`UpstreamTree.files` and
:meth:`UpstreamTree.grep` stay those of the clone's own tree.
"""

from __future__ import annotations

import ast
import atexit
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

__all__ = ["COMPANION_ALIAS", "COMPANION_LOCK_ALIAS", "COMPANION_LOCK_FILE", "COMPANION_PREFIX", "REF_PATTERN",
           "CompanionSource", "Ref", "Submodule", "Surface", "UpstreamTree", "class_surface", "companion_sources",
           "definition_surface", "is_companion_ref", "lock_entry_problems", "lock_package_id", "parse_ref",
           "parse_source_ref", "read_companion_lock"]

#: ``path/in/clone:LINE`` or ``path:FIRST-LAST`` (a provenance reference).
REF_PATTERN = re.compile(r"^(?P<path>[^:\s][^:]*?):(?P<line>[1-9][0-9]*)(?:-(?P<end>[1-9][0-9]*))?$")
#: The prefix of a citation into a declared companion source: ``companion:<alias>/<path>:<LINE>[-<END>]``.
#: :data:`REF_PATTERN` refuses it (the prefix holds a colon), so a check that was not taught the prefix fails closed.
COMPANION_PREFIX = "companion:"
#: A companion alias as the task card declares it (``companions[].alias``).
COMPANION_ALIAS = re.compile(r"^[a-z][a-z0-9_-]{1,39}$")
_COMPANION_REF = re.compile(r"^companion:(?P<alias>[^/\s]*)/(?P<rest>\S.*)$")
#: ``<generation>-<distro>-<simulator release>`` of a companion (``ros1-noetic-gazebo11``).
COMPANION_PROFILE = re.compile(r"^ros[12]-(?P<distro>[a-z]+)-[a-z0-9.+-]+$")
#: A non-ROS profile of a user-authorized hardware stop (``micromanager-2.0-gamma-20230120``).
#: It does not match :data:`COMPANION_PROFILE`: a ROS companion never sets ``hardware_stop``.
HARDWARE_STOP_PROFILE = re.compile(r"^(?!ros[12]-)[a-z][a-z0-9.+-]{1,80}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_LOCAL_PATH = re.compile(r"^(labs|robots)/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
#: How deep reads follow git submodules: a submodule of the clone is depth 1, a submodule of that submodule depth 2.
_MAX_SUBMODULE_DEPTH = 2
#: A full object id: SHA-1 (40 hex digits) or SHA-256 (64).
_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_GITMODULES_HEADER = re.compile(r'^\[\s*submodule\s+"((?:[^"\\]|\\.)*)"\s*\]$')
_GITMODULES_PATH = re.compile(r"^path\s*=\s*(.*)$", re.IGNORECASE)
_GITMODULES_MAX = 256 * 1024
#: The ``LOCK.json`` alias of a fetched companion clone (``companions[].lock``): ``<owner>__<repo>@<ref>``.
COMPANION_LOCK_ALIAS = re.compile(r"^[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+@[A-Za-z0-9_.+-]+$")
#: The bookkeeping file of the fetched companion clones, in the companions root (``work/companions/LOCK.json``).
COMPANION_LOCK_FILE = "LOCK.json"
#: Where a fetched companion clone lives: ``work/companions/<owner>__<repo>@<first 12 hex of the commit>``.
_LOCK_LOCAL_PATH = re.compile(r"^work/companions/(?P<name>[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+)@(?P<short>[0-9a-f]{12})$")
_GITHUB_URL = re.compile(r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$")
#: At most this many write-bit entries are listed by :meth:`UpstreamTree.writable_entries`.
_WRITABLE_SHOWN = 5
_GIT_TIMEOUT_S = 60
_MAX_FILES = 200_000
_MAX_BLOB = 8 * 1024 * 1024
#: Bases that add no attributes a fake could need (or that the AST cannot follow but are harmless).
_PLAIN_BASES = frozenset({"object", "ABC", "abc.ABC", "Generic", "typing.Generic", "Protocol", "typing.Protocol"})
_SOURCE_ROOTS = ("", "src/", "lib/", "python/", "py/")
_HOOKS_LOCK = threading.Lock()
_HOOKS_DIR: list[str] = []  # the empty hooks directory of this process's git commands, made on first use


def _git_env() -> dict[str, str]:
    """The environment of every git command here: no lock, no prompt, the C locale, and no clone's hooks directory.

    git runs a clone's own filters (``git status`` over a Git LFS file starts git-lfs), and git-lfs installs its hooks
    into the hooks directory when they are missing: a gate run wrote four hooks into a clone's ``.git/hooks`` that way
    (wave D). ``core.hooksPath`` therefore names an empty temporary directory of this process, passed in
    ``GIT_CONFIG_PARAMETERS`` (the variable of ``git -c``) after the caller's own entries.
    """
    with _HOOKS_LOCK:
        if not _HOOKS_DIR:
            _HOOKS_DIR.append(tempfile.mkdtemp(prefix="mhs-git-hooks-"))
            atexit.register(shutil.rmtree, _HOOKS_DIR[0], ignore_errors=True)
    entry = "'" + f"core.hooksPath={_HOOKS_DIR[0]}".replace("'", "'\\''") + "'"
    env = dict(os.environ)
    previous = env.get("GIT_CONFIG_PARAMETERS", "").strip()
    env.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C",
                "GIT_CONFIG_PARAMETERS": f"{previous} {entry}" if previous else entry})
    return env


@dataclass(frozen=True)
class Ref:
    path: str
    line: int
    end: int

    def __str__(self) -> str:
        return f"{self.path}:{self.line}" + (f"-{self.end}" if self.end != self.line else "")


def parse_ref(text: Any) -> Ref | None:
    """``Ref`` for ``"path:LINE"`` / ``"path:FIRST-LAST"`` (``None`` when ``text`` is not such a reference)."""
    if not isinstance(text, str):
        return None
    match = REF_PATTERN.match(text.strip())
    if match is None:
        return None
    line = int(match.group("line"))
    end = int(match.group("end") or line)
    if end < line:
        return None
    return Ref(match.group("path"), line, end)


def safe_relpath(path: str) -> str | None:
    """``path`` as a clean relative POSIX path, or ``None`` when it is absolute or leaves the clone."""
    if not path or "\\" in path or path.startswith("/"):
        return None
    parts = PurePosixPath(path).parts
    if any(part == ".." for part in parts):
        return None
    clean = "/".join(part for part in parts if part not in (".", ""))
    return clean or None


def is_companion_ref(text: Any) -> bool:
    """True when ``text`` is written as a companion citation (``companion:...``), well formed or not."""
    return isinstance(text, str) and text.strip().startswith(COMPANION_PREFIX)


def parse_source_ref(text: Any) -> tuple[str | None, Ref] | None:
    """``(alias, Ref)`` for ``companion:<alias>/<path>:<LINE>[-<END>]``, ``(None, Ref)`` for a clone ``path:LINE``.

    ``None`` when ``text`` is neither. A companion citation needs an alias of the card's form
    (:data:`COMPANION_ALIAS`) and a path that is already clean and relative (:func:`safe_relpath` returns it
    unchanged): no ``..``, no ``./``, no doubled or leading slash. Whether the alias is declared, and the scope a
    companion citation may appear in, are the gate's checks (user decision of 2026-11-05: only a reviewed card
    declares a companion). A clone citation is returned exactly as :func:`parse_ref` returns it.
    """
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if not stripped.startswith(COMPANION_PREFIX):
        ref = parse_ref(stripped)
        return (None, ref) if ref is not None else None
    match = _COMPANION_REF.match(stripped)
    if match is None or not COMPANION_ALIAS.match(match.group("alias")):
        return None
    ref = parse_ref(match.group("rest"))
    if ref is None or safe_relpath(ref.path) != ref.path:
        return None
    return match.group("alias"), ref


@dataclass
class CompanionSource:
    """One companion source a task card declares (``companions``): a clone read at its pinned commit.

    A corpus companion is a corpus clone under ``labs/`` or ``robots/``. A lock companion (``lock`` set) is a clone
    fetched under ``work/companions/`` and listed in the ``LOCK.json`` of :attr:`lock_root` under its ``lock`` alias.
    ``tree`` is ``None`` when the clone directory is missing (G1 ``NO_COMPANION_CLONE``); ``problems`` lists what is
    wrong with the card entry itself (G1 ``COMPANION_CARD``).
    """

    alias: str
    package_id: str
    commit: str
    profile: str
    local_path: str
    path: Path | None
    tree: "UpstreamTree | None"
    evidence: list[Mapping[str, Any]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    #: the ``LOCK.json`` alias of a fetched companion clone (``None`` for a corpus companion)
    lock: str | None = None
    #: the ref the clone was fetched at (``LOCK.json`` ``ref``, a tag or branch name), as the card copies it
    ref: str | None = None
    #: the directory that holds ``LOCK.json`` and the fetched clone (``work/companions`` or ``--companions-root``)
    lock_root: Path | None = None
    #: user decision 4 (2026-11-05): this lock companion may be cited by one hardware package's stop
    hardware_stop: bool = False

    @property
    def label(self) -> str:
        return f"{self.alias}@{self.commit[:12]}"


def companion_sources(card: Mapping[str, Any], base: Path | None,
                      companions_root: Path | None = None) -> tuple[dict[str, CompanionSource], list[str]]:
    """The companion sources of a task card, keyed by alias, and the problems of the ``companions`` field.

    ``base`` is the directory the card's ``local_path`` values are relative to (the project root). A card without
    ``companions`` gives ``({}, [])``. Each entry needs a unique alias, a ``package_id`` other than the card's own,
    a 40-hex ``commit``, a ROS profile and a version-evidence list, and a ``local_path`` under ``labs/`` or ``robots/``;
    an entry with ``lock`` (a ``LOCK.json`` alias) instead needs the local path
    ``work/companions/<owner>__<repo>@<first 12 hex of commit>`` and a ``ref`` equal to the text of ``lock`` after
    ``@``. An entry with ``hardware_stop`` true (user decision 4, 2026-11-05) is a lock entry whose profile is not a
    ROS profile, whose card ``family`` is ``direct`` or ``python-object`` and whose ``safety.expected_mode`` is
    ``hardware``, and whose ``ref`` is the full commit while the text of ``lock`` after ``@`` is that commit's first
    12 hex digits. An entry that lacks one is reported and left out (so
    nothing it would cite resolves). At most three entries. ``companions_root`` (the gate's ``--companions-root``)
    replaces the directory of a lock entry's local path: its clone is ``companions_root/<basename>`` and its
    ``LOCK.json`` is ``companions_root/LOCK.json``; corpus entries are read from ``base`` as always.
    """
    raw = card.get("companions") if isinstance(card, Mapping) else None
    if raw is None:
        return {}, []
    problems: list[str] = []
    out: dict[str, CompanionSource] = {}
    if not isinstance(raw, list) or not 1 <= len(raw) <= 3:
        return {}, ["companions must be a list of 1 to 3 entries"]
    for index, item in enumerate(raw):
        where = f"companions[{index}]"
        if not isinstance(item, Mapping):
            problems.append(f"{where} is not an object")
            continue
        alias, package_id, commit = item.get("alias"), item.get("package_id"), item.get("commit")
        profile, local_path = item.get("profile"), item.get("local_path")
        evidence = item.get("version_evidence")
        locked = "lock" in item
        lock, ref = item.get("lock"), item.get("ref")
        hardware_stop = item.get("hardware_stop") is True
        wrong = []
        if not isinstance(alias, str) or not COMPANION_ALIAS.match(alias):
            wrong.append("alias")
        if not isinstance(package_id, str) or not package_id.startswith("gh.") or package_id == card.get("package_id"):
            wrong.append("package_id (a repository other than the card's own)")
        if not isinstance(commit, str) or not _COMMIT.match(commit):
            wrong.append("commit")
        if "hardware_stop" in item and item.get("hardware_stop") is not True:
            wrong.append("hardware_stop (exactly true, or omit it)")
        if hardware_stop and not locked:
            wrong.append("hardware_stop (only together with lock)")
        if hardware_stop:
            if not isinstance(profile, str) or HARDWARE_STOP_PROFILE.match(profile) is None:
                wrong.append("profile (a non-ROS hardware-stop profile)")
            safety = card.get("safety") if isinstance(card.get("safety"), Mapping) else {}
            if safety.get("expected_mode") != "hardware":
                wrong.append("hardware_stop (safety.expected_mode must be hardware)")
            if card.get("family") not in ("direct", "python-object"):
                wrong.append("hardware_stop (family must be direct or python-object)")
        elif not isinstance(profile, str) or not COMPANION_PROFILE.match(profile):
            wrong.append("profile")
        if locked:
            if not isinstance(lock, str) or not COMPANION_LOCK_ALIAS.match(lock):
                wrong.append("lock (a LOCK.json alias <owner>__<repo>@<ref>)")
            suffix = lock.partition("@")[2] if isinstance(lock, str) else ""
            if hardware_stop:
                if not (isinstance(ref, str) and isinstance(commit, str) and _COMMIT.match(ref)
                        and ref == commit and suffix == commit[:12]):
                    wrong.append("ref (the full commit; the text of lock after '@' is its first 12 hex digits)")
            elif not isinstance(ref, str) or not ref or ref != suffix:
                wrong.append("ref (the text of lock after '@')")
            matched = _LOCK_LOCAL_PATH.match(local_path) if isinstance(local_path, str) else None
            if matched is None or not isinstance(commit, str) or matched.group("short") != commit[:12]:
                wrong.append("local_path (work/companions/<owner>__<repo>@<first 12 hex of commit>)")
        elif not isinstance(local_path, str) or not _LOCAL_PATH.match(local_path):
            wrong.append("local_path")
        if not isinstance(evidence, list) or not all(isinstance(entry, Mapping) for entry in evidence):
            wrong.append("version_evidence")
        if wrong:
            problems.append(f"{where}: invalid {', '.join(wrong)}")
            continue
        if alias in out:
            problems.append(f"{where}: alias {alias!r} is declared twice")
            continue
        home = Path(base) if base is not None else Path.cwd()
        lock_root = None
        if locked:
            lock_root = Path(companions_root) if companions_root is not None else home / PurePosixPath(local_path).parent
            path = lock_root / PurePosixPath(local_path).name
        else:
            path = home / local_path
        tree = UpstreamTree(path, commit) if path.is_dir() else None
        out[alias] = CompanionSource(alias, package_id, commit, profile, local_path, path, tree,
                                     [dict(entry) for entry in evidence], lock=lock if locked else None,
                                     ref=ref if locked else None, lock_root=lock_root, hardware_stop=hardware_stop)
    return out, problems


@dataclass(frozen=True)
class Submodule:
    """A git submodule that a pinned clone records as a gitlink, read at the commit the gitlink names."""

    #: where the gitlink is, relative to the clone root (a nested submodule: the full path from the clone root)
    path: str
    #: the submodule's name in the ``.gitmodules`` of the tree that records the gitlink, at that tree's commit
    name: str
    #: the gitlink: the submodule commit that the pinned tree records, and the only commit read
    commit: str
    #: the submodule's own git directory (its object store), relative to the clone root
    git_dir: str


def _parse_gitmodules(text: str) -> tuple[dict[str, str], list[str]]:
    """``({path: name}, problems)`` of a ``.gitmodules`` file (git config syntax, read without git).

    Only ``[submodule "<name>"]`` sections and their ``path`` keys matter. A name or path that is not a clean relative
    path, a section with two paths, a path claimed by two names and a continued line are problems, and the paths they
    concern are left out (fail closed).
    """
    paths: dict[str, list[str]] = {}
    problems: list[str] = []
    seen_names: dict[str, int] = {}
    current: str | None = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.endswith("\\"):
            problems.append(f".gitmodules:{number} continues a line, which this reader does not follow")
            current = None
            continue
        if line.startswith("["):
            header = _GITMODULES_HEADER.match(line)
            current = re.sub(r"\\(.)", r"\1", header.group(1)) if header else None
            if current is not None:
                seen_names[current] = seen_names.get(current, 0) + 1
            continue
        match = _GITMODULES_PATH.match(line)
        if current is None or match is None:
            continue
        value = match.group(1).strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = re.sub(r"\\(.)", r"\1", value[1:-1])
        paths.setdefault(current, []).append(value)
    out: dict[str, str] = {}
    claimed: dict[str, list[str]] = {}
    for name, values in paths.items():
        clean_name = safe_relpath(name)
        if seen_names.get(name, 0) != 1 or len(values) != 1:
            problems.append(f"submodule {name!r} has {len(values)} paths in {seen_names.get(name, 0)} sections")
            continue
        path = safe_relpath(values[0])
        if clean_name != name or path is None or path != values[0].rstrip("/") or "\0" in name:
            problems.append(f"submodule {name!r} has a name or path that is not a clean relative path")
            continue
        claimed.setdefault(path, []).append(name)
    for path, names in claimed.items():
        if len(names) == 1:
            out[path] = names[0]
        else:
            problems.append(f"{path} is the path of several submodules {sorted(names)}")
    return out, problems


def _read_head(git_dir: Path) -> str | None:
    """The commit ``git_dir/HEAD`` names, read from the files (a detached id, or a loose or packed ref), or None."""
    try:
        head = git_dir / "HEAD"
        if head.is_symlink() or not head.is_file():
            return None
        text = head.read_text(encoding="utf-8", errors="replace").strip()
        if _OBJECT_ID.match(text):
            return text
        if not text.startswith("ref:"):
            return None
        ref = text[4:].strip()
        parts = ref.split("/")
        if not ref.startswith("refs/") or any(part in ("", ".", "..") for part in parts) or "\\" in ref:
            return None
        loose = git_dir.joinpath(*parts)
        if loose.is_file() and not loose.is_symlink():
            value = loose.read_text(encoding="utf-8", errors="replace").strip()
            return value if _OBJECT_ID.match(value) else None
        packed = git_dir / "packed-refs"
        if packed.is_file() and not packed.is_symlink():
            for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith(("#", "^")):
                    continue
                value, _, name = line.partition(" ")
                if name.strip() == ref:
                    return value if _OBJECT_ID.match(value) else None
    except OSError:
        return None
    return None


def lock_package_id(repo_url: Any) -> str | None:
    """``gh.<owner>/<repo>`` (lower case) of a ``https://github.com/<owner>/<repo>[.git]`` URL, else ``None``."""
    match = _GITHUB_URL.match(repo_url) if isinstance(repo_url, str) else None
    if match is None:
        return None
    return f"gh.{match.group('owner')}/{match.group('repo')}".lower()


def read_companion_lock(root: Path | None) -> tuple[dict[str, Mapping[str, Any]] | None, str | None]:
    """``({alias: entry}, None)`` from ``root/LOCK.json`` (the fetched companion clones), or ``(None, problem)``.

    The file is bookkeeping of the user-authorised fetch (``work/companions/``): ``{"clones": [{alias, repo_url,
    ref, commit, path, profile, needed_by, ...}]}``. A missing or unreadable file, a ``clones`` that is not a list of
    objects with a string alias, or an alias listed twice is a problem: the companions that name it fail closed.
    """
    if root is None:
        return None, "no companions root (work/companions or --companions-root) is known"
    path = Path(root) / COMPANION_LOCK_FILE
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"{path} does not exist"
    except (OSError, ValueError) as exc:
        return None, f"{path} cannot be read ({type(exc).__name__}: {exc})"
    clones = document.get("clones") if isinstance(document, Mapping) else None
    if not isinstance(clones, list) or not all(isinstance(entry, Mapping) and isinstance(entry.get("alias"), str)
                                               for entry in clones):
        return None, f"{path}: clones must be a list of objects with an alias"
    out: dict[str, Mapping[str, Any]] = {}
    for entry in clones:
        if entry["alias"] in out:
            return None, f"{path}: alias {entry['alias']!r} is listed twice"
        out[entry["alias"]] = entry
    return out, None


def lock_entry_problems(source: CompanionSource, entry: Mapping[str, Any] | None, package_id: Any) -> list[str]:
    """What keeps a lock companion of the card ``package_id`` from matching its ``LOCK.json`` entry ``entry``.

    The entry must exist and repeat the card: the same commit, path (``work/companions/<owner>__<repo>@<commit12>``),
    profile and ref; its ``repo_url`` must name the card's ``package_id`` (``gh.<owner>/<repo>``, lower case); and the
    card's own package must be in its ``needed_by``, the scope the fetch was authorised for (a clone fetched for other
    packages is not borrowed silently; widening ``needed_by`` is a reviewed LOCK.json edit).
    """
    if entry is None:
        return [f"LOCK.json has no entry {source.lock!r}"]
    problems = []
    for key, value in (("commit", source.commit), ("path", source.local_path), ("profile", source.profile),
                       ("ref", source.ref)):
        if entry.get(key) != value:
            problems.append(f"LOCK.json {key} {entry.get(key)!r} differs from the card's {value!r}")
    named = lock_package_id(entry.get("repo_url"))
    if named != source.package_id:
        problems.append(f"LOCK.json repo_url {entry.get('repo_url')!r} names {named!r}, not the card's "
                        f"package_id {source.package_id!r}")
    needed = entry.get("needed_by")
    if not isinstance(needed, list) or package_id not in needed:
        problems.append(f"{package_id!r} is not in the LOCK.json needed_by {needed!r} (the clone was fetched for "
                        "other packages)")
    return problems


class UpstreamTree:
    """One upstream source tree: a git clone read at ``commit``, or a plain directory."""

    def __init__(self, root: Path, commit: str | None = None, *, use_git: bool = True):
        self._init_state(Path(root), commit, shutil.which("git") if use_git else None)
        if use_git and self._git and (self.root / ".git").exists():
            top = self._run("rev-parse", "--show-toplevel")
            if top is not None and Path(top.strip()).resolve() == self.root.resolve():
                self.kind = "git"
            else:
                self.notes.append(f"{self.root} is not the top of a git checkout; reading the working tree")
        elif use_git and not self._git and (self.root / ".git").exists():
            self.notes.append("git is not installed; reading the working tree instead of the pinned commit")

    def _init_state(self, root: Path, commit: str | None, git: str | None) -> None:
        self.root = root
        self.commit = commit
        self.kind = "worktree"
        self.notes: list[str] = []
        self._git = git
        self._files: list[str] | None = None
        self._blobs: dict[str, bytes | None] = {}
        self._pinned: bool | None = None
        #: a submodule's tree reads its own git directory (``--git-dir``) instead of discovering one under ``root``
        self._git_dir: Path | None = None
        self._depth = 0
        self._prefix = ""  # this tree's path from the outermost clone root ("" for the clone itself)
        self._outer: UpstreamTree = self
        self._gitmodules: dict[str, str] | None = None
        self._gitlinks: dict[str, str | None] = {}
        self._children: dict[str, tuple[UpstreamTree | None, str | None]] = {}
        self._record: Submodule | None = None  # what this tree is, when it is a submodule's tree
        #: full path -> :class:`Submodule` for every git submodule a read went into (kept on the outermost tree)
        self.submodules: dict[str, Submodule] = {}
        #: full path -> why reads under that git submodule were refused (kept on the outermost tree)
        self.submodule_refusals: dict[str, str] = {}

    # -- git ------------------------------------------------------------------
    def _git_location(self) -> list[str]:
        if self._git_dir is not None:
            return [f"--git-dir={self._git_dir}"]
        return ["-C", str(self.root)]

    def _run(self, *args: str, binary: bool = False) -> Any:
        if not self._git:
            return None
        env = _git_env()
        try:
            done = subprocess.run([self._git, "--no-optional-locks", *self._git_location(), *args],
                                  capture_output=True, timeout=_GIT_TIMEOUT_S, env=env, check=False,
                                  stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            return None
        if done.returncode != 0:
            return None
        if binary:
            return done.stdout
        return done.stdout.decode("utf-8", "replace")

    @property
    def is_git(self) -> bool:
        return self.kind == "git"

    def head(self) -> str | None:
        if not self.is_git:
            return None
        out = self._run("rev-parse", "HEAD")
        return out.strip() if out else None

    def has_commit(self, commit: str | None = None) -> bool:
        sha = commit or self.commit
        if not self.is_git or not sha:
            return False
        return self._run("cat-file", "-e", f"{sha}^{{commit}}") is not None

    def modified(self, *, untracked: bool = False) -> list[str] | None:
        """Tracked files that differ from ``HEAD`` (``None`` when unknown); with ``untracked`` also every untracked
        file (``git status --porcelain --untracked-files=all``, listed as ``?? <path>``).

        In a checkout on a case-insensitive file system, tracked paths that differ only in case share one file, and
        all but one of them read as modified; they are left out while the file holds the content of one of them.
        """
        if not self.is_git:
            return None
        out = self._run("status", "--porcelain", "--untracked-files=all" if untracked else "--untracked-files=no")
        if out is None:
            return None
        lines = [line for line in out.splitlines() if line.strip()]
        changed = [line[3:] for line in lines if not line.startswith("??")]
        shared = self._case_shared(changed)
        return [path for path in changed if path not in shared] + [line for line in lines if line.startswith("??")]

    def writable_entries(self, limit: int = _WRITABLE_SHOWN) -> list[str]:
        """Up to ``limit`` entries of the work tree with a write bit (``.git`` excluded, symlinks not followed).

        A fetched companion clone is kept read-only (``chmod -R a-w`` of its work tree, ``work/companions/LOCK.json``):
        a write bit anywhere is a sign that something may have changed it. ``lstat`` only: no file is opened.
        """
        found: list[str] = []
        root = self.root
        try:
            if stat.S_IMODE(os.lstat(root).st_mode) & 0o222:
                found.append(".")
        except OSError:
            return ["."]
        for directory, dirs, names in os.walk(root):
            if Path(directory) == root:
                dirs[:] = [item for item in dirs if item != ".git"]
            dirs.sort()
            for name in sorted(dirs) + sorted(names):
                full = os.path.join(directory, name)
                try:
                    info = os.lstat(full)
                except OSError:
                    found.append(os.path.relpath(full, root))
                    continue
                if stat.S_ISLNK(info.st_mode):
                    continue
                if stat.S_IMODE(info.st_mode) & 0o222:
                    found.append(Path(os.path.relpath(full, root)).as_posix())
                if len(found) >= limit:
                    return found
        return found

    def _case_shared(self, changed: list[str]) -> set[str]:
        """The tracked paths that share one file with a path of ``changed`` and whose content that file holds."""
        if not changed or (self._run("config", "--get", "core.ignorecase") or "").strip() != "true":
            return set()
        blobs: dict[str, dict[str, str]] = {}
        for line in (self._run("ls-files", "-s", "-z") or "").split("\0"):
            meta, _, path = line.partition("\t")
            fields = meta.split()
            if len(fields) == 3:
                blobs.setdefault(path.lower(), {})[path] = fields[1]
        shared: set[str] = set()
        for path in changed:
            group = blobs.get(path.lower(), {})
            if len(group) > 1 and path not in shared:
                held = (self._run("hash-object", "--", path) or "").strip()
                if held in group.values():
                    shared.update(group)
        note = (f"{len(shared)} tracked paths share files with paths that differ only in case (this file system "
                f"ignores case), e.g. {sorted(shared)[:2]}: not reported as modified while each file holds the "
                "content of one of its paths")
        if shared and note not in self.notes:
            self.notes.append(note)
        return shared

    @property
    def pinned(self) -> bool:
        """True when files are read from the git object store at :attr:`commit` (asked of git once per tree)."""
        if self._pinned is None:
            self._pinned = self.is_git and bool(self.commit) and self.has_commit()
        return self._pinned

    # -- files ----------------------------------------------------------------
    def read_bytes(self, path: str) -> bytes | None:
        rel = safe_relpath(path)
        if rel is None:
            return None
        if rel in self._blobs:
            return self._blobs[rel]
        data: bytes | None = None
        if self.pinned:
            data = self._run("cat-file", "blob", f"{self.commit}:{rel}", binary=True)
            if data is None:
                data = self._read_in_submodule(rel)
        else:
            target = self.root / rel
            try:
                resolved = target.resolve()
                if resolved.is_file() and (resolved == self.root.resolve() or self.root.resolve() in resolved.parents):
                    if resolved.stat().st_size <= _MAX_BLOB:
                        data = resolved.read_bytes()
            except OSError:
                data = None
        self._blobs[rel] = data
        return data

    def read_text(self, path: str) -> str | None:
        data = self.read_bytes(path)
        if data is None or b"\0" in data[:4096]:
            return None
        return data.decode("utf-8", "replace")

    def exists(self, path: str) -> bool:
        return self.read_bytes(path) is not None

    def files(self) -> list[str]:
        """Every file path of the tree (bounded)."""
        if self._files is not None:
            return self._files
        out: list[str] = []
        if self.pinned:
            listing = self._run("ls-tree", "-r", "--name-only", str(self.commit))
            out = (listing or "").splitlines()[:_MAX_FILES]
        else:
            root = self.root.resolve()
            for directory, dirs, names in os.walk(root):
                dirs[:] = sorted(item for item in dirs if not item.startswith(".") and item != "__pycache__")
                for name in sorted(names):
                    out.append((Path(directory) / name).relative_to(root).as_posix())
                    if len(out) >= _MAX_FILES:
                        break
                if len(out) >= _MAX_FILES:
                    break
        self._files = out
        return out

    def grep(self, token: str) -> bool:
        """True when ``token`` occurs (case-insensitive, fixed string) in a text file of the tree."""
        if not token:
            return False
        if self.pinned:
            code = self._status("grep", "-I", "-i", "-F", "-q", "-e", token, str(self.commit), "--")
            if code in (0, 1):
                return code == 0
        needle = token.lower()
        for path in self.files():
            text = self.read_text(path)
            if text is not None and needle in text.lower():
                return True
        return False

    def _status(self, *args: str) -> int | None:
        if not self._git:
            return None
        env = _git_env()
        try:
            done = subprocess.run([self._git, "--no-optional-locks", *self._git_location(), *args],
                                  capture_output=True, timeout=_GIT_TIMEOUT_S, env=env, check=False,
                                  stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            return None
        return done.returncode

    # -- git submodules ---------------------------------------------------------
    def submodule_paths(self) -> list[str]:
        """The submodule paths that the pinned ``.gitmodules`` of this tree declares (sorted; empty when unpinned)."""
        return sorted(self._declared_submodules())

    def _declared_submodules(self) -> dict[str, str]:
        if self._gitmodules is None:
            self._gitmodules = {}
            if self.pinned:
                data = self._run("cat-file", "blob", f"{self.commit}:.gitmodules", binary=True)
                if data is not None and len(data) <= _GITMODULES_MAX and b"\0" not in data:
                    self._gitmodules, _problems = _parse_gitmodules(data.decode("utf-8", "replace"))
        return self._gitmodules

    def _gitlink(self, path: str) -> str | None:
        """The commit the pinned tree records at ``path`` when that entry is a gitlink (mode 160000), else None."""
        if path not in self._gitlinks:
            listing = self._run("--literal-pathspecs", "ls-tree", "-z", str(self.commit), "--", path)
            found = []
            for entry in (listing or "").split("\0"):
                meta, sep, name = entry.partition("\t")
                fields = meta.split()
                if sep and name == path and len(fields) == 3:
                    found.append(fields)
            ok = len(found) == 1 and found[0][0] == "160000" and found[0][1] == "commit" \
                and _OBJECT_ID.match(found[0][2]) is not None
            self._gitlinks[path] = found[0][2] if ok else None
        return self._gitlinks[path]

    def _modules_dir(self) -> Path | None:
        """Where this tree's git keeps its submodules' git directories (``<git dir>/modules``)."""
        if self._git_dir is not None:
            return self._git_dir / "modules"
        git = self.root / ".git"
        if git.is_dir() and not git.is_symlink():
            return git / "modules"
        return None

    def locate_submodule(self, path: str) -> tuple[UpstreamTree, str] | None:
        """``(tree, inner path)`` when ``path`` lies in a readable git submodule of this pinned tree, else None.

        The submodule is read only at the commit its gitlink records, and only when it is declared in the pinned
        ``.gitmodules``, checked out, at that commit (``HEAD`` read from its git directory) and its object store holds
        the commit; otherwise the reason is recorded in :attr:`submodule_refusals` of the outermost tree.
        """
        rel = safe_relpath(path)
        if rel is None or not self.pinned or self._depth >= _MAX_SUBMODULE_DEPTH:
            return None
        declared = self._declared_submodules()
        candidates = sorted((item for item in declared if rel.startswith(item + "/")), key=len)
        if not candidates:
            return None
        links = [(item, self._gitlink(item)) for item in candidates]
        links = [(item, commit) for item, commit in links if commit is not None]
        if len(links) != 1:
            self._refuse(candidates[0], f"{candidates[0]} is declared in the pinned .gitmodules, but the pinned tree "
                         f"{str(self.commit)[:12]} records no gitlink there")
            return None
        sub, commit = links[0]
        child = self._child(sub, declared[sub], commit)
        if child is None:
            return None
        return child, rel[len(sub) + 1:]

    def refusal_for(self, path: str) -> str | None:
        """Why a read of ``path`` was refused inside a git submodule (the deepest refused one it lies in), or None."""
        rel = safe_relpath(path)
        if rel is None:
            return None
        found = [item for item in self._outer.submodule_refusals if rel.startswith(item + "/")]
        return self._outer.submodule_refusals[max(found, key=len)] if found else None

    def _refuse(self, path: str, reason: str) -> None:
        full = self._prefix + path
        self._outer.submodule_refusals.setdefault(full, reason)

    def _child(self, path: str, name: str, commit: str) -> UpstreamTree | None:
        if path in self._children:
            return self._children[path][0]
        child, reason = self._open_submodule(path, name, commit)
        self._children[path] = (child, reason)
        if reason is not None:
            self._refuse(path, reason)
        return child

    def _open_submodule(self, path: str, name: str, commit: str) -> tuple[UpstreamTree | None, str | None]:
        full = self._prefix + path
        where = f"git submodule {full} (gitlink {commit[:12]} of the pinned commit {str(self.commit)[:12]})"
        if safe_relpath(name) != name:
            return None, f"{where}: its .gitmodules name {name!r} is not a clean relative path"
        outer_root = self._outer.root.resolve()
        current = self.root
        for part in path.split("/"):
            current = current / part
            if current.is_symlink():
                return None, f"{where}: {self._prefix}{path} is a symbolic link in the checkout, not read"
        work = self.root / path
        if not work.is_dir():
            return None, f"{where} is absent from the checkout"
        link = work / ".git"
        if link.is_symlink() or not (link.is_file() or link.is_dir()):
            return None, f"{where} is not checked out (no .git in {full}): the submodule is empty"
        modules = self._modules_dir()
        if link.is_dir():
            git_dir = link.resolve()   # the layout of git before 1.7.8: the git directory inside the checkout
        else:
            try:
                text = link.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                text = ""
            if not text.startswith("gitdir:"):
                return None, f"{where}: {full}/.git is not a 'gitdir:' file"
            target = Path(text[len("gitdir:"):].strip())
            git_dir = (target if target.is_absolute() else work / target).resolve()
            expected = (modules / name).resolve() if modules is not None else None
            if expected is None or git_dir != expected:
                return None, (f"{where}: {full}/.git names {git_dir}, not the git directory "
                              f"{expected if expected is not None else '<git dir>/modules/' + name} of submodule {name!r}")
        if outer_root not in git_dir.parents or not (git_dir / "objects").is_dir():
            return None, f"{where}: its git directory {git_dir} is not a git directory inside the clone"
        head = _read_head(git_dir)
        if head is None:
            return None, f"{where}: the HEAD of {git_dir} cannot be read"
        if head != commit:
            return None, f"{where} is checked out at {head[:12]}, another commit: nothing under it is read"
        child = UpstreamTree.__new__(UpstreamTree)
        child._init_state(self.root / path, commit, self._git)
        child.kind = "git"
        child._git_dir = git_dir
        child._depth = self._depth + 1
        child._prefix = full + "/"
        child._outer = self._outer
        if not child.has_commit(commit):
            return None, f"{where}: the object store {git_dir} does not hold the commit {commit[:12]}"
        child._record = Submodule(full, name, commit, git_dir.relative_to(outer_root).as_posix())
        return child, None

    def _read_in_submodule(self, rel: str) -> bytes | None:
        found = self.locate_submodule(rel)
        if found is None:
            return None
        child, inner = found
        data = child.read_bytes(inner)
        if data is not None:
            child.note_read()
        return data

    def note_read(self) -> None:
        """Record on the outermost tree that a read went into this submodule's tree."""
        if self._record is not None:
            self._outer.submodules.setdefault(self._record.path, self._record)


# ---------------------------------------------------------------------------
# AST surface of an upstream class
# ---------------------------------------------------------------------------


@dataclass
class Surface:
    """The attributes an upstream class defines, as far as the AST shows them."""

    symbol: str
    file: str | None = None
    line: int | None = None
    names: set[str] = field(default_factory=set)
    #: why a name missing from :attr:`names` may still exist (an external base, ``__getattr__``, ``setattr``)
    open: list[str] = field(default_factory=list)
    #: why the class could not be read at all
    problems: list[str] = field(default_factory=list)
    #: ``file:Class`` of the class and of every base followed inside the clone (the class itself first)
    classes: list[str] = field(default_factory=list)
    #: ``file`` -> number of lines left out, for each file of :attr:`classes` read as Python 2 (:func:`_parse_legacy`)
    legacy: dict[str, int] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return self.file is not None and not self.problems


def _module_candidates(module: str) -> list[str]:
    parts = module.split(".")
    stem = "/".join(parts)
    out = []
    for prefix in _SOURCE_ROOTS:
        out.append(f"{prefix}{stem}.py")
        out.append(f"{prefix}{stem}/__init__.py")
    return out


def _find_module(tree: UpstreamTree, module: str, hint: str | None = None, *, submodules: bool = False) -> str | None:
    """The file of ``module`` in the tree: the hint, the source roots, then the shortest path ending in it.

    ``submodules`` (only for the ``native`` symbol itself, never while following imports or bases) also tries each
    git submodule as a source root, read at its gitlink commit, when nothing else matched: following a base class into
    a submodule would change what G7 reads for packages that never cited the submodule.
    """
    if hint:
        rel = safe_relpath(hint)
        if rel and tree.exists(rel) and rel.endswith(".py"):
            return rel
    for candidate in _module_candidates(module):
        if tree.exists(candidate):
            return candidate
    stem = "/".join(module.split("."))
    suffixes = (f"/{stem}.py", f"/{stem}/__init__.py")
    matches = sorted((path for path in tree.files() if path.endswith(suffixes)), key=lambda item: (len(item), item))
    if matches or not submodules:
        return matches[0] if matches else None
    # Only when the clone's own tree has no match: a git submodule is a source root of its own, read at its gitlink
    # commit (``evs_gz_utils.gz_step_example`` in the submodule evs_gz_utils is evs_gz_utils/evs_gz_utils/...).
    candidates = _module_candidates(module)
    for submodule in tree.submodule_paths():
        found = tree.locate_submodule(f"{submodule}/{candidates[0]}")
        if found is None:
            continue
        for candidate in candidates:
            if found[0].exists(candidate):
                found[0].note_read()
                return f"{submodule}/{candidate}"
    return None


def _refused_submodules(tree: UpstreamTree) -> str:
    """``; git submodules not read: ...`` for a message about a module the clone lacks, or ``""``."""
    refusals = getattr(tree, "submodule_refusals", {}) or {}
    if not refusals:
        return ""
    shown = [refusals[path] for path in sorted(refusals)[:3]]
    return "; git submodules not read: " + "; ".join(shown) + (" ..." if len(refusals) > 3 else "")


def _relative_module(file: str, level: int, module: str | None) -> str:
    """The path stem (``pkg/sub/mod``) a ``from <level dots><module> import ...`` in ``file`` names."""
    parts = list(PurePosixPath(file).parts[:-1])
    if level > 1:
        parts = parts[: max(0, len(parts) - (level - 1))]
    if module:
        parts += module.split(".")
    return "/".join(parts)


#: Python 2 lines a lenient reading rewrites before it leaves a line out (``print x`` and ``exec code`` define no
#: member; ``except E, e:``, ``0777``, ``10L`` and ``ur''`` keep their statement in Python 3 spelling).
_PY2_STATEMENT = re.compile(r"^(?P<indent>[ \t]*)(?:print\b(?![ \t]*[(=.,)\]])|exec[ \t]+(?![(=]))")
_PY2_EXCEPT = re.compile(r"^(?P<indent>[ \t]*)except[ \t]+(?P<what>.+?)[ \t]*,[ \t]*(?P<name>[A-Za-z_]\w*)[ \t]*:")
_PY2_OCTAL = re.compile(r"(?<![\w.])0(?P<digits>[0-7]+)(?![\w.])")
_PY2_LONG = re.compile(r"(?<![\w.])(?P<digits>\d+|0[xX][0-9a-fA-F]+)[lL](?!\w)")
_PY2_UNICODE_RAW = re.compile(r"(?<![\w])[uU](?=[rR]['\"])")
_LEADING_WHITESPACE = re.compile(r"^[ \t]+")
#: how many lines a lenient reading may leave out before it gives the file up
_LEGACY_MAX_EDITS = 400


def _legacy_line(line: str, message: str) -> str:
    """``line`` in a spelling Python 3 parses: Python 2 forms rewritten, else ``pass`` (``if True:`` for a block)."""
    if "unexpected indent" in message:
        return ""  # the continuation of a statement already left out
    indent = line[: len(line) - len(line.lstrip())]
    match = _PY2_EXCEPT.match(line)
    if match:
        return f"{match.group('indent')}except {match.group('what')} as {match.group('name')}:"
    for pattern, replacement in ((_PY2_OCTAL, r"0o\g<digits>"), (_PY2_LONG, r"\g<digits>"), (_PY2_UNICODE_RAW, "")):
        fixed = pattern.sub(replacement, line)
        if fixed != line:
            return fixed
    code = re.sub(r"#.*$", "", line).rstrip()
    return f"{indent}if True:" if code.endswith(":") else f"{indent}pass"


def _parse_legacy(text: str, path: str, *, changed_lines: set[int] | None = None) -> tuple[ast.Module | None, int]:
    """Parse source that Python 3 rejects (Python 2) leniently, for its classes and members only.

    Tabs in the indentation expand to the columns of 8 Python 2 used, ``print`` and ``exec`` statements become ``pass``,
    and every line the parser still rejects is rewritten (:func:`_legacy_line`) one at a time.  Every line keeps its
    number, so a class is found at the line the clone shows.  Returns the module and the number of lines changed, or
    ``None`` when the source does not parse after :data:`_LEGACY_MAX_EDITS` changes.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [_LEADING_WHITESPACE.sub(lambda match: match.group(0).expandtabs(8), line) for line in lines]
    changed = 0
    for index, line in enumerate(lines):
        match = _PY2_STATEMENT.match(line)
        if match:
            lines[index] = f"{match.group('indent')}pass"
            changed += 1
            if changed_lines is not None:
                changed_lines.add(index + 1)
    for _ in range(_LEGACY_MAX_EDITS):
        try:
            return ast.parse("\n".join(lines), filename=path), changed
        except SyntaxError as exc:  # IndentationError and TabError are SyntaxErrors
            index = (exc.lineno or 0) - 1
            if not 0 <= index < len(lines):
                return None, changed
            fixed = _legacy_line(lines[index], str(exc.msg))
            if fixed == lines[index]:
                return None, changed
            lines[index] = fixed
            changed += 1
            if changed_lines is not None:
                changed_lines.add(index + 1)
        except ValueError:
            return None, changed
    return None, changed


def _never_runs(test: ast.expr, *, type_checking: bool = True) -> bool:
    """True for a branch test that is false when the module runs: ``False``, ``0``, ``None``, ``''`` and, for an
    ``if``, ``TYPE_CHECKING`` / ``typing.TYPE_CHECKING`` (true only for a type checker)."""
    if isinstance(test, ast.Constant):
        return not test.value
    if type_checking and isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    return type_checking and isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


class _Reader:
    def __init__(self, tree: UpstreamTree):
        self.tree = tree
        self.modules: dict[str, ast.Module | None] = {}
        self.seen: set[tuple[str, str]] = set()
        #: ``path`` -> lines left out, for each module read with :func:`_parse_legacy`
        self.legacy: dict[str, int] = {}

    def parse(self, path: str) -> ast.Module | None:
        if path not in self.modules:
            text = self.tree.read_text(path)
            try:
                self.modules[path] = ast.parse(text, filename=path) if text is not None else None
            except (SyntaxError, ValueError):
                module, changed = _parse_legacy(text or "", path)
                self.modules[path] = module
                if module is not None:
                    self.legacy[path] = changed
        return self.modules[path]

    def module_file(self, dotted: str, current: str | None = None, level: int = 0) -> str | None:
        if level and current is not None:
            rel = _relative_module(current, level, dotted or None)
            for candidate in (rel + ".py", rel + "/__init__.py"):
                if self.tree.exists(candidate):
                    return candidate
            return None
        return _find_module(self.tree, dotted)

    def find_class(self, path: str, name: str, depth: int = 0) -> tuple[str, ast.ClassDef] | None:
        """``(file, ClassDef)`` of ``name`` in module ``path`` (following imports and aliases)."""
        module = self.parse(path)
        if module is None or depth > 6:
            return None
        head, _, rest = name.partition(".")
        for node in module.body:
            if isinstance(node, ast.ClassDef) and node.name == head:
                found: ast.ClassDef | None = node
                for part in [item for item in rest.split(".") if item]:
                    found = next((child for child in (found.body if found else [])
                                  if isinstance(child, ast.ClassDef) and child.name == part), None)
                return (path, found) if found is not None else None
        for node in module.body:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if (alias.asname or alias.name) == head:
                        target = self.module_file(node.module or "", path, node.level)
                        if target is None and node.level == 0 and node.module:
                            target = _find_module(self.tree, node.module)
                        if target is not None:
                            found = self.find_class(target, alias.name + (f".{rest}" if rest else ""), depth + 1)
                            if found is not None:
                                return found
                        submodule = self.module_file(f"{node.module or ''}.{alias.name}".strip("."), path, node.level)
                        if submodule is not None and rest:
                            return self.find_class(submodule, rest, depth + 1)
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                    and node.targets[0].id == head and isinstance(node.value, ast.Name):
                return self.find_class(path, node.value.id + (f".{rest}" if rest else ""), depth + 1)
        return None

    def find_definition(self, path: str, name: str, depth: int = 0) -> tuple[str, int, str] | None:
        """``(file, line, kind)`` of what module ``path`` binds ``name`` to when it has run, or ``None``.

        The module's statements are read in order, as they would run: a ``class``, ``def`` or ``async def``, an
        assignment with a value (``x = ...``, ``x: T = ...``) or a ``from ... import name`` binds the name; a
        ``del name`` unbinds it; a bare annotation (``x: int``) and an augmented assignment (``x += 1``, which needs
        an earlier binding) bind nothing. Module level includes the blocks of a top-level ``if``, ``try``,
        ``with``, ``for`` or ``while`` (a script assigns its instrument under ``if __name__ == "__main__":``),
        never a function or class body, and never a branch that does not run: the body of ``if False:``, ``if 0:``
        or ``if TYPE_CHECKING:`` (its ``else`` runs) and of ``while False:``. An imported name is followed into the
        clone as :meth:`find_class` follows it.
        """
        module = self.parse(path)
        if module is None or depth > 6 or "." in name:
            return None
        bound: list[Any] = [None]

        def visit(statements: list[ast.stmt]) -> None:
            for node in statements:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name == name:
                        bound[0] = (path, node.lineno, "class" if isinstance(node, ast.ClassDef) else "function")
                elif isinstance(node, ast.Assign):
                    if any(name in _target_names(target) for target in node.targets):
                        bound[0] = (path, node.lineno, "name")
                elif isinstance(node, ast.AnnAssign):
                    if node.value is not None and name in _target_names(node.target):
                        bound[0] = (path, node.lineno, "name")
                elif isinstance(node, ast.Delete):
                    if any(name in _target_names(target) for target in node.targets):
                        bound[0] = None
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if (alias.asname or alias.name) == name:
                            bound[0] = node
                elif isinstance(node, ast.If):
                    if not _never_runs(node.test):
                        visit(node.body)
                    visit(node.orelse)
                elif isinstance(node, ast.While):
                    if not _never_runs(node.test, type_checking=False):
                        visit(node.body)
                    visit(node.orelse)
                elif isinstance(node, (ast.For, ast.AsyncFor)):
                    visit(node.body)
                    visit(node.orelse)
                elif isinstance(node, (ast.With, ast.AsyncWith)):
                    visit(node.body)
                elif isinstance(node, ast.Try) or type(node).__name__ == "TryStar":
                    visit(node.body)
                    for handler in node.handlers:
                        visit(handler.body)
                    visit(node.orelse)
                    visit(node.finalbody)

        visit(module.body)
        found = bound[0]
        if not isinstance(found, ast.ImportFrom):
            return found
        for alias in found.names:
            if (alias.asname or alias.name) != name:
                continue
            target = self.module_file(found.module or "", path, found.level)
            if target is None and found.level == 0 and found.module:
                target = _find_module(self.tree, found.module)
            if target is None:
                return None
            return self.find_definition(target, alias.name, depth + 1)
        return None

    def attribute_setters(self, path: str, cls: ast.ClassDef) -> list[str]:
        """Classes of the clone that ``cls`` hands itself to (``Helper(owner=self)``) and that set attributes with
        computed names on an object they hold (``setattr(self._owner, name, ...)``): commands a firmware table
        generates at run time, for example, which the AST of ``cls`` cannot show."""
        out: list[str] = []
        for function in cls.body:
            args = function.args.posonlyargs + function.args.args \
                if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) else []
            if not args:
                continue
            owner = args[0].arg
            for node in ast.walk(function):
                if not isinstance(node, ast.Call):
                    continue
                values = list(node.args) + [keyword.value for keyword in node.keywords]
                name = _dotted(node.func)
                if not name or name in out or not any(isinstance(item, ast.Name) and item.id == owner
                                                      for item in values):
                    continue
                found = self.find_class(path, name)
                if found is not None and _sets_attributes_on_held_object(found[1]):
                    out.append(name)
        return out

    def base_target(self, path: str, base: ast.expr) -> tuple[str, str] | None:
        """``(module file, class name)`` of a base class expression, when it lives in the tree."""
        if isinstance(base, ast.Subscript):
            base = base.value
        module = self.parse(path)
        if module is None:
            return None
        if isinstance(base, ast.Name):
            for node in module.body:
                if isinstance(node, ast.ClassDef) and node.name == base.id:
                    return path, base.id
            for node in module.body:
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if (alias.asname or alias.name) == base.id:
                            target = self.module_file(node.module or "", path, node.level)
                            if target is not None:
                                return target, alias.name
            return None
        if isinstance(base, ast.Attribute) and isinstance(base.value, (ast.Name, ast.Attribute)):
            dotted = _dotted(base.value)
            if dotted is None:
                return None
            for node in module.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if (alias.asname or alias.name) == dotted:
                            target = _find_module(self.tree, alias.name)
                            if target is not None:
                                return target, base.attr
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if (alias.asname or alias.name) == dotted:
                            target = self.module_file(f"{node.module or ''}.{alias.name}".strip("."), path, node.level)
                            if target is not None:
                                return target, base.attr
            target = _find_module(self.tree, dotted)
            if target is not None:
                return target, base.attr
        return None

    def collect(self, path: str, cls: ast.ClassDef, surface: Surface, depth: int = 0) -> None:
        key = (path, cls.name)
        if key in self.seen or depth > 12:
            return
        self.seen.add(key)
        surface.classes.append(f"{path}:{cls.name}")
        if path in self.legacy:
            surface.legacy[path] = self.legacy[path]
        for node in cls.body:
            _collect_member(node, surface)
        for helper in self.attribute_setters(path, cls):
            note = f"{helper} sets attributes dynamically on the {cls.name} it is given (setattr)"
            if note not in surface.open:
                surface.open.append(note)
        for base in cls.bases:
            text = _unparse(base)
            if text in _PLAIN_BASES:
                continue
            target = self.base_target(path, base)
            found = self.find_class(target[0], target[1]) if target is not None else None
            if found is None:
                surface.open.append(f"base {text} of {cls.name} is not defined in the clone")
                continue
            self.collect(found[0], found[1], surface, depth + 1)


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr}" if head else None
    return None


def _unparse(node: ast.expr) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001 - only used in messages
        return "<expression>"


def _target_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [name for item in target.elts for name in _target_names(item)]
    return []


def _collect_member(node: ast.stmt, surface: Surface) -> None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        surface.names.add(node.name)
        if node.name in ("__getattr__", "__getattribute__"):
            surface.open.append(f"the class defines {node.name}, so any attribute may exist")
        _collect_instance_attributes(node, surface)
    elif isinstance(node, ast.ClassDef):
        surface.names.add(node.name)
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            for name in _target_names(target):
                surface.names.add(name)
                if name == "__slots__":
                    surface.names.update(_strings(node.value))
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name):
        surface.names.add(node.target.id)
    elif isinstance(node, (ast.If, ast.Try)):
        for child in list(getattr(node, "body", [])) + list(getattr(node, "orelse", [])):
            _collect_member(child, surface)


def _sets_attributes_on_held_object(cls: ast.ClassDef) -> bool:
    """True when a method of ``cls`` calls ``setattr(self.<attribute>, <computed name>, ...)``."""
    for function in cls.body:
        args = function.args.posonlyargs + function.args.args \
            if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) else []
        if not args:
            continue
        owner = args[0].arg
        for node in ast.walk(function):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr" \
                    and len(node.args) > 1 and isinstance(node.args[0], ast.Attribute) \
                    and isinstance(node.args[0].value, ast.Name) and node.args[0].value.id == owner \
                    and not (isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)):
                return True
    return False


def _strings(node: ast.expr) -> list[str]:
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return [item.value for item in node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    return []


def _collect_instance_attributes(function: ast.FunctionDef | ast.AsyncFunctionDef, surface: Surface) -> None:
    args = function.args.posonlyargs + function.args.args
    if not args:
        return
    owner = args[0].arg
    for node in ast.walk(function):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        for target in targets:
            for item in ast.walk(target):
                if isinstance(item, ast.Attribute) and isinstance(item.value, ast.Name) and item.value.id == owner:
                    surface.names.add(item.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr" \
                and node.args and isinstance(node.args[0], ast.Name) and node.args[0].id == owner:
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                surface.names.add(node.args[1].value)
            else:
                note = f"{function.name}() sets attributes dynamically (setattr)"
                if note not in surface.open:
                    surface.open.append(note)


def class_surface(tree: UpstreamTree, symbol: str, *, hint_file: str | None = None) -> Surface:
    """The attributes of the upstream class ``symbol`` (``package.module:Class``), read with :mod:`ast` only."""
    surface = Surface(symbol)
    module, _, name = str(symbol).partition(":")
    if not module or not name:
        surface.problems.append(f"native {symbol!r} is not 'package.module:Class'")
        return surface
    path = _find_module(tree, module, hint_file, submodules=True)
    if path is None:
        surface.problems.append(f"module {module} of {symbol} is not in the clone (looked for "
                                f"{', '.join(_module_candidates(module)[:4])} ...){_refused_submodules(tree)}")
        return surface
    reader = _Reader(tree)
    if reader.parse(path) is None:
        surface.problems.append(f"{path} cannot be parsed")
        return surface
    found = reader.find_class(path, name)
    if found is None and hint_file:
        # The card's file can be where the class is registered (gym register(...)), not the module that defines it.
        resolved = _find_module(tree, module, submodules=True)
        if resolved is not None and resolved != path:
            path, found = resolved, reader.find_class(resolved, name)
    if found is None:
        surface.problems.append(f"class {name} is not defined in {path}")
        return surface
    surface.file, surface.line = found[0], found[1].lineno
    reader.collect(found[0], found[1], surface)
    return surface


def definition_surface(tree: UpstreamTree, symbol: str, *, hint_file: str | None = None) -> Surface:
    """Where ``package.module:Name`` is defined in the clone, read with :mod:`ast` only (gate G7, transport families).

    A transport-family driver (serial, SCPI, ROS, HTTP, SiLA 2, MCP client) never runs its ``native`` symbol: it names
    the upstream code the command table or bindings come from. That provenance must exist at the pinned commit: a
    class (resolved as :func:`class_surface` resolves it, members not collected), a module-level function, or a
    module-level name (the instrument a script opens, ``inst = rm.open_resource(...)``). The module is found as
    :func:`class_surface` finds it, the card's file hint first. ``Surface.file``/``line`` name the definition;
    ``Surface.problems`` say why there is none.
    """
    surface = Surface(symbol)
    module, _, name = str(symbol).partition(":")
    if not module or not name:
        surface.problems.append(f"native {symbol!r} is not 'package.module:Name'")
        return surface
    path = _find_module(tree, module, hint_file, submodules=True)
    if path is None:
        surface.problems.append(f"module {module} of {symbol} is not in the clone (looked for "
                                f"{', '.join(_module_candidates(module)[:4])} ...){_refused_submodules(tree)}")
        return surface
    reader = _Reader(tree)
    if reader.parse(path) is None:
        surface.problems.append(f"{path} cannot be parsed")
        return surface

    def alternatives():
        yield path
        if hint_file:   # looked up only when the hinted file lacks the name (reads nothing more otherwise)
            resolved = _find_module(tree, module, submodules=True)
            if resolved is not None and resolved != path:
                yield resolved

    for candidate in alternatives():
        if "." in name:  # a nested class: Outer.Inner
            found_class = reader.find_class(candidate, name)
            if found_class is not None:
                surface.file, surface.line = found_class[0], found_class[1].lineno
                surface.classes.append(f"{found_class[0]}:{found_class[1].name}")
                return surface
            continue
        found = reader.find_definition(candidate, name)
        if found is not None:
            surface.file, surface.line = found[0], found[1]
            if found[2] == "class":
                surface.classes.append(f"{found[0]}:{name}")
            return surface
    surface.problems.append(f"{name} is not defined in {path} (no class, function or module-level name of that name)")
    return surface
