"""Throw-away git repositories with submodules, laid out the way ``git submodule update`` leaves them.

Only temporary directories are touched; git runs without user or system configuration (``gate_support.git``).
"""

from __future__ import annotations

import os
from pathlib import Path

from tests.driver import gate_support as gs


def make_repo(path: Path, files: dict[str, str]) -> str:
    """A new repository at ``path`` with ``files`` committed; returns the commit."""
    path.mkdir(parents=True, exist_ok=True)
    gs.git(path, "init", "-q")
    for name, text in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    gs.git(path, "add", "-A")
    gs.git(path, "commit", "-q", "-m", "files")
    return gs.git(path, "rev-parse", "HEAD")


def add_submodule(parent: Path, path: str, origin: Path, commit: str, *, name: str | None = None,
                  checkout: bool = True, git_dir: Path | None = None) -> Path:
    """Record ``origin`` at ``commit`` as the submodule ``path`` of the repository ``parent`` and stage it.

    The gitlink and the ``.gitmodules`` entry are staged in ``parent`` (commit them yourself). With ``checkout``, the
    submodule is checked out as git does it: its git directory is ``<git dir of parent>/modules/<name>`` (or
    ``git_dir``), its checkout holds a relative ``gitdir:`` file and its ``HEAD`` is ``commit``, detached. Returns
    the submodule's git directory.
    """
    name = name or path
    parent = parent.resolve()   # relative gitdir and worktree links are computed between resolved paths
    parent_git = parent / ".git"
    if parent_git.is_file():   # parent is itself a checked-out submodule: its git directory is named in the file
        text = parent_git.read_text(encoding="utf-8").strip()[len("gitdir:"):].strip()
        parent_git = (parent / text).resolve()
    modules = git_dir or (parent_git / "modules" / name)
    work = parent / path
    if checkout:
        modules.parent.mkdir(parents=True, exist_ok=True)
        gs.git(parent, "clone", "-q", "--no-checkout", "--separate-git-dir", str(modules), str(origin), str(work))
        gs.git(work, "checkout", "-q", "--detach", commit)
        (work / ".git").write_text(f"gitdir: {os.path.relpath(modules, work)}\n", encoding="utf-8")
        gs.git(work, "config", "core.worktree", os.path.relpath(work, modules))
    with (parent / ".gitmodules").open("a", encoding="utf-8") as handle:
        handle.write(f'[submodule "{name}"]\n\tpath = {path}\n\turl = https://example.invalid/{name}.git\n')
    gs.git(parent, "update-index", "--add", "--cacheinfo", f"160000,{commit},{path}")
    gs.git(parent, "add", ".gitmodules")
    return modules
