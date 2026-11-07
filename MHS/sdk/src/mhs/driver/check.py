"""The acceptance gate of a driver package: ``python -m mhs.driver check <dir> --backend fake`` (plan 3.9).

A package is done when this exits 0.  The gate runs nine gates on the
package directory and writes ``check-report.json`` (``check-report.schema.json``)
into it; it exits 0 on a pass, 1 on a failure (the failing gate ids are
printed) and 2 on a usage error.  A pass on a fake or sim backend is evidence
``contract_checked`` only, never an MHS-Device level.

========  =========================================================================
gate      checks
========  =========================================================================
G1        layout and isolation: ``task.json``, ``driver.py``, ``driver.lock.json``,
          ``test_driver.py`` (and ``fake.py`` or ``fixtures/`` for a hardware
          driver) exist; ``task.json`` names this directory, equals the registry
          card when there is one (a card that declares ``companions`` must have
          one) and is not quarantined; no symlink leaves the
          package; ``RESULT.json`` / ``site-limits.example.json`` validate; the
          clone exists and its tracked files are unmodified, before and after the run;
          each companion clone is at its pin and unmodified (a fetched lock
          companion also matches its ``LOCK.json`` entry, has no untracked file
          and no write bit)
G2        lock: ``driver.lock.json`` validates; its package id, commit, repository
          and licence equal the card's; the pinned commit is in the clone
G3        strict resolve: the driver imports and resolves against the catalogue
          (known classes and kinds, no drift or widening, limit paths resolve),
          strict mode accepts the declared and the fake view, the mode is the
          card's ``safety.expected_mode`` and the risk at least its floor, a
          hardware R1+ driver has ``@estop`` and a ``safe_state``
          and limits every numeric write/invoke input (or ``operator_required``),
          and every Limit cites ``source`` (``vendor_doc``/``upstream_code``) + ``ref``;
          a hardware driver's fake/sim backend is not the upstream ``native`` class
          (nor derived from it) and lives in the package unless the card names an
          upstream simulator; package code does not reach into the gate, the
          runtime or the interpreter (``FORBIDDEN``) and leaves ``mhs`` unpatched
          (``GATE_TAMPERED``)
G4        provenance: every Limit/Fact ``ref`` (``path:LINE``) exists in the clone at
          the pinned commit (a warning when the cited line lacks the bound); so does
          the ``action_space_ref`` of a ``GymnasiumDriver``
G5        reference: ``reference.json`` and ``REFERENCE.md`` equal a fresh
          ``python -m mhs.driver reference`` output
G6        behaviour (:mod:`mhs.driver.behaviour`), on fresh in-process endpoints
G7        native surface: every attribute the fake defines or the driver touched
          exists on the ``native`` class in the AST of the pinned clone (upstream
          code is parsed, never imported); serial/SCPI families: every command
          mnemonic sent occurs in the clone
G8        protocol and surface: the in-process conformance suite awards
          ``MHS-Sim`` CL3 on servers that apply ``site-limits.example.json``
          (an operator_required limit needs the overlay to be written at all);
          the MCP projection builds; every input property has a
          description (and numbers a unit); every tool description and the
          driver-owned part of each tool are at most 2 KB
G9        repository tests: ``test_driver.py`` keeps the ``check_driver`` harness
          call and passes in a child process within 180 s with the network disabled
========  =========================================================================

Synthetic tutorials (``MHS/sdk/examples/thermostat``) have ``"upstream": null``
in ``task.json``: they have no repository, so G2 accepts a lock whose
``upstream`` is ``null`` and G4/G7 read the synthetic upstream inside the
package (``local_path`` is then relative to the package, e.g. ``vendor``).
Real task cards always have an upstream; a driver under ``MHS/drivers/`` with
``upstream: null`` fails G2.

Package conformance fixtures (``fixtures/conformance.json``, the
:mod:`mhs.conformance.synth` fixture format) are used by G6 and G8.

Isolation.  The command line (:func:`run_check_isolated`) never imports
package code: it runs the gates in a child process (:mod:`mhs.driver._gate`,
network and device files disabled) and exits 0 only when that child wrote a
schema-valid passing report whose ``report_digest`` checks out.  A package
that exits the interpreter (``SystemExit``, ``os._exit``, a signal) or hangs
fails with ``<gate>.ABORTED`` / ``<gate>.TIMEOUT`` for the gate that was
running.  In the child (and in-process, :func:`run_check`), ``SystemExit``
from package code is a finding of the running gate, the gate functions are
bound before the package is imported, and the ``mhs`` modules are compared
with a snapshot taken before the import after every gate (``G3.GATE_TAMPERED``).
The parent also repeats the static scan of the package sources (``G3.FORBIDDEN``)
itself, enforces the tamper events the child reported while it ran, and fails
every gate that carries an error finding.  It accepts the child's report only
when its header (package id, driver directory, backend, upstream pin) is the
one the parent derives itself, every gate is required (a full run), and the
child's progress stream reached the report with a result for every gate the
report lists as run that the report does not contradict.  Residual risk: the
gates evaluate package code in-process, so code written to defeat the snapshot
(or to forge both the child's report and its progress stream) is not ruled out
mechanically; CI re-runs the gate and human review covers the rest.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib
import inspect
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping, Sequence

from .. import _ids, canonical
from .. import catalog as _catalog
from .. import units as _units
from ..schema import default_store
from . import upstream as _upstream
from .loader import LOCK_FILE, driver_class, read_lock
from .ref_numeric import ones_box_bounds
from .package import REFERENCE_JSON, REFERENCE_MD, TASK_FILE, find_root, read_json, reference_documents, relative_to_root
from .spec import DriverDefinitionError

__all__ = [
    "CONFORMANCE_LEVEL",
    "CONFORMANCE_PROFILE",
    "GATES",
    "GATE_TIMEOUT_S",
    "INNER_ENV",
    "REPORT_FILE",
    "REPO_TEST_TIMEOUT_S",
    "TOOL_LIMIT_BYTES",
    "CheckUsageError",
    "format_report",
    "run_check",
    "run_check_isolated",
    "stable_digest",
    "static_findings",
]

GATES: tuple[tuple[str, str], ...] = (
    ("G1", "Layout and isolation"),
    ("G2", "Lock"),
    ("G3", "Strict resolve"),
    ("G4", "Provenance"),
    ("G5", "Reference"),
    ("G6", "Behaviour"),
    ("G7", "Native surface"),
    ("G8", "Protocol and surface"),
    ("G9", "Repository tests"),
)
REPORT_FILE = "check-report.json"
#: Set in the G9 child process: ``mhs.testing.check_driver`` then skips G9 (no recursion).
INNER_ENV = "MHS_DRIVER_GATE_INNER"
_ROOT_ENV = "MHS_DRIVER_GATE_ROOT"
_CLONE_ENV = "MHS_DRIVER_GATE_CLONE"
#: ``--companions-root`` of the gate, handed to its own G9 run of ``test_driver.py`` (lock companions).
_COMPANIONS_ENV = "MHS_DRIVER_GATE_COMPANIONS"
REPO_TEST_TIMEOUT_S = 180
#: Bound of the whole gate run in its child process (G9's own bound included).
GATE_TIMEOUT_S = 900
CONFORMANCE_PROFILE = "MHS-Sim"
CONFORMANCE_LEVEL = "CL3"
TOOL_LIMIT_BYTES = 2048
FIXTURES_FILE = "fixtures/conformance.json"
EXAMPLE_OVERLAY = "site-limits.example.json"
_GATE_BACKENDS = ("fake", "sim")
_RISKS = ("R0", "R1", "R2", "R3")
_REQUIRED_FILES = (TASK_FILE, "driver.py", LOCK_FILE, "test_driver.py")
_PROJECTION_PROPERTIES = frozenset({"session_id", "command_id", "expected_revision", "permit_id", "deadline_ms"})
_MAX_FINDINGS = 200
_SYNTHETIC_LOCK_ERROR = "$.upstream: expected object, got null"


class CheckUsageError(ValueError):
    """The gate cannot run as asked (exit status 2)."""


@dataclass
class Finding:
    code: str
    message: str
    severity: str = "error"
    path: str | None = None
    ref: str | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"code": self.code, "message": (self.message or self.code)[:2000],
                               "severity": self.severity}
        if self.path:
            out["path"] = str(self.path)[:512]
        if self.ref:
            out["ref"] = str(self.ref)[:500]
        return out


@dataclass
class Gate:
    id: str
    name: str
    status: str = "pass"
    required: bool = True
    duration_ms: float = 0.0
    findings: list[Finding] = field(default_factory=list)

    def error(self, code: str, message: str, path: str | None = None, ref: str | None = None) -> None:
        self.findings.append(Finding(f"{self.id}.{code}", message, "error", path, ref))

    def warning(self, code: str, message: str, path: str | None = None, ref: str | None = None) -> None:
        self.findings.append(Finding(f"{self.id}.{code}", message, "warning", path, ref))

    def skip(self, reason: str, *, required: bool = True) -> None:
        self.status = "skip"
        self.required = required
        self.findings.append(Finding(f"{self.id}.NOT_RUN", reason, "warning"))

    def settle(self) -> None:
        if self.status == "skip":
            return
        if any(item.severity == "error" for item in self.findings):
            self.status = "fail"
        elif self.findings:
            self.status = "warn"
        else:
            self.status = "pass"

    def to_json(self) -> dict[str, Any]:
        findings = self.findings[:_MAX_FINDINGS]
        if len(self.findings) > _MAX_FINDINGS:
            findings = findings[:-1] + [Finding(f"{self.id}.TRUNCATED",
                                                f"{len(self.findings) - _MAX_FINDINGS + 1} more findings not shown",
                                                "warning")]
        return {"id": self.id, "name": self.name, "status": self.status, "required": self.required,
                "duration_ms": round(self.duration_ms, 1), "findings": [item.to_json() for item in findings]}


def _crash_text(exc: BaseException) -> str:
    """A finding text for an exception raised by package code (``SystemExit`` included)."""
    if isinstance(exc, SystemExit):
        return (f"package code raised SystemExit({exc.code!r}) (sys.exit(), exit() or raise SystemExit): a driver "
                "package never exits the interpreter")
    return f"{type(exc).__name__}: {str(exc)[:800]}"


# ---------------------------------------------------------------------------
# static scan of the package sources (G3 FORBIDDEN; repeated by the CLI parent)
# ---------------------------------------------------------------------------

#: SDK modules package code never imports: the gate itself and the runtime it checks the driver against.
_GATE_INTERNALS = ("mhs.driver.prerequisites", "mhs.driver.check", "mhs.driver.behaviour", "mhs.driver._repotests", "mhs.driver._gate",
                   "mhs.driver.upstream", "mhs.driver.ros_check", "mhs.driver.qcodes_check", "mhs.driver.ophyd_check", "mhs.driver.http_check", "mhs.driver.mcp_client_check", "mhs.driver.sila2_check", "mhs.testing.recorder", "mhs.conformance",
                   "mhs._server", "mhs.server", "mhs.mcp",
                   "mhs.driver.pylabrobot_check",  # PyLabRobot helper
                   "mhs.driver.tag_check",  # tag-bridge helper (2026-11-04)
                   "mhs.driver.pybind_surface")  # pybind11 native selectors (phase 3)
#: Interpreter internals package code never imports.
_INTERPRETER_MODULES = ("builtins", "gc", "ctypes", "_ctypes", "cffi")
#: ``module.attribute`` uses that exit the interpreter or reach into it.
_FORBIDDEN_MEMBERS = frozenset({
    ("sys", "exit"), ("sys", "modules"), ("sys", "_getframe"), ("sys", "settrace"), ("sys", "setprofile"),
    ("sys", "meta_path"), ("sys", "path_hooks"), ("sys", "addaudithook"), ("sys", "argv"), ("os", "_exit"),
    ("os", "abort"), ("os", "kill"), ("os", "killpg"), ("threading", "settrace"), ("threading", "setprofile"),
    ("inspect", "currentframe"), ("inspect", "stack"), ("_thread", "interrupt_main"),
})
#: Modules whose attributes package code never reaches by a computed name (``getattr(os, "_ex" + "it")``).
_REFLECTED_MODULES = frozenset({"os", "sys", "builtins", "importlib", "_thread", "signal", "posix", "nt"})
_REFLECTION_CALLS = frozenset({"getattr", "setattr", "delattr", "hasattr"})
#: Attributes of frames and tracebacks (reaching the gate's own variables) on any object.
_FRAME_ATTRIBUTES = frozenset({"f_globals", "f_locals", "f_back", "f_builtins", "gi_frame", "cr_frame", "ag_frame",
                               "tb_frame", "_getframe"})
#: Attributes that rewrite a function or class in place when assigned.
_REWRITE_ATTRIBUTES = frozenset({"__code__", "__globals__", "__defaults__", "__kwdefaults__", "__class__",
                                 "__bases__", "__dict__"})
_EXIT_CALLS = frozenset({"exit", "quit"})
_FORBIDDEN_NAMES = frozenset({"SystemExit", "__builtins__", "__import__"})
#: The private members through which the endpoint binds a served mode to a ROS bridge and the bridge commits a safe
#: state (SAFE-049, CORE-088; verification F3 of phase 3): only mhs.server binds, only the bridge commits. Package code
#: that names one, as an attribute, a name or a string (``getattr``/``setattr``/``__dict__`` keys), could grant itself
#: a sensed confirmation (integrator edit I9, Claude Sonnet review S1 of p3-hardening-3).
_PRIVATE_BINDING_MEMBERS = frozenset({"_bind_served_mode", "_bind_sensed_route", "_grant_served_mode", "_served_mode",
                                      "_mhs_served_mode", "_commit_safe_state_locked", "_safe_state_achieved",
                                      "_safe_stamp"})


def _module_denied(module: str) -> str | None:
    for prefix in _GATE_INTERNALS:
        if module == prefix or module.startswith(prefix + "."):
            return f"imports {module}, a module of the acceptance gate or the runtime it checks the driver against"
    root = module.split(".")[0]
    if root in _INTERPRETER_MODULES:
        return f"imports {module}, an interpreter internal"
    return None


def _constant_text(node: ast.AST | None) -> str | None:
    """The string an expression of string constants spells (``'mhs.driver.' + 'check'``, an f-string of constants)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _constant_text(node.left), _constant_text(node.right)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        parts = [_constant_text(item) for item in node.values]
        return "".join(parts) if all(part is not None for part in parts) else None  # type: ignore[arg-type]
    if isinstance(node, ast.FormattedValue) and node.conversion == -1 and node.format_spec is None:
        return _constant_text(node.value)
    return None


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def _is_main_guard(node: ast.stmt) -> bool:
    test = getattr(node, "test", None)
    return (isinstance(node, ast.If) and isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
            and test.left.id == "__name__" and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value == "__main__")


class _Scan(ast.NodeVisitor):
    """Forbidden constructs of one package source file (see :func:`static_findings`)."""

    def __init__(self) -> None:
        self.found: list[tuple[int, str]] = []
        self.modules: dict[str, str] = {}   # alias -> module (plain imports)
        self.sdk: set[str] = set()          # names bound to objects imported from mhs
        self.importers: set[str] = set()    # names bound to importlib.import_module / __import__

    def flag(self, node: ast.AST, text: str) -> None:
        self.found.append((getattr(node, "lineno", 0), text))

    def visit_Module(self, node: ast.Module) -> None:
        for statement in node.body:
            if not _is_main_guard(statement):
                self.visit(statement)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            denied = _module_denied(alias.name)
            if denied:
                self.flag(node, denied)
            bound = alias.asname or alias.name.split(".")[0]
            self.modules[bound] = alias.name if alias.asname else alias.name.split(".")[0]
            if alias.name == "mhs" or alias.name.startswith("mhs."):
                self.sdk.add(bound)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            return
        module = node.module or ""
        denied = _module_denied(module)
        if denied:
            self.flag(node, denied)
        for alias in node.names:
            full = f"{module}.{alias.name}"
            if not denied:
                inner = _module_denied(full) if module.startswith("mhs") else None
                if inner:
                    self.flag(node, inner)
            if (module, alias.name) in _FORBIDDEN_MEMBERS:
                self.flag(node, f"imports {module}.{alias.name}")
            if alias.name in _FORBIDDEN_NAMES:
                self.flag(node, f"imports {alias.name}")
            if alias.name in _PRIVATE_BINDING_MEMBERS:
                self.flag(node, f"imports {alias.name}, a private member of the endpoint's served-mode binding "
                          "(SAFE-049)")
            if module == "mhs" or module.startswith("mhs."):
                self.sdk.add(alias.asname or alias.name)
            if module == "importlib" and alias.name in ("import_module", "__import__"):
                self.importers.add(alias.asname or alias.name)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name):
            module = self.modules.get(node.value.id, node.value.id)
            if (module, node.attr) in _FORBIDDEN_MEMBERS:
                self.flag(node, f"uses {module}.{node.attr}")
        if node.attr in _FRAME_ATTRIBUTES:
            self.flag(node, f"reads .{node.attr} (interpreter frames)")
        if node.attr in _PRIVATE_BINDING_MEMBERS:
            self.flag(node, f"uses .{node.attr}, a private member of the endpoint's served-mode binding or the bridge's "
                      "safe-state commit (only the server binds a served mode; SAFE-049)")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in _FORBIDDEN_NAMES:
            self.flag(node, f"uses {node.id}")
        if node.id in _PRIVATE_BINDING_MEMBERS:
            self.flag(node, f"uses {node.id}, a private member of the endpoint's served-mode binding (SAFE-049)")

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and node.value in _PRIVATE_BINDING_MEMBERS:
            self.flag(node, f"names {node.value!r}, a private member of the endpoint's served-mode binding or the "
                      "bridge's safe-state commit (only the server binds a served mode; SAFE-049)")

    def _spelled(self, node: ast.AST) -> None:
        """A private binding member spelled as a constant expression (``'_bind_' + 'served_mode'``, an f-string of
        constants); a name computed at run time is beyond a static scan."""
        text = _constant_text(node)
        if text in _PRIVATE_BINDING_MEMBERS:
            self.flag(node, f"spells {text!r}, a private member of the endpoint's served-mode binding or the "
                      "bridge's safe-state commit (only the server binds a served mode; SAFE-049)")

    def visit_BinOp(self, node: ast.BinOp) -> None:
        self._spelled(node)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self._spelled(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name) and func.id in _EXIT_CALLS:
            self.flag(node, f"calls {func.id}() (exits the interpreter)")
        if isinstance(func, ast.Name) and func.id in _REFLECTION_CALLS and node.args \
                and isinstance(node.args[0], ast.Name) and self.modules.get(node.args[0].id) in _REFLECTED_MODULES:
            module = self.modules[node.args[0].id]
            member = _constant_text(node.args[1]) if len(node.args) > 1 else None
            if member is None:
                self.flag(node, f"calls {func.id}() on {module} with a computed attribute name")
            elif (module, member) in _FORBIDDEN_MEMBERS:
                self.flag(node, f"uses {module}.{member} (through {func.id}())")
        importer = (isinstance(func, ast.Name) and func.id in self.importers) or (
            isinstance(func, ast.Attribute) and func.attr in ("import_module", "__import__")
            and isinstance(func.value, ast.Name) and self.modules.get(func.value.id) == "importlib")
        if importer and node.args:
            name = _constant_text(node.args[0])
            denied = _module_denied(name) if name is not None else None
            if denied:
                self.flag(node, denied)
        if isinstance(func, ast.Name) and func.id in ("setattr", "delattr") and node.args \
                and _root_name(node.args[0]) in self.sdk:
            self.flag(node, f"calls {func.id}() on an object of the SDK (monkeypatching mhs)")
        patcher = (isinstance(func, ast.Attribute) and func.attr in ("patch", "object", "dict", "multiple")
                   and "patch" in ast.dump(func)) or (isinstance(func, ast.Name) and func.id == "patch")
        if patcher and node.args:
            target = node.args[0]
            if (isinstance(target, ast.Constant) and isinstance(target.value, str)
                    and (target.value == "mhs" or target.value.startswith("mhs."))) or _root_name(target) in self.sdk:
                self.flag(node, "patches the SDK (mock.patch of mhs)")
        self.generic_visit(node)

    def _targets(self, targets: Iterable[ast.expr]) -> None:
        for target in targets:
            for item in ast.walk(target):
                if isinstance(item, ast.Attribute):
                    if item.attr in _REWRITE_ATTRIBUTES:
                        self.flag(item, f"assigns .{item.attr} (rewrites a function or class in place)")
                    elif _root_name(item) in self.sdk:
                        self.flag(item, f"assigns into the SDK ({_unparse(item)}): package code never patches mhs")
                elif isinstance(item, ast.Subscript) and _root_name(item) in self.sdk:
                    self.flag(item, f"assigns into the SDK ({_unparse(item)}): package code never patches mhs")

    def visit_Assign(self, node: ast.Assign) -> None:
        self._targets(node.targets)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._targets([node.target])
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._targets([node.target])
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        self._targets(node.targets)
        self.generic_visit(node)


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)[:120]
    except Exception:  # noqa: BLE001 - only used in messages
        return "<expression>"


