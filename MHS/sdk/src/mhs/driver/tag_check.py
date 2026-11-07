"""Pinned-source and recorded-wire checks for tag-bridge drivers (gate G7).

Every declared point cites the clone lines that show its address in its role.
In Python source (parsed with ``ast``; comments, strings and other numbers do not
count): a Modbus register is the address argument of a Modbus read or write call
(the first positional argument, or an address keyword, of a Modbus-shaped call
such as ``read_holding_registers``, ``write_register``, ``read_coils``,
``read_bit`` or ``write_float``) or the value of a register constant or map
entry; where the call shows its table and direction (its name or
an explicit ``functioncode``) they must agree with the point. An EPICS PV suffix
is an assignment target or a string literal, an Alpaca member a class, function
or string literal, and the Alpaca device type a string literal at
``device_type_ref``. A cited file that is not parseable Python is checked as text
and the gate says so in a warning, as it does when a register constant shows no
table or direction. Every request the fake transport received while G6 and G8 ran
must equal a declared point request with an access that allows the operation,
carry a finite ``timeout_s`` and, for a write, a wire value the point's codec
accepts. This proves where the addresses occur in the pinned source and that
nothing undeclared reached the transport. It does not prove a deployment's
address map, the device's register semantics or a physical stop; a reviewer
still reads every cited line. No upstream code is imported or executed.
"""
from __future__ import annotations

import ast
import json
import math
import re
from typing import Any, Mapping

from .tag_config import decode, encode
from .upstream import parse_ref, safe_relpath

_INTEGER = re.compile(r"(?<![\w.])(0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|[0-9][0-9_]*)(?![\w.])")
_WIRE = ("read_point", "write_point", "invoke_point")
#: names of calls that address Modbus data (pymodbus, minimalmodbus, pyModbusTCP, umodbus) and the keywords that
#: carry the address; ``set_input_current(1000)`` or ``register_callback(5)`` are not Modbus calls
_MODBUS_CALL = re.compile(r"(?:read|write|get|set|mask_write|readwrite|read_write)\w*registers?|\w*registers?"
                          r"|\w*(?:coils?|discrete\w*|holding\w*)|(?:read|write)_(?:bits?|long|float|string)")
_ADDRESS_KEYWORDS = frozenset({"registeraddress", "address", "register", "reg", "addr", "regaddr", "reg_addr",
                               "bit_addr", "starting_address", "start_address", "start", "registernumber"})
#: Modbus function codes and the (table, direction) they address
_FUNCTION_CODES = {1: ("coil", "read"), 2: ("discrete", "read"), 3: ("holding", "read"), 4: ("input", "read"),
                   5: ("coil", "write"), 6: ("holding", "write"), 15: ("coil", "write"), 16: ("holding", "write")}


def _cited(tree: Any, gate: Any, ref: Any, label: str) -> tuple[str, Any] | None:
    """``(document, parsed ref)`` of a citation that exists at the pinned commit (else a finding and ``None``)."""
    parsed = parse_ref(ref)
    if parsed is None or safe_relpath(parsed.path) != parsed.path:
        gate.error("TAG_REF_FORMAT", f"{label} needs a relative path:LINE source citation", label, str(ref))
        return None
    document = tree.read_text(parsed.path)
    if document is None:
        gate.error("TAG_REF_MISSING", f"{label}: {parsed.path} is missing or is not readable text in the pinned "
                   "source tree", label, str(ref))
        return None
    lines = document.splitlines()
    if parsed.end > len(lines):
        gate.error("TAG_REF_LINE", f"{label}: cited line {parsed.end} exceeds the {len(lines)} lines of "
                   f"{parsed.path}", label, str(ref))
        return None
    return document, parsed


def _span(document: str, line: int, end: int) -> str:
    return "\n".join(document.splitlines()[line - 1:end])


def _module(document: str, path: str) -> ast.Module | None:
    if not path.endswith((".py", ".pyw", ".pyi")):
        return None
    try:
        return ast.parse(document)
    except (SyntaxError, ValueError):
        return None


