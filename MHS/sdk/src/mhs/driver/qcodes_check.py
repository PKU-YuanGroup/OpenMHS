"""Narrow pinned AST evidence for declared QCoDeS Parameter selectors.

This proves an explicit Parameter constructor with native get/set commands,
not instrument behavior, safe RF load, installed QCoDeS version or execution
of an arbitrary factory. Dynamic add_parameter/channel factories need a
separately reviewed profile; get/set names alone are never evidence.
"""
from __future__ import annotations

import ast
from typing import Any

from .qcodes_config import parameter_specs
from .upstream import parse_ref

# These protocols can replace storage, identity or normal member resolution.
# Explicit use is refused regardless of whether Python spells it as a method,
# a literal class binding, an alias, or an attribute reached through super().
_IDENTITY_MEMBERS = {"__getattribute__", "__getattr__", "__setattr__", "__delattr__",
                     "__dict__", "__class__", "__slots__", "__new__", "__init_subclass__",
                     "__mro_entries__", "__bases__", "__base__", "__mro__", "__prepare__",
                     "__get__", "__set__", "__delete__", "__call__"}
_REFLECTION = {"getattr", "setattr", "delattr"}


def _path(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _path(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def _value(node: ast.AST):
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return node.value
    return None


def _targets(node: ast.AST):
    return node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []


def _contains(node: ast.AST, ref) -> bool:
    return node.lineno <= ref.line <= ref.end <= getattr(node, "end_lineno", node.lineno)


def _scope_nodes(scope):
    """Include compound statements, but do not enter a nested lexical scope."""
    stack = list(scope.body)
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _bindings(scope):
    """Conservative lexical binding/mutation inventory, including rare forms."""
    result = {}
    def add(name, node):
        if name:
            result.setdefault(name, []).append(node)
    for node in _scope_nodes(scope):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                add(alias.asname or alias.name.split(".")[0], node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add(node.name, node)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            add(node.id, node)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
            path = _path(node)
            add(path.split(".")[0] if path else None, node)
        elif isinstance(node, ast.ExceptHandler):
            add(node.name, node)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)):
            add(node.name, node)
        elif isinstance(node, ast.MatchMapping):
            add(node.rest, node)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                add(name, node)
    return result


def _parameter_names(module: ast.Module) -> set[str]:
    bindings = _bindings(module)
    if "*" in bindings:
        return set()
    names = set()
    for node in module.body:
        if isinstance(node, ast.ImportFrom) and node.module == "qcodes.parameters" and node.level == 0:
            for alias in node.names:
                name = alias.asname or alias.name
                if alias.name == "Parameter" and bindings.get(name) == [node]:
                    names.add(name)
    return names


def _native_command(node: ast.AST | None) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str) and bool(node.value.strip())
    path = _path(node) if node is not None else None
    return bool(path and "." in path and not any(part in {"cache", "get_latest"} for part in path.split(".")))


def _check_call(call: ast.AST, names: set[str], item: dict, bound_names=()) -> str | None:
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id not in names:
        return "assignment must construct the imported qcodes.parameters.Parameter"
    if call.func.id in bound_names:
        return "Parameter import is shadowed by a function argument or local binding"
    keywords = {keyword.arg: keyword.value for keyword in call.keywords}
    for op in ("get", "set"):
        if item[op] and not _native_command(keywords.get(op + "_cmd")):
            return f"Parameter needs a source-visible native {op}_cmd (None/cache-only is not a measurement)"
    return None


def _bound_names(function):
    names = {arg.arg for arg in (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs)}
    names.update(arg.arg for arg in (function.args.vararg, function.args.kwarg) if arg is not None)
    names.update(_bindings(function))
    return names


def _module(tree, path, cache):
    if path not in cache:
        text = tree.read_text(path)
        if text is None:
            raise ValueError("cited file is absent from the pinned tree")
        if len(cache) >= 32 or len(text.encode("utf-8")) > 1048576:
            raise ValueError("Parameter evidence exceeds the 32-file / 1 MiB per-file AST bound")
        cache[path] = ast.parse(text)
    return cache[path]


def _related(path, wanted):
    return bool(path and (path == wanted or path.startswith(wanted + ".") or wanted.startswith(path + ".")))