def _synthetic_clone(directory: Path, card: Any) -> Path | None:
    """The synthetic tutorial's stand-in clone inside the package (``upstream: null``, relative ``local_path``)."""
    if not isinstance(card, Mapping) or "upstream" not in card or card.get("upstream") is not None:
        return None
    local = card.get("local_path")
    rel = _upstream.safe_relpath(local) if isinstance(local, str) else None
    return (directory / rel).resolve() if rel else None


def static_findings(directory: str | os.PathLike[str], card: Any = None) -> list[tuple[str, str, str]]:
    """``(code, message, path)`` of the forbidden constructs in the package's Python files (gate G3).

    Package code (``driver.py``, ``fake.py``, ``native.py``, ``test_driver.py``,
    helpers) never imports the gate, the conformance harness or the runtime
    internals (``mhs.server``, ``mhs._server``, ``mhs.mcp``), never patches
    ``mhs`` (assignments, ``setattr``, ``mock.patch``), never exits the
    interpreter (``sys.exit``, ``os._exit``, ``exit()``, ``SystemExit``) and
    never reaches into it (``sys.modules``, ``sys.argv``, frames, ``builtins``,
    ``__import__``, ``gc``, ``ctypes``, ``getattr`` on ``os``/``sys``/``builtins``
    with a computed name, ``importlib.import_module`` of a gate module spelled
    in constants), and never names a private member of the endpoint's
    served-mode binding or the bridge's safe-state commit (``_bind_served_mode``,
    ``_grant_served_mode``, ``_bind_sensed_route``, ``_served_mode``,
    ``_mhs_served_mode``, ``_commit_safe_state_locked``,
    ``_safe_state_achieved``, ``_safe_stamp``; as an attribute, a name or a
    string), so package code cannot grant itself a sensed confirmation
    (SAFE-049).  The ``if __name__ == "__main__":`` block of a file is not
    scanned; neither is the synthetic tutorial's stand-in clone.  Nothing is
    imported: the files are parsed with :mod:`ast`.
    """
    root = Path(directory).resolve()
    if card is None:
        card, _problem = read_json(root / TASK_FILE)
    skip = _synthetic_clone(root, card)
    out: list[tuple[str, str, str]] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if any(part == "__pycache__" or part.startswith(".") for part in relative.parts[:-1]):
            continue
        if skip is not None and (path.resolve() == skip or skip in path.resolve().parents):
            continue
        name = relative.as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
        except (OSError, SyntaxError, ValueError) as exc:
            out.append(("G3.SYNTAX", f"{name} cannot be parsed: {type(exc).__name__}: {exc}", name))
            continue
        scan = _Scan()
        scan.visit(tree)
        for line, text in sorted(set(scan.found)):
            out.append(("G3.FORBIDDEN", f"{name}:{line}: {text}; package code must not exit, reach into or patch the "
                        "interpreter, the SDK runtime or the acceptance gate", name))
    return out


# ---------------------------------------------------------------------------
# integrity of the mhs modules while package code runs (G3 GATE_TAMPERED)
# ---------------------------------------------------------------------------

#: Modules the gates use, imported before any package code so a snapshot covers them.
_GATE_MODULES = ("mhs.bridge.ros_sensed", "mhs.driver.sensed_stop",  # sensed-confirmation stop (SAFE-049)
                 "mhs.bridge.mcp_stdio", "mhs.driver.prerequisites", "mhs.bridge.sila2", "mhs.bridge.sila2_replay", "mhs.driver.sila2", "mhs.driver.sila2_config", "mhs.driver.sila2_check", "mhs.bridge.mcp_client", "mhs.driver.mcp_client_config", "mhs.driver.mcp_client_check", "mhs.driver.mcp_client_driver", "mhs.adapter", "mhs.bridge.base", "mhs.bridge.camera_pixels", "mhs.bridge.pymmcore_camera", "mhs.bridge.http", "mhs.bridge.http_replay", "mhs.bridge.ros", "mhs.bridge.ros_images", "mhs.bridge.ros_pointcloud", "mhs.artifacts", "mhs.bridge.ros_transport", "mhs.canonical",
                 "mhs.catalog", "mhs.conformance",
                 "mhs.conformance.inprocess", "mhs.conformance.synth", "mhs.driver.base", "mhs.driver.behaviour",
                 "mhs.driver.build", "mhs.driver.families", "mhs.driver.loader", "mhs.driver.model",
                 "mhs.driver.package", "mhs.driver.http_config", "mhs.driver.http_check", "mhs.driver.qcodes_config", "mhs.driver.qcodes_check", "mhs.driver.ophyd_config", "mhs.driver.upstream", "mhs.driver.ros_check", "mhs.driver.ophyd_check", "mhs.limits", "mhs.mcp", "mhs.schema",
                 "mhs.schema.store", "mhs.server", "mhs._server.strict", "mhs.testing", "mhs.testing.recorder",
                 "mhs.units",
                 # PyLabRobot helper
                 "mhs.bridge.pylabrobot", "mhs.driver.pylabrobot", "mhs.driver.pylabrobot_check",
                 "mhs.testing.pylabrobot",
                 # tag-bridge helper (2026-11-04)
                 "mhs.bridge.tags", "mhs.bridge.tag_fake", "mhs.driver.tag_config", "mhs.driver.tag_driver",
                 "mhs.driver.tag_check",
                 # factory-built environments (2026-11-05)
                 "mhs.driver.factory_check",
                 # pybind11 native selectors (phase 3)
                 "mhs.driver.pybind_surface",
                 # files a native wrote, published as artifacts (2026-11-05)
                 "mhs.file_artifacts")
#: Modules whose module-level containers (dicts, lists, sets) are compared too.
_CORE_MODULES = frozenset({"mhs.bridge.ros_sensed", "mhs.driver.sensed_stop",  # sensed-confirmation stop (SAFE-049)
                           "mhs.bridge.mcp_stdio", "mhs.driver.prerequisites", "mhs.driver.sila2_config", "mhs.driver.sila2_check", "mhs.bridge.sila2", "mhs.driver.mcp_client_config", "mhs.driver.mcp_client_check", "mhs.driver.check", "mhs.driver.behaviour", "mhs.driver._repotests", "mhs.driver._gate",
                           "mhs.testing.recorder", "mhs.driver.ros_check", "mhs.driver.qcodes_check", "mhs.driver.ophyd_check", "mhs.driver.http_check",
                           "mhs.bridge.pymmcore_camera", "mhs.bridge.ros_images", "mhs.bridge.ros_pointcloud",
                           # PyLabRobot helper
                           "mhs.bridge.pylabrobot", "mhs.driver.pylabrobot", "mhs.driver.pylabrobot_check",
                           # tag-bridge helper (2026-11-04)
                           "mhs.bridge.tags", "mhs.driver.tag_config", "mhs.driver.tag_check",
                           # factory-built environments (2026-11-05)
                           "mhs.driver.factory_check",
                           # pybind11 native selectors (phase 3)
                           "mhs.driver.pybind_surface",
                           # files a native wrote, published as artifacts (2026-11-05)
                           "mhs.file_artifacts"})
# Active core leases are runtime state, not immutable admission policy. Keep
# camera policy containers covered without rejecting legitimate lease changes.
_RUNTIME_CONTAINERS = frozenset({("mhs.bridge.sila2", "_OWNERS"), ("mhs.bridge.pymmcore_camera", "_OWNERS")})


# Capture the concrete immutable regex type before package code runs.
_REGEX_TYPE = type(re.compile(""))


class _RegexIdentity:
    """Keep a policy alive for the snapshot lifetime without a large repr."""

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return type(other) is _RegexIdentity and self.value is other.value


def _function_print(value: Any) -> tuple[Any, ...]:
    return (id(value), id(getattr(value, "__code__", None)), id(getattr(value, "__defaults__", None)),
            id(getattr(value, "__kwdefaults__", None)))


def _class_print(value: type) -> tuple[Any, ...]:
    members: list[tuple[Any, ...]] = []
    for key, member in sorted(vars(value).items(), key=lambda item: item[0]):
        if inspect.isfunction(member):
            members.append((key,) + _function_print(member))
        elif isinstance(member, (staticmethod, classmethod)):
            members.append((key, id(member)) + _function_print(member.__func__))
        elif isinstance(member, property):
            members.append((key, id(member), id(member.fget), id(member.fset), id(member.fdel)))
        elif inspect.isclass(member):
            members.append((key, id(member)))
    return (id(value), tuple(members))


def _fingerprint(key: str, value: Any, core: bool) -> Any:
    if type(value) is _REGEX_TYPE:
        # Compiled patterns hold policy too. Identity rejects replacement even
        # when subclass hooks compiled behavior not represented by the text.
        pattern = value.pattern
        # re.compile preserves str/bytes subclasses; do not call their overrides.
        if isinstance(pattern, str):
            kind, length = "str", str.__len__(pattern)
            encoded = str.encode(pattern, "utf-8", "surrogatepass")
        else:
            kind, length, encoded = "bytes", bytes.__len__(pattern), pattern
        return ("regex", _RegexIdentity(value), kind, length, value.flags,
                hashlib.sha256(encoded).digest())
    if inspect.isfunction(value) or inspect.isbuiltin(value):
        return ("f",) + _function_print(value)
    if inspect.isclass(value):
        return ("c",) + _class_print(value)
    if inspect.ismodule(value):
        return ("m", id(value))
    if isinstance(value, (str, bytes, float, complex, tuple, frozenset)):
        return ("v", repr(value))
    if isinstance(value, int) and not key.startswith("_"):  # private ints and flags are counters and caches
        return ("v", repr(value))
    if core and isinstance(value, (dict, list, set)):
        try:
            return ("d", id(value), hashlib.sha256(repr(value).encode("utf-8", "replace")).hexdigest())
        except Exception:  # noqa: BLE001 - an unrepresentable container is compared by identity
            return ("d", id(value))
    return None


def _integrity_snapshot() -> dict[tuple[str, str], Any]:
    """Fingerprints of the functions, classes, modules and constants of every loaded ``mhs`` module."""
    out: dict[tuple[str, str], Any] = {}
    for name, module in list(sys.modules.items()):
        if module is None or not (name == "mhs" or name.startswith("mhs.")):
            continue
        try:
            items = list(vars(module).items())
        except TypeError:  # pragma: no cover - not a real module
            continue
        core = name in _CORE_MODULES
        for key, value in items:
            if key == "__warningregistry__":
                continue
            print_ = _fingerprint(key, value, core and (name, key) not in _RUNTIME_CONTAINERS)
            if print_ is not None:
                out[(name, key)] = print_
    return out


def _integrity_changes(before: Mapping[tuple[str, str], Any], after: Mapping[tuple[str, str], Any]) -> list[str]:
    return sorted(f"{module}.{key}" for (module, key), value in before.items() if after.get((module, key)) != value)


#: The principal of the approvals the gate attests for itself: never a person, and only on the gate's own server.
_GATE_APPROVAL_PRINCIPAL = "gate:fake-backend"


def _gate_approval(request: Mapping[str, Any]) -> dict[str, Any]:
    """The approval authority of the gate's in-process server for an R3 hardware view over the fake driver.

    That server reaches no device, so the approval it attests is the gate's own, under a principal no person has; a
    server that serves hardware is built with the operator's verifier and never with this one."""
    return {"verified": True, "approvals": [{"principal": _GATE_APPROVAL_PRINCIPAL, "method": "human_click",
                                              "evidence_ref": "mhs.driver.check: the hardware view over the fake backend"}]}


def _declares_artifact_output(binding: Any) -> bool:
    """True when the binding's resolved output schema names an artifact reference (``artifact_ref``/``image_ref``)."""
    schema = getattr(getattr(binding, "effective", None), "output_schema", None)
    if not isinstance(schema, Mapping):
        schema = getattr(binding, "output_schema", None)
    properties = schema.get("properties") if isinstance(schema, Mapping) else None
    return isinstance(properties, Mapping) and any(name in properties for name in ("artifact_ref", "image_ref"))


# ---------------------------------------------------------------------------
# context
# ---------------------------------------------------------------------------


class _Context:
    """What the gates share: the package, its card and lock, the driver class and model, the upstream tree."""

    def __init__(self, directory: Path, backend: str, root: Path | None, clone: Path | None, inner: bool,
                 companions_root: Path | None = None):
        self.dir = directory
        self.backend = backend
        self.root = root
        self.inner = inner
        #: ``--companions-root``: where the fetched (lock) companion clones and their LOCK.json are read instead of
        #: the directory of each lock entry's local path (``work/companions``)
        self.companions_root = companions_root
        self.card, self.card_problem = read_json(directory / TASK_FILE)
        if self.card is not None and not isinstance(self.card, dict):
            self.card, self.card_problem = None, f"{TASK_FILE} must be a JSON object"
        card = self.card or {}
        self.synthetic = "upstream" in card and card.get("upstream") is None
        self.upstream_card = card.get("upstream") if isinstance(card.get("upstream"), Mapping) else {}
        self.commit = self.upstream_card.get("commit") if isinstance(self.upstream_card.get("commit"), str) else None
        self.lock, self.lock_problems = read_lock(directory)
        self.clone_path = self._clone_path(clone)
        self.tree: _upstream.UpstreamTree | None = None
        if self.clone_path is not None and self.clone_path.is_dir():
            self.tree = _upstream.UpstreamTree(self.clone_path, None if self.synthetic else self.commit,
                                               use_git=not self.synthetic)
        self.clone_modified_before = self.tree.modified() if self.tree is not None else None
        #: the card's companion sources (``companions``, user decision 2026-11-05), keyed by alias; a card without
        #: them has none, and every check below is then silent
        self.companions: dict[str, _upstream.CompanionSource] = {}
        self.companion_problems: list[str] = []
        self.companion_modified_before: dict[str, list[str] | None] = {}
        if not self.synthetic and "companions" in card:
            self.companions, self.companion_problems = _upstream.companion_sources(card, self.root or Path.cwd(),
                                                                                   companions_root)
            for alias, source in self.companions.items():
                if source.tree is not None and source.tree.is_git:
                    # A fetched (lock) clone counts untracked files too: its whole work tree is the pinned commit.
                    self.companion_modified_before[alias] = source.tree.modified(untracked=source.lock is not None)
        self.cls: Any = None
        self.import_error: str | None = None
        self.model: Any = None
        self.model_error: DriverDefinitionError | None = None
        self.instance: Any = None
        self.logs: list[Any] = []
        self.g3_ok = False
        self.fixtures_path = directory / FIXTURES_FILE if (directory / FIXTURES_FILE).is_file() else None
        self.fixtures: Any = None
        self.fixtures_problem: str | None = None
        #: ``site-limits.example.json`` (G6 checks it only narrows; G8 serves it, so operator_required limits are filled)
        self.example_overlay: Mapping[str, Any] | None = None
        if (directory / EXAMPLE_OVERLAY).is_file():
            document, _problem = read_json(directory / EXAMPLE_OVERLAY)
            self.example_overlay = document if isinstance(document, Mapping) else None
        self._load()
        from . import prerequisites

        self.prerequisites = None
        self.prerequisites_problem = None
        self.preparation_runs: list[Any] = []
        self._preparation_servers: list[Any] = []
        try:
            self.prerequisites = prerequisites.load(self)
        except Exception as exc:
            self.prerequisites_problem = f"{prerequisites.FILE}: {type(exc).__name__}: {exc}"

    def _clone_path(self, clone: Path | None) -> Path | None:
        if clone is not None:
            return clone.resolve()
        local = (self.card or {}).get("local_path")
        if not isinstance(local, str) or not local:
            return None
        if self.synthetic:
            rel = _upstream.safe_relpath(local)
            return (self.dir / rel).resolve() if rel else None
        path = Path(local)
        if path.is_absolute():
            return path
        base = self.root or Path.cwd()
        return (base / path).resolve()

    def _load(self) -> None:
        if self.fixtures_path is not None:
            try:
                from ..conformance.synth import load_fixtures

                self.fixtures = load_fixtures(str(self.fixtures_path))
            except Exception as exc:  # noqa: BLE001 - reported by G1
                self.fixtures_problem = f"{FIXTURES_FILE} cannot be read: {exc}"
        if not (self.dir / "driver.py").is_file():
            self.import_error = "driver.py is missing"
            return
        try:
            self.cls = driver_class(self.dir)
        except DriverDefinitionError as exc:
            self.import_error = str(exc)
            return
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # noqa: BLE001 - any import failure (SystemExit included) is a G3 finding
            self.import_error = _crash_text(exc)
            return
        try:
            if getattr(self.cls, "_needs_instance", False):
                from .families import OphydDriver
                if issubclass(self.cls, OphydDriver):
                    OphydDriver._check_runtime_hooks.__func__(self.cls)
                    from .ophyd_config import model_contract
                    declared = OphydDriver._declared_model.__func__(self.cls, {}, self.backend)
                    self._ophyd_trusted_contract = model_contract(declared)
                    runtime = OphydDriver._declared_runtime_config.__func__(self.cls, declared, {}, self.backend)
                    self._ophyd_trusted_runtime = model_contract(runtime)
                self.instance = self.cls(backend=self.backend, base_dir=self.dir)
                self.model = self.instance._model
            else:
                self.model = self.cls.driver_model()
        except DriverDefinitionError as exc:
            self.model_error = exc
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # noqa: BLE001
            self.model_error = DriverDefinitionError(f"the driver cannot be built: {_crash_text(exc)}")

    @property
    def mode(self) -> str:
        if self.model is not None:
            return str(self.model.mode)
        declared = getattr(self.cls, "mode", None) if self.cls is not None else None
        if declared in ("hardware", "simulated"):
            return str(declared)
        expected = ((self.card or {}).get("safety") or {}).get("expected_mode")
        return expected if expected in ("hardware", "simulated") else "hardware"

    @property
    def family(self) -> str:
        from . import families

        if self.cls is None:
            return "unknown"
        from .mcp_client_driver import McpClientDriver
        if issubclass(self.cls, McpClientDriver):
            return 'mcp-client'
        # --- PyLabRobot helper ---
        from .pylabrobot import PyLabRobotDriver
        if issubclass(self.cls, PyLabRobotDriver):
            return "pylabrobot"
        # --- end PyLabRobot helper ---
        from .tag_driver import TagDriver  # tag-bridge helper (2026-11-04)
        if issubclass(self.cls, TagDriver):
            return "tag-bridge"
        for name, label in (("Sila2Driver", "sila2"), ("HttpDriver", "http"), ("OphydDriver", "ophyd"), ("SerialDriver", "serial"), ("ScpiDriver", "scpi"), ("GymnasiumDriver", "gymnasium"),
                            ("MujocoDriver", "mujoco"), ("QcodesDriver", "qcodes"), ("PythonObjectDriver", "python-object"), ("RosDriver", "ros")):
            if issubclass(self.cls, getattr(families, name)):
                return label
        return "direct"

    @property
    def transport_family(self) -> bool:
        return self.family in ("serial", "scpi", "ros", "http", "mcp-client", "sila2", "tag-bridge")

    def fake_entry(self) -> Any:
        backends = dict(getattr(self.cls, "backends", {}) or {}) if self.cls is not None else {}
        return backends.get(self.backend)

    @property
    def records_native(self) -> bool:
        """True when the backend object is the package's own fake (wrapped in a Recorder)."""
        if self.cls is None:
            return False
        if self.family in ("gymnasium", "mujoco"):
            entry = self.fake_entry()
            return isinstance(entry, str) and entry.startswith(".")
        return True

    def close(self) -> None:
        for server in self._preparation_servers:
            try:
                # These servers borrowed an already-owned Driver. Closing the
                # server evidence handle must never close that Driver twice.
                server.close()
            except KeyboardInterrupt:
                raise
            except BaseException:
                pass
        if self.instance is not None:
            try:
                self.instance.close()
            except KeyboardInterrupt:
                raise
            except BaseException:  # noqa: BLE001 - closing never fails (nor exits the gate)
                pass

    # -- endpoints ----------------------------------------------------------------
    def phase_codes(self) -> dict[Any, str]:
        out: dict[Any, str] = {}
        if self.model is None or self.cls is None:
            return out
        attrs: list[tuple[str | None, str]] = [(param.getter, "read") for param in self.model.params]
        attrs += [(item.attr, "read") for item in self.model.interlocks]
        if self.model.estop is not None:
            attrs.append((self.model.estop.attr, "estop"))
        attrs.append((self.model.reset_attr, "reset"))
        attrs += [("setup", "setup"), ("teardown", "setup")]
        for attr, phase in attrs:
            if not attr:
                continue
            fn = getattr(self.cls, attr, None)
            if not callable(fn):
                continue
            try:
                out[inspect.unwrap(fn).__code__] = phase
            except AttributeError:
                continue
        if self.family == "ros":
            from ..bridge.ros import RosBridge

            # The receive thread only observes messages. Its trusted SDK frame
            # must win over an overlapping actuation window; outbound send()
            # remains an actuation and remains subject to fault injection.
            out[RosBridge._receive.__code__] = "read"
        if self.family == "sila2":
            from ..bridge.sila2 import Sila2Bridge

            # Protective workers also observe retirement and release owned
            # resources. Those calls must never borrow an open estop window,
            # including when a broken Stop method sends no request at all.
            out[Sila2Bridge._invoke_stop.__code__] = "estop"
            out[Sila2Bridge._observation.__code__] = "read"
            out[Sila2Bridge._release_resources.__code__] = "act"
            # Bind normal work to its executing thread, not a global window
            # held by a simultaneous protective or ordinary caller.
            out[Sila2Bridge._ordinary_read.__code__] = "read"
            out[Sila2Bridge._ordinary_action.__code__] = "act"
        return out

    def wrapper(self) -> Callable[[Any], Any] | None:
        if not self.records_native:
            return None
        from ..testing import Recorder, log_of

        codes = self.phase_codes()

        def wrap(native: Any) -> Any:
            recorder = Recorder(native)
            log = log_of(recorder)
            log.phase_codes.update(codes)
            self.logs.append(log)
            return recorder

        return wrap

    def open_driver(self, native_filter: Callable[[Any], Any] | None = None) -> Any:
        from ..adapter import load_driver

        wrap = self.wrapper()
        if native_filter is not None:
            # G6 SENSED_FAIL_OPEN, STALL_FAIL_OPEN and FRESH_FAIL_OPEN: the gate's filter sits between the (recorded)
            # fake transport and the bridge.
            recorder = wrap
            wrap = (lambda native: native_filter(recorder(native))) if recorder is not None else native_filter
        driver = load_driver(self.dir, self.backend, native_wrapper=wrap)
        log = self.last_log(driver)
        if log is not None:
            _open_windows(driver, log)
        return driver

    def last_log(self, driver: Any) -> Any:
        if not self.records_native:
            return None
        from ..testing import Recorder, log_of

        native = getattr(driver, "_native_value", None)
        return log_of(native) if isinstance(native, Recorder) else None

    @staticmethod
    def _artifact_store(driver: Any) -> Any:
        """Fresh gate-owned storage for image/point-cloud/log/MCP producers, with SDK default bounds.

        The gate is the local operator for its fake endpoint. Its policy is the
        normal 2 MiB per artifact, 32 MiB total, 128 grants and 300 second lifetime;
        package configuration cannot enlarge these limits. Other drivers
        allocate nothing. This store only accepts bytes explicitly published by
        a command: it never imports caller paths or URLs.
        """
        from .families import HttpDriver, Sila2Driver
        from .mcp_client_driver import McpClientDriver
        mcp_outputs = isinstance(driver, McpClientDriver) and any(
            item['output']['kind'] == 'png' or item['output'].get('artifact')
            for item in driver._mcp_config['tools'].values())
        sila_binary = isinstance(driver, Sila2Driver) and any("artifact" in item for item in driver._sila_config["commands"].values())
        http_logs = isinstance(driver, HttpDriver) and any(
            item.get('operation') == 'logs' for item in driver._http_config['commands'].values())
        # Any binding whose declared output names an artifact reference (for example a direct driver's extension
        # action that publishes a file the native wrote with mhs.file_artifacts) gets the same default store
        # (NATIVE-FILE-ARTIFACTS, 2026-11-05); a driver that publishes nothing is unaffected by it.
        declared_outputs = any(_declares_artifact_output(binding) for binding in driver._model.bindings)
        if not sila_binary and not http_logs and not mcp_outputs and not declared_outputs and not any(binding.capability_id in ("cap.sensing.image.v1", "cap.sensing.point_cloud.v1") for binding in driver._model.bindings):
            return None
        from ..artifacts import LocalArtifactStore

        return LocalArtifactStore()

    def _prerequisite_for(self, case: str | None) -> Any:
        if self.prerequisites_problem:
            raise DriverDefinitionError(self.prerequisites_problem)
        plan = self.prerequisites
        if case is None:
            return None
        if plan is None:
            raise DriverDefinitionError("no gate prerequisite profile was declared")
        if case == plan.capability_id:
            return None  # Connect itself always starts from the original state.
        if case not in plan.cases:
            raise DriverDefinitionError("unknown gate prerequisite target")
        return plan

    def endpoint(self, *, site_limits: Any = None, gate_case: str | None = None,
                 native_filter: Callable[[Any], Any] | None = None) -> Any:
        from ..conformance.inprocess import Harness
        from .behaviour import Endpoint, Session
        from .build import build_server, close_server
        from . import prerequisites

        plan = self._prerequisite_for(gate_case)
        if plan is not None:
            site_limits = prerequisites.overlay(plan, site_limits)
        driver = self.open_driver(native_filter)
        store = None
        try:
            store = self._artifact_store(driver)
            server = build_server(driver, site_limits=site_limits, artifact_store=store)
        except BaseException:
            try:
                driver.close()
            finally:
                if store is not None:
                    store.close()
            raise
        harness = None
        try:
            if plan is not None:
                self.preparation_runs.append(prerequisites.execute(server, plan))
            harness = Harness(server)
            session = Session(server, next(iter(server.devices)))
        except BaseException:
            try:
                if harness is not None:
                    harness.restore()
            finally:
                close_server(server)
            raise

        def close() -> None:
            try:
                harness.restore()
            finally:
                close_server(server)

        return Endpoint(server, harness, session, self.last_log(driver), close)

    def hardware_endpoint(self) -> Any:
        """The declared hardware view served over the fake backend object (the hardware factory is never called)."""
        from ..conformance.inprocess import Harness
        from ..server import MHSServer
        from .behaviour import Endpoint, Session
        from .build import DEFAULT_ENDPOINT_ID, build_manifest, build_server, close_server, device_from_manifest
        from . import prerequisites

        plan = self._prerequisite_for('safety' if self.prerequisites is not None else None)
        driver = self.open_driver()
        store = None
        try:
            if plan is not None:
                if len(self._preparation_servers) >= 128:
                    raise DriverDefinitionError("gate prerequisite server ownership budget exhausted")
                preparation = build_server(driver, site_limits=prerequisites.overlay(plan, None))
                self._preparation_servers.append(preparation)
                try:
                    self.preparation_runs.append(prerequisites.execute(preparation, plan))
                finally:
                    # MHSServer.close closes only its evidence/store handle.
                    # The outer scope owns the Driver through projection and
                    # calls driver.close exactly once on failure or final close.
                    preparation.close()
            store = self._artifact_store(driver)
            manifest = build_manifest(_hardware_view_subject(self, driver) if self.instance is not None else self.cls, backend="hardware")
            device = device_from_manifest(manifest, driver)
            # R3 hardware needs an authenticated approval for every session (SAFE-033/034); without one the strict
            # server refuses the session and the behaviour checks cannot run.  This server serves the fake driver, so
            # the gate is its own approval authority, for R3 only (R2 keeps its fail-closed permits).
            verifier = _gate_approval if device.safety.risk_class == "R3" else None
            server = MHSServer(DEFAULT_ENDPOINT_ID, [device], strict=True, approval_verifier=verifier,
                               artifact_store=store)
        except BaseException:
            try:
                driver.close()
            finally:
                if store is not None:
                    store.close()
            raise
        # The bridge is the fake driver, so the harness's hardware gate (CON-031) has nothing real to protect.
        harness = None
        try:
            harness = Harness(server, allow_actuation=True)
            session = Session(server, device.device_id)
        except BaseException:
            try:
                if harness is not None:
                    harness.restore()
            finally:
                close_server(server)
            raise

        def close() -> None:
            try:
                harness.restore()
            finally:
                close_server(server)

        return Endpoint(server, harness, session, self.last_log(driver), close)

    def server_factory(self) -> Callable[[], Any]:
        """Fresh strict servers for the conformance run (G8), with ``site-limits.example.json`` applied.

        An operator_required limit refuses every call that sets it until an operator overlay fills it, so a suite
        run on the bare driver could not write its only parameter; the package's example overlay stands for the
        configured site.
        """
        from .build import build_server, close_server
        from . import prerequisites

        def factory() -> Any:
            plan = self._prerequisite_for('safety' if self.prerequisites is not None else None)
            driver = self.open_driver()
            store = None
            try:
                store = self._artifact_store(driver)
                server = build_server(driver, site_limits=self.example_overlay, artifact_store=store)
            except BaseException:
                try:
                    driver.close()
                finally:
                    if store is not None:
                        store.close()
                raise
            if plan is not None:
                try:
                    self.preparation_runs.append(prerequisites.execute(server, plan))
                except BaseException:
                    close_server(server)
                    raise
            return server, (lambda: close_server(server))

        return factory