def _within(node: Any, line: int, end: int) -> bool:
    lineno = getattr(node, "lineno", None)
    return isinstance(lineno, int) and line <= lineno <= end


def _int_value(node: Any) -> int | None:
    return node.value if isinstance(node, ast.Constant) and type(node.value) is int else None


def _call_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return func.id if isinstance(func, ast.Name) else ""


def modbus_role(call: ast.Call) -> tuple[str | None, str | None]:
    """``(table, direction)`` a Modbus call shows; ``None`` where its name and arguments do not decide it."""
    for keyword in call.keywords:
        if keyword.arg == "functioncode" and _int_value(keyword.value) in _FUNCTION_CODES:
            return _FUNCTION_CODES[_int_value(keyword.value)]
    name = _call_name(call).lower()
    direction = "read" if name.startswith(("read", "get")) else "write" if name.startswith(("write", "set")) else None
    if "input_register" in name or "inputregister" in name:
        return "input", direction or "read"
    if "discrete" in name:
        return "discrete", direction or "read"
    if "holding" in name:
        return "holding", direction
    if "coil" in name:
        return "coil", direction
    if direction == "write" and ("register" in name or name in ("write_long", "write_float", "write_string")):
        return "holding", "write"          # only holding registers are writable registers in Modbus
    if direction == "write" and "bit" in name:
        return "coil", "write"             # only coils are writable bits in Modbus
    return None, direction


def modbus_proofs(module: ast.Module, line: int, end: int, register: int) -> tuple[list[tuple], int]:
    """Calls ``[(table, direction)]`` whose address argument on a cited line is ``register``, and the number of
    register constants or map entries on the cited lines that hold it."""
    calls: list[tuple] = []
    constants = 0
    for node in ast.walk(module):
        if isinstance(node, ast.Call):
            if _MODBUS_CALL.fullmatch(_call_name(node).lower()) is None:
                continue
            address = node.args[0] if node.args else next(
                (keyword.value for keyword in node.keywords if keyword.arg in _ADDRESS_KEYWORDS), None)
            if address is not None and _int_value(address) == register and _within(address, line, end):
                calls.append(modbus_role(node))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            if _int_value(node.value) == register and _within(node.value, line, end):
                constants += 1
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                for item in (key, value):
                    if item is not None and _int_value(item) == register and _within(item, line, end):
                        constants += 1
    return calls, constants


def _names(module: ast.Module, line: int, end: int) -> set[str]:
    """Assignment targets, class and function names and string literals on the cited lines (no comments)."""
    out: set[str] = set()
    for node in ast.walk(module):
        if not _within(node, line, end):
            continue
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            out.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            out.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            out.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
    return out


