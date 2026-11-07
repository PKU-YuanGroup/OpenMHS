"""Gate G7 for a Gymnasium environment that a factory function of the clone builds (``native_factory``).

Some simulation suites never define their environment class: a function of the clone composes the task and returns
an instance of a class that lives in another library (RoboPianist's ``robopianist.suite.load`` returns a dm_control
composer ``Environment`` from ``mujoco_utils``). G7's class rule cannot read that class, and naming the task class as
``native`` would check the fake against the wrong surface. A ``GymnasiumDriver`` then declares::

    native = "robopianist.suite:load"
    native_factory = {"returns": "mujoco_utils.composer_utils.Environment",
                      "ref": "robopianist/suite/__init__.py:87-93"}

and G7 checks, at the pinned commit and with :mod:`ast` only (nothing is imported or run):

* ``native`` is an undecorated, synchronous module-level function of the clone (the card's file hint first);
* every ``return`` of that function returns a call of exactly ``returns``, resolved through a module-level import of
  the function's file (``from mujoco_utils import composer_utils`` makes ``composer_utils.Environment`` the name
  ``mujoco_utils.composer_utils.Environment``); a name the function binds itself, a relative import or any other
  return fails;
* ``ref`` cites that file and covers every such return statement;
* the class is not defined in the clone (otherwise the class rule applies: name the class as ``native``);
* the fake and the driver use only the environment interface the bridge holds such an object to: the dm_env interface
  when the gate's backend declares the ``dm_env_v1`` profile, the Gymnasium environment interface otherwise. Nothing
  else may be implemented by the fake or used by the driver (``NOT_UPSTREAM``).

What this does not prove: that the external class really provides that interface, its behaviour, or the factory's
keyword arguments. Those are the reviewer's (REVIEW.md item 7), as for every upstream class.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Mapping

from .upstream import _dotted, _find_module, _never_runs, _Reader, parse_ref, safe_relpath

__all__ = ["DM_ENV_INTERFACE", "check_factory_surface", "declaration_problems"]

#: The dm_env ``Environment`` methods, and ``control_timestep``, the dm_control control-suite and composer method that
#: the dm_env adapter reads for the fidelity timestep (MHS/sdk/docs/gym-live-routes.md).
DM_ENV_INTERFACE = frozenset({"reset", "step", "action_spec", "observation_spec", "reward_spec", "discount_spec",
                              "close", "control_timestep"})
_KEYS = frozenset({"returns", "ref"})
_DOTTED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")


def declaration_problems(value: Any) -> list[str]:
    """What is wrong with a ``native_factory`` declaration (empty when it is well formed)."""
    if not isinstance(value, Mapping) or set(value) != _KEYS:
        return ["native_factory must be {'returns': 'package.module.Class', 'ref': 'path/in/clone:LINE[-END]'} "
                "(exactly these two keys)"]
    problems = []
    returns = value.get("returns")
    if not isinstance(returns, str) or len(returns) > 200 or not _DOTTED.match(returns):
        problems.append("native_factory.returns must be the dotted name of the class the factory constructs "
                        "(package.module.Class)")
    ref = value.get("ref")
    parsed = parse_ref(ref) if isinstance(ref, str) else None
    if parsed is None or safe_relpath(parsed.path) is None:
        problems.append("native_factory.ref must cite the factory's return statement as 'path/in/clone:LINE[-END]'")
    return problems


def _module_function(module: ast.Module, name: str, line: int) -> ast.AST | None:
    """The module-level ``def name`` at ``line`` (also inside a top-level ``if``/``try``/``with`` block)."""
    found = None

    def visit(statements: list[ast.stmt]) -> None:
        nonlocal found
        for node in statements:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name and node.lineno == line:
                found = node
            elif isinstance(node, ast.If):
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
    return found


def _returns(function: ast.FunctionDef) -> list[ast.Return]:
    """The ``return`` statements of ``function`` itself (not of nested functions, classes or lambdas)."""
    return sorted((node for node in _own_nodes(function) if isinstance(node, ast.Return)), key=lambda item: item.lineno)


def _own_nodes(function: ast.FunctionDef) -> list[ast.AST]:
    """Every node of ``function``'s own body (not of nested functions, classes or lambdas)."""
    out: list[ast.AST] = []
    stack: list[ast.AST] = list(function.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        out.append(node)
        stack.extend(ast.iter_child_nodes(node))
    return out


def _always_returns(statements: list[ast.stmt]) -> bool:
    """True when every path through ``statements`` ends in a ``return`` or ``raise`` (a conservative reading: loops
    and ``match`` never count, so a factory that can fall off its end, and return None, is refused)."""
    if not statements:
        return False
    last = statements[-1]
    if isinstance(last, (ast.Return, ast.Raise)):
        return True
    if isinstance(last, ast.If):
        return _always_returns(last.body) and _always_returns(last.orelse)
    if isinstance(last, (ast.With, ast.AsyncWith)):
        return _always_returns(last.body)
    if isinstance(last, ast.Try) or type(last).__name__ == "TryStar":
        return (_always_returns(last.body + last.orelse if last.orelse else last.body)
                and all(_always_returns(handler.body) for handler in last.handlers))
    return False


def _bound_in(function: ast.FunctionDef, name: str) -> bool:
    """True when ``function`` binds ``name`` itself: a parameter, an assignment, a loop or ``with`` target, an import,
    a ``global``/``nonlocal`` or a nested definition."""
    args = function.args
    params = args.posonlyargs + args.args + args.kwonlyargs + [item for item in (args.vararg, args.kwarg) if item]
    if any(param.arg == name for param in params):
        return True
    for node in ast.walk(function):
        if node is function:
            continue
        if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, (ast.Store, ast.Del)):
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return True
        if isinstance(node, (ast.Import, ast.ImportFrom)) and any(
                (alias.asname or alias.name.split(".")[0]) == name for alias in node.names):
            return True
        if isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names:
            return True
        if isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name) and node.target.id == name:
            return True
    return False