#: Bridge contract methods and the recorder phase they open (see :meth:`mhs.testing.RecordLog.window`).
_WINDOWS = {"read": "read", "interlocks": "read", "safety_status": "read", "estop": "estop", "reset": "reset",
            "call": "act", "write": "act", "restore": "act", "safe_state": "act"}


def _open_windows(driver: Any, log: Any) -> None:
    """Shadow the driver's contract methods on the instance so native calls on helper threads get their phase."""
    import functools

    for name, phase in _WINDOWS.items():
        original = getattr(driver, name, None)
        if not callable(original):
            continue

        def windowed(*args: Any, _original: Any = original, _phase: str = phase, **kwargs: Any) -> Any:
            with log.window(_phase):
                return _original(*args, **kwargs)

        functools.update_wrapper(windowed, original)
        # The runtime tells a Bridge default (a software-only e-stop) from an override by __func__.
        windowed.__func__ = getattr(original, "__func__", None)  # type: ignore[attr-defined]
        setattr(driver, name, windowed)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _risk_index(value: Any) -> int:
    return _RISKS.index(value) if value in _RISKS else 0


def _owner_repo(card: Mapping[str, Any]) -> tuple[str | None, str | None]:
    package_id = card.get("package_id")
    if isinstance(package_id, str) and package_id.startswith("gh.") and "/" in package_id:
        owner, _, repo = package_id[3:].partition("/")
        return owner, repo
    return None, None


def _limit_rules(model: Any) -> list[tuple[str, str, Any]]:
    """``(capability id, limit path, rule)`` of every limit the driver declares."""
    out = []
    for binding in model.bindings:
        for path, rule in sorted((binding.limits or {}).items()):
            out.append((binding.capability_id, str(path), rule))
    return out


def _derived(ctx: _Context, capability_id: str) -> bool:
    """Limits the simulator families derive from the live simulator (action spaces, ctrlrange)."""
    return ctx.family in ("gymnasium", "mujoco") and capability_id == "cap.world.step.v1"


#: The reader's patterns run in time linear in the length of a run of digits or blanks (RUNTIME-AND-GATE-FIXES): a
#: number is written ``\d+(?:\.\d*)?``, which matches exactly the strings ``\d+\.?\d*`` matched and tries their ends in
#: the same order (longest first) but has one way to split each; a number that must be followed by more of the pattern
#: (the factor of ``2 * pi``, a quantity's unit) never starts right after a digit, and a pi term without a sign never
#: starts right after a blank: a match never starts there anyway, because the same match (the same groups, the same
#: end) starts one character earlier. The old patterns retried every split at every digit of a run of digits, cubic in
#: its length (800 digits about a second, 5,000 more than two minutes), and every blank of a run, quadratic.
_PI_TERM = re.compile(
    r"(?:(?P<sign>[-+])|(?<!\s))\s*(?:(?<!\d)(?P<k>\d+(?:\.\d*)?)\s*\*\s*)?"
    r"(?<![A-Za-z0-9_.])(?:(?:math|np|numpy)\.)?pi\b"
    r"(?:\s*\*\s*(?P<m>\d+(?:\.\d*)?))?(?:\s*/\s*(?P<d>\d+(?:\.\d*)?))?")
_RADIANS_CALL = re.compile(r"(?:math|np|numpy)\.(?:radians|deg2rad)\(\s*(?P<deg>[-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*\)")
#: a line that states its angles in degrees: ``deg``, ``degrees``, ``°``, or a number directly followed by the CJK
#: degree sign U+5EA6, the unit of a Chinese or Japanese comment such as "(0-180 degrees)"
_IN_DEGREES = re.compile(r"\bdeg(?:ree)?s?\b|°|(?<=\d)\u5ea6", re.IGNORECASE)


_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_GROUPED = re.compile(r"(?<![\d,.])[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d,])")  # 5,000 and 2,147,400,000
#: Python literals: 750_000, 65_535.5, 0b1111_1111, 0xFF, 0o17 (not inside an identifier such as var_1_000)
_PY_LITERAL = re.compile(r"(?<![\w.])[-+]?(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|\d+(?:_\d+)+(?:\.\d+(?:_\d+)*)?)"
                         r"(?!\w|\.\d)")
#: a bound on the size of a signed value: ``±5``, ``+/- 5``, ``abs(x) > 1000`` (that number), ``magnitude`` (all of them)
_SYMMETRIC = re.compile(r"(?:±|\+/-)\s*(?P<a>\d+\.?\d*|\.\d+)|\babs\([^()]*\)\s*[<>]=?\s*(?P<b>\d+\.?\d*|\.\d+)")
_MAGNITUDE = re.compile(r"\bmagnitudes?\b", re.IGNORECASE)
_QUANTITY = re.compile(r"(?P<value>[-+]?(?:(?<!\d)\d+(?:\.\d*)?|(?<!\d)\.\d+)(?:[eE][-+]?\d+)?)\s?"
                       r"(?P<unit>[A-Za-zµμ]{1,3})\b")
#: a Gymnasium ``Discrete(n)`` (``Discrete(n=5)``, ``Discrete(3, start=-1)``) allows the actions start .. start + n - 1
_DISCRETE = re.compile(r"\bDiscrete\(\s*(?:n\s*=\s*)?(?P<n>\d+)\s*(?P<rest>(?:,[^()]*)?)\)")
_DISCRETE_START = re.compile(r"\bstart\s*=\s*(?P<start>[-+]?\d+)")
#: a literal Python ``range(stop)``, ``range(start, stop)`` or ``range(start, stop, step)`` of integer literals holds
#: its first and last elements (``if time not in range(0,255)`` accepts 0 through 254); a name, a call, a float or a
#: zero step in its arguments, ``np.arange`` or another name ending in ``range`` shows nothing more
_RANGE = re.compile(r"(?<![\w.])range\(\s*(?P<a>[-+]?\d+)\s*(?:,\s*(?P<b>[-+]?\d+)\s*(?:,\s*(?P<c>[-+]?\d+)\s*)?)?\)")
#: a NumPy array of ones that is a whole bound, ``np.ones(4)``, ``-np.ones([4])`` or ``np.ones((n,), dtype=...)`` after
#: ``(``, ``[``, ``,``, ``:`` or ``=``, holds 1 or -1; one that an operator scales or offsets (``np.ones(n) * limit``,
#: ``2 * np.ones(n)``, ``high - np.ones(2)``, ``x += np.ones(2)``) holds another number
_ONES = re.compile(r"(?:^|[(\[,:]|(?<![=<>!+\-*/%@&|^])=)\s*(?:(?P<sign>-)\s*)?"
                   r"(?:np|numpy)\.ones\((?:[^()]|\([^()]*\))*\)(?!\s*[-+*/%@.\[])")


def _numbers_in(text: str) -> list[float]:
    """The numbers a cited line shows: literals (with Python's forms ``750_000``, ``0b1111_1111``, ``0xFF``), numbers with
    thousands separators (``5,000``), the upper end of a
    range written without spaces (``[5-6000]`` shows 5 and 6000, not -6000), and the angle forms upstream code writes
    for them (``2 * math.pi``, ``-math.pi / 2``, ``np.radians(90)``), which G4 must not call missing.  A line that
    states its angles in degrees (``util.degrees(-25)``, ``Angle(degrees=44.5)``, ``-170 to 170 deg``) also shows them
    in radians, the unit of the catalogue's angle classes.  A symmetric bound shows its negative too: ``±5`` and
    ``abs(x) > 1000`` that of its number, a line that speaks of a magnitude (``a magnitude past these``) those of all.
    A Gymnasium ``Discrete(n)`` shows its largest action ``n - 1`` (``start + n - 1`` with ``start=``), the bound the
    bridge derives from it, a literal integer ``range(start, stop[, step])`` its first and last elements (the
    membership test ``x not in range(0, 255)`` accepts 0 through 254), and a bound written ``np.ones(n)`` or ``-np.ones([n])`` shows 1 or -1, unless an operator
    scales it (``np.ones(n) * self.max_torque``). A bounded source-only AST reader also recognizes a Box whose
    ones-based bounds and literal scale are defined in the same straight-line cited span; it never imports or
    executes the cited code or resolves values outside that span."""
    out = []
    for match in _NUMBER.finditer(text):
        token = match.group(0)
        try:
            value = float(token)
        except ValueError:
            continue
        out.append(value)
        if token[0] == "-" and match.start() > 0 and text[match.start() - 1].isdigit():
            out.append(-value)  # "5-6000": a range, the hyphen is not a sign
    for match in _GROUPED.finditer(text):
        out.append(float(match.group(0).replace(",", "")))
    for match in _PY_LITERAL.finditer(text):
        token = match.group(0)
        try:
            out.append(float(token) if "_" in token and not re.search(r"0[xXbBoO]", token) else float(int(token, 0)))
        except (ValueError, OverflowError):
            continue  # a literal no float holds (a hex constant of more than 256 digits) shows nothing more
    for match in _PI_TERM.finditer(text):
        divisor = float(match.group("d") or 1)
        if divisor == 0:
            continue  # "pi / 0" shows no angle (it stopped the gate with ZeroDivisionError before)
        value = math.pi * float(match.group("k") or 1) * float(match.group("m") or 1) / divisor
        out.append(-value if match.group("sign") == "-" else value)
    for match in _RADIANS_CALL.finditer(text):
        out.append(math.radians(float(match.group("deg"))))
    for match in _DISCRETE.finditer(text):
        start = _DISCRETE_START.search(match.group("rest"))
        try:
            out.append(float((int(start.group("start")) if start else 0) + int(match.group("n")) - 1))
        except (ValueError, OverflowError):
            continue  # no float holds it (or int() refuses more than 4,300 digits): the line shows nothing more
    for match in _RANGE.finditer(text):
        out.extend(_range_ends(match))
    for match in _ONES.finditer(text):
        out.append(-1.0 if match.group("sign") else 1.0)
    out.extend(ones_box_bounds(text))
    if _IN_DEGREES.search(text):
        out.extend([math.radians(value) for value in list(out)])
    for match in _SYMMETRIC.finditer(text):
        out.append(-float(match.group("a") or match.group("b")))
    if _MAGNITUDE.search(text):
        out.extend([-value for value in list(out) if value > 0])
    return out


def _range_ends(match: re.Match[str]) -> list[float]:
    """The first and last element of one literal ``range(...)`` match; nothing for an empty range, a zero step or a
    literal no float holds (more than about 308 digits; ``int()`` also refuses more than 4300): such a line shows
    nothing more, as a plain literal of that length shows no usable bound either."""
    first, second, third = match.group("a"), match.group("b"), match.group("c")
    try:
        if second is None:
            start, stop, step = 0, int(first), 1
        else:
            start, stop, step = int(first), int(second), (int(third) if third is not None else 1)
        if step == 0:
            return []  # range() refuses a zero step: the line states no set of values
        values = range(start, stop, step)
        if not values:
            return []
        return [float(values[0]), float(values[-1])]
    except (OverflowError, ValueError):
        return []


def _in_unit(text: str, unit: str) -> list[float]:
    """The quantities ``text`` writes with a unit symbol that converts to ``unit`` (``0.08 m`` shows 80 in ``mm``)."""
    out = []
    for match in _QUANTITY.finditer(text):
        symbol = match.group("unit").replace("µ", "u").replace("μ", "u")
        if symbol == unit:
            continue
        try:
            out.append(_units.convert(float(match.group("value")), symbol, unit))
        except (_units.UnitError, ValueError):
            continue  # not a unit symbol, or another dimension
    return out


def _unshown(rule: Mapping[str, Any], cited: str) -> list[float]:
    """The bounds of ``rule`` the cited text does not show, in the rule's unit or converted from a unit the text writes.
    A bound of 0 is never reported: it is the floor of a magnitude (a voltage, a volume, a speed) that its setter
    states elsewhere, and it can only narrow a range."""
    found = _numbers_in(cited)
    if isinstance(rule.get("unit"), str):
        found += _in_unit(cited, rule["unit"])
    return [value for value in _bound_numbers(rule)
            if value != 0 and not any(abs(value - item) <= 1e-9 * max(1.0, abs(value)) for item in found)]


def _bound_numbers(rule: Mapping[str, Any]) -> list[float]:
    out: list[float] = []
    for key in ("min", "max"):
        value = rule.get(key)
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item):
                out.append(float(item))
    return out


def _git_status_label(tree: _upstream.UpstreamTree) -> str:
    return f"{tree.root} at {tree.commit[:12]}" if tree.pinned and tree.commit else str(tree.root)


# ---------------------------------------------------------------------------
# G1
# ---------------------------------------------------------------------------