def address_findings(point: Mapping[str, Any], document: str, path: str, line: int,
                     end: int) -> tuple[list[tuple[str, str]], list[str]]:
    """``([(code, message)], [warning])`` of one point's address proof on the cited lines of ``document``.

    Codes: ``TAG_ADDRESS_NOT_UPSTREAM`` (the address is not shown in its role), ``TAG_TABLE_NOT_UPSTREAM`` and
    ``TAG_ACCESS_NOT_UPSTREAM`` (the cited call addresses another Modbus table or only the other direction).
    """
    request = point["request"]
    module = _module(document, path)
    text = _span(document, line, end)
    if request["profile"] == "modbus":
        register = request["register"]
        if module is None:
            if register in integer_literals(text):
                return [], [f"register {register} occurs on the cited lines of {path}, which is not parseable Python: "
                            "its role (address, function code, scale, comment) is not checked; read the line"]
            return [("TAG_ADDRESS_NOT_UPSTREAM", f"the cited lines do not show register {register}")], []
        calls, constants = modbus_proofs(module, line, end, register)
        if not calls and not constants:
            return [("TAG_ADDRESS_NOT_UPSTREAM",
                     f"the cited lines do not show register {register} as the address argument of a Modbus read or "
                     "write call or as a register constant (function codes, counts, scale factors and comments are "
                     "not addresses)")], []
        if not calls:
            return [], [f"register {register} is shown only as a constant; its table and direction are not shown on "
                        "the cited lines: cite the call that reads or writes it, or read the line"]
        errors: list[tuple[str, str]] = []
        warnings: list[str] = []
        tables = {table for table, _direction in calls if table}
        if tables and request["table"] not in tables:
            errors.append(("TAG_TABLE_NOT_UPSTREAM",
                           f"register {register} is declared in the {request['table']} table, but the cited call "
                           f"addresses the {'/'.join(sorted(tables))} table"))
        elif not tables:
            warnings.append(f"the cited call of register {register} does not show its table (no function code or "
                            "table name); read the line")
        shown = {direction for _table, direction in calls if direction}
        wanted = {"read": {"read"}, "write": {"write"}, "read-write": {"read", "write"}}[point["access"]]
        missing = wanted - shown
        if missing and all(direction for _table, direction in calls):
            errors.append(("TAG_ACCESS_NOT_UPSTREAM",
                           f"register {register} is declared {point['access']}, but the cited calls only "
                           f"{'/'.join(sorted(shown))} it"))
        elif missing:
            warnings.append(f"the cited calls of register {register} do not show whether they "
                            f"{'/'.join(sorted(missing))} it; read the line")
        return errors, warnings
    token = request["pv"] if request["profile"] == "epics-ca" else request["member"]
    if module is None:
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", text) is not None:
            return [], [f"{token!r} occurs on the cited lines of {path}, which is not parseable Python: its role is "
                        "not checked; read the line"]
        return [("TAG_ADDRESS_NOT_UPSTREAM", f"the cited source does not show {token!r}")], []
    if token in _names(module, line, end):
        return [], []
    what = ("an assignment target or string literal" if request["profile"] == "epics-ca"
            else "a class, function or string literal")
    return [("TAG_ADDRESS_NOT_UPSTREAM",
             f"the cited lines do not show {token!r} as {what} (comments and other words do not count)")], []


def integer_literals(text: str) -> set[int]:
    """Integer literals written in ``text`` (decimal, hex, binary, octal; underscores allowed)."""
    out: set[int] = set()
    for match in _INTEGER.finditer(text):
        token = match.group(1).replace("_", "")
        try:
            out.add(int(token, 0) if token[:2].lower() in ("0x", "0b", "0o") else int(token, 10))
        except ValueError:
            continue
    return out


def wire_value_ok(point: Mapping[str, Any], raw: Any) -> bool:
    """True when ``raw`` is a value the point's codec produces for some engineering value."""
    try:
        if point["request"]["profile"] == "modbus":
            if point["request"]["table"] == "coil":
                return type(raw) is bool
            decode(point, raw)
            return True
        return encode(point, raw) == raw and type(encode(point, raw)) is type(raw)
    except (ValueError, KeyError, TypeError):
        return False


def _native(ctx: Any, gate: Any) -> None:
    """The provenance symbol: an entry symbol of the card that exists in the clone (as G7 checks other families)."""
    from . import upstream as _upstream

    symbol = getattr(ctx.cls, "native", None)
    if isinstance(symbol, str) and symbol.startswith("pyfile:"):
        return  # checked by the explicit source selector gate
    if not isinstance(symbol, str) or ":" not in symbol:
        gate.error("NO_NATIVE", "native must name the upstream class or module that shows the point map "
                   "('package.module:Class'); it is parsed, never imported", "driver.py")
        return
    symbols = [item for item in (ctx.card or {}).get("entry_symbols") or [] if isinstance(item, Mapping)]
    if symbols and not any(item.get("symbol") == symbol for item in symbols):
        text = f"native {symbol} is not one of the card's entry_symbols {[item.get('symbol') for item in symbols][:5]}"
        if any(item.get("confidence") in ("ast", "override") for item in symbols):
            gate.error("NOT_AN_ENTRY_SYMBOL", text, "driver.py")
        else:
            gate.warning("NOT_AN_ENTRY_SYMBOL", text, "driver.py")
    hint = next((item.get("file") for item in symbols if item.get("symbol") == symbol), None)
    surface = _upstream.class_surface(ctx.tree, symbol, hint_file=hint if isinstance(hint, str) else None)
    for problem in surface.problems:
        gate.error("NATIVE_NOT_FOUND", problem, "driver.py")


