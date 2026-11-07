"""The OpenAI4S core patch this reference host needs (``openai4s-core.patch``).

The governed MHS route is wired into two OpenAI4S core files: ``MCPService``
in ``openai4s/host/mcp.py`` hands MHS connector rows to
:mod:`openai4s_mhs.hostroute`, and ``HostDispatcher`` in
``openai4s/host_dispatch.py`` adds the named ``mhs_emergency_stop`` action and
the device-bound ``mhs__estop`` approval exception.  Upstream OpenAI4S does not
contain that code, so the change is recorded as a patch against one upstream
commit (the ``Base-Commit`` header of ``openai4s-core.patch``).

Everything here reads git state only: ``capture`` runs ``git diff`` in the
checkout, and ``check`` applies the patch in a temporary ``git clone --shared``
of it (``--no-optional-locks`` throughout; nothing is written to the
checkout)::

    python3 -m openai4s_mhs core-patch check              # applies at Base-Commit, no drift
    python3 -m openai4s_mhs core-patch check --worktree   # same, against a full checkout
    python3 -m openai4s_mhs core-patch capture            # print the patch from the checkout
    python3 -m openai4s_mhs core-patch capture --write    # rewrite openai4s-core.patch
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "CorePatch",
    "CorePatchError",
    "DEFAULT_SOURCE",
    "OVERLAY_PATCH_FILE",
    "PATCH_FILE",
    "UPSTREAM_URL",
    "capture",
    "captured_text",
    "check",
    "load",
    "parse",
    "render",
    "write",
]

_INTEGRATION = Path(__file__).resolve().parents[1]
#: The recorded core patch (required by the governed host route).
PATCH_FILE = _INTEGRATION / "openai4s-core.patch"
#: The optional developer-overlay hook (``openai4s/__init__.py``); not required.
OVERLAY_PATCH_FILE = _INTEGRATION / "openai4s-mhs.patch"
#: The OpenAI4S checkout of this workspace (read-only).
DEFAULT_SOURCE = _INTEGRATION.parents[1] / "work" / "openai4s-src"
UPSTREAM_URL = "https://github.com/PKU-YuanGroup/OpenAI4S.git"

_HEADER_RE = re.compile(r"^([A-Z][A-Za-z0-9-]*):\s*(.*)$")
_DIFF_FILE_RE = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.MULTILINE)
_PLUS_FILE_RE = re.compile(r"^\+\+\+ b/(\S+)", re.MULTILINE)
_VERSION_RE = re.compile(r"""^__version__\s*=\s*["']([^"']+)["']""", re.MULTILINE)
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class CorePatchError(RuntimeError):
    """A patch that cannot be read, captured or checked, with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)


@dataclass(frozen=True)
class CorePatch:
    """The recorded patch: ``Key: value`` header lines, then a ``git diff`` body."""

    text: str
    header: dict[str, str] = field(default_factory=dict)
    body: str = ""

    @property
    def base_commit(self) -> str:
        return self.header.get("Base-Commit", "")

    @property
    def files(self) -> list[str]:
        found = [match.group(2) for match in _DIFF_FILE_RE.finditer(self.body)]
        return found or [match.group(1) for match in _PLUS_FILE_RE.finditer(self.body)]


def parse(text: str) -> CorePatch:
    """Split a patch into its header fields and its diff body."""
    found = re.search(r"^(?:diff --git |--- )", text, re.MULTILINE)
    if found is None:
        raise CorePatchError("MHS.HOST.PROTOCOL_ERROR", "the text contains no diff")
    marker = found.start()
    header: dict[str, str] = {}
    for line in text[:marker].splitlines():
        match = _HEADER_RE.match(line.strip())
        if match:
            header[match.group(1)] = match.group(2).strip()
    return CorePatch(text=text, header=header, body=text[marker:])