def _g1(ctx: _Context, gate: Gate) -> None:
    for name in _REQUIRED_FILES:
        if not (ctx.dir / name).is_file():
            gate.error("MISSING_FILE", f"{name} is missing (package layout: task.json, driver.py, fake.py or "
                       "fixtures/, facts.md, test_driver.py, driver.lock.json, reference.json, REFERENCE.md and, "
                       "once the gate passed or the work is blocked, RESULT.json)", name)
    if ctx.mode == "hardware" and not ((ctx.dir / "fake.py").is_file() or (ctx.dir / "fixtures").is_dir()):
        gate.error("MISSING_FAKE", "a hardware driver needs fake.py or fixtures/ (the gate never touches hardware)",
                   "fake.py")
    if not (ctx.dir / "facts.md").is_file():
        gate.warning("NO_FACTS_MD", "facts.md is missing (tags and facts with their source and file:line)", "facts.md")
    if ctx.card is None:
        gate.error("CARD_INVALID", ctx.card_problem or f"{TASK_FILE} is invalid", TASK_FILE)
    else:
        _g1_card(ctx, gate)
    for path in sorted(ctx.dir.rglob("*")):
        relative = path.relative_to(ctx.dir)
        if path.is_symlink():
            try:
                resolved = path.resolve()
            except OSError:
                resolved = None
            if resolved is None or (resolved != ctx.dir and ctx.dir not in resolved.parents):
                gate.error("SYMLINK_OUTSIDE", f"{relative.as_posix()} is a symlink that leaves the package",
                           relative.as_posix())
        if path.name == "__pycache__" and path.is_dir():
            gate.warning("BYTECODE", f"{relative.as_posix()}/ holds bytecode; delete it (never commit __pycache__)",
                         relative.as_posix())
    for name, schema in (("RESULT.json", "driver-result.schema.json"), (EXAMPLE_OVERLAY, "site-limits.schema.json")):
        if not (ctx.dir / name).is_file():
            continue
        document, problem = read_json(ctx.dir / name)
        problems = [problem] if problem else default_store().validate(document, schema)
        for item in problems[:5]:
            gate.error("INVALID_FILE", f"{name}: {item}", name)
    problem = ctx.fixtures_problem
    if problem:
        gate.error("INVALID_FILE", problem, FIXTURES_FILE)
    if ctx.prerequisites_problem:
        gate.error("INVALID_PREREQUISITES", ctx.prerequisites_problem, "fixtures/gate-prerequisites.json")
    if ctx.clone_path is None:
        gate.error("NO_CLONE", f"{TASK_FILE} has no local_path, so the upstream clone cannot be checked", TASK_FILE)
    elif not ctx.clone_path.is_dir():
        gate.error("NO_CLONE", f"the upstream clone {ctx.clone_path} does not exist (task.json local_path; pass "
                   "--clone <path> for a sandbox copy)", str(ctx.clone_path))
    elif ctx.tree is not None:
        if ctx.clone_modified_before:
            gate.error("CLONE_MODIFIED", f"the upstream clone has modified tracked files: "
                       f"{ctx.clone_modified_before[:5]} (the clone is read-only: never write in it, not even to "
                       "restore it; an operator restores it from the pinned commit)", str(ctx.clone_path))
        for note in ctx.tree.notes:
            gate.warning("CLONE_NOTE", note, str(ctx.clone_path))
    if "companions" in (ctx.card or {}):
        _g1_companions(ctx, gate)


def _g1_companions(ctx: _Context, gate: Gate) -> None:
    """The companion sources the card declares (user decision 2026-11-05; ``companions``).

    Each is a corpus clone that must exist, be the top of a git checkout whose HEAD *is* the pinned commit (an
    error, stricter than the package clone's ``HEAD_DIFFERS`` warning: the deployment's simulator is matched to
    this exact source), and have no modified tracked file. Its ``version_evidence`` ties the package's stack to the
    companion's: every cited range shows its token (case-insensitive), the entry has evidence on the package side and
    on a companion side, and the distro of its profile is shown on both. Every defect is an error: nothing here is
    a warning a reviewer could accept.

    ``task.json`` is the package's own file, so its companions are believed only when the registry card confirms
    them: that card must exist and be readable (``COMPANION_CARD``), and :func:`_g1_card` refuses a ``task.json``
    that differs from it (``CARD_EDITED``). Only a reviewed override puts companions on the registry card
    (``MHS/registry/validate.py`` ``check_companions``), so a package cannot add or rewrite one.
    """
    if ctx.synthetic:
        gate.error("COMPANION_CARD", f"{TASK_FILE}: a synthetic tutorial (upstream null) declares no companions",
                   TASK_FILE)
        return
    registry = _registry_card(ctx)
    if registry is None or not registry.is_file():
        shown = (relative_to_root(registry, ctx.root) if registry is not None
                 else "MHS/registry/tasks/<track>/<package directory>.json")
        gate.error("COMPANION_CARD", f"{TASK_FILE} declares companions, but no registry card {shown} confirms them: "
                   "companions come only from a reviewed registry override through the registry card, which "
                   f"{TASK_FILE} must equal (run the gate on the package in the project tree)", TASK_FILE)
    else:
        _document, problem = read_json(registry)
        if problem is not None:
            gate.error("COMPANION_CARD", f"the registry card {relative_to_root(registry, ctx.root)} cannot be read "
                       f"({problem}), so the companions of {TASK_FILE} are not confirmed", TASK_FILE)
    for problem in ctx.companion_problems:
        gate.error("COMPANION_CARD", f"{TASK_FILE}: {problem}", TASK_FILE)
    locks: dict[Path, tuple[Any, str | None]] = {}
    for alias, source in ctx.companions.items():
        where = f"companions[{alias!r}]"
        if source.lock is not None:
            _g1_companion_lock(ctx, gate, where, source, locks)
        if source.tree is None:
            gate.error("NO_COMPANION_CLONE", f"{where}: the companion clone {source.path} ({source.package_id}) does "
                       "not exist", str(source.path))
            continue
        if not source.tree.is_git:
            gate.error("COMPANION_NOT_GIT", f"{where}: {source.path} is not the top of a git checkout, so its pinned "
                       f"commit {source.commit[:12]} cannot be read", str(source.path))
            continue
        head = source.tree.head()
        if head != source.commit:
            gate.error("COMPANION_HEAD", f"{where}: the companion clone is at {str(head)[:12]}, not the pinned "
                       f"{source.commit[:12]}; a companion is cited only at the commit its card pins (an operator "
                       "restores the clone; never write in it)", str(source.path))
        modified = ctx.companion_modified_before.get(alias)
        if modified is None:
            gate.error("COMPANION_MODIFIED", f"{where}: the tracked files of the companion clone cannot be checked "
                       "(git status failed)", str(source.path))
        elif modified:
            gate.error("COMPANION_MODIFIED", f"{where}: the companion clone has "
                       f"{'modified tracked or untracked' if source.lock is not None else 'modified tracked'} files: "
                       f"{modified[:5]} (the clone is read-only: never write in it, not even to restore it)",
                       str(source.path))
        if source.lock is not None:
            writable = source.tree.writable_entries()
            if writable:
                gate.error("COMPANION_WRITABLE", f"{where}: the fetched companion clone has write bits in its work "
                           f"tree: {writable} (LOCK.json clones are kept read-only with chmod -R a-w, .git excluded; "
                           "an operator re-fetches or restores it with tools/fetch_companions.py, never by writing "
                           "in it)", str(source.path))
        _g1_companion_version(ctx, gate, alias, source)


def _g1_companion_lock(ctx: _Context, gate: Gate, where: str, source: _upstream.CompanionSource,
                       locks: dict[Path, tuple[Any, str | None]]) -> None:
    """A fetched companion (``lock``) must match its ``LOCK.json`` entry (DESIGN-2, user authorisation 2026-11-05):
    the file exists in the companions root, lists the alias, repeats the card's commit, path, profile and ref, its
    repo_url names the card's package_id, and its needed_by lists this package. Every mismatch is an error."""
    root = source.lock_root
    if root not in locks:
        locks[root] = _upstream.read_companion_lock(root)
    entries, problem = locks[root]
    if entries is None:
        gate.error("COMPANION_LOCK", f"{where}: {problem}; a fetched companion is cited only as its LOCK.json lists "
                   "it (fetch it with tools/fetch_companions.py, or pass --companions-root DIR)", TASK_FILE)
        return
    for item in _upstream.lock_entry_problems(source, entries.get(str(source.lock)), (ctx.card or {}).get("package_id")):
        gate.error("COMPANION_LOCK", f"{where} (lock {source.lock}): {item}", TASK_FILE)


def _evidence_tree(ctx: _Context, side: Any, alias: str) -> tuple[Any, str] | None:
    """``(tree, label)`` of a ``version_evidence`` side: ``package``, ``companion`` (this one) or ``companion:<alias>``."""
    if side == "package":
        return (ctx.tree, "the package clone") if ctx.tree is not None else None
    if side == "companion":
        other = alias
    elif isinstance(side, str) and side.startswith("companion:"):
        other = side[len("companion:"):]
    else:
        return None
    source = ctx.companions.get(other)
    if source is None or source.tree is None or not source.tree.is_git:
        return None
    return source.tree, f"companion {source.label}"


def _g1_companion_version(ctx: _Context, gate: Gate, alias: str, source: _upstream.CompanionSource) -> None:
    where = f"companions[{alias!r}].version_evidence"
    distro_match = _upstream.COMPANION_PROFILE.match(source.profile)
    distro = distro_match.group("distro") if distro_match else ""
    shown: dict[str, list[str]] = {"package": [], "companion": []}
    for index, item in enumerate(source.evidence):
        side, ref_text, token = item.get("side"), item.get("ref"), item.get("token")
        label = f"{where}[{index}]"
        located = _evidence_tree(ctx, side, alias)
        ref = _upstream.parse_ref(ref_text)
        if located is None or ref is None or _upstream.safe_relpath(ref.path) != ref.path \
                or not isinstance(token, str) or len(token.strip()) < 2:
            gate.error("COMPANION_VERSION", f"{label}: needs side package, companion or companion:<declared alias>, "
                       "a path:LINE ref in that tree and a token", TASK_FILE, str(ref_text))
            continue
        tree, tree_label = located
        document = tree.read_text(ref.path)
        lines = document.splitlines() if document is not None else []
        if document is None or ref.end > len(lines):
            gate.error("COMPANION_VERSION", f"{label}: {ref} does not exist in {tree_label} at its pinned commit",
                       TASK_FILE, str(ref_text))
            continue
        cited = "\n".join(lines[ref.line - 1:ref.end]).lower()
        if token.lower() not in cited:
            gate.error("COMPANION_VERSION", f"{label}: {ref} in {tree_label} does not show {token!r}", TASK_FILE,
                       str(ref_text))
            continue
        shown["package" if side == "package" else "companion"].append(cited)
    for kind in ("package", "companion"):
        if not shown[kind]:
            gate.error("COMPANION_VERSION", f"{where}: no {kind}-side evidence range that shows its token; the version "
                       "match needs both sides", TASK_FILE)
        elif distro and not any(distro in text for text in shown[kind]):
            gate.error("COMPANION_VERSION", f"{where}: no {kind}-side evidence range shows the profile's distro "
                       f"{distro!r} ({source.profile})", TASK_FILE)


