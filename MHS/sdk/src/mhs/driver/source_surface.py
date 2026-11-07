"""Strict AST evidence for explicit source selectors; never imports upstream code."""

from __future__ import annotations

import ast
import inspect
import re
import stat
from dataclasses import dataclass, field
from typing import Any

from .source_selector import SourceSelector, source_path
from .upstream import Surface, UpstreamTree, _MAX_BLOB, _Reader, _parse_legacy


def _tree_entries(tree: UpstreamTree, path: str) -> list[list[str]]:
    """``[mode, type, object id]`` of the entries the pinned tree records at exactly ``path``."""
    listing = tree._run("--literal-pathspecs", "ls-tree", "-z", str(tree.commit), "--", path)
    wanted = []
    for entry in (listing or "").split("\0"):
        meta, sep, name = entry.partition("\t")
        fields = meta.split()
        if sep and name == path and len(fields) == 3:
            wanted.append(fields)
    return wanted


def regular_source(tree: UpstreamTree, path: str) -> str:
    """Read exactly a pinned regular blob, or a contained unpinned tutorial file."""
    if source_path(path) is None:
        raise ValueError(f"unsafe source path {path!r}")
    if tree.commit or tree.is_git:
        if not tree.pinned:
            raise ValueError("explicit source evidence requires an available pinned Git commit")
        source, inner = tree, path
        wanted = _tree_entries(tree, path)
        if not wanted:
            # A path inside a git submodule is read at its gitlink commit from its own object store (SUBMODULES);
            # a path that names the gitlink itself stays an error below.
            located = tree.locate_submodule(path)
            if located is not None:
                source, inner = located
                wanted = _tree_entries(source, inner)
        if len(wanted) != 1 or wanted[0][0] not in ("100644", "100755") or wanted[0][1] != "blob":
            raise ValueError(f"{path} is not a regular blob at the pinned commit"
                             + (f" ({tree.refusal_for(path)})" if tree.refusal_for(path) else ""))
        oid = wanted[0][2]
        size = source._run("cat-file", "-s", oid)
        if size is None or not size.strip().isdigit() or int(size) > _MAX_BLOB:
            raise ValueError(f"{path} exceeds the source blob bound or is unavailable")
        data = source._run("cat-file", "blob", oid, binary=True)
        if data is not None and source is not tree:
            source.note_read()
    else:
        # Synthetic tutorials are deliberately not Git clones. A claimed pin never enters this path.
        target = tree.root
        try:
            for part in path.split("/"):
                target = target / part
                if target.is_symlink():
                    raise ValueError(f"{path} traverses a symlink")
            info = target.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_BLOB:
                raise ValueError(f"{path} is not a bounded regular source file")
            data = target.read_bytes()
        except OSError as exc:
            raise ValueError(f"{path} is unavailable") from exc
    if data is None or len(data) > _MAX_BLOB or b"\0" in data:
        raise ValueError(f"{path} is not a bounded text source")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path} is not UTF-8 source") from exc


@dataclass
class ExplicitSurface(Surface):
    signatures: dict[str, inspect.Signature] = field(default_factory=dict)


_DEFAULT = object()  # Default presence only; AST expressions are never evaluated.


def function_signature(node: ast.FunctionDef) -> inspect.Signature:
    args = node.args
    positional = args.posonlyargs + args.args
    first_default = len(positional) - len(args.defaults)
    params = [inspect.Parameter(arg.arg, inspect.Parameter.POSITIONAL_ONLY if index < len(args.posonlyargs)
                                else inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                default=_DEFAULT if index >= first_default else inspect.Parameter.empty)
              for index, arg in enumerate(positional)]
    if args.vararg:
        params.append(inspect.Parameter(args.vararg.arg, inspect.Parameter.VAR_POSITIONAL))
    params += [inspect.Parameter(arg.arg, inspect.Parameter.KEYWORD_ONLY,
                                default=_DEFAULT if default is not None else inspect.Parameter.empty)
               for arg, default in zip(args.kwonlyargs, args.kw_defaults)]
    if args.kwarg:
        params.append(inspect.Parameter(args.kwarg.arg, inspect.Parameter.VAR_KEYWORD))
    return inspect.Signature(params)