def _module_bindings(module: ast.Module, name: str) -> list[ast.stmt]:
    """Every module-level statement that binds ``name`` (top-level ``if``/``try``/``with`` blocks included, never a
    branch that does not run)."""
    out: list[ast.stmt] = []

    def visit(statements: list[ast.stmt]) -> None:
        for node in statements:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == name:
                    out.append(node)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if any((alias.asname or alias.name.split(".")[0]) == name for alias in node.names):
                    out.append(node)
            elif isinstance(node, ast.If):
                if not _never_runs(node.test):
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
            else:
                for child in ast.walk(node):
                    if isinstance(child, ast.Name) and child.id == name and isinstance(child.ctx, (ast.Store, ast.Del)):
                        out.append(node)
                        break

    visit(module.body)
    return out


def _imported_name(module: ast.Module, function: ast.FunctionDef, callee: str) -> tuple[str | None, str]:
    """``(full dotted name, "")`` of ``callee`` through the module-level import that binds its first part, or
    ``(None, why not)``."""
    head, _, rest = callee.partition(".")
    if _bound_in(function, head):
        return None, f"{head} is bound inside the factory itself"
    bindings = _module_bindings(module, head)
    if len(bindings) != 1:
        return None, (f"{head} is not bound by a module-level import" if not bindings
                      else f"{head} is bound {len(bindings)} times at module level")
    node = bindings[0]
    suffix = f".{rest}" if rest else ""
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.asname == head:
                return alias.name + suffix, ""
            if alias.asname is None and alias.name.split(".")[0] == head:
                return head + suffix, ""
    if isinstance(node, ast.ImportFrom):
        if node.level:
            return None, f"{head} comes from a relative import (code of the clone)"
        for alias in node.names:
            if (alias.asname or alias.name) == head and node.module:
                return f"{node.module}.{alias.name}{suffix}", ""
    return None, f"{head} is bound by a definition or assignment of the module, not by an import"