def _registry_card(ctx: _Context) -> Path | None:
    """``MHS/registry/tasks/<track>/<package directory>.json`` under the project root: the registry card that
    ``task.json`` must equal (``CARD_EDITED``). ``None`` without a root or when ``track`` is not one plain path
    segment (the card schema allows ``labs`` and ``robots``), so a ``track`` can never point the comparison at a file
    outside the registry's task cards."""
    track = (ctx.card or {}).get("track")
    if ctx.root is None or not isinstance(track, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", track):
        return None
    return ctx.root / "MHS" / "registry" / "tasks" / track / f"{ctx.dir.name}.json"


def _g1_card(ctx: _Context, gate: Gate) -> None:
    card = ctx.card or {}
    for key in ("package_id", "driver_dir", "local_path"):
        if not isinstance(card.get(key), str) or not card.get(key):
            gate.error("CARD_INVALID", f"{TASK_FILE}: {key} must be a non-empty string", TASK_FILE)
    if "upstream" not in card:
        gate.error("CARD_INVALID", f"{TASK_FILE}: upstream is missing (null only for a synthetic tutorial)", TASK_FILE)
    if card.get("quarantine") is True:
        gate.error("QUARANTINE", f"{TASK_FILE} is quarantined: this package must not be built (RESULT.json blocked "
                   "QUARANTINE)", TASK_FILE)
    driver_dir = card.get("driver_dir")
    if isinstance(driver_dir, str) and driver_dir:
        here = relative_to_root(ctx.dir, ctx.root)
        inside = ctx.root is not None and not Path(here).is_absolute()
        if inside and PurePosixPath(driver_dir).as_posix().rstrip("/") != here:
            gate.error("CARD_MISMATCH", f"{TASK_FILE} driver_dir is {driver_dir!r}, but the package is {here!r}",
                       TASK_FILE)
        elif not inside and PurePosixPath(driver_dir).name != ctx.dir.name:
            gate.error("CARD_MISMATCH", f"{TASK_FILE} driver_dir {driver_dir!r} does not name this directory "
                       f"({ctx.dir.name!r})", TASK_FILE)
    if ctx.root is not None and not ctx.synthetic:
        registry = _registry_card(ctx)
        if registry is not None and registry.is_file():
            document, problem = read_json(registry)
            if problem is None and document != card:
                gate.error("CARD_EDITED", f"{TASK_FILE} differs from the registry card "
                           f"{relative_to_root(registry, ctx.root)}; task.json is input and is never edited", TASK_FILE)
        schema = ctx.root / "MHS" / "registry" / "schema" / "taskcard.schema.json"
        if schema.is_file():
            try:
                from ..schema.store import SchemaStore

                # A private store: indexing a file by path must not leak into the shared default store.
                problems = SchemaStore(extra_roots=[schema.parent]).validate(card, str(schema))
            except Exception as exc:  # noqa: BLE001 - a schema we cannot use is not the package's fault
                problems = []
                gate.warning("CARD_SCHEMA", f"taskcard.schema.json cannot be applied ({type(exc).__name__}: {exc})")
            for item in problems[:5]:
                gate.error("CARD_INVALID", f"{TASK_FILE}: {item}", TASK_FILE)


def _g1_after(ctx: _Context, gate: Gate) -> None:
    for alias, before in ctx.companion_modified_before.items():
        source = ctx.companions.get(alias)
        after = (source.tree.modified(untracked=source.lock is not None)
                 if source is not None and source.tree is not None else None)
        if after is None or after != (before or []):
            gate.error("COMPANION_WRITTEN", f"companions[{alias!r}]: the companion clone changed while the gate ran (or "
                       f"cannot be checked any more): {(after or [])[:5]}", str(source.path if source else alias))
            gate.settle()
    if ctx.tree is None:
        return
    after = ctx.tree.modified()
    if after is not None and after != (ctx.clone_modified_before or []):
        gate.error("CLONE_WRITTEN", f"the upstream clone changed while the gate ran: {after[:5]}", str(ctx.clone_path))
        gate.settle()
    _g1_submodules(ctx, gate)


def _g1_submodules(ctx: _Context, gate: Gate) -> None:
    """One warning per git submodule the gates read (SUBMODULES, 2026-11-05): evidence from another repository."""
    tree = ctx.tree
    records = sorted(getattr(tree, "submodules", {}).values(), key=lambda item: item.path)
    for record in records:
        gate.warning("SUBMODULE_SOURCE", f"{record.path}/ is the git submodule {record.name!r}: the gates read it at "
                     f"{record.commit}, the gitlink of the pinned commit {str(ctx.commit)[:12]}, from its own object "
                     f"store {record.git_dir} (its checkout's HEAD is that commit); it is another repository, whose "
                     "licence the card does not state", record.path, record.commit)
    if records:
        gate.settle()


# ---------------------------------------------------------------------------
# G2
# ---------------------------------------------------------------------------


def _g2(ctx: _Context, gate: Gate) -> None:
    if not (ctx.dir / LOCK_FILE).is_file():
        gate.error("NO_LOCK", f"{LOCK_FILE} is missing (python3 -m mhs.driver new writes it)", LOCK_FILE)
        return
    lock = ctx.lock if isinstance(ctx.lock, Mapping) else {}
    problems = list(ctx.lock_problems)
    if ctx.synthetic:
        problems = [item for item in problems if not item.endswith(_SYNTHETIC_LOCK_ERROR)]
        if lock.get("upstream", "missing") is not None:
            gate.error("SYNTHETIC_LOCK", f"a synthetic tutorial ({TASK_FILE} upstream null) has upstream null in "
                       f"{LOCK_FILE}", LOCK_FILE)
        if ctx.root is not None and (ctx.root / "MHS" / "drivers") in ctx.dir.parents:
            gate.error("NO_UPSTREAM", f"{TASK_FILE} has upstream null, but real driver packages (MHS/drivers/) always "
                       "pin an upstream repository, commit and licence", TASK_FILE)
        else:
            gate.warning("SYNTHETIC", f"synthetic tutorial ({TASK_FILE} upstream null): no repository to pin; G4 and "
                         f"G7 read the synthetic upstream {(ctx.card or {}).get('local_path')!r} inside the package",
                         TASK_FILE)
    for item in problems[:10]:
        gate.error("LOCK_INVALID", item, LOCK_FILE)
    if not lock:
        return
    card = ctx.card or {}
    if lock.get("package_id") != card.get("package_id"):
        gate.error("PACKAGE_MISMATCH", f"{LOCK_FILE} package_id {lock.get('package_id')!r} differs from {TASK_FILE} "
                   f"{card.get('package_id')!r}", LOCK_FILE)
    if lock.get("sdk_version") != _ids.SDK_VERSION:
        gate.warning("SDK_VERSION", f"{LOCK_FILE} sdk_version {lock.get('sdk_version')!r} differs from the running SDK "
                     f"{_ids.SDK_VERSION}", LOCK_FILE)
    if not ctx.synthetic:
        _g2_upstream(ctx, gate, lock)
    if "companions" in card or "companions" in lock:
        _g2_companions(ctx, gate, lock)
    _g2_backends(ctx, gate, lock)
    files = lock.get("files") if isinstance(lock.get("files"), Mapping) else {}
    for name, digest in sorted(files.items()):
        rel = _upstream.safe_relpath(str(name))
        try:
            data = (ctx.dir / rel).read_bytes() if rel else None
        except OSError:
            data = None
        actual = "sha256:" + hashlib.sha256(data).hexdigest() if data is not None else None
        if actual != digest:
            gate.warning("FILE_CHANGED", f"{name} changed since {LOCK_FILE} was written (files digest)", str(name))


def _g2_upstream(ctx: _Context, gate: Gate, lock: Mapping[str, Any]) -> None:
    card = ctx.upstream_card
    pinned = lock.get("upstream") if isinstance(lock.get("upstream"), Mapping) else {}
    if not card:
        gate.error("CARD_UPSTREAM", f"{TASK_FILE} upstream must be {{repo_url, commit, license_spdx}}", TASK_FILE)
        return
    for key, code in (("commit", "COMMIT_MISMATCH"), ("repo_url", "REPO_MISMATCH"), ("license_spdx", "LICENSE_MISMATCH")):
        if card.get(key) is None:
            gate.error("CARD_UPSTREAM", f"{TASK_FILE} upstream has no {key}", TASK_FILE)
        elif pinned.get(key) != card.get(key):
            gate.error(code, f"{LOCK_FILE} upstream.{key} {pinned.get(key)!r} differs from the card's "
                       f"{card.get(key)!r}", LOCK_FILE)
    if card.get("license_class") and pinned.get("license_class") and card["license_class"] != pinned["license_class"]:
        gate.warning("LICENSE_CLASS", f"license_class {pinned['license_class']!r} differs from the card's "
                     f"{card['license_class']!r}", LOCK_FILE)
    tree = ctx.tree
    if tree is None:
        return
    if tree.is_git:
        if not tree.has_commit(ctx.commit):
            gate.error("COMMIT_ABSENT", f"the pinned commit {ctx.commit} is not in the clone {tree.root}",
                       str(tree.root))
        else:
            head = tree.head()
            if head and head != ctx.commit:
                gate.warning("HEAD_DIFFERS", f"the clone is at {head[:12]}, not the pinned {str(ctx.commit)[:12]}; G4 "
                             "and G7 read the pinned commit from the object store", str(tree.root))
    else:
        gate.warning("NOT_GIT", f"the clone {tree.root} is not a git checkout: the pinned commit cannot be verified "
                     "and G4/G7 read the working tree", str(tree.root))


def _g2_companions(ctx: _Context, gate: Gate, lock: Mapping[str, Any]) -> None:
    """``driver.lock.json`` ``companions`` repeat the card's ``[{package_id, commit}]`` in order, with the ``lock``
    alias of a fetched companion; each pinned commit is in its clone. A lock may not add a companion the card does
    not declare, nor drop one it does."""
    card_items = (ctx.card or {}).get("companions")
    expected = [{"package_id": item.get("package_id"), "commit": item.get("commit"),
                 **({"lock": item.get("lock")} if "lock" in item else {})}
                for item in (card_items if isinstance(card_items, list) else []) if isinstance(item, Mapping)]
    locked = lock.get("companions")
    actual = [dict(item) for item in locked] if isinstance(locked, list) and all(
        isinstance(item, Mapping) for item in locked) else locked
    if actual != expected:
        gate.error("COMPANION_MISMATCH", f"{LOCK_FILE} companions {actual!r} differ from the card's {expected!r} "
                   "(each {package_id, commit} of task.json companions, with its lock when it has one, in order)",
                   LOCK_FILE)
    for alias, source in ctx.companions.items():
        if source.tree is not None and source.tree.is_git and not source.tree.has_commit(source.commit):
            gate.error("COMPANION_COMMIT_ABSENT", f"companions[{alias!r}]: the pinned commit {source.commit} is not in "
                       f"the companion clone {source.path}", str(source.path))


def _g2_backends(ctx: _Context, gate: Gate, lock: Mapping[str, Any]) -> None:
    if ctx.cls is None:
        return
    declared = dict(getattr(ctx.cls, "backends", {}) or {})
    strings = {key: value for key, value in declared.items() if isinstance(value, str)}
    locked = lock.get("backends") if isinstance(lock.get("backends"), Mapping) else {}
    if strings and len(strings) == len(declared) and dict(locked) != strings:
        gate.error("BACKENDS_DIFFER", f"{LOCK_FILE} backends {dict(locked)} differ from the class's backends: set "
                   f"\"backends\" to {json.dumps(strings, sort_keys=True)} (`mhs.driver new` writes the backends of its "
                   "template kind, not those of your class)", LOCK_FILE)


# ---------------------------------------------------------------------------
# G3
# ---------------------------------------------------------------------------


def _g3(ctx: _Context, gate: Gate) -> None:
    for code, message, path in static_findings(ctx.dir, ctx.card):
        gate.findings.append(Finding(code, message, "error", path))
    if ctx.import_error is not None:
        gate.error("IMPORT", f"the driver cannot be loaded: {ctx.import_error}", "driver.py")
        return
    if ctx.model_error is not None:
        for problem in ctx.model_error.problems:
            gate.error("DEFINITION", problem, "driver.py")
        return
    model = ctx.model
    card = ctx.card or {}
    safety = card.get("safety") if isinstance(card.get("safety"), Mapping) else {}
    expected = safety.get("expected_mode")
    if expected in ("hardware", "simulated") and expected != model.mode:
        # The card decides the mode: a hardware card done as a "simulated" driver would skip every hardware rule
        # below (e-stop, safe state, LIMITS_UNSET, the fake-backend checks) and the gate's fake/sim backend checks.
        gate.error("MODE_MISMATCH", f"the driver declares mode {model.mode!r}, but {TASK_FILE} safety.expected_mode "
                   f"is {expected!r}: build the driver in the card's mode (a hardware card needs a hardware driver "
                   "with a fake backend; the gate never touches hardware)", "driver.py")
    if getattr(model, "estop_confirmation", None) is not None:
        _g3_sensed(ctx, gate, expected)
    _g3_backends(ctx, gate)
    from .build import build_manifest, device_from_manifest, strict_findings

    subject = ctx.instance if ctx.instance is not None else ctx.cls
    views = ([("simulated", ctx.backend)] if model.mode == "simulated"
             else [("hardware view", "hardware"), (f"{ctx.backend} view", ctx.backend)])
    seen: set[str] = set()
    for label, view in views:
        try:
            findings = strict_findings(subject, backend=view)
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # noqa: BLE001
            gate.error("STRICT", f"{label}: strict resolution failed: {_crash_text(exc)}", "driver.py")
            continue
        for finding in findings:
            text = finding.text()
            if text in seen:
                continue
            seen.add(text)
            if getattr(finding, "refuse", True):
                gate.error("STRICT", f"{label}: {text}", "driver.py")
            else:
                gate.warning("STRICT_NOTE", f"{label}: {text}", "driver.py")
    if model.mode == "hardware" and not any(item.severity == "error" for item in gate.findings):
        _g3_hardware_limits(ctx, gate, build_manifest, device_from_manifest)
    floor = safety.get("risk_floor")
    if floor in _RISKS and _risk_index(model.risk) < _risk_index(floor):
        gate.error("RISK_FLOOR", f"risk {model.risk} is below the task card's risk_floor {floor}", "driver.py")
    if model.device_kind not in _catalog.default_catalog().resource_kinds:
        gate.error("UNKNOWN_KIND", f"device_kind {model.device_kind!r} is not a catalogue resource kind "
                   "(python3 -m mhs.driver catalog show <cap id> lists a class's kinds)", "driver.py")
    if model.mode == "hardware" and _risk_index(model.risk) >= 1:
        if model.estop is None:
            gate.error("NO_ESTOP", f"a hardware driver at {model.risk} needs an @estop method (the native stop the "
                       "runtime calls after it latches)", "driver.py")
        if not model.safe_state:
            gate.error("NO_SAFE_STATE", f"a hardware driver at {model.risk} declares safe_state (one sentence)",
                       "driver.py")
    derived = {binding.capability_id: set(binding.derived_limits) for binding in model.bindings}
    for capability_id, path, rule in _limit_rules(model):
        where = f"{capability_id} {path}"
        if rule == "operator_required":
            continue
        if not isinstance(rule, Mapping):
            gate.error("LIMIT_INVALID", f"{where}: limit {rule!r} is not a rule", path)
            continue
        source, ref = rule.get("source"), rule.get("ref")
        if source is None and path in derived.get(capability_id, ()):
            continue  # derived from a fake backend's action space, not a Limit: its ref names the backend
        if source == "operator":
            gate.error("LIMIT_SOURCE", f"{where}: an operator bound belongs in site-limits.json (the overlay), not "
                       "in driver.py; cite vendor_doc/upstream_code or use Limit.operator_required(reason)", path)
        elif source not in ("vendor_doc", "upstream_code"):
            gate.error("UNSOURCED_LIMIT", f"{where}: every Limit cites source='vendor_doc' or 'upstream_code' and "
                       "ref='path:LINE'; when no source states the bound use Limit.operator_required(reason)", path)
        elif not isinstance(ref, str) or not ref.strip():
            gate.error("UNSOURCED_LIMIT", f"{where}: source {source} needs ref='path/in/clone:LINE'", path)
    authored = (ctx.lock or {}).get("authored_by") if isinstance(ctx.lock, Mapping) else None
    if isinstance(authored, Mapping) and authored.get("kind") == "model":
        for fact in model.facts:
            if fact.source not in ("vendor_doc", "upstream_code"):
                gate.error("FACT_SOURCE", f"fact {fact.text[:80]!r}: a model-authored driver writes only vendor_doc "
                           f"or upstream_code facts (got {fact.source})", "driver.py")
    owner, _repo = _owner_repo(card)
    if owner:
        expected = re.sub(r"[^a-z0-9_-]+", "_", owner.lower())
        for binding in model.bindings:
            if binding.capability_id.startswith("x-cap."):
                segment = binding.capability_id.split(".")[1]
                if segment not in (expected, owner.lower()):
                    gate.warning("XCAP_OWNER", f"{binding.capability_id}: extension ids are x-cap.{expected}.<name>.v1 "
                                 "(the owner of the upstream repository)", binding.capability_id)
    ctx.g3_ok = not any(item.severity == "error" for item in gate.findings)


def _g3_sensed(ctx: _Context, gate: Gate, expected: Any) -> None:
    """A sensed-confirmation stop (SAFE-049): a simulated card, the fake backend's placeholder thresholds and ROS 2
    source histories, and (verification F3 of phase 3) a served manifest of mode ``simulated`` on the SDK's own ROS
    route, the only one an endpoint binds."""
    if expected != "simulated":
        # A dual-mode registry record yields a hardware card, and an override cannot remove a scanned hardware mode:
        # no hardware card can use the profile (the user's decision of 2026-11-05: simulators only).
        gate.error("SENSED_STOP_CARD", f"a sensed-confirmation stop is for simulated devices only (SAFE-049); "
                   f"{TASK_FILE} safety.expected_mode is {expected!r}, not 'simulated'", "driver.py")
    _g3_sensed_served(ctx, gate)
    declared = getattr(ctx.cls, "_sensed_declaration", None)
    if not callable(declared):
        return
    from . import sensed_stop

    declaration, problems = declared()
    if declaration is None or problems:
        return
    for read in (sensed_stop.fixture_values, sensed_stop.fixture_history):
        try:
            read(ctx.dir, declaration)
        except ValueError as exc:
            gate.error("SENSED_FIXTURE", f"{exc} (placeholders for the fake backend only, never a device fact)",
                       sensed_stop.FIXTURE)


def _g3_sensed_served(ctx: _Context, gate: Gate) -> None:
    """Verification F3: the endpoint lets a sensed confirmation stand for a stop only on what it serves, a manifest
    of mode ``simulated`` declaring the confirmation, and only on the SDK's own ROS route (it binds no other bridge).
    The served manifest is checked as the server checks it at start-up."""
    from types import SimpleNamespace

    from ..server import _sdk_ros_route_class, _sensed_stop_problems
    from .build import build_manifest

    subject = ctx.instance if ctx.instance is not None else ctx.cls
    try:
        manifest = build_manifest(subject, backend=ctx.backend)
    except KeyboardInterrupt:
        raise
    except BaseException as exc:  # noqa: BLE001 - reported by the strict views below
        gate.error("SENSED_SERVED", f"the served manifest of the sensed-confirmation stop cannot be built: "
                   f"{_crash_text(exc)}", "driver.py")
        return
    served = SimpleNamespace(device_id=manifest.get("device_id"), mode=manifest.get("mode"),
                             safety=SimpleNamespace(estop=(manifest.get("safety") or {}).get("estop")))
    for problem in _sensed_stop_problems(served):
        gate.error("SENSED_SERVED", problem, "driver.py")
    estop = (manifest.get("safety") or {}).get("estop")
    if not isinstance(estop, Mapping) or not isinstance(estop.get("confirmation"), Mapping):
        gate.error("SENSED_SERVED", "the served manifest does not publish safety.estop.confirmation, so no endpoint "
                   "binds the sensed-confirmation stop (SAFE-049, CORE-088)", "driver.py")
    if not _sdk_ros_route_class(ctx.cls):
        gate.error("SENSED_ROUTE", "a sensed-confirmation stop stands for a stop only on the SDK's own ROS route: a "
                   "RosDriver that does not override call, make_bridge, inner, estop, safety_status or "
                   "_run_safe_state (the endpoint binds no other bridge, so its confirmation would never commit)",
                   "driver.py")


def _hardware_view_subject(ctx: _Context, driver: Any = None) -> Any:
    """Publish the exact verified model snapshot, with no caller projection hook.

    Dynamic hardware contracts are supported only by the explicit Ophyd unit
    metadata compiler. All model fields are compared, including non-manifest
    action risk and the fully resolved schemas/constraints. No native factory is
    selected and a second build cannot invoke a subclass hook to erase policy.
    """
    import copy
    from .base import Driver
    from .families import HttpDriver, OphydDriver, Sila2Driver
    from .ophyd_config import model_contract
    subject = driver if driver is not None else ctx.instance
    if subject is None:
        return ctx.cls
    from .mcp_client_driver import McpClientDriver
    if issubclass(ctx.cls, McpClientDriver):
        projection = object.__new__(Driver)
        projection._model = McpClientDriver._verified_model(subject)
        projection.backend = subject.backend
        return projection
    if issubclass(ctx.cls, Sila2Driver):
        Sila2Driver._verify(subject)
        projection = object.__new__(Driver)
        projection._model = copy.deepcopy(subject._sila_model)
        projection.backend = subject.backend
        return projection
    if issubclass(ctx.cls, HttpDriver):
        projection = object.__new__(Driver)
        projection._model = HttpDriver._verified_model(subject)
        projection.backend = subject.backend
        return projection
    if not issubclass(ctx.cls, OphydDriver):
        raise DriverDefinitionError("instance-specific hardware projection requires an explicit supported metadata compiler")
    OphydDriver._check_runtime_hooks.__func__(ctx.cls)
    expected = OphydDriver._declared_model.__func__(ctx.cls, subject._ophyd_options, subject.backend)
    runtime = OphydDriver._declared_runtime_config.__func__(ctx.cls, expected, subject._ophyd_options, subject.backend)
    runtime_contract = model_contract(runtime)
    if (model_contract(subject._ophyd_config) != runtime_contract
            or subject._ophyd_runtime_contract != runtime_contract
            or getattr(ctx, '_ophyd_trusted_runtime', runtime_contract) != runtime_contract):
        raise DriverDefinitionError('Ophyd runtime mapping changed the trusted hardware contract')
    candidate = copy.deepcopy(subject._model)
    contract = model_contract(candidate)
    trusted = getattr(ctx, "_ophyd_trusted_contract", subject._ophyd_contract)
    if contract != model_contract(expected) or contract != subject._ophyd_contract or contract != trusted:
        raise DriverDefinitionError("instance metadata changed the declared hardware contract beyond explicit unit_bindings")
    # This is a data-only Driver shell: construction/open is intentionally not
    # called. The original driver remains the bridge of hardware_endpoint.
    projection = object.__new__(Driver)
    projection._model = candidate
    projection.backend = subject.backend
    return projection


def _g3_hardware_limits(ctx: _Context, gate: Gate, build_manifest: Any, device_from_manifest: Any) -> None:
    """Hardware view: R1+ write/invoke numeric inputs need a limit or operator_required (``LIMITS_UNSET``)."""
    from ..server import MHSServer
    from .._server.strict import MHSStrictError

    try:
        manifest = build_manifest(_hardware_view_subject(ctx), backend="hardware")
        device = device_from_manifest(manifest, None)
        server = MHSServer("mhs://localhost", [device], strict=True)
    except (DriverDefinitionError, MHSStrictError) as exc:
        for item in getattr(exc, "problems", None) or [str(exc)]:
            gate.error("STRICT", f"hardware view: {item}", "driver.py")
        return
    except Exception as exc:  # noqa: BLE001
        gate.error("STRICT", f"hardware view cannot be served: {type(exc).__name__}: {exc}", "driver.py")
        return
    try:
        for finding in server.strict_findings:
            if finding.get("rule") == "limits-unset":
                gate.error("LIMITS_UNSET", f"{finding.get('capability_id')}: {finding.get('message')}; on hardware at "
                           "R1+ every numeric input needs a sourced Limit or Limit.operator_required(reason)",
                           str(finding.get("capability_id")))
    finally:
        server.close()


def _package_module(ctx: _Context, module: Any) -> bool:
    """True for a module of this driver package or of the SDK (``mhs``); False for upstream or other code."""
    if not isinstance(module, str):
        return False
    package = str(getattr(ctx.cls, "__module__", "")).rpartition(".")[0]
    return (bool(package) and (module == package or module.startswith(package + "."))) or module == "mhs" \
        or module.startswith("mhs.")


def _clone_locations(ctx: _Context, klass: type) -> set[str]:
    """``file:Class`` of an imported class in the clone (:attr:`mhs.driver.upstream.Surface.classes` form).

    Two independent readings: the class's import path resolved in the clone's
    AST, and the file it was loaded from when that file lies inside the clone.
    Empty for classes that are not upstream code (builtins, other libraries).
    """
    out: set[str] = set()
    module, name = getattr(klass, "__module__", None), getattr(klass, "__qualname__", None)
    if ctx.tree is None or not isinstance(module, str) or not isinstance(name, str) or module == "builtins" \
            or "<locals>" in name:
        return out
    try:
        surface = _upstream.class_surface(ctx.tree, f"{module}:{name}")
    except Exception:  # noqa: BLE001 - an unreadable module is simply not a location
        surface = None
    if surface is not None and surface.found:
        out.update(surface.classes[:1])
    try:
        source = inspect.getsourcefile(klass)
    except (TypeError, OSError):
        source = None
    if source and ctx.clone_path is not None:
        path, clone = Path(source).resolve(), ctx.clone_path.resolve()
        if clone in path.parents:
            out.add(f"{path.relative_to(clone).as_posix()}:{klass.__name__}")
    return out


def _g3_backends(ctx: _Context, gate: Gate) -> None:
    """A hardware driver's fake/sim backend is never the upstream ``native`` class: the gate never touches hardware.

    A string entry outside the package (``"pkg.mod:Class"``) is refused unless
    the card names an upstream simulator (``mock_strategy.preferred``
    ``"upstream-sim"``), and even then it may not be ``native`` or a subclass
    of it in the clone's AST (it is not imported here).  A package entry
    (``".fake:Fake"``) or a callable is resolved: neither it nor a class in its
    MRO may be ``native`` (compared by import path and by the class's location
    in the clone, so ``native`` named through a re-export is still seen), and
    it must be package or SDK code.
    """
    if ctx.cls is None or ctx.model is None or ctx.model.mode != "hardware":
        return
    from .base import _resolve_symbol

    native = getattr(ctx.cls, "native", None)
    native = native.strip() if isinstance(native, str) and ":" in native else None
    card = ctx.card or {}
    strategy = card.get("mock_strategy") if isinstance(card.get("mock_strategy"), Mapping) else {}
    upstream_sim = strategy.get("preferred") == "upstream-sim"
    declared = dict(getattr(ctx.cls, "backends", {}) or {})
    hint = "write the fake in fake.py ('.fake:Fake...') or record fixtures/; the gate never opens the device"
    native_location: str | None = None  # ``file:Class`` of native in the clone, "" when it cannot be read
    for key in ("fake", "sim"):
        entry = declared.get(key)
        if entry is None:
            continue
        where = f"backends[{key!r}]"
        if isinstance(entry, str) and not entry.startswith("."):
            if native and entry.strip() == native:
                gate.error("FAKE_IS_NATIVE", f"{where} = {entry!r} is the upstream class native itself: the {key} "
                           f"backend would drive the hardware; {hint}", "driver.py")
            elif not upstream_sim:
                gate.error("FAKE_OUTSIDE_PACKAGE", f"{where} = {entry!r} is code outside the package: a hardware "
                           f"driver's {key} backend is the package's fake unless the card names an upstream simulator "
                           "(mock_strategy.preferred 'upstream-sim')", "driver.py")
            elif native and ctx.tree is not None:
                native_surface = _upstream.class_surface(ctx.tree, native)
                sim_surface = _upstream.class_surface(ctx.tree, entry)
                if native_surface.classes and native_surface.classes[0] in sim_surface.classes:
                    gate.error("FAKE_IS_NATIVE", f"{where} = {entry!r} is (or derives from) the upstream class "
                               f"{native} ({native_surface.classes[0]} in the clone): it inherits the hardware code; "
                               f"{hint}", "driver.py")
            continue
        try:
            package = getattr(sys.modules.get(ctx.cls.__module__), "__package__", None)
            target = _resolve_symbol(entry, package) if isinstance(entry, str) else entry
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # noqa: BLE001 - a backend that cannot load is a finding
            gate.error("BACKEND_IMPORT", f"{where} = {entry!r} cannot be loaded: {_crash_text(exc)}", "driver.py")
            continue
        chain = list(target.__mro__) if inspect.isclass(target) else [target]
        if native and native_location is None and ctx.tree is not None:
            located = _upstream.class_surface(ctx.tree, native).classes[:1]
            native_location = located[0] if located else ""
        for klass in chain:
            symbol = f"{getattr(klass, '__module__', '')}:{getattr(klass, '__qualname__', '')}"
            same = bool(native) and symbol == native
            if not same and native_location and inspect.isclass(klass) \
                    and not _package_module(ctx, getattr(klass, "__module__", None)):
                # native may name the class through a re-export ("pkg:Class"): compare where it is defined.
                same = native_location in _clone_locations(ctx, klass)
            if same:
                what = "the upstream class" if klass is target else "a class derived from the upstream class"
                gate.error("FAKE_IS_NATIVE", f"{where} = {entry!r} resolves to {what} {native}: it inherits the "
                           f"hardware code; {hint}", "driver.py")
                break
        else:
            module = getattr(target, "__module__", None)
            if not upstream_sim and not _package_module(ctx, module):
                gate.error("FAKE_OUTSIDE_PACKAGE", f"{where} = {entry!r} resolves to {module}:"
                           f"{getattr(target, '__qualname__', '?')}, code outside the package: a hardware driver's "
                           f"{key} backend is the package's own fake; {hint}", "driver.py")


# ---------------------------------------------------------------------------
# G4
# ---------------------------------------------------------------------------


def _g4(ctx: _Context, gate: Gate) -> None:
    if ctx.model is None:
        gate.skip("not run: the driver did not resolve (G3)")
        return
    tree = ctx.tree
    if tree is None:
        gate.error("NO_CLONE", "no upstream clone to check the references against (G1)")
        return
    if not ctx.synthetic and not tree.pinned:
        gate.warning("WORKTREE", f"references are checked against the working tree of {tree.root} (not the pinned "
                     "commit)")
    refs: list[tuple[str, str, Any, Mapping[str, Any] | None]] = []
    for capability_id, path, rule in _limit_rules(ctx.model):
        if isinstance(rule, Mapping) and rule.get("source") in ("vendor_doc", "upstream_code"):
            if (_derived(ctx, capability_id) and _upstream.parse_ref(rule.get("ref")) is None
                    and not _upstream.is_companion_ref(rule.get("ref"))):
                continue  # derived from the simulator object itself (its spaces / model)
            refs.append(("limit", f"{capability_id} {path}", rule.get("ref"), rule))
    for fact in ctx.model.facts:
        if fact.source in ("vendor_doc", "upstream_code"):
            refs.append(("fact", f"fact {fact.text[:60]!r}", fact.ref, None))
    # A cited threshold of a sensed-confirmation stop is a limit: its line must show the number (SAFE-049).
    confirmation = getattr(ctx.model, "estop_confirmation", None) or {}
    for item in confirmation.get("thresholds") or []:
        if isinstance(item, Mapping) and item.get("source") in ("vendor_doc", "upstream_code"):
            rule = {key: item[key] for key in ("source", "ref", "unit") if item.get(key) is not None}
            rule[str(item.get("bound"))] = item.get("value")
            refs.append(("limit", f"sensed_stop threshold {item.get('name')}", item.get("ref"), rule))
    physical = ctx.model.estop_physical_ref
    if physical:
        if _upstream.parse_ref(physical) is not None or _upstream.is_companion_ref(physical):
            refs.append(("estop", "estop_physical_ref", physical, None))
        else:
            gate.warning("ESTOP_REF", f"estop_physical_ref {physical!r} is not a path:LINE reference; it cannot be "
                         "checked", "estop_physical_ref")
    space_ref = getattr(ctx.cls, "action_space_ref", None)
    if _upstream.is_companion_ref(space_ref):
        # The definition already refuses it (families.py); refused here too, so the scope rule has one place.
        refs.append(("space", "action_space_ref", space_ref, None))
    label = _git_status_label(tree)
    for kind, where, text, rule in refs:
        if _upstream.is_companion_ref(text):
            # A companion source (user decision 2026-11-05) is citable by facts only here; a bound, the physical
            # stop and the action space always cite the package's own clone.
            parsed = _upstream.parse_source_ref(text)
            if parsed is None:
                gate.error("REF_FORMAT", f"{where}: ref {text!r} must be 'companion:<alias>/path/in/companion:LINE' "
                           "with a clean relative path", where, str(text))
                continue
            if kind != "fact":
                # A hardware companion_stop citation is checked in G7, not here. Bounds stay on the package clone.
                gate.error("COMPANION_REF_SCOPE", f"{where}: ref {text!r} cites a companion source; only facts, the "
                           "e-stop, its read-back and the declared re-enable may (a bound, estop_physical_ref and "
                           "action_space_ref cite the package's own clone)", where, str(text))
                continue
            source = ctx.companions.get(parsed[0])
            if source is None:
                gate.error("COMPANION_UNDECLARED", f"{where}: ref {text!r} names companion {parsed[0]!r}, which "
                           f"{TASK_FILE} does not declare (companions come only from a reviewed registry override)",
                           where, str(text))
                continue
            if source.tree is None or not source.tree.pinned:
                gate.error("REF_MISSING", f"{where}: the companion clone of {parsed[0]!r} cannot be read at its pinned "
                           "commit (G1, G2)", where, str(text))
                continue
            _g4_resolve(gate, source.tree, parsed[1], kind, where, text, rule, f"{source.package_id} at {source.label}",
                        companion=True)
            continue
        ref = _upstream.parse_ref(text)
        if ref is None:
            gate.error("REF_FORMAT", f"{where}: ref {text!r} must be 'path/in/clone:LINE'", where, str(text))
            continue
        _g4_resolve(gate, tree, ref, kind, where, text, rule, label)


def _g4_resolve(gate: Gate, tree: Any, ref: Any, kind: str, where: str, text: Any, rule: Any, label: str, *,
                companion: bool = False) -> None:
    """One G4 citation: the file exists in ``tree`` at its pin, the line exists, and a limit's line shows its bound.

    A companion citation into a binary file is an error, not the ``REF_BINARY`` warning a signature accepts: every
    companion defect fails the gate."""
    relpath = _upstream.safe_relpath(ref.path)
    if relpath is None:
        gate.error("REF_FORMAT", f"{where}: ref {text!r} must be a relative path inside the clone", where, str(text))
        return
    data = tree.read_bytes(relpath)
    if data is None:
        refused = tree.refusal_for(relpath)  # a git submodule that is absent, empty or at another commit
        gate.error("REF_MISSING", f"{where}: {relpath} does not exist in {label}"
                   + (f" ({refused})" if refused else ""), where, str(text))
        return
    text_doc = tree.read_text(relpath)
    if text_doc is None and companion:
        gate.error("COMPANION_REF_BINARY", f"{where}: {relpath} in {label} is not a text file; a companion citation "
                   "must name a text line", where, str(text))
        return
    if text_doc is None:
        gate.warning("REF_BINARY", f"{where}: {relpath} is not a text file; line {ref.line} cannot be checked",
                     where, str(text))
        return
    lines = text_doc.splitlines()
    if ref.end > len(lines):
        gate.error("REF_LINE", f"{where}: {relpath} has {len(lines)} lines; line {ref.end} does not exist in "
                   f"{label}", where, str(text))
        return
    if kind == "limit" and rule is not None:
        # Preserve statement boundaries for source-only local Box expressions.
        missing = _unshown(rule, "\n".join(lines[ref.line - 1:ref.end]))
        if missing:
            gate.warning("REF_VALUE", f"{where}: the cited line {ref} does not show {missing}", where, str(text))


# ---------------------------------------------------------------------------
# G5
# ---------------------------------------------------------------------------


def _g5(ctx: _Context, gate: Gate) -> None:
    if not ctx.g3_ok:
        gate.skip("not run: the driver did not resolve (G3)")
        return
    try:
        data, markdown = reference_documents(ctx.dir, cls=ctx.cls, instance=ctx.instance)
    except KeyboardInterrupt:
        raise
    except BaseException as exc:  # noqa: BLE001
        gate.error("RENDER", f"the reference file cannot be generated: {_crash_text(exc)}", REFERENCE_JSON)
        return
    hint = "regenerate it: python3 -m mhs.driver reference <dir>"
    for name, expected in ((REFERENCE_JSON, data), (REFERENCE_MD, markdown.encode("utf-8"))):
        path = ctx.dir / name
        if not path.is_file():
            gate.error("MISSING", f"{name} is missing; {hint}", name)
        elif path.read_bytes() != expected:
            gate.error("STALE", f"{name} is stale (it differs from the generated file); {hint}", name)


# ---------------------------------------------------------------------------
# G6
# ---------------------------------------------------------------------------


def _g6(ctx: _Context, gate: Gate) -> None:
    if not ctx.g3_ok:
        gate.skip("not run: the driver did not resolve (G3)")
        return
    from .behaviour import BehaviourRun
    from .build import hardware_device_id

    run = BehaviourRun(endpoint=ctx.endpoint, model=ctx.model,
                       hardware_view=ctx.hardware_endpoint if ctx.model.mode == "hardware" else None,
                       fixtures=ctx.fixtures, example_overlay=ctx.example_overlay,
                       hardware_id=hardware_device_id(ctx.model),
                       recorded=ctx.records_native, has_prerequisites=ctx.prerequisites is not None,
                       sensed=_sensed_sources(ctx), stall=_stall_source(ctx), fresh=_fresh_source(ctx),
                       hosted=bool(_hosted_api(ctx)))
    try:
        findings = run.run()
    except KeyboardInterrupt:
        raise
    except BaseException as exc:  # noqa: BLE001 - a crash (or SystemExit) of the driver under test is a finding
        findings = list(run.findings) + [("G6.CRASH", f"the behaviour checks could not complete: "
                                                      f"{_crash_text(exc)}", "error", None)]
    for code, message, severity, path in findings:
        gate.findings.append(Finding(code, message, severity, path))


def _frozen_contradiction(term: Mapping[str, Any]) -> Any:
    """A value that cannot satisfy ``term``, written by G6's frozen filter into the term's first field.

    An ``equals`` term gets another value of the same type (the opposite boolean, a neighbouring integer, a
    different string, or the next representable float). A numeric term gets JSON ``true``, which fails the
    finite-number check. The field is the first predicate term's path, in declaration order.
    """
    if "equals" in term:
        value = term["equals"]
        if isinstance(value, bool):
            return not value
        if isinstance(value, str):
            return f"{value} " if value else "frozen"
        if isinstance(value, int):
            return value + 1 if value < 2**31 - 1 else value - 1
        if isinstance(value, float):
            if not math.isfinite(value):
                return 0.0
            # 1e20 + 1.0 is still 1e20. nextafter moves every finite float, including that one.
            shifted = math.nextafter(value, math.inf)
            if shifted == value or not math.isfinite(shifted):
                shifted = math.nextafter(value, -math.inf)
            if shifted != value and math.isfinite(shifted):
                return shifted
            return True
    return True


def _sensed_sources(ctx: _Context) -> dict[str, tuple] | None:
    """topic -> (stamp path, ROS version, first predicate field[, freshness, contradiction]) of a sensed stop.

    A 3-tuple is a stamp source. An arrival source adds ``"arrival"``, an empty stamp path and the value G6's
    frozen filter writes: G6 must not invent a producer stamp for it, and must not leave an ``equals`` predicate
    unchanged.
    """
    if getattr(ctx.model, "estop_confirmation", None) is None:
        return None
    declared = getattr(ctx.cls, "_sensed_declaration", None)
    if not callable(declared):
        return None
    declaration, problems = declared()
    if declaration is None or problems:
        return None
    out: dict[str, tuple] = {}
    for name, source in declaration.sources.items():
        chosen: Mapping[str, Any] | None = None
        field_path: str | None = None
        for term in declaration.terms:
            if term.get("source") != name:
                continue
            paths = [path for path in (term.get("paths") or [term.get("path")]) if path]
            if not paths:
                continue
            chosen = term
            field_path = str(paths[0])
            break
        if chosen is None or field_path is None:
            continue
        freshness = str(source.get("freshness", "stamp"))
        ros_version = int(getattr(ctx.cls, "ros_version", 2))
        if freshness == "arrival":
            out[str(source["topic"])] = ("", ros_version, field_path, "arrival", _frozen_contradiction(chosen))
        else:
            out[str(source["topic"])] = (str(source.get("stamp_path", "header.stamp")), ros_version, field_path)
    return out or None


def _stall_source(ctx: _Context) -> tuple[str, str] | None:
    """``(service, stall path)`` of a ROS driver's stall read-back (E1), which G6 breaks on purpose (STALL_FAIL_OPEN)."""
    if ctx.family != "ros" or ctx.cls is None:
        return None
    readback = dict(getattr(ctx.cls, "safety_bindings", {}) or {}).get("safe_state")
    stall = readback.get("stall") if isinstance(readback, Mapping) else None
    if not isinstance(stall, Mapping) or not isinstance(readback.get("service"), str) \
            or not isinstance(stall.get("path"), str):
        return None
    return readback["service"], stall["path"]


def _fresh_source(ctx: _Context) -> tuple[str, str, bool] | None:
    """``(topic, flag path, confirming value)`` of a ROS driver's fresh-sample topic read-back (E2), which G6 breaks
    on purpose (FRESH_FAIL_OPEN)."""
    if ctx.family != "ros" or ctx.cls is None:
        return None
    readback = dict(getattr(ctx.cls, "safety_bindings", {}) or {}).get("safe_state")
    if not isinstance(readback, Mapping) or not isinstance(readback.get("fresh"), Mapping):
        return None
    success = readback.get("success")
    if (not isinstance(readback.get("topic"), str) or not isinstance(success, Mapping)
            or not isinstance(success.get("path"), str) or not isinstance(success.get("equals"), bool)):
        return None
    return readback["topic"], success["path"], success["equals"]


# ---------------------------------------------------------------------------
# G7
# ---------------------------------------------------------------------------


def _g7(ctx: _Context, gate: Gate) -> None:
    if ctx.cls is None:
        gate.skip("not run: the driver cannot be imported (G3)")
        return
    from .hardware_stop import declares_companion_stop

    # User decision 4 (2026-11-05) does not widen ROS, gym, or any other family's companion scope.
    if declares_companion_stop(ctx.cls) and ctx.family not in ("direct", "python-object"):
        gate.error("HARDWARE_STOP_SCOPE", "companion_stop is only for a direct or python-object hardware driver; "
                   f"this driver is family {ctx.family}", "driver.py")
    symbol = getattr(ctx.cls, "native", None)
    if isinstance(symbol, str) and symbol.startswith("pybind:"):
        # Before the upstream-backend shortcut: a pybind11 selector is refused for every family but a direct Driver
        # and the python-object family, whatever its fake backend is.
        _g7_pybind(ctx, gate, symbol)
        return
    if (ctx.family in ("gymnasium", "mujoco") and not ctx.records_native
            and not str(getattr(ctx.cls, "native", "")).startswith("pyfile:")):
        gate.warning("UPSTREAM_BACKEND", "the fake backend is the upstream simulator itself; there is no fake surface "
                     "to check")
        return
    if ctx.tree is None:
        gate.error("NO_CLONE", "no upstream clone to read the native class from (G1)")
        return
    if isinstance(symbol, str) and symbol.startswith("pyfile:"):
        from .source_gate import check_explicit_source
        from .source_selector import parse_selector

        selector = parse_selector(symbol)
        if selector is None:
            gate.error("NO_NATIVE", "invalid explicit source selector", "driver.py")
            return
        check_explicit_source(ctx, gate, selector, _fake_target(ctx), _fake_members(ctx),
                              check_members=not ctx.transport_family)
        if not ctx.transport_family:
            return
    elif ctx.family in _NATIVE_PROVENANCE_FAMILIES and symbol is not None:
        # A transport family's native names provenance (its code never runs); it must still exist in the clone at
        # the pinned commit, or an invented symbol passes. The tag bridge resolves its native class itself.
        _g7_transport_native(ctx, gate, symbol)
    if ctx.family == "tag-bridge":  # tag-bridge helper (2026-11-04)
        from .tag_check import check_tag_surface

        check_tag_surface(ctx, gate)
        return
    if ctx.family == "ros":
        from .ros_check import check_ros_surface

        check_ros_surface(ctx, gate)
        return
    if ctx.family == "mcp-client":
        from .mcp_client_check import check_mcp_client_surface
        check_mcp_client_surface(ctx, gate)
        return
    if ctx.family == "sila2":
        from .sila2_check import check_sila2_surface

        check_sila2_surface(ctx, gate)
        return
    if ctx.family == "http":
        from .http_check import check_http_surface

        check_http_surface(ctx, gate)
        return
    if ctx.transport_family:
        _g7_transport(ctx, gate)
        return
    symbol = getattr(ctx.cls, "native", None)
    if not isinstance(symbol, str) or ":" not in symbol:
        gate.error("NO_NATIVE", "native must name the upstream class ('package.module:Class'); G7 checks the fake "
                   "against it", "driver.py")
        return
    card = ctx.card or {}
    hint = None
    symbols = [item for item in card.get("entry_symbols") or [] if isinstance(item, Mapping)]
    for item in symbols:
        if item.get("symbol") == symbol and isinstance(item.get("file"), str):
            hint = item["file"]
    if symbols and not any(item.get("symbol") == symbol for item in symbols):
        text = f"native {symbol} is not one of the card's entry_symbols {[item.get('symbol') for item in symbols][:5]}"
        if any(item.get("confidence") in ("ast", "override") for item in symbols):
            gate.error("NOT_AN_ENTRY_SYMBOL", f"{text}: the card's entry class was confirmed in the clone (its AST or "
                       "a maintainer's override), and the fake is checked against it (use it as native, or stop with "
                       "blocked ENTRY_UNVERIFIED)", "driver.py")
        else:
            gate.warning("NOT_AN_ENTRY_SYMBOL", text, "driver.py")
    factory = getattr(ctx.cls, "native_factory", None)
    if factory is not None:
        # An environment a factory function of the clone builds from a class outside it (FACTORY-ENVIRONMENTS).
        from .factory_check import check_factory_surface

        check_factory_surface(ctx, gate, symbol, hint, factory, _fake_members(ctx), _GYMNASIUM_ENV_API)
        return
    surface = _upstream.class_surface(ctx.tree, symbol, hint_file=hint)
    for problem in surface.problems:
        gate.error("NATIVE_NOT_FOUND", f"{problem} ({_git_status_label(ctx.tree)})", "driver.py")
    if not surface.found:
        return
    if ctx.family == "qcodes":
        from .qcodes_check import check_qcodes_surface
        check_qcodes_surface(ctx, gate, surface)
    # --- PyLabRobot helper: profile references against the pinned clone ---
    if ctx.family == "pylabrobot":
        from .pylabrobot_check import check_pylabrobot_surface
        check_pylabrobot_surface(ctx, gate)
    # --- end PyLabRobot helper ---
    for file, changed in sorted(surface.legacy.items()):
        gate.warning("LEGACY_SOURCE", f"{file} is Python 2 source: G7 read it with {changed} line(s) Python 3 cannot "
                     "parse left out (print statements and the like), so a member defined only on such a line is "
                     "not seen; the clone cannot be imported under Python 3, so native.py must port it", file)
    if ctx.family == "ophyd":
        from .ophyd_check import check_ophyd_surface
        check_ophyd_surface(ctx, gate, surface)
    external_base = any(item.startswith("base ") for item in surface.open)
    from .hardware_stop import check_hardware_stop

    exempt = check_hardware_stop(ctx, gate, set(surface.names))
    used: dict[str, str] = {}
    for name in sorted(_fake_members(ctx)):
        used.setdefault(name, "defined by the fake")
    # A backend in an isolated simulator host: the recorded object is the SDK's host, whose own safety-path members
    # (stop, readback, ...) are not environment members; its declared stop and read-back paths are checked instead.
    host_api = _hosted_api(ctx)
    for log in ctx.logs:
        # Only names the backend resolved: a probe the fake answered with AttributeError adds nothing.
        for name in sorted(log.found):
            if name in host_api and name not in used:
                continue
            if not (name.startswith("__") and name.endswith("__")):
                used[name] = "used by the driver"
    _g7_host_paths(ctx, gate, symbol, surface)
    absent = sorted(name for name in used if name not in surface.names and name not in exempt)
    for name in absent:
        message = (f"{name!r} ({used[name]}) is not an attribute of {symbol} in {surface.file}:{surface.line} "
                   f"({_git_status_label(ctx.tree)})")
        if surface.open and ctx.tree.grep(name):
            gate.warning("MAYBE_ABSENT", f"{message}; it may come from elsewhere: {surface.open[0]}", name,
                         f"{surface.file}:{surface.line}")
        elif external_base and ctx.family == "gymnasium" and name in _GYMNASIUM_ENV_API:
            gate.warning("MAYBE_ABSENT", f"{message}; it is part of the Gymnasium environment interface, which a base "
                         "outside the clone provides", name, f"{surface.file}:{surface.line}")
        elif surface.open:
            gate.error("NOT_UPSTREAM", f"{message}, and the name occurs nowhere in the clone (although "
                       f"{surface.open[0]}): a fake may only implement what the upstream class has", name,
                       f"{surface.file}:{surface.line}")
        else:
            gate.error("NOT_UPSTREAM", f"{message}: a fake may only implement what the upstream class has", name,
                       f"{surface.file}:{surface.line}")


def _hosted_api(ctx: _Context) -> frozenset[str]:
    """The SDK host's own member names when the gate's backend runs in an isolated simulator host, else none."""
    configs = getattr(ctx.cls, "process_by_backend", None) if ctx.cls is not None else None
    if not isinstance(configs, Mapping) or ctx.backend not in configs:
        return frozenset()
    from ..bridge.sim_host import ProcessHost

    return ProcessHost.HOST_API


def _g7_host_paths(ctx: _Context, gate: Gate, symbol: str, surface: Any) -> None:
    """The declared stop and read-back of every isolated-process backend name upstream members (``HOST_PATH``).

    The host resolves each path on ``env.unwrapped`` (the native class): its first name must be an attribute of
    ``native`` in the clone, read as for the fake's members (a base or a ``setattr`` helper the reader cannot follow
    only warns); every further name, and every name of the read-back field, must occur in a text file of the clone at
    the pin. This shows that the names exist upstream, not what they do: the reviewer traces them (REVIEW.md item 5).
    """
    configs = getattr(ctx.cls, "process_by_backend", None)
    if not isinstance(configs, Mapping) or ctx.tree is None:
        return
    for backend in sorted(str(key) for key in configs):
        config = configs.get(backend)
        if not isinstance(config, Mapping):
            continue   # G3 reports the declaration
        readback = config.get("readback") if isinstance(config.get("readback"), Mapping) else {}
        for label, path, whole in (("stop", config.get("stop"), True), ("readback.path", readback.get("path"), True),
                                   ("readback.field", readback.get("field"), False)):
            if not isinstance(path, str) or not path:
                continue
            where = f"process_by_backend[{backend!r}].{label} {path!r}"
            parts = path.split(".")
            first, rest = (parts[0], parts[1:]) if whole else (None, parts)
            if first is not None and first not in surface.names:
                message = (f"{where}: {first!r} is not an attribute of {symbol} in {surface.file}:{surface.line} "
                           f"({_git_status_label(ctx.tree)}); the host resolves the path on env.unwrapped")
                if surface.open and ctx.tree.grep(first):
                    gate.warning("HOST_PATH", f"{message}; it may come from elsewhere: {surface.open[0]}", "driver.py")
                else:
                    gate.error("HOST_PATH", message, "driver.py")
            for name in rest:
                if not ctx.tree.grep(name):
                    gate.error("HOST_PATH", f"{where}: {name!r} occurs nowhere in the clone at the pinned commit "
                               f"({_git_status_label(ctx.tree)}): a declared stop or read-back names upstream code",
                               "driver.py")


def _g7_pybind(ctx: _Context, gate: Gate, symbol: str) -> None:
    """A ``pybind:<file>#<scope>.<Name>`` native: the class a pybind11 binding source of the clone exposes.

    Only a direct ``Driver`` or the python-object family may name one (their fake stands in for the bound object;
    transport and simulator families resolve their natives otherwise). The card's entry symbols constrain it as they
    constrain a ``package.module:Class`` native. The fake's public members and every attribute the driver used must be
    members the binding defines (:mod:`mhs.driver.pybind_surface`); argument shapes are not checked.
    """
    from .pybind_surface import parse_pybind_selector, pybind_surface

    selector = parse_pybind_selector(symbol)
    if selector is None:
        gate.error("NO_NATIVE", "invalid pybind11 source selector (pybind:<path>.cpp#<scope>.<Name>)", "driver.py")
        return
    if ctx.family not in ("direct", "python-object"):
        gate.error("NATIVE_NOT_FOUND", f"a pybind11 source selector names the native of a direct Driver or a "
                   f"PythonObjectDriver, not of the {ctx.family} family", "driver.py")
        return
    symbols = [item for item in (ctx.card or {}).get("entry_symbols") or [] if isinstance(item, Mapping)]
    if symbols and not any(item.get("symbol") == symbol for item in symbols):
        text = f"native {symbol} is not one of the card's entry_symbols {[item.get('symbol') for item in symbols][:5]}"
        if any(item.get("confidence") in ("ast", "override") for item in symbols):
            gate.error("NOT_AN_ENTRY_SYMBOL", f"{text}: the card's entry class was confirmed in the clone",
                       "driver.py")
        else:
            gate.warning("NOT_AN_ENTRY_SYMBOL", text, "driver.py")
    if ctx.tree is None:
        gate.error("NO_CLONE", "no upstream clone to read the native class from (G1)")
        return
    surface = pybind_surface(ctx.tree, selector)
    for problem in surface.problems:
        gate.error("NATIVE_NOT_FOUND", f"{problem} ({_git_status_label(ctx.tree)})", "driver.py")
    if not surface.found:
        return
    used: dict[str, str] = {name: "defined by the fake" for name in sorted(_fake_members(ctx))}
    for log in ctx.logs:
        for name in sorted(log.found):
            if not (name.startswith("__") and name.endswith("__")):
                used[name] = "used by the driver"
    for name in sorted(name for name in used if name not in surface.names):
        gate.error("NOT_UPSTREAM", f"{name!r} ({used[name]}) is not a member that the pybind11 binding of "
                   f"{selector.name} defines in {surface.file}:{surface.line} ({_git_status_label(ctx.tree)}): a fake "
                   "may only implement what the upstream class has", name, f"{surface.file}:{surface.line}")


def _fake_target(ctx: _Context) -> Any:
    """Resolve only the package's fake backend, never its source-only native selector."""
    entry = ctx.fake_entry()
    target: Any = entry
    if isinstance(entry, str):
        if not entry.startswith("."):
            return None  # upstream code (an upstream simulator, G3)
        from .base import _resolve_symbol

        try:
            target = _resolve_symbol(entry, getattr(sys.modules.get(ctx.cls.__module__), "__package__", None))
        except KeyboardInterrupt:
            raise
        except BaseException:  # noqa: BLE001 - G3/G6 report a backend that cannot load
            return None
    return target


def _fake_members(ctx: _Context) -> set[str]:
    """Public methods and properties of the package's fake backend class (instance data members are not counted)."""
    target = _fake_target(ctx)
    if not inspect.isclass(target) or not _package_module(ctx, target.__module__):
        return set()
    out: set[str] = set()
    for klass in target.__mro__:
        if klass is object or not _package_module(ctx, klass.__module__) or klass.__module__.split(".")[0] == "mhs":
            continue
        for name, value in vars(klass).items():
            if name.startswith("_"):
                continue
            if callable(value) or isinstance(value, (property, staticmethod, classmethod)):
                out.add(name)
    return out


#: what ``gymnasium.Env`` gives every environment: a native class whose base lies outside the clone inherits these even
#: when no file of the clone names them (a ManiSkill ``BaseEnv`` subclass and its ``action_space``)
_GYMNASIUM_ENV_API = frozenset({"action_space", "observation_space", "reset", "step", "render", "close", "unwrapped",
                                "np_random", "np_random_seed", "spec", "metadata", "render_mode", "reward_range"})

_COMMON_COMMAND = re.compile(r"^\*[A-Za-z]+\??$")


#: transport families whose ``native`` G7 resolves with :func:`_g7_transport_native` (``tag-bridge`` checks its own)
_NATIVE_PROVENANCE_FAMILIES = frozenset({"serial", "scpi", "ros", "http", "mcp-client", "sila2"})


def _g7_transport_native(ctx: _Context, gate: Gate, symbol: Any) -> None:
    """The ``native`` of a serial, SCPI, ROS, HTTP, SiLA 2 or MCP-client driver exists in the clone (or is unset).

    Such a native is provenance, never imported: a class, a module-level function or a module-level name of the pinned
    clone (:func:`mhs.driver.upstream.definition_surface`), found with the card's file hint as G7 finds other
    families' classes. ``None`` (a ROS driver that binds a graph, not a Python class) has nothing to resolve; a value
    that is not ``package.module:Name`` is G3's.
    """
    if not isinstance(symbol, str) or ":" not in symbol:
        return
    card = getattr(ctx, "card", None) or {}
    symbols = [item for item in card.get("entry_symbols") or [] if isinstance(item, Mapping)]
    hint = next((item.get("file") for item in symbols
                 if item.get("symbol") == symbol and isinstance(item.get("file"), str)), None)
    surface = _upstream.definition_surface(ctx.tree, symbol, hint_file=hint)
    for problem in surface.problems:
        gate.error("NATIVE_NOT_FOUND", f"{problem} ({_git_status_label(ctx.tree)}); a transport family's native "
                   "names the upstream code its commands come from and must exist in the clone", "driver.py")


def _g7_transport(ctx: _Context, gate: Gate) -> None:
    lines: set[str] = set()
    for log in ctx.logs:
        for call in log.calls:
            if call.kind == "call" and call.name in ("write", "query", "send", "write_line") and call.args:
                if isinstance(call.args[0], (str, bytes)):
                    text = call.args[0].decode("ascii", "replace") if isinstance(call.args[0], bytes) else call.args[0]
                    lines.add(text.strip())
    if not lines:
        gate.warning("NO_COMMANDS", "the fake transport recorded no command (nothing to check against the clone)")
        return
    tokens: set[str] = set()
    for line in sorted(lines):
        for part in line.split(";"):
            head = re.split(r"[\s?{(]", part.strip(), maxsplit=1)[0]
            if not head or _COMMON_COMMAND.match(head) or not re.search(r"[A-Za-z]", head):
                continue
            tokens.add(head)
    for token in sorted(tokens):
        if ctx.tree.grep(token):
            continue
        segments = [item for item in token.strip(":").split(":") if len(item) >= 2]
        if segments and all(ctx.tree.grep(item) for item in segments):
            continue
        gate.error("COMMAND_NOT_UPSTREAM", f"command {token!r} (sent by the driver) does not occur in the clone "
                   f"({_git_status_label(ctx.tree)}); the fake may only answer commands the upstream code or manual "
                   "uses. The checked token is the text before the first space, '?', '{' or '(' of a sent line. If the "
                   "upstream builds this command from parts (a letter and a number, a framed message), a command table "
                   "cannot reproduce it: write a direct Driver over the upstream class (driver-authoring.md, 'Choosing "
                   "the shape'). Do not change the wire syntax to pass this check", token)


# ---------------------------------------------------------------------------
# G8
# ---------------------------------------------------------------------------


def _g8(ctx: _Context, gate: Gate) -> None:
    if not ctx.g3_ok:
        gate.skip("not run: the driver did not resolve (G3)")
        return
    from ..conformance import level_awarded
    from ..conformance.inprocess import run_suite_inprocess

    options: dict[str, Any] = {}
    if ctx.fixtures_path is not None:
        options["fixtures"] = str(ctx.fixtures_path)
    try:
        report = run_suite_inprocess(ctx.server_factory(), profile=CONFORMANCE_PROFILE, level=CONFORMANCE_LEVEL,
                                     **options)
    except KeyboardInterrupt:
        raise
    except BaseException as exc:  # noqa: BLE001
        gate.error("CONFORMANCE", f"the in-process conformance run failed: {_crash_text(exc)}")
    else:
        awarded = level_awarded(report)
        if awarded != CONFORMANCE_LEVEL:
            failing = [item for item in report.get("tests") or []
                       if item.get("required") and item.get("status") != "pass"]
            exempt = [item for item in failing if _no_limits_exempt(ctx, item)]
            failing = [item for item in failing if item not in exempt]
            if exempt and not failing:
                gate.warning("SAFE014_NOT_APPLICABLE", f"the suite awards {awarded}: SAFE-014 (out-of-limit "
                             "refusals) has nothing to probe because the driver declares no limit on any actuating "
                             f"capability; every other {CONFORMANCE_LEVEL} test passed")
            else:
                unfilled = [f"{capability_id} {path}" for capability_id, path, rule in _limit_rules(ctx.model)
                            if rule == "operator_required"]
                hint = ""
                if unfilled and ctx.example_overlay is None:
                    hint = (f"; the driver declares operator_required limits ({', '.join(unfilled[:4])}) and the "
                            f"conformance run serves {EXAMPLE_OVERLAY} to fill them: add that file (see the tutorial "
                            "package)")
                gate.error("CONFORMANCE", f"{CONFORMANCE_PROFILE} {CONFORMANCE_LEVEL} not achieved (level "
                           f"{awarded or 'none'}); failing required tests: "
                           + ", ".join(str(item.get("id")) for item in failing[:12]) + hint)
                for item in failing[:20]:
                    gate.error("TEST", f"{item.get('id')} {item.get('status')}: "
                               f"{str(item.get('detail') or '')[:600]}", str(item.get("id")))
    _g8_mcp(ctx, gate)


def _no_limits_exempt(ctx: _Context, test: Mapping[str, Any]) -> bool:
    """SAFE-014 skipped because there is no limit at all: not a defect of a driver that limits nothing.

    Hardware R1+ drivers limit every numeric input (G3), so this only covers
    actions without numeric inputs and unlimited R0 or simulated drivers.  A
    limited path the suite cannot probe is still a failure (add a fixture).
    """
    if test.get("id") != "SAFE-014" or test.get("status") != "skip":
        return False
    if not str(test.get("detail") or "").startswith("endpoint declares no limits"):
        return False
    return not any(binding.limits for binding in ctx.model.bindings)


def _schema_numbers(schema: Any, path: str, out: list[tuple[str, str, bool]]) -> None:
    """``(path, type, has unit)`` of every numeric leaf of ``schema``."""
    if not isinstance(schema, Mapping):
        return
    kinds = schema.get("type")
    kinds = [kinds] if isinstance(kinds, str) else list(kinds or [])
    if "array" in kinds or isinstance(schema.get("items"), Mapping):
        items = schema.get("items") if isinstance(schema.get("items"), Mapping) else {}
        item_kinds = items.get("type")
        item_kinds = [item_kinds] if isinstance(item_kinds, str) else list(item_kinds or [])
        if any(kind in ("number", "integer") for kind in item_kinds):
            unit = bool(items.get("x-mhs-unit") or schema.get("x-mhs-unit"))
            out.append((f"{path}[*]", "number" if "number" in item_kinds else "integer", unit))
        else:
            _schema_numbers(items, f"{path}[*]", out)
        return
    if any(kind in ("number", "integer") for kind in kinds):
        out.append((path, "number" if "number" in kinds else "integer", bool(schema.get("x-mhs-unit"))))
        return
    for name, sub in (schema.get("properties") or {}).items():
        _schema_numbers(sub, f"{path}.{name}", out)


def _g8_mcp(ctx: _Context, gate: Gate) -> None:
    from ..conformance.inprocess import client_for
    from ..mcp import MCPProjection

    try:
        server, cleanup = ctx.server_factory()()
    except KeyboardInterrupt:
        raise
    except BaseException as exc:  # noqa: BLE001
        gate.error("MCP", f"no endpoint for the MCP projection: {_crash_text(exc)}")
        return
    try:
        client = client_for(server)
        projection = MCPProjection(client)
        with contextlib.redirect_stderr(io.StringIO()):
            initialized = projection.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "mhs-driver-gate", "version": _ids.SDK_VERSION}}})
            listed = projection.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        if not isinstance(initialized, Mapping) or "error" in initialized:
            gate.error("MCP", f"the MCP projection does not initialize: {(initialized or {}).get('error')}")
            return
        if not isinstance(listed, Mapping) or "error" in listed:
            gate.error("MCP", f"the MCP projection cannot list its tools: {(listed or {}).get('error')}")
            return
        tools = [tool for tool in (listed.get("result") or {}).get("tools") or [] if "x-mhs" in tool]
        if not tools:
            gate.error("MCP", "the MCP projection lists no capability tool")
        for tool in tools:
            _g8_tool(gate, tool, hardware=ctx.model.mode == "hardware")
    except KeyboardInterrupt:
        raise
    except BaseException as exc:  # noqa: BLE001
        gate.error("MCP", f"the MCP projection cannot be built: {_crash_text(exc)}")
    finally:
        try:
            cleanup()
        except KeyboardInterrupt:
            raise
        except BaseException:  # noqa: BLE001
            pass