def load(path: str | os.PathLike[str] | None = None) -> CorePatch:
    target = Path(path) if path is not None else PATCH_FILE
    try:
        return parse(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CorePatchError("MHS.HOST.CONFIG_REQUIRED", f"cannot read {target}: {exc}") from exc


def _git(args: list[str], *, cwd: str | os.PathLike[str] | None = None,
         check: bool = True) -> subprocess.CompletedProcess[str]:
    if shutil.which("git") is None:
        raise CorePatchError("MHS.HOST.ADAPTER_MISSING", "git is not on PATH")
    env = dict(os.environ)
    env.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"})
    command = ["git", "--no-optional-locks"]
    if cwd is not None:
        command.extend(["-C", str(cwd)])
    completed = subprocess.run(command + list(args), capture_output=True, text=True, env=env, check=False)
    if check and completed.returncode != 0:
        raise CorePatchError(
            "MHS.HOST.PROTOCOL_ERROR",
            f"git {' '.join(args[:2])} failed: {(completed.stderr or completed.stdout).strip()[:500]}",
        )
    return completed


def _repository(source: str | os.PathLike[str]) -> Path:
    path = Path(source).expanduser()
    if not path.is_dir():
        raise CorePatchError("MHS.HOST.CONFIG_REQUIRED", f"OpenAI4S checkout not found: {path}")
    inside = _git(["rev-parse", "--is-inside-work-tree"], cwd=path, check=False)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise CorePatchError("MHS.HOST.CONFIG_REQUIRED", f"not a git checkout: {path}")
    return path


def _openai4s_version(source: Path, commit: str) -> str:
    shown = _git(["show", f"{commit}:openai4s/__init__.py"], cwd=source, check=False)
    match = _VERSION_RE.search(shown.stdout) if shown.returncode == 0 else None
    return match.group(1) if match else "unknown"


def _normalise(body: str) -> str:
    return body.replace("\r\n", "\n").rstrip("\n") + "\n"


def capture(source: str | os.PathLike[str] | None = None) -> tuple[str, str]:
    """``(HEAD commit, diff body)`` of the checkout's uncommitted change, read-only.

    Untracked files would be missing from ``git diff``, so they are refused
    rather than silently left out.
    """
    path = _repository(source if source is not None else DEFAULT_SOURCE)
    head = _git(["rev-parse", "HEAD"], cwd=path).stdout.strip()
    untracked = [
        line[3:]
        for line in _git(["status", "--porcelain", "--untracked-files=all"], cwd=path).stdout.splitlines()
        if line.startswith("?? ")
    ]
    if untracked:
        raise CorePatchError(
            "MHS.HOST.PROTOCOL_ERROR",
            "the checkout has untracked files that a diff would leave out: " + ", ".join(untracked[:10]),
        )
    body = _git(["diff", "--no-color", "--no-ext-diff", "--no-textconv", "--full-index", "HEAD"],
                cwd=path).stdout
    if not body.strip():
        raise CorePatchError("MHS.HOST.PROTOCOL_ERROR", f"the checkout has no change against {head}")
    return head, _normalise(body)


def render(body: str, *, base_commit: str, openai4s_version: str) -> str:
    """The patch file: a header the tooling can read, then the diff body."""
    files = [match.group(2) for match in _DIFF_FILE_RE.finditer(body)]
    added = sum(1 for line in body.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in body.splitlines() if line.startswith("-") and not line.startswith("---"))
    header = [
        "OpenAI4S core patch required by the OpenMHS reference host (integration/openai4s).",
        "",
        "OpenMHS is an independent open-source project, not affiliated with or endorsed by",
        "Anthropic. OpenAI4S is an independent upstream project; this patch is not part of it.",
        "",
        "The governed MHS route needs two OpenAI4S core files changed: MCPService hands MHS",
        "connector rows to openai4s_mhs.hostroute (journal, host ledger, endpoint evidence,",
        "trusted e-stop), and HostDispatcher gains the named mhs_emergency_stop action and the",
        "device-bound mhs__estop approval exception. Without it, MHS connector rows still run",
        "through the stock MCP path, but ungoverned (see integration/openai4s/README.md).",
        "",
        f"Upstream: {UPSTREAM_URL}",
        f"Base-Commit: {base_commit}",
        f"OpenAI4S-Version: {openai4s_version}",
        "Files: " + " ".join(files),
        f"Stat: {len(files)} files changed, {added} insertions(+), {removed} deletions(-)",
        "Captured: git --no-optional-locks -C work/openai4s-src diff --full-index HEAD (read-only)",
        "Check: python3 -m openai4s_mhs core-patch check",
        "Apply: git -C <OpenAI4S checkout at Base-Commit> apply <this file>",
        "",
    ]
    return "\n".join(header) + "\n" + _normalise(body)


def _apply_check(source: Path, base_commit: str, patch_path: Path, *, worktree: bool) -> tuple[bool, str]:
    """``git apply --check`` in a throwaway ``clone --shared`` at ``base_commit``."""
    scratch = tempfile.mkdtemp(prefix="openai4s-core-patch-")
    try:
        clone = Path(scratch) / "openai4s"
        _git(["clone", "--quiet", "--shared", "--no-checkout", str(source.resolve()), str(clone)])
        if worktree:
            _git(["checkout", "--quiet", "--detach", base_commit], cwd=clone)
            applied = _git(["apply", "--check", str(patch_path.resolve())], cwd=clone, check=False)
        else:
            _git(["read-tree", base_commit], cwd=clone)
            applied = _git(["apply", "--check", "--cached", str(patch_path.resolve())], cwd=clone, check=False)
        return applied.returncode == 0, (applied.stderr or applied.stdout).strip()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def check(
    patch: str | os.PathLike[str] | None = None,
    source: str | os.PathLike[str] | None = None,
    *,
    base_commit: str | None = None,
    worktree: bool = False,
    compare: bool = True,
) -> dict[str, Any]:
    """Whether the patch applies at its base commit, and whether it still matches the checkout.

    ``applies`` is the result of ``git apply --check`` in a temporary clone of
    ``source`` at the base commit (``--cached`` against that commit's index
    unless ``worktree``).  ``matches`` compares the patch body with a fresh
    :func:`capture` when the checkout's HEAD is the base commit (``None``
    otherwise).  ``ok`` needs ``applies`` and no drift.
    """
    patch_path = Path(patch) if patch is not None else PATCH_FILE
    recorded = load(patch_path)
    base = base_commit or recorded.base_commit
    if not _COMMIT_RE.match(base or ""):
        raise CorePatchError("MHS.HOST.PROTOCOL_ERROR", f"{patch_path.name} has no 40-hex Base-Commit header")
    path = _repository(source if source is not None else DEFAULT_SOURCE)
    has_base = _git(["cat-file", "-e", f"{base}^{{commit}}"], cwd=path, check=False).returncode == 0
    result: dict[str, Any] = {
        "patch": str(patch_path),
        "source": str(path),
        "base_commit": base,
        "files": recorded.files,
        "mode": "worktree" if worktree else "index",
        "applies": None,
        "matches": None,
    }
    if not has_base:
        result["reason"] = f"the checkout does not contain the base commit {base}"
        result["ok"] = False
        return result
    applies, detail = _apply_check(path, base, patch_path, worktree=worktree)
    result["applies"] = applies
    if detail:
        result["apply_output"] = detail[:2000]
    if compare:
        head = _git(["rev-parse", "HEAD"], cwd=path).stdout.strip()
        result["source_head"] = head
        if head == base:
            try:
                _head, body = capture(path)
                result["matches"] = _normalise(body) == _normalise(recorded.body)
            except CorePatchError as exc:
                result["matches"] = False
                result["reason"] = exc.message
        else:
            result["reason"] = "the checkout's HEAD is not the base commit; drift not compared"
    result["ok"] = bool(applies) and result["matches"] is not False
    return result


def write(source: str | os.PathLike[str] | None = None,
          path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Capture the checkout's change and write it as the recorded patch."""
    checkout = _repository(source if source is not None else DEFAULT_SOURCE)
    head, body = capture(checkout)
    text = render(body, base_commit=head, openai4s_version=_openai4s_version(checkout, head))
    target = Path(path) if path is not None else PATCH_FILE
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, target)
    return {"patch": str(target), "base_commit": head, "files": parse(text).files}


def captured_text(source: str | os.PathLike[str] | None = None) -> str:
    """The patch file :func:`write` would produce, without writing it."""
    checkout = _repository(source if source is not None else DEFAULT_SOURCE)
    head, body = capture(checkout)
    return render(body, base_commit=head, openai4s_version=_openai4s_version(checkout, head))