def _parent_map(node):
    return {child: parent for parent in ast.walk(node) for child in ast.iter_child_nodes(parent)}


def _lexically_clear(name, node, parents):
    while node in parents:
        node = parents[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and name in _bound_names(node):
            return False
        if isinstance(node, ast.Lambda):
            args = node.args
            bound = {arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
            bound.update(arg.arg for arg in (args.vararg, args.kwarg) if arg is not None)
            bound.update(item.id for item in ast.walk(node.body) if isinstance(item, ast.Name)
                         and isinstance(item.ctx, (ast.Store, ast.Del)))
            if name in bound:
                return False
    return True


def _plain_builtin(name, node, module, parents):
    return name not in _bindings(module) and _lexically_clear(name, node, parents)


def _type_test_use(node, module, parents):
    parent = parents.get(node)
    while isinstance(parent, (ast.Tuple, ast.List)):
        node, parent = parent, parents.get(parent)
    return (isinstance(parent, ast.Call) and _path(parent.func) == "isinstance"
            and len(parent.args) == 2 and node is parent.args[1]
            and _plain_builtin("isinstance", parent, module, parents))


def _reflection_use(node, module, parents, wanted=None):
    """Allow only explicit unrelated native metadata, never opaque lookup."""
    if not isinstance(node, ast.Name) or node.id not in _REFLECTION or not isinstance(node.ctx, ast.Load):
        return
    call = parents.get(node)
    if (not isinstance(call, ast.Call) or call.func is not node or len(call.args) < 2
            or not _plain_builtin(node.id, call, module, parents)):
        raise ValueError("reflection builtins may not be shadowed or escape as aliases")
    owner = _path(call.args[0])
    attribute = call.args[1]
    if (not owner or not owner.startswith("self.") or not isinstance(attribute, ast.Constant)
            or not isinstance(attribute.value, str) or attribute.value in _IDENTITY_MEMBERS
            or (wanted and (_related(owner, wanted) or _related(owner + "." + attribute.value, wanted)))):
        raise ValueError("reflection is supported only for literal metadata on a disjoint explicit self member")


def _symbol_lifetime(module, name, *, class_symbol=False):
    """Only calls/types/bases may consume a proven constructor identity.

    Assignment through an alias, a decorator, a container or a callback is
    unsupported even if the later use appears harmless. No alias analysis or
    arbitrary Python execution is used to manufacture source evidence.
    """
    parents = _parent_map(module)
    for node in _scope_nodes(module):
        if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(node.ctx, (ast.Store, ast.Del)):
            raise ValueError("module namespace/member mutation is outside the declaration profile")
    for node in ast.walk(module):
        if isinstance(node, ast.Attribute) and node.attr in _IDENTITY_MEMBERS | _REFLECTION:
            raise ValueError("explicit dynamic identity/storage member access is outside the declaration profile")
        if isinstance(node, ast.ImportFrom) and node.module == "builtins" and any(alias.name in _REFLECTION or alias.name == "*" for alias in node.names):
            raise ValueError("imported/aliased reflection builtins are outside the declaration profile")
        _reflection_use(node, module, parents)
        if isinstance(node, ast.Name) and node.id in {"globals", "locals", "vars", "eval", "exec", "__import__", "__builtins__"}:
            raise ValueError("dynamic namespace access is outside the declaration profile")
        if ((isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, (ast.Store, ast.Del)))
                or (isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names)):
            raise ValueError(f"constructor identity {name!r} is rebound outside its declaration")
        if not isinstance(node, ast.Name) or node.id != name or not isinstance(node.ctx, ast.Load):
            continue
        parent = parents.get(node)
        if isinstance(parent, ast.ClassDef) and node in parent.bases:
            continue
        if ((isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) and parent.returns is node)
                or (isinstance(parent, ast.arg) and parent.annotation is node)
                or (isinstance(parent, ast.AnnAssign) and parent.annotation is node)):
            continue
        if class_symbol:
            if _type_test_use(node, module, parents):
                continue
        elif isinstance(parent, ast.Call) and parent.func is node:
            continue
        raise ValueError(f"constructor identity {name!r} escapes the supported call/type/base grammar")