def _g8_tool(gate: Gate, tool: Mapping[str, Any], *, hardware: bool) -> None:
    name = str(tool.get("name"))
    description = str(tool.get("description") or "")
    size = len(description.encode("utf-8"))
    if size > TOOL_LIMIT_BYTES:
        gate.error("TOOL_DESCRIPTION", f"{name}: the tool description is {size} bytes (limit {TOOL_LIMIT_BYTES})", name)
    schema = copy_schema(tool.get("inputSchema"))
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    for key in list(properties):
        if key in _PROJECTION_PROPERTIES:
            properties.pop(key)
    owned = {"name": name, "description": description, "inputSchema": schema}
    owned_size = len(canonical.jcs(owned))
    if owned_size > TOOL_LIMIT_BYTES:
        gate.error("TOOL_SIZE", f"{name}: the driver-owned part of the tool (name, description, input fields) is "
                   f"{owned_size} bytes (limit {TOOL_LIMIT_BYTES}); shorten descriptions or split the capability", name)
    for key, prop in sorted(properties.items()):
        if not isinstance(prop, Mapping) or not str(prop.get("description") or "").strip():
            gate.error("NO_DESCRIPTION", f"{name}: input {key!r} has no description (Field(description=...))",
                       f"{name}.{key}")
        numbers: list[tuple[str, str, bool]] = []
        _schema_numbers(prop, key, numbers)
        for path, kind, has_unit in numbers:
            if has_unit:
                continue
            if kind == "number" and hardware:
                gate.error("NO_UNIT", f"{name}: numeric input {path} has no unit (Field(unit=<UCUM code>); '1' for "
                           "a dimensionless number)", f"{name}.{path}")
            elif kind == "number":
                gate.warning("NO_UNIT", f"{name}: numeric input {path} has no unit (a simulator may use its own "
                             "units; say so in the description)", f"{name}.{path}")
            else:
                gate.warning("NO_UNIT", f"{name}: integer input {path} has no unit (use '1' for a count)",
                             f"{name}.{path}")


