"""G7 checks for explicit Python source selectors, separate from legacy class lookup."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any

from .source_selector import SourceSelector, entry_shape
from .source_surface import explicit_surface, signature_shape


def check_explicit_source(ctx: Any, gate: Any, selector: SourceSelector, fake: Any,
                          fake_members: set[str], *, check_members: bool = True) -> None:
    entries = [item for item in (ctx.card or {}).get("entry_symbols", []) if isinstance(item, Mapping)]
    matching = [item for item in entries if item.get("symbol") == selector.value]
    if entries and not matching:
        gate.error("NOT_AN_ENTRY_SYMBOL", f"{selector.value} is not a confirmed card entry", "driver.py")
    if not entries and (ctx.card or {}).get("upstream"):
        gate.error("NOT_AN_ENTRY_SYMBOL", "an explicit source selector needs a confirmed card entry", "driver.py")
    for item in matching:
        if not entry_shape(item.get("symbol"), item.get("file"), item.get("line")):
            gate.error("ENTRY_SOURCE", "source selector, file and entry line disagree", "driver.py")
    surface = explicit_surface(ctx.tree, selector)
    for problem in surface.problems:
        gate.error("NATIVE_NOT_FOUND", problem, "driver.py")
    if not surface.found:
        from .hardware_stop import check_hardware_stop, declares_companion_stop

        if declares_companion_stop(getattr(ctx, "cls", None)):
            check_hardware_stop(ctx, gate, set())
        return
    for item in matching:
        if item.get("file") != surface.file or item.get("line") != surface.line:
            gate.error("ENTRY_SOURCE", f"the actual source entry is {surface.file}:{surface.line}", "driver.py")
    for path, count in surface.legacy.items():
        gate.warning("LEGACY_SOURCE", f"{path}: {count} Python 2 print statements were omitted while parsing; "
                     "upstream was not imported and hardware requires a separate port", path)
    if not check_members:
        return  # Serial/SCPI still check their transport payloads after this source-identity check.
    from .hardware_stop import check_hardware_stop

    # A user-authorized hardware stop (decision 4, 2026-11-05) may name members the package clone does not define.
    exempt = check_hardware_stop(ctx, gate, set(surface.names))
    used = set(fake_members)
    for log in ctx.logs:
        used.update(name for name in log.found if not name.startswith("__"))
        used.update(call.name for call in log.calls if call.name == "__call__" or not call.name.startswith("__"))
    for name in sorted(used - surface.names - exempt):
        gate.error("NOT_UPSTREAM", f"{name!r} is not a verified member of {selector.value}", name,
                   f"{surface.file}:{surface.line}")
    if selector.kind != "module":
        return
    if not inspect.isclass(fake):
        gate.error("FAKE_SIGNATURE", "an explicit module surface requires a concrete fake class for signature checks")
        return
    for klass in fake.__mro__:
        if klass is not object and any(name in vars(klass) for name in ("__getattr__", "__getattribute__", "__call__")):
            gate.error("FAKE_SIGNATURE", "a dynamic fake attribute catch-all cannot verify a module surface")
    for name in sorted(fake_members & surface.names):
        descriptor = next((vars(klass)[name] for klass in fake.__mro__ if name in vars(klass)), None)
        bound = not isinstance(descriptor, staticmethod)
        function = descriptor.__func__ if isinstance(descriptor, (staticmethod, classmethod)) else descriptor
        if not inspect.isfunction(function) or inspect.iscoroutinefunction(function):
            gate.error("FAKE_SIGNATURE", f"{name}: the fake member must be a synchronous function", name)
            continue
        if "__signature__" in vars(function):
            gate.error("FAKE_SIGNATURE", f"{name}: a fake cannot replace its callable signature metadata", name)
            continue
        signature = inspect.signature(function, follow_wrapped=False, eval_str=False)
        params = list(signature.parameters.values())
        if bound:
            if not params or params[0].kind not in (inspect.Parameter.POSITIONAL_ONLY,
                                                   inspect.Parameter.POSITIONAL_OR_KEYWORD):
                gate.error("FAKE_SIGNATURE", f"{name}: bound fake method has no self/cls parameter", name)
                continue
            signature = signature.replace(parameters=params[1:])
        if signature_shape(signature) != signature_shape(surface.signatures[name]):
            gate.error("FAKE_SIGNATURE", f"{name}: fake {signature} differs from the source callable signature", name)
    for log in ctx.logs:
        for call in log.calls:
            if call.name.startswith("__") or call.name not in surface.signatures:
                continue
            if call.kind in ("set", "del"):
                gate.error("NATIVE_MUTATION", f"{call.name}: mutation of a module function is unsupported", call.name)
            elif call.kind == "call":
                try:
                    surface.signatures[call.name].bind(*call.args, **call.kwargs)
                except TypeError as exc:
                    gate.error("CALL_SIGNATURE", f"{call.name}: recorded arguments do not bind: {exc}", call.name)