def _factory_body(factory, module):
    """Recognize the complete finite same-file factory, without executing it."""
    if factory.decorator_list or isinstance(factory, ast.AsyncFunctionDef):
        raise ValueError("decorated/asynchronous Parameter factories are unsupported")
    body = [node for node in factory.body if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                                                and isinstance(node.value.value, str))]
    if (len(body) == 3 and isinstance(body[0], ast.Assign) and len(body[0].targets) == 1
            and isinstance(body[0].targets[0], ast.Name) and isinstance(body[1], ast.Assign)
            and len(body[1].targets) == 1
            and _path(body[1].targets[0]) == body[0].targets[0].id + ".__doc__"
            and isinstance(body[1].value, ast.Constant) and isinstance(body[1].value.value, str)):
        body = [body[0], body[2]]
    if (len(body) != 2 or not isinstance(body[0], ast.Assign) or len(body[0].targets) != 1
            or not isinstance(body[0].targets[0], ast.Name)
            or not isinstance(body[1], ast.Return) or not isinstance(body[1].value, ast.Name)
            or body[1].value.id != body[0].targets[0].id):
        raise ValueError("factory must construct one Parameter and return exactly that object")
    error = _check_call(body[0].value, _parameter_names(module), {"get": False, "set": False}, _bound_names(factory))
    if error:
        raise ValueError(error)
    return body[0].value


def _receiver_argument(node, module, parents):
    """Finite self escapes: Parameter instrument, proven factory, isinstance."""
    parent = parents.get(node)
    if isinstance(parent, ast.keyword) and parent.arg == "instrument":
        call = parents.get(parent)
        return (isinstance(call, ast.Call) and _path(call.func) in _parameter_names(module)
                and _lexically_clear(_path(call.func), call, parents))
    if not isinstance(parent, ast.Call):
        return False
    if (_path(parent.func) == "isinstance" and len(parent.args) == 2 and parent.args[0] is node
            and _plain_builtin("isinstance", parent, module, parents)):
        return True
    name = _path(parent.func)
    definitions = _bindings(module).get(name, [])
    if (not name or not _lexically_clear(name, parent, parents) or len(definitions) != 1 or not isinstance(definitions[0], ast.FunctionDef)
            or definitions[0] not in module.body or not parent.args or parent.args[0] is not node):
        return False
    factory = definitions[0]
    positional = [*factory.args.posonlyargs, *factory.args.args]
    if not positional or positional[0].arg != "self":
        return False
    _symbol_lifetime(module, name)
    _factory_body(factory, module)
    return True