def check_tag_surface(ctx: Any, gate: Any) -> None:
    from .tag_driver import TagDriver

    try:
        config = TagDriver.bridge_config.__func__(ctx.cls)
    except Exception as exc:  # noqa: BLE001 - G3 reports the definition; G7 cannot check an invalid one
        gate.error("TAG_DECLARATION_INVALID", f"the tag declaration does not compile: {str(exc)[:300]}", "driver.py")
        return
    _native(ctx, gate)
    points = config["points"]
    for name, point in sorted(points.items()):
        label = f"tag_config.points[{name!r}]"
        cited = _cited(ctx.tree, gate, point["source_ref"], label + ".source_ref")
        if cited is None:
            continue
        document, ref = cited
        errors, warnings = address_findings(point, document, ref.path, ref.line, ref.end)
        for code, message in errors:
            gate.error(code, f"{label}: {message}", label, point["source_ref"])
        for message in warnings:
            gate.warning("TAG_ADDRESS_UNDECIDED", f"{label}: {message}", label, point["source_ref"])
    if config["profile"] == "alpaca":
        cited = _cited(ctx.tree, gate, config["device_type_ref"], "tag_config.device_type_ref")
        if cited is not None:
            document, ref = cited
            module = _module(document, ref.path)
            shown = (config["device_type"] in _names(module, ref.line, ref.end) if module is not None else
                     re.search(rf"['\"]{re.escape(config['device_type'])}['\"]",
                               _span(document, ref.line, ref.end)) is not None)
            if not shown:
                gate.error("TAG_ADDRESS_NOT_UPSTREAM", f"tag_config.device_type_ref does not show the device type "
                           f"{config['device_type']!r} as a string literal", "tag_config.device_type_ref",
                           config["device_type_ref"])
    declared = {json.dumps(point["request"], sort_keys=True): point for point in points.values()}
    allowed = {"read_point": ("read", "read-write"), "write_point": ("write", "read-write"),
               "invoke_point": ("invoke",)}
    seen = 0
    for log in ctx.logs:
        for call in log.calls:
            if call.kind != "call" or call.name not in _WIRE:
                continue
            seen += 1
            request = call.args[0] if call.args else call.kwargs.get("request")
            point = None
            if isinstance(request, Mapping):
                try:
                    point = declared.get(json.dumps(dict(request), sort_keys=True))
                except (TypeError, ValueError):
                    point = None
            if point is None:
                gate.error("TAG_WIRE_UNDECLARED", f"recorded {call.name} request {str(request)[:160]} is not a "
                           "declared point address", call.name)
                continue
            if point["access"] not in allowed[call.name]:
                gate.error("TAG_WIRE_ACCESS", f"recorded {call.name} of point {point['name']!r} whose access is "
                           f"{point['access']}", call.name)
            timeout = call.kwargs.get("timeout_s")
            if (isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout)
                    or not 0 < timeout <= 10):
                gate.error("TAG_WIRE_TIMEOUT", f"recorded {call.name} of {point['name']!r} without a finite "
                           "timeout_s in (0, 10] s", call.name)
            if call.name == "write_point":
                raw = call.args[1] if len(call.args) > 1 else call.kwargs.get("raw")
                if not wire_value_ok(point, raw):
                    gate.error("TAG_WIRE_VALUE", f"recorded write of {point['name']!r} carries {raw!r}, which its "
                               "codec does not produce", call.name)
            if call.name == "invoke_point":
                args = call.args[1] if len(call.args) > 1 else call.kwargs.get("args")
                if not isinstance(args, Mapping) or set(args) != set(point["params"]):
                    gate.error("TAG_WIRE_VALUE", f"recorded invoke of {point['name']!r} with form fields "
                               f"{sorted(args) if isinstance(args, Mapping) else args!r}", call.name)
    if not seen:
        gate.warning("TAG_NO_TRAFFIC", "no tag transport request was recorded: only the cited declarations were "
                     "checked, not wire traffic (G6 must exercise the fake transport)")