def check_factory_surface(ctx: Any, gate: Any, symbol: str, hint: str | None, factory: Any, fake_members: set[str],
                          gymnasium_interface: frozenset[str]) -> None:
    """G7 for ``native_factory`` (see the module docstring)."""
    if ctx.family != "gymnasium":
        gate.error("FACTORY_FAMILY", "native_factory applies to GymnasiumDriver environments only", "driver.py")
        return
    problems = declaration_problems(factory)
    for problem in problems:
        gate.error("FACTORY_DECLARATION", problem, "driver.py")
    if problems:
        return
    module_name, _, name = symbol.partition(":")
    if not module_name or not name or "." in name:
        gate.error("FACTORY_DECLARATION", f"native {symbol!r} must name a module-level function of the clone "
                   "('package.module:function') when native_factory is declared", "driver.py")
        return
    tree = ctx.tree
    label = f"{tree.root} at {str(tree.commit)[:12]}" if tree.pinned and tree.commit else str(tree.root)
    path = _find_module(tree, module_name, hint, submodules=True)
    reader = _Reader(tree)
    if path is None or reader.parse(path) is None:
        gate.error("NATIVE_NOT_FOUND", f"module {module_name} of {symbol} is not in the clone or cannot be parsed "
                   f"({label})", "driver.py")
        return
    definition = reader.find_definition(path, name)
    if definition is None:
        gate.error("NATIVE_NOT_FOUND", f"{name} is not defined in {path} ({label})", "driver.py")
        return
    file, line, kind = definition
    module = reader.parse(file)
    function = _module_function(module, name, line) if module is not None and kind == "function" else None
    if not isinstance(function, ast.FunctionDef) or function.decorator_list:
        gate.error("FACTORY_NOT_FUNCTION", f"{symbol} is not an undecorated synchronous module-level function in "
                   f"{file}:{line} ({label}); a factory is a plain def whose returns G7 can read", "driver.py")
        return
    if any(isinstance(node, (ast.Yield, ast.YieldFrom, ast.Await)) for node in _own_nodes(function)):
        gate.error("FACTORY_NOT_FUNCTION", f"{symbol} ({file}:{line}) is a generator: calling it returns no "
                   "environment", "driver.py")
        return
    expected = factory["returns"]
    returns = _returns(function)
    if not returns:
        gate.error("FACTORY_RETURN", f"{symbol} ({file}:{line}) has no return statement", "driver.py")
        return
    if not _always_returns(function.body):
        gate.error("FACTORY_RETURN", f"{symbol} ({file}:{line}) can end without a return statement and then "
                   "returns None", "driver.py")
    for statement in returns:
        span = f"{file}:{statement.lineno}"
        if not isinstance(statement.value, ast.Call) or _dotted(statement.value.func) is None:
            gate.error("FACTORY_RETURN", f"{span}: the factory returns something other than a call of {expected}",
                       "driver.py", span)
            continue
        full, why = _imported_name(module, function, _dotted(statement.value.func))
        if full is None:
            gate.error("FACTORY_RETURN", f"{span}: {_dotted(statement.value.func)}(...) cannot be resolved ({why})",
                       "driver.py", span)
        elif full != expected:
            gate.error("FACTORY_RETURN", f"{span}: the factory returns {full}(...), not {expected}", "driver.py", span)
    ref = parse_ref(factory["ref"])
    if ref.path != file:
        gate.error("FACTORY_REF", f"native_factory.ref cites {ref.path}, but {symbol} is defined in {file}",
                   "driver.py", factory["ref"])
    else:
        for statement in returns:
            first, last = statement.lineno, getattr(statement, "end_lineno", None) or statement.lineno
            if not (ref.line <= first and last <= ref.end):
                gate.error("FACTORY_REF", f"native_factory.ref {factory['ref']} does not cover the return statement "
                           f"at {file}:{first}-{last}", "driver.py", factory["ref"])
    class_module, _, class_name = expected.rpartition(".")
    target = _find_module(tree, class_module, submodules=True)
    if target is not None and reader.find_class(target, class_name) is not None:
        gate.error("FACTORY_IN_CLONE", f"{expected} is defined in the clone ({target}); name that class as native "
                   "instead of its factory", "driver.py")
    profiles = dict(getattr(ctx.cls, "dm_env_by_backend", {}) or {})
    if profiles.get(ctx.backend) is not None:
        interface, what = DM_ENV_INTERFACE, "dm_env environment"
    else:
        interface, what = gymnasium_interface, "Gymnasium environment"
    used: dict[str, str] = {}
    for member in sorted(fake_members):
        used.setdefault(member, "defined by the fake")
    for log in ctx.logs:
        for member in sorted(log.found):
            if not (member.startswith("__") and member.endswith("__")):
                used[member] = "used by the driver"
    for member in sorted(used):
        if member not in interface:
            gate.error("NOT_UPSTREAM", f"{member!r} ({used[member]}) is not part of the {what} interface that the "
                       f"return value of {symbol} ({expected}, a class outside the clone) is held to: "
                       f"{sorted(interface)}", member, f"{file}:{line}")
