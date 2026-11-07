"""Pinned source evidence for a PyLabRobot profile (gate G7, family ``pylabrobot``).

Every reference of ``plr_profile`` must name a text file and lines of the clone at the pinned commit.  An
operation's ``ref`` is a span of at most :data:`MAX_SPAN_LINES` lines; every other reference names exactly one line.
In a Python file the cited code is read with ``ast`` (comments and docstrings never count):

* ``handler_ref``: an assignment on that line to the handler's last name (``self.lh, ... = ...`` or ``lh = ...``);
* ``setup_ref``, ``close_ref``, ``stop.ref``: a definition of that name (``def``/``async def``) on that line, or a
  call of it (``x.name(...)``);
* ``channels_ref``: the channel count as an integer literal on that line;
* ``tip_tracking_ref`` / ``volume_tracking_ref``: the call ``set_tip_tracking(True)`` / ``set_volume_tracking(True)``;
* each labware ``ref``: the labware name as a string argument of a call (``TipRack(name="tips")``);
* each operation ``ref``: a call of every PyLabRobot front-end method of the kind inside the span, and for
  ``transfer``/``mix`` made on the handler (``env.lh.aspirate(...)``).

A labware name may also be cited in a JSON deck file, as a ``"name": "<labware>"`` pair on the cited line; no other
file type can satisfy a reference.  This proves where the upstream writes these things.  It does not prove
PyLabRobot behaviour, the deck of a real robot, a working stop or its physical effect; the generic G7 check of the
fake against ``native`` still runs first.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Callable

from .pylabrobot import OPERATION_CALLS, PlrProfile
from .upstream import parse_ref, safe_relpath

__all__ = ["MAX_SPAN_LINES", "check_pylabrobot_surface"]

#: The longest span an operation reference may cite; wider spans could hold unrelated calls.
MAX_SPAN_LINES = 40


class _Source:
    """One cited file of the clone: its lines and, for Python, its parsed tree."""

    def __init__(self, relpath: str, text: str):
        self.relpath = relpath
        self.lines = text.splitlines()
        self.tree: ast.AST | None = None
        self.parse_error = False
        if relpath.endswith(".py"):
            try:
                self.tree = ast.parse(text)
            except (SyntaxError, ValueError):
                self.parse_error = True

    def nodes(self, first: int, last: int) -> list[ast.AST]:
        """AST nodes that start inside ``first..last`` (1-based, inclusive)."""
        if self.tree is None:
            return []
        return [node for node in ast.walk(self.tree)
                if isinstance(getattr(node, "lineno", None), int) and first <= node.lineno <= last]


def _name_of(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _targets(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, ast.Assign):
        found: list[ast.AST] = []
        for target in node.targets:
            found.extend(ast.walk(target))
        return found
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        return list(ast.walk(node.target))
    return []


def _assigns(name: str) -> Callable[[_Source, int, int], bool]:
    def check(source: _Source, first: int, last: int) -> bool:
        return any(_name_of(target) == name and getattr(target, "lineno", None) == first
                   for node in source.nodes(first, last) for target in _targets(node))
    return check


def _defines_or_calls(name: str) -> Callable[[_Source, int, int], bool]:
    def check(source: _Source, first: int, last: int) -> bool:
        for node in source.nodes(first, last):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                return True
            if isinstance(node, ast.Call) and _name_of(node.func) == name:
                return True
        return False
    return check


def _integer(value: int) -> Callable[[_Source, int, int], bool]:
    def check(source: _Source, first: int, last: int) -> bool:
        return any(isinstance(node, ast.Constant) and type(node.value) is int and node.value == value
                   for node in source.nodes(first, last))
    return check


def _switch_on(name: str) -> Callable[[_Source, int, int], bool]:
    def check(source: _Source, first: int, last: int) -> bool:
        return any(isinstance(node, ast.Call) and _name_of(node.func) == name and node.args
                   and isinstance(node.args[0], ast.Constant) and node.args[0].value is True
                   for node in source.nodes(first, last))
    return check


def _call_argument(text: str) -> Callable[[_Source, int, int], bool]:
    def check(source: _Source, first: int, last: int) -> bool:
        # The call may start on an earlier line; the string argument itself must be on the cited line.
        for node in ast.walk(source.tree) if source.tree is not None else ():
            if not isinstance(node, ast.Call):
                continue
            values = list(node.args) + [keyword.value for keyword in node.keywords]
            if any(isinstance(value, ast.Constant) and value.value == text and value.lineno == first
                   for value in values):
                return True
        return False
    return check


def _calls_on(method: str, receiver: str | None) -> Callable[[_Source, int, int], bool]:
    def check(source: _Source, first: int, last: int) -> bool:
        for node in source.nodes(first, last):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == method
                    and (receiver is None or _name_of(node.func.value) == receiver)):
                return True
        return False
    return check


def _json_name(text: str) -> re.Pattern[str]:
    return re.compile(rf'"name"\s*:\s*"{re.escape(text)}"')


def check_pylabrobot_surface(ctx: Any, gate: Any) -> None:
    """Check every source reference of the driver's ``plr_profile`` against the clone (G7 errors on mismatch)."""
    profile = getattr(ctx.cls, "plr_profile", None)
    if type(profile) is not PlrProfile:
        gate.error("PLR_PROFILE", "plr_profile is not a PlrProfile; nothing can be checked against the clone",
                   "driver.py")
        return
    last = lambda path: str(path).split(".")[-1]  # noqa: E731 - local shorthand
    handler = last(profile.handler) if profile.handler else None
    # (where, ref, single line?, AST predicate, JSON pattern or None, what it must show)
    entries: list[tuple[str, Any, bool, Callable[[_Source, int, int], bool], re.Pattern[str] | None, str]] = []
    if handler:
        entries.append(("plr_profile.handler_ref", profile.handler_ref, True, _assigns(handler), None,
                        f"an assignment to {handler!r}"))
    entries.append(("plr_profile.setup_ref", profile.setup_ref, True, _defines_or_calls(last(profile.setup)), None,
                    f"a definition or call of {last(profile.setup)!r}"))
    entries.append(("plr_profile.close_ref", profile.close_ref, True, _defines_or_calls(last(profile.close)), None,
                    f"a definition or call of {last(profile.close)!r}"))
    entries.append(("plr_profile.channels_ref", profile.channels_ref, True, _integer(profile.channels), None,
                    f"the integer {profile.channels}"))
    for name, ref in (("set_tip_tracking", profile.tip_tracking_ref),
                      ("set_volume_tracking", profile.volume_tracking_ref)):
        if ref is not None:
            entries.append((f"plr_profile.{name.split('_', 1)[1]}_ref", ref, True, _switch_on(name), None,
                            f"the call {name}(True)"))
    for item in profile.labware:
        entries.append((f"labware {item.name!r}", item.ref, True, _call_argument(item.name), _json_name(item.name),
                        f"the name {item.name!r} as a call argument (or a JSON \"name\" field)"))
    for capability_id, operation in profile.operations:
        receiver = handler if operation.kind != "tracked_volumes" else None
        for call in OPERATION_CALLS.get(operation.kind, ()):
            on = f" on {receiver!r}" if receiver else ""
            entries.append((capability_id, operation.ref, False, _calls_on(call, receiver), None,
                            f"a call of .{call}(){on}"))
    if profile.stop is not None:
        entries.append(("plr_profile.stop.ref", profile.stop.ref, True, _defines_or_calls(last(profile.stop.native)),
                        None, f"a definition or call of {last(profile.stop.native)!r}"))
    sources: dict[str, _Source | None] = {}
    reported: set[tuple[str, str]] = set()
    for where, text, single, predicate, json_pattern, what in entries:
        ref = parse_ref(text)
        relpath = safe_relpath(ref.path) if ref is not None else None
        problem = None
        if ref is None or relpath is None:
            problem = f"{text!r} is not a 'path/in/clone:LINE' reference"
        elif single and ref.end != ref.line:
            problem = f"{text} is a span; cite the one line that shows {what}"
        elif ref.end - ref.line + 1 > MAX_SPAN_LINES:
            problem = f"{text} spans {ref.end - ref.line + 1} lines; cite at most {MAX_SPAN_LINES}"
        if problem is None and relpath not in sources:
            document = ctx.tree.read_text(relpath)
            sources[relpath] = _Source(relpath, document) if document is not None else None
        source = sources.get(relpath) if problem is None else None
        if problem is None and source is None:
            problem = f"{relpath} is not a text file of the clone"
        elif problem is None and ref.end > len(source.lines):
            problem = f"{relpath} has {len(source.lines)} lines; line {ref.end} does not exist"
        if problem is not None:
            if (where, str(text)) not in reported:
                reported.add((where, str(text)))
                gate.error("PLR_REF", f"{where}: {problem}", where, str(text))
            continue
        if source.tree is not None:
            shown = predicate(source, ref.line, ref.end)
        elif json_pattern is not None and relpath.endswith(".json"):
            shown = bool(json_pattern.search(source.lines[ref.line - 1]))
        else:
            if (where, str(text)) not in reported:
                reported.add((where, str(text)))
                reason = ("cannot be parsed as Python" if source.parse_error
                          else "is neither Python nor a JSON deck file")
                gate.error("PLR_SOURCE", f"{where}: {relpath} {reason}; the reference cannot be read", where,
                           str(text))
            continue
        if not shown:
            gate.error("PLR_SOURCE", f"{where}: the cited code at {text} does not show {what}", where, str(text))