def _bindings(node: ast.AST) -> set[str]:
    """Names bound by a statement; stop at function/class bodies, which have another scope."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return {alias.asname or alias.name.split(".")[0] for alias in node.names}
    if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
        return {node.id}
    return set().union(*(_bindings(child) for child in ast.iter_child_nodes(node)))


def _module_mutation(module: ast.Module) -> bool:
    # Dynamic module namespace manipulation cannot prove a stable callable surface.
    def top_level_mutation(node: ast.AST) -> bool:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return False
        if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(node.ctx, (ast.Store, ast.Del)):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("setattr", "delattr"):
            return True
        return any(top_level_mutation(child) for child in ast.iter_child_nodes(node))

    if top_level_mutation(module):
        return True
    for node in ast.walk(module):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in (
                "exec", "eval", "globals", "locals", "vars", "__import__"):
            return True
        if isinstance(node, (ast.Import, ast.ImportFrom)) and any(alias.name == "*" for alias in node.names):
            return True
    return False


def explicit_surface(tree: UpstreamTree, selector: SourceSelector) -> ExplicitSurface:
    surface = ExplicitSurface(selector.value)
    path = selector.path
    if path is None:
        surface.problems.append("an explicit source-file selector is required")
        return surface
    try:
        text = regular_source(tree, path)
        try:
            module = ast.parse(text, filename=path)
        except SyntaxError:
            changed: set[int] = set()
            module, count = _parse_legacy(text, path, changed_lines=changed)
            lines = text.splitlines()
            if module is None or any(re.match(r"^[ \t]*print(?:\s|>>)", lines[line - 1]) is None for line in changed):
                raise ValueError("legacy source requires changes beyond standalone Python 2 print statements")
            surface.legacy[path] = count
    except (ValueError, SyntaxError) as exc:
        surface.problems.append(str(exc))
        return surface
    surface.file = path
    surface.line = 1
    if _module_mutation(module):
        surface.problems.append(f"{path} mutates its namespace dynamically; no explicit surface can be proven")
        return surface
    direct: dict[str, list[ast.stmt]] = {}
    for node in module.body:
        for name in _bindings(node):
            direct.setdefault(name, []).append(node)
    if selector.kind == "module":
        for name, nodes in direct.items():
            node = nodes[0]
            if (name.startswith("_") or len(nodes) != 1 or not isinstance(node, ast.FunctionDef)
                    or node.decorator_list):
                continue
            surface.names.add(name)
            surface.signatures[name] = function_signature(node)
        if not surface.names:
            surface.problems.append(f"{path} has no verified public synchronous module functions")
        return surface
    parts = selector.name.split(".")
    nodes = direct.get(parts[0], [])
    cls = nodes[0] if len(nodes) == 1 and isinstance(nodes[0], ast.ClassDef) else None
    for part in parts[1:]:
        candidates = [node for node in cls.body if isinstance(node, ast.ClassDef) and node.name == part] if cls else []
        cls = candidates[0] if len(candidates) == 1 else None
    if cls is None or cls.decorator_list:
        surface.problems.append(f"class {selector.name} is not an undecorated direct definition in {path}")
        return surface

    class LocalReader(_Reader):
        # Exact-file selectors do not follow imported aliases or search other source files.
        def parse(self, wanted: str) -> ast.Module | None:
            return module if wanted == path else None

        def module_file(self, *args: Any, **kwargs: Any) -> None:
            return None

        def find_class(self, wanted: str, name: str, depth: int = 0) -> tuple[str, ast.ClassDef] | None:
            if wanted != path or depth > 6:
                return None
            body = module.body
            found = None
            for part in name.split("."):
                candidates = [node for node in body if part in _bindings(node)]
                if len(candidates) != 1 or not isinstance(candidates[0], ast.ClassDef) or candidates[0].decorator_list:
                    return None
                found = candidates[0]
                body = found.body
            return (path, found) if found is not None else None

        def base_target(self, wanted: str, base: ast.expr) -> tuple[str, str] | None:
            if isinstance(base, ast.Name) and self.find_class(wanted, base.id) is not None:
                return path, base.id
            return None

    surface.line = cls.lineno
    LocalReader(tree).collect(path, cls, surface)
    return surface


def signature_shape(signature: inspect.Signature) -> tuple[tuple[str, Any, bool], ...]:
    return tuple((param.name, param.kind, param.default is not inspect.Parameter.empty)
                 for param in signature.parameters.values())