def _class_grammar(cls, module, wanted):
    """Accept declaration-shaped constructors and nonescaping Parameter use."""
    if cls.decorator_list or cls.keywords or len(cls.bases) > 1:
        raise ValueError("class decorators, metaclass keywords and multiple inheritance are outside the static profile")
    for statement in cls.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Pass)):
            continue
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)) and all(isinstance(target, ast.Name) for target in _targets(statement)):
            try:
                ast.literal_eval(_value(statement))
                continue
            except (ValueError, TypeError):
                pass
        raise ValueError("class body permits only methods, docstrings and literal named constants")
    bindings = _bindings(cls)
    if _IDENTITY_MEMBERS.intersection(bindings):
        raise ValueError("identity/storage special class bindings are unsupported regardless of value")
    initializers = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "__init__"]
    if bindings.get("__init__", []) != initializers or len(initializers) > 1:
        raise ValueError("effective __init__ must be one direct, unreplaced method definition")
    if any(name in bindings for name in ("__new__", "__init_subclass__", "__mro_entries__")):
        raise ValueError("dynamic instance or subclass construction is outside the static profile")
    parents = _parent_map(cls)
    for method in (node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
        static = (len(method.decorator_list) == 1 and _path(method.decorator_list[0]) == "staticmethod"
                  and "staticmethod" not in _bindings(module) and "staticmethod" not in bindings)
        positional = [*method.args.posonlyargs, *method.args.args]
        if (isinstance(method, ast.AsyncFunctionDef) or (method.decorator_list and not static)
                or (not static and (not positional or positional[0].arg != "self"))):
            raise ValueError("methods need an explicit self receiver or unshadowed staticmethod")
        if method.name == "__init__":
            if static or any(not isinstance(node, (ast.Assign, ast.AnnAssign, ast.Expr, ast.Pass)) for node in method.body):
                raise ValueError("initializer must be straight-line assignment/call statements; control transfer is unsupported")
        for node in ast.walk(method):
            _reflection_use(node, module, parents, wanted)
            if ((isinstance(node, ast.Name) and node.id == "self" and isinstance(node.ctx, (ast.Store, ast.Del)))
                    or (isinstance(node, ast.ExceptHandler) and node.name == "self")
                    or (isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name == "self")
                    or (isinstance(node, ast.MatchMapping) and node.rest == "self")):
                raise ValueError("rebinding or deleting the instance receiver is unsupported")
            if method.name == "__init__" and isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom, ast.Await)):
                raise ValueError("initializer control transfer is outside the supported grammar")
            if isinstance(node, ast.Name) and node.id == "self" and isinstance(node.ctx, ast.Load):
                parent = parents.get(node)
                if isinstance(parent, ast.Attribute) and parent.value is node:
                    if parent.attr in {"__dict__", "__class__"}:
                        raise ValueError("dynamic instance/class dictionary access is unsupported")
                elif not _receiver_argument(node, module, parents):
                    raise ValueError("instance receiver escapes the supported Parameter construction grammar")
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and _related(_path(node), wanted):
                parent = parents.get(node)
                if isinstance(parent, ast.Attribute) and parent.value is node:
                    continue  # Inspect the complete path at the outermost node.
                if (isinstance(parent, ast.Call) and parent.func is node
                        and _path(node) in {wanted, wanted + ".get", wanted + ".set"}):
                    continue
                raise ValueError("Parameter/prefix may only be invoked directly; aliases, containers and escaping members are unsupported")


def _selector_assignment(tree, surface, item, cache):
    """Find one unconditional initializer and reject visible path replacement.

    This is a deliberately bounded declaration proof, not execution of Python.
    Conditional construction, aliases, dynamic setattr and overwritten ancestors
    require a separately reviewed source adapter rather than optimistic inference.
    """
    wanted = "self." + item["parameter"]
    found = []
    initializers = []
    for entry in sorted(surface.classes):
        path, owner = entry.rsplit(":", 1)
        module = _module(tree, path, cache)
        classes = [node for node in module.body if isinstance(node, ast.ClassDef) and node.name == owner]
        if len(classes) != 1 or _bindings(module).get(owner) != classes:
            raise ValueError("selected class name must have one unconditional module definition")
        cls = classes[0]
        _symbol_lifetime(module, owner, class_symbol=True)
        _class_grammar(cls, module, wanted)
        for parameter_name in _parameter_names(module):
            _symbol_lifetime(module, parameter_name)
        module_bindings = _bindings(module)
        for base in cls.bases:
            base_path = _path(base)
            bindings = module_bindings.get(base_path.split(".")[0], []) if base_path else []
            if (not base_path or len(bindings) != 1 or bindings[0] not in module.body
                    or not isinstance(bindings[0], (ast.Import, ast.ImportFrom, ast.ClassDef))):
                raise ValueError("class ancestry binding is dynamic, shadowed or unsupported")
        if item["parameter"].split(".")[0] in _bindings(cls):
            raise ValueError("class-level selector/prefix override is unsupported")
        for child in cls.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.name == "__init__":
                    initializers.append((child, module))
                if child.name in {"__getattribute__", "__getattr__", "__setattr__"} or _related("self." + child.name, wanted):
                    raise ValueError("dynamic or overridden selector member is outside the static Parameter profile")
            elif any(_related("self." + (_path(target) or ""), wanted) for target in _targets(child)):
                raise ValueError("class-level selector/prefix replacement is not a Parameter initializer")
        parents = {child: node for node in ast.walk(cls) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(cls):
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)) and _related(_path(node), wanted):
                assignment = parents.get(node)
                function = parents.get(assignment)
                if (not isinstance(assignment, (ast.Assign, ast.AnnAssign)) or _path(node) != wanted
                        or len(_targets(assignment)) != 1 or not isinstance(function, ast.FunctionDef)
                        or function not in cls.body or function.name != "__init__" or function.decorator_list
                        or not function.args.args or function.args.args[0].arg != "self"):
                    raise ValueError("selector/prefix/member mutation or conditional construction is unsupported")
                found.append((path, assignment, function, module))
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and _related(_path(_value(node)), wanted):
                raise ValueError("aliasing the selected Parameter/prefix is outside the static profile")
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)):
                container = _path(node.value)
                if container and (_related(container, wanted) or _related(container.removesuffix(".__dict__"), wanted)):
                    raise ValueError("indexed selector/prefix/member mutation is unsupported")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"setattr", "delattr"}:
                owner_path = _path(node.args[0]) if node.args else None
                attr = node.args[1] if len(node.args) > 1 else None
                target = owner_path + "." + attr.value if owner_path and isinstance(attr, ast.Constant) and isinstance(attr.value, str) else owner_path
                if _related(target, wanted):
                    raise ValueError("dynamic selector/prefix/member mutation is unsupported")
    ref = parse_ref(item["source_ref"])
    if len(found) != 1 or found[0][0] != ref.path or not _contains(found[0][1], ref):
        raise ValueError("citation must identify the unique exact self selector assignment in the selected class ancestry")
    for function, module in initializers:
        if function is found[0][2]:
            continue
        # An overridden initializer must actually delegate. Finding a matching
        # assignment in an unused base initializer is not construction evidence.
        delegates = [node.value for node in function.body if isinstance(node, ast.Expr)
                     and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
                     and node.value.func.attr == "__init__" and isinstance(node.value.func.value, ast.Call)
                     and isinstance(node.value.func.value.func, ast.Name)
                     and node.value.func.value.func.id == "super"
                     and not node.value.func.value.args and not node.value.func.value.keywords]
        if (len(delegates) != 1 or "super" in _bound_names(function) or "super" in _bindings(module)
                or function.decorator_list):
            raise ValueError("other local initializers must unconditionally delegate via unshadowed super().__init__")
    return found[0][1:]