def copy_schema(value: Any) -> dict[str, Any]:
    return json.loads(json.dumps(value)) if isinstance(value, Mapping) else {}


# ---------------------------------------------------------------------------
# G9
# ---------------------------------------------------------------------------


def _has_harness_call(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Name) and func.id == "check_driver") or (
                    isinstance(func, ast.Attribute) and func.attr == "check_driver"):
                return True
    return False


def _g9(ctx: _Context, gate: Gate, earlier_failed: bool, timeout_s: float) -> None:
    if ctx.inner:
        gate.skip("not run: this is the gate's own run of test_driver.py", required=False)
        return
    test = ctx.dir / "test_driver.py"
    if not test.is_file():
        gate.error("MISSING", "test_driver.py is missing", "test_driver.py")
        return
    if not _has_harness_call(test):
        gate.error("NO_HARNESS", "test_driver.py must call mhs.testing.check_driver(HERE, backend=...) (cases may be "
                   "added, never removed)", "test_driver.py")
        return
    if earlier_failed:
        gate.skip("not run: fix the failing gates first (test_driver.py runs the gate again)")
        return
    src = str(Path(__file__).resolve().parents[2])
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([src] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env[INNER_ENV] = "1"
    if ctx.root is not None:
        env[_ROOT_ENV] = str(ctx.root)
    if ctx.clone_path is not None:
        env[_CLONE_ENV] = str(ctx.clone_path)
    if ctx.companions_root is not None:
        env[_COMPANIONS_ENV] = str(ctx.companions_root)
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="mhs-gate-g9-") as holder:
            # An empty working directory: "python -m" puts it first on sys.path, and a package file named like a
            # standard module must not shadow it.
            cwd = Path(holder) / "cwd"
            cwd.mkdir()
            result = Path(holder) / "result.json"
            done = subprocess.run([sys.executable, "-m", "mhs.driver._repotests", str(test), "--result", str(result)],
                                  cwd=cwd, env=env, capture_output=True, timeout=timeout_s, stdin=subprocess.DEVNULL,
                                  check=False)
            outcome, _problem = read_json(result)
    except subprocess.TimeoutExpired:
        gate.error("TIMEOUT", f"test_driver.py did not finish within {timeout_s:.0f} s (blocked code GATE_TIMEOUT)",
                   "test_driver.py")
        return
    elapsed = time.monotonic() - started
    tail = done.stderr.decode("utf-8", "replace")[-1500:]
    if not isinstance(outcome, Mapping):
        # The runner writes its result after the cases ran: without it, something ended the process early.
        gate.error("NO_RESULT", f"test_driver.py ended (exit {done.returncode}) in {elapsed:.1f} s without the test "
                   "runner's result: a test, a fixture or the file itself ended the interpreter (os._exit, a signal) "
                   f"before the cases completed:\n{tail}", "test_driver.py")
    elif done.returncode != 0 or outcome.get("ok") is not True or not outcome.get("tests_run"):
        gate.error("FAILED", f"test_driver.py failed (exit {done.returncode}) in {elapsed:.1f} s"
                   f"{': ' + str(outcome.get('error')) if outcome.get('error') else ''}:\n{tail}", "test_driver.py")


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------


def _emit(progress: Callable[[dict[str, Any]], None] | None, event: dict[str, Any]) -> None:
    if progress is None:
        return
    try:
        progress(event)
    except Exception:  # noqa: BLE001 - progress is advisory
        pass


def run_check(directory: str | os.PathLike[str], backend: str = "fake", *, root: str | os.PathLike[str] | None = None,
              clone: str | os.PathLike[str] | None = None, write_report: bool = True, gates: Iterable[str] | None = None,
              inner: bool = False, timeout_s: float = REPO_TEST_TIMEOUT_S,
              progress: Callable[[dict[str, Any]], None] | None = None,
              companions_root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Run the gates in this process on a driver directory and return the check report (``check-report.schema.json``).

    ``root`` is the project root (default: found above ``directory``) that
    ``task.json`` paths are relative to; ``clone`` overrides the clone path
    (a sandbox copy); ``companions_root`` is where the fetched (lock) companion
    clones and their ``LOCK.json`` are read instead of ``work/companions``.  ``gates`` limits the run to some gate ids (the others
    are reported ``skip`` with ``required: false``, and the evidence is
    ``none``); ``inner`` is the gate's own G9 run (G9 skipped); ``progress``
    receives ``{"stage": <gate id or step>}`` and ``{"gate": <result>}``
    events.  Package code runs in this process: the command line uses
    :func:`run_check_isolated` instead.  Raises :class:`CheckUsageError` for
    a missing directory or a backend other than ``fake``/``sim``.
    """
    path = Path(directory).expanduser()
    if not path.is_dir():
        raise CheckUsageError(f"{directory} is not a directory")
    if backend not in _GATE_BACKENDS:
        raise CheckUsageError(f"the gate runs on the {' or '.join(_GATE_BACKENDS)} backend only; a hardware check is "
                              "an operator procedure outside the gate (0.9)")
    if inner:
        root = root or os.environ.get(_ROOT_ENV) or None
        clone = clone or os.environ.get(_CLONE_ENV) or None
        companions_root = companions_root or os.environ.get(_COMPANIONS_ENV) or None
    directory_path = path.resolve()
    root_path = Path(root).resolve() if root is not None else find_root(directory_path)
    clone_path = Path(clone).expanduser() if clone is not None else None
    companions_path = Path(companions_root).expanduser().resolve() if companions_root is not None else None
    selected = set(gates) if gates is not None else None
    unknown = sorted((selected or set()) - {gate_id for gate_id, _name in GATES})
    if unknown:
        raise CheckUsageError(f"unknown gate ids {unknown}")
    started = time.monotonic()
    # Everything the run calls is bound before package code is imported (driver.py may try to patch the gate),
    # and the mhs modules are fingerprinted so a patch is seen (G3.GATE_TAMPERED).
    for name in _GATE_MODULES:
        importlib.import_module(name)
    runners: dict[str, Callable[[_Context, Gate], None]] = {"G1": _g1, "G2": _g2, "G3": _g3, "G4": _g4, "G5": _g5,
                                                            "G6": _g6, "G7": _g7, "G8": _g8}
    repo_tests, after_run, crash_text, emit, build, write = _g9, _g1_after, _crash_text, _emit, _report, _write_report
    snapshot, changes = _integrity_snapshot, _integrity_changes
    codes = (snapshot.__code__, changes.__code__, _fingerprint.__code__)
    baseline = snapshot()
    tampered: list[str] = []
    results = {gate_id: Gate(gate_id, name) for gate_id, name in GATES}

    def audit() -> None:
        if (snapshot.__code__, changes.__code__, _fingerprint.__code__) != codes:
            found = ["mhs.driver.check (the integrity check itself)"]
        else:
            found = changes(baseline, snapshot())
        new = [item for item in found if item not in tampered]
        if new:
            tampered.extend(new)
            emit(progress, {"tampered": new})  # the parent of the CLI run enforces these too

    emit(progress, {"stage": "load"})
    ctx = _Context(directory_path, backend, root_path, clone_path, inner, companions_path)
    audit()
    try:
        # G3 first: the other gates read what it resolves.
        for gate_id in ("G3", "G1", "G2", "G4", "G5", "G6", "G8", "G7"):
            gate = results[gate_id]
            if selected is not None and gate_id not in selected and gate_id != "G3":
                gate.skip("not selected in this run", required=False)
                continue
            emit(progress, {"stage": gate_id})
            begun = time.monotonic()
            try:
                runners[gate_id](ctx, gate)
            except KeyboardInterrupt:
                raise
            except BaseException as exc:  # noqa: BLE001 - a gate never crashes (or exits) the run
                gate.error("CRASH", f"the gate crashed: {crash_text(exc)}")
            gate.duration_ms = (time.monotonic() - begun) * 1000
            gate.settle()
            if selected is not None and gate_id == "G3" and gate_id not in selected:
                gate.findings = []
                gate.skip("not selected in this run", required=False)
            audit()
            emit(progress, {"gate": gate.to_json()})
        gate = results["G9"]
        if selected is not None and "G9" not in selected:
            gate.skip("not selected in this run", required=False)
        else:
            emit(progress, {"stage": "G9"})
            begun = time.monotonic()
            earlier = bool(tampered) or any(results[item].status == "fail" for item in results if item != "G9")
            repo_tests(ctx, gate, earlier, timeout_s)
            gate.duration_ms = (time.monotonic() - begun) * 1000
            gate.settle()
            emit(progress, {"gate": gate.to_json()})
        emit(progress, {"stage": "after"})
        after_run(ctx, results["G1"])
    finally:
        emit(progress, {"stage": "close"})
        ctx.close()
    audit()
    if tampered:
        gate = results["G3"]
        if gate.status == "skip":
            gate.status = "pass"
            gate.required = True
            gate.findings = []
        gate.findings.append(_tamper_finding(tampered))
        gate.settle()
    emit(progress, {"stage": "report"})
    complete = selected is None and not inner
    report = build(ctx.card, directory_path, root_path, backend, [results[gate_id].to_json() for gate_id, _ in GATES],
                   duration_ms=(time.monotonic() - started) * 1000, complete=complete)
    if write_report and not inner:
        write(directory_path, report)
    return report


def _tamper_finding(tampered: Sequence[str]) -> Finding:
    return Finding("G3.GATE_TAMPERED", f"the SDK changed while package code ran: {', '.join(tampered[:8])}"
                   f"{' ...' if len(tampered) > 8 else ''}; package code never patches mhs (the gate's verdict "
                   "cannot be trusted)", "error", "driver.py")


#: Members of a check report the CLI parent derives itself (:func:`_identity`) and the child's report must repeat.
_IDENTITY_KEYS = ("$schema", "openmhs", "package_id", "driver_dir", "backend", "sdk_version", "upstream")


def _identity(card: Any, directory_path: Path, root_path: Path | None, backend: str) -> dict[str, Any]:
    """The header of a check report: schema, versions, package id, driver directory, backend and upstream pin."""
    card = card if isinstance(card, Mapping) else {}
    out: dict[str, Any] = {
        "$schema": _ids.SCHEMA_BASE + "check-report.schema.json",
        "openmhs": _ids.SPEC_VERSION,
    }
    package_id = card.get("package_id")
    if isinstance(package_id, str) and re.match(r"^gh\.[a-z0-9_.-]+/[a-z0-9_.-]+$", package_id):
        out["package_id"] = package_id
    out.update({
        "driver_dir": relative_to_root(directory_path, root_path)[:512],
        "backend": backend,
        "sdk_version": _ids.SDK_VERSION,
    })
    upstream_card = card.get("upstream") if isinstance(card.get("upstream"), Mapping) else {}
    commit = upstream_card.get("commit")
    if isinstance(commit, str) and re.match(r"^[0-9a-f]{40}([0-9a-f]{24})?$", commit):
        upstream: dict[str, Any] = {"commit": commit}
        if isinstance(upstream_card.get("repo_url"), str):
            upstream["repo_url"] = upstream_card["repo_url"]
        out["upstream"] = upstream
    return out


def _report(card: Any, directory_path: Path, root_path: Path | None, backend: str, gates: Sequence[Mapping[str, Any]],
            *, duration_ms: float, complete: bool) -> dict[str, Any]:
    """The check report of gate results (validated against ``check-report.schema.json``, digest added)."""
    gates = [dict(item) for item in gates]
    for item in gates:  # a gate with an error finding fails, whatever status it carries
        if item.get("status") != "fail" and any(finding.get("severity", "error") == "error"
                                                for finding in item.get("findings") or []):
            item["status"], item["required"] = "fail", True
    failed = [item["id"] for item in gates if item["status"] == "fail"]
    if not failed:
        # A required gate that did not run never passes silently.
        failed = [item["id"] for item in gates if item["status"] == "skip" and item.get("required", True)]
    passed = not failed
    complete = complete and all(item["status"] in ("pass", "warn") for item in gates)
    report = _identity(card, directory_path, root_path, backend)
    report.update({
        "generated_at": canonical.now_rfc3339(),
        "duration_ms": round(max(duration_ms, 0.0), 1),
        "passed": passed,
        "failed": failed,
        "gates": gates,
        "evidence_state": "contract_checked" if passed and complete else "none",
    })
    report["report_digest"] = canonical.digest(report)
    problems = default_store().validate(report, "check-report.schema.json")
    if problems:  # pragma: no cover - the report is built to the schema
        raise RuntimeError("check report does not validate (SDK bug): " + "; ".join(problems[:5]))
    return report


def _write_report(directory_path: Path, report: Mapping[str, Any]) -> None:
    (directory_path / REPORT_FILE).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


#: Members of a check report that differ between two runs of an unchanged package: the clock and the durations.
_CLOCK_KEYS = frozenset({"generated_at", "duration_ms", "report_digest"})


def stable_digest(report: Mapping[str, Any]) -> str:
    """``sha256:...`` of a check report without its clock, the digest ``RESULT.json`` records as ``gate.digest``.

    The report's own ``report_digest`` covers ``generated_at`` and the
    durations, so every gate run of the same package gives a new one.  This
    digest is the JCS digest of the report without ``report_digest``,
    ``generated_at`` and the durations (the report's and each gate's), so two
    runs that found the same thing give the same value, and ``RESULT.json``
    stays valid until the result of the gate changes (a gate or finding, the
    backend, the upstream pin or the SDK version).  The command line prints it
    after a passing run; ``MHS/registry/validate.py`` accepts it (and the
    report's own ``report_digest``) as ``gate.digest`` of a package that has a
    ``check-report.json``.
    """
    body = {key: value for key, value in report.items() if key not in _CLOCK_KEYS}
    gates = body.get("gates")
    if isinstance(gates, (list, tuple)):
        body["gates"] = [{key: value for key, value in gate.items() if key != "duration_ms"}
                         if isinstance(gate, Mapping) else gate for gate in gates]
    return canonical.digest(body)


def _verified(document: Any, *, identity: Mapping[str, Any] | None = None,
              progress: tuple[str | None, Mapping[str, Mapping[str, Any]]] | None = None,
              ) -> tuple[dict[str, Any] | None, str]:
    """``(report, "")`` when ``document`` is a check report that validates and whose digest checks out.

    With ``identity`` (the header the parent derived itself, :func:`_identity`)
    the report must be of a full run of this package: the same header, every
    gate required, evidence ``contract_checked`` exactly when it passed.  With
    ``progress`` (``(last stage, gate results)`` of the child's progress
    stream) the run must have reached the report, and every gate the report
    lists as run must have a result in the stream that the report does not
    contradict (a gate that failed there fails in the report, with its error
    codes).  Otherwise ``(None, why)``.
    """
    if not isinstance(document, Mapping) or not isinstance(document.get("report"), Mapping):
        return None, "no report"
    report = dict(document["report"])
    problems = default_store().validate(report, "check-report.schema.json")
    if problems:
        return None, f"the report does not validate: {problems[0]}"
    unsigned = {key: value for key, value in report.items() if key != "report_digest"}
    if canonical.digest(unsigned) != report.get("report_digest"):
        return None, "the report digest does not match its content"
    if report.get("passed") is not (not report.get("failed")):
        return None, "passed and failed disagree"
    gates = [dict(item) for item in report.get("gates") or []]
    if [item.get("id") for item in gates] != [gate_id for gate_id, _name in GATES]:
        return None, "the gates are not G1-G9 in order"
    if identity is not None:
        for key in _IDENTITY_KEYS:
            if report.get(key) != identity.get(key):
                return None, f"the report's {key} {report.get(key)!r} is not this run's {identity.get(key)!r}"
        if any(item.get("required") is not True for item in gates):
            return None, "a gate of a full run is reported as not required"
        if (report.get("evidence_state") == "contract_checked") is not bool(report.get("passed")):
            return None, "the evidence state and the verdict of a full run disagree"
    if progress is not None:
        stage, finished = progress
        if stage != "report":
            return None, f"the progress stream ends at {stage!r}, before the report was built"
        for item in gates:
            if item.get("status") == "skip":
                continue
            seen = finished.get(str(item.get("id")))
            if seen is None:
                return None, f"{item.get('id')} has no result in the progress stream"
            if seen.get("status") == "fail" and item.get("status") != "fail":
                return None, f"{item.get('id')} failed in the progress stream but not in the report"
            findings = item.get("findings") or []
            if not any(str(finding.get("code")).endswith(".TRUNCATED") for finding in findings):
                # Error codes, not just codes: an error the report turned into a warning is lost too.
                kept = {str(finding.get("code")) for finding in findings if finding.get("severity", "error") == "error"}
                lost = sorted({str(finding.get("code")) for finding in seen.get("findings") or []
                               if finding.get("severity", "error") == "error"} - kept)
                if lost:
                    return None, f"{item.get('id')} lost the error findings {lost[:3]} of the progress stream"
    return report, ""


def _read_progress(path: Path) -> tuple[str | None, dict[str, dict[str, Any]], list[str]]:
    """``(last stage, finished gate results by id, tampered mhs names)`` from the child's progress file."""
    stage: str | None = None
    finished: dict[str, dict[str, Any]] = {}
    tampered: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None, finished, tampered
    gate_ids = {gate_id for gate_id, _name in GATES}
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, Mapping):
            continue
        if isinstance(event.get("stage"), str):
            stage = event["stage"]
        if isinstance(event.get("tampered"), list):
            tampered.extend(str(item) for item in event["tampered"] if str(item) not in tampered)
        gate = event.get("gate")
        if isinstance(gate, Mapping) and gate.get("id") in gate_ids and gate.get("status") in ("pass", "warn", "fail",
                                                                                               "skip"):
            finished[str(gate["id"])] = dict(gate)
    return stage, finished, tampered


def _aborted_report(card: Any, directory_path: Path, root_path: Path | None, backend: str, stage: str | None,
                    finished: Mapping[str, Mapping[str, Any]], code: str, message: str,
                    duration_ms: float) -> dict[str, Any]:
    """The failing report of a gate run that ended without a valid report (blamed on the running gate)."""
    blamed = stage if stage in {gate_id for gate_id, _name in GATES} else ("G1" if stage == "after" else "G3")
    labels = {"load": "the import of driver.py", "close": "the closing of the driver", None: "start-up"}
    where = labels.get(stage, stage)

    def gates(keep_finished: bool) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for gate_id, name in GATES:
            if keep_finished and gate_id != blamed and gate_id in finished:
                out.append(dict(finished[gate_id]))
                continue
            gate = Gate(gate_id, name)
            if gate_id == blamed:
                gate.error(code, f"{message} (while running {where})")
                gate.settle()
            else:
                gate.skip(f"not run: the gate process ended during {where}")
            out.append(gate.to_json())
        return out

    try:
        return _report(card, directory_path, root_path, backend, gates(True), duration_ms=duration_ms, complete=False)
    except RuntimeError:  # a finished gate the child wrote does not validate: report only what is certain
        return _report(card, directory_path, root_path, backend, gates(False), duration_ms=duration_ms, complete=False)


def _enforce(report: dict[str, Any], card: Any, directory_path: Path, root_path: Path | None,
             findings: Sequence[tuple[str, str, str]]) -> dict[str, Any]:
    """The child's report with what the parent established itself (the child may have been tampered with).

    ``findings`` (the parent's static scan plus, when the child's progress
    reported a changed ``mhs`` module, one ``G3.GATE_TAMPERED``) are added to
    G3 unless the child's G3 already has them (``GATE_TAMPERED``: any
    wording), and every gate with an error finding is ``fail`` whatever status
    the child wrote.  The report is rebuilt (new digest) only when something
    changed.
    """
    gates = [dict(item) for item in report["gates"]]
    g3 = next(item for item in gates if item["id"] == "G3")
    present = {(item.get("code"), item.get("message")) for item in g3.get("findings") or []}
    codes = {item.get("code") for item in g3.get("findings") or []}
    missing = [item for item in findings if (item[0], item[1]) not in present
               and not (item[0] == "G3.GATE_TAMPERED" and item[0] in codes)]
    changed = bool(missing)
    if missing:
        g3["findings"] = list(g3.get("findings") or []) + [Finding(code, message, "error", path).to_json()
                                                           for code, message, path in missing]
    for gate in gates:
        errors = [item for item in gate.get("findings") or [] if item.get("severity", "error") == "error"]
        if errors and gate.get("status") != "fail":
            gate["status"], gate["required"], changed = "fail", True, True
    if not changed:
        return report
    return _report(card, directory_path, root_path, str(report.get("backend")), gates,
                   duration_ms=float(report.get("duration_ms") or 0.0), complete=report.get("evidence_state") ==
                   "contract_checked")


def run_check_isolated(directory: str | os.PathLike[str], backend: str = "fake", *,
                       root: str | os.PathLike[str] | None = None, clone: str | os.PathLike[str] | None = None,
                       write_report: bool = True, timeout_s: float = GATE_TIMEOUT_S,
                       companions_root: str | os.PathLike[str] | None = None) -> tuple[dict[str, Any], str]:
    """Run the gate in a child process and return ``(check report, the child's stderr)`` (the command line).

    This process never imports package code.  The child
    (:mod:`mhs.driver._gate`) runs :func:`run_check` with the network and
    device files disabled; its report is accepted only when it validates, its
    ``report_digest`` checks out, its header is the one this process derives
    and its progress stream backs it (:func:`_verified`).  A child that ends
    without one (package
    code called ``os._exit``, a signal killed it, it hung past ``timeout_s``)
    gives a failing report that blames the gate that was running
    (``<gate>.ABORTED`` / ``<gate>.TIMEOUT``) and keeps the results of the
    gates that had finished.  The static scan of the package
    (:func:`static_findings`) is repeated here and merged into G3 with the
    tamper events the child reported (:func:`_enforce`).  The
    report is written to ``<dir>/check-report.json`` unless ``write_report``
    is false.  Raises :class:`CheckUsageError` like :func:`run_check`.
    """
    path = Path(directory).expanduser()
    if not path.is_dir():
        raise CheckUsageError(f"{directory} is not a directory")
    if backend not in _GATE_BACKENDS:
        raise CheckUsageError(f"the gate runs on the {' or '.join(_GATE_BACKENDS)} backend only; a hardware check is "
                              "an operator procedure outside the gate (0.9)")
    directory_path = path.resolve()
    root_path = Path(root).expanduser().resolve() if root is not None else find_root(directory_path)
    clone_path = Path(clone).expanduser().resolve() if clone is not None else None
    companions_path = Path(companions_root).expanduser().resolve() if companions_root is not None else None
    card, _problem = read_json(directory_path / TASK_FILE)
    src = str(Path(__file__).resolve().parents[2])
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([src] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop(INNER_ENV, None)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="mhs-gate-") as holder:
        cwd = Path(holder) / "cwd"
        cwd.mkdir()
        result, progress = Path(holder) / "report.json", Path(holder) / "progress.jsonl"
        command = [sys.executable, "-m", "mhs.driver._gate", "--result", str(result), "--progress", str(progress),
                   "--backend", backend]
        if root_path is not None:
            command += ["--root", str(root_path)]
        if clone_path is not None:
            command += ["--clone", str(clone_path)]
        if companions_path is not None:
            command += ["--companions-root", str(companions_path)]
        command.append(str(directory_path))
        timed_out = False
        try:
            done = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=timeout_s,
                                  stdin=subprocess.DEVNULL, check=False)
            returncode: int | None = done.returncode
            stderr = done.stderr.decode("utf-8", "replace")
        except subprocess.TimeoutExpired as exc:
            timed_out, returncode = True, None
            stderr = (exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else ""
        document, _problem = read_json(result)
        stage, finished, tampered = _read_progress(progress)
    if isinstance(document, Mapping) and isinstance(document.get("usage_error"), str):
        raise CheckUsageError(document["usage_error"])
    identity = _identity(card, directory_path, root_path, backend)
    report, why = (_verified(document, identity=identity, progress=(stage, finished)) if returncode == 0
                   else (None, f"exit status {returncode}"))
    if report is None:
        tail = stderr.strip()[-1200:]
        if timed_out:
            code, message = "TIMEOUT", (f"the gate did not finish within {timeout_s:.0f} s (blocked code "
                                        "GATE_TIMEOUT)")
        else:
            cause = ("package code ended or crashed the interpreter (os._exit, a signal, a fatal error)"
                     if returncode != 0 or not isinstance(document, Mapping) else
                     "the report is not the gate's own (package code wrote or altered it)")
            code, message = "ABORTED", f"the gate process ended without a valid report ({why}): {cause}"
        if tail:
            message += f"; last output:\n{tail}"
        report = _aborted_report(card, directory_path, root_path, backend, stage, finished, code, message[:1900],
                                 (time.monotonic() - started) * 1000)
    established = static_findings(directory_path, card)
    if tampered:
        finding = _tamper_finding(tampered)
        established.append((finding.code, finding.message, str(finding.path)))
    report = _enforce(report, card, directory_path, root_path, established)
    if write_report:
        _write_report(directory_path, report)
    return report, stderr


def format_report(report: Mapping[str, Any], *, verbose: bool = False) -> str:
    """The human summary the CLI prints: failing gates with their findings, the codes of the warnings of the other
    gates (``verbose`` prints every message); a pass ends with the gate digest (:func:`stable_digest`, the value for
    ``RESULT.json`` ``gate.digest``) and the ``PASS`` line."""
    lines = [f"mhs.driver check {report.get('driver_dir')} (backend {report.get('backend')})"]
    for gate in report.get("gates") or []:
        lines.append(f"  {gate['id']} {gate['status']:<4} {gate.get('name', '')}")
        show = gate["status"] == "fail" or verbose
        if gate["status"] == "warn" and not verbose:
            counts: dict[str, int] = {}
            for finding in gate.get("findings") or []:
                if finding.get("severity") == "warning":
                    counts[str(finding.get("code"))] = counts.get(str(finding.get("code")), 0) + 1
            if counts:
                names = ", ".join(code if number == 1 else f"{code} x{number}" for code, number in counts.items())
                lines.append(f"       warnings: {names} (--verbose prints the messages)")
        for finding in gate.get("findings") or []:
            if show or finding.get("severity") == "error":
                text = str(finding.get("message")).replace("\n", "\n         ")
                lines.append(f"       {finding.get('severity', 'error')} {finding.get('code')}: {text}")
    if report.get("passed"):
        lines.append(f"gate digest (RESULT.json gate.digest): {stable_digest(report)}")
        lines.append(f"PASS: evidence {report.get('evidence_state')}")
    else:
        lines.append("FAIL: " + " ".join(report.get("failed") or []))
    return "\n".join(lines)