def _proof(tree, surface, item, cache):
    ref = parse_ref(item["source_ref"])
    assignment, function, module = _selector_assignment(tree, surface, item, cache)
    call = _value(assignment)
    names = _parameter_names(module)
    if "factory_ref" not in item:
        error = _check_call(call, names, item, _bound_names(function))
        if error:
            raise ValueError(error)
        return
    factory_ref = parse_ref(item["factory_ref"])
    if factory_ref.path != ref.path or not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
        raise ValueError("factory_ref supports only an explicit same-file function call")
    factories = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == call.func.id]
    if (len(factories) != 1 or not _contains(factories[0], factory_ref)
            or _bindings(module).get(call.func.id) != factories
            or call.func.id in _bound_names(function) or factories[0].decorator_list):
        raise ValueError("factory_ref must identify the called same-file function")
    factory = factories[0]
    _symbol_lifetime(module, factory.name)
    call = _factory_body(factory, module)
    error = _check_call(call, names, item, _bound_names(factory))
    if error:
        raise ValueError(error)


def check_qcodes_surface(ctx: Any, gate: Any, surface: Any) -> None:
    try:
        specs = parameter_specs(ctx.cls.parameter_bindings, ctx.cls.parameters)
    except Exception as exc:
        gate.error("QCODES_CONFIG", str(exc), "driver.py")
        return
    cache = {}
    approved: set[str] = set()
    for name, item in specs.items():
        try:
            _proof(ctx.tree, surface, item, cache)
        except (ValueError, SyntaxError, TypeError, AttributeError) as exc:
            gate.error("QCODES_PARAMETER_SOURCE", f"{name}: {exc}", name, item["source_ref"])
            continue
        approved.add(item["parameter"])
        for op in ("get", "set"):
            if item[op]:
                approved.add(item["parameter"] + "." + op)
        # Traversing a declared channel path is not an operation.
        parts = item["parameter"].split(".")
        approved.update(".".join(parts[:i]) for i in range(1, len(parts)))
    for log in ctx.logs:
        for path in sorted(log.found_paths):
            if "." in path and path not in approved:
                gate.error("QCODES_UNDECLARED_MEMBER", f"nested member {path!r} is not a source-proven Parameter operation", path)
