"""Finite tag/register/PV declarations for :class:`mhs.driver.TagDriver` (no I/O, no imports, no discovery).

``compile_tags`` turns the class attributes of a config-only tag driver into
one detached, JSON-only configuration: named points with a protocol address,
a typed codec and the source line that shows the address; read and write maps
of the resource state; commands (fixed or input-bound writes, Alpaca method
calls, observation reads) with confirmation predicates; and the stop. The
codecs below are the only place engineering values become wire values. A value
the codec cannot represent exactly is refused, never rounded or clamped.

Profiles: ``modbus`` (holding/input registers, coils, discrete inputs),
``epics-ca`` (Channel Access PV suffixes; the deployment prefix belongs to the
native transport) and ``alpaca`` (ASCOM Alpaca device properties and methods).
OPC UA, Tango, ADS and S7 are deliberately not profiles of this version.
"""
from __future__ import annotations

import copy
import decimal
import json
import math
import re
import struct

from .spec import DriverDefinitionError
from .upstream import parse_ref, safe_relpath

PROFILES = frozenset({"modbus", "epics-ca", "alpaca"})
#: Protocol families a caller might name that this helper refuses explicitly (no untested profile).
UNSUPPORTED_PROFILES = frozenset({"opcua", "opc-ua", "tango", "ads", "s7", "snap7", "bacnet", "mqtt"})
MAX_POINTS = 64
MAX_COMMANDS = 32
MAX_STEPS = 8
MAX_CONFIRM = 8
MAX_STRING = 256
EPICS_MAX_STRING = 40
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
_PV = re.compile(r"[A-Za-z0-9_:.\-{}\[\]]{1,60}\Z")
_MEMBER = re.compile(r"[a-z][a-z0-9]{0,63}\Z")
_FORM = re.compile(r"[A-Z][A-Za-z0-9]{0,63}\Z")
_DEVICE_TYPE = re.compile(r"[a-z][a-z0-9]{0,31}\Z")

_MODBUS_TABLES = {"holding": "register", "input": "register", "coil": "bit", "discrete": "bit"}
_MODBUS_TYPES = {"uint16": 1, "int16": 1, "bool": 1, "uint32": 2, "int32": 2, "float32": 2}
_EPICS_TYPES = frozenset({"integer", "number", "string"})
_ALPACA_TYPES = frozenset({"integer", "number", "boolean", "string"})
_ACCESS = frozenset({"read", "write", "read-write"})
#: Point types whose values can be compared exactly in a confirmation predicate.
_EXACT = frozenset({"uint16", "int16", "bool", "uint32", "int32", "integer", "boolean", "string"})


def fail(message):
    raise DriverDefinitionError("tag-bridge: " + message)


def plain(value, *, depth=0, _budget=None):
    """Accept only concrete JSON values (no subclasses, hooks, cycles or non-finite numbers)."""
    if _budget is None:
        _budget = [20000]
    _budget[0] -= 1
    if depth > 12 or _budget[0] < 0:
        fail("declaration nesting or size exceeds the finite bound")
    if value is None or type(value) in (bool, int, str):
        if type(value) is str and len(value) > 4096:
            fail("declaration string exceeds 4096 characters")
        return
    if type(value) is float:
        if not math.isfinite(value):
            fail("declaration contains a non-finite number")
        return
    if type(value) is dict:
        if len(value) > 256 or any(type(key) is not str or len(key) > 128 for key in value):
            fail("declaration object has too many or non-string keys")
        for item in value.values():
            plain(item, depth=depth + 1, _budget=_budget)
        return
    if type(value) is list:
        if len(value) > 256:
            fail("declaration array exceeds 256 entries")
        for item in value:
            plain(item, depth=depth + 1, _budget=_budget)
        return
    fail("only concrete JSON values are supported, got " + type(value).__name__)


def detached(value):
    plain(value)
    return json.loads(json.dumps(value, allow_nan=False, sort_keys=True))


def _keys(value, allowed, required, label):
    if type(value) is not dict or set(value) - set(allowed) or set(required) - set(value):
        fail(f"{label} has missing or unknown keys (allowed: {sorted(allowed)})")
    return value


def _integer(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        fail(f"{label} must be an integer in {low}..{high}")
    return value


def _reference(value, label):
    ref = parse_ref(value)
    if ref is None or safe_relpath(ref.path) != ref.path or ref.end - ref.line > 60:
        fail(f"{label} must cite a relative path:LINE or a bounded path:FIRST-LAST (at most 60 lines)")
    return value


# ---------------------------------------------------------------------------
# codecs
# ---------------------------------------------------------------------------

def _decimals_value(raw, decimals):
    return raw if decimals == 0 else raw / (10 ** decimals)


def _finite_number(value, label):
    """``value`` if it is a finite int or float (never bool); no float conversion of an int (huge ints stay exact)."""
    if type(value) is int:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError(f"{label} needs a finite number")


def _decimals_raw(value, decimals, label):
    """The register integer for ``value`` at ``decimals``; exact or refused, never rounded.

    A float counts by its shortest decimal representation (``repr``), the value a JSON request carries: 3.3 at two
    decimals is 330; 3.30000001, 3.3000000001 and 0.1 + 0.2 (0.30000000000000004) are refused.
    """
    value = _finite_number(value, label)
    if type(value) is int:
        return value * 10 ** decimals            # exact integer arithmetic; the range check follows
    scaled = decimal.Decimal(repr(value)).scaleb(decimals)   # at most 17 + 6 digits: exact at 28-digit precision
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{label} = {value!r:.40} is not a multiple of the register resolution 1e-{decimals}"
                         if decimals else f"{label} = {value!r:.40} is not an integer register value")
    return int(scaled)


def encode(point, value):
    """The wire value of an engineering ``value`` for ``point`` (``ValueError`` when not exactly representable)."""
    try:
        return _encode(point, value)
    except (OverflowError, decimal.InvalidOperation) as exc:
        raise ValueError(f"{point['name']} = {value!r:.40} is outside the representable range") from exc


def _encode(point, value):
    label = point["name"]
    kind = point["type"]
    profile = point["request"]["profile"]
    if profile == "modbus":
        table = point["request"]["table"]
        if _MODBUS_TABLES[table] == "bit":
            if type(value) is not bool:
                raise ValueError(f"{label} needs a boolean")
            return value
        if kind == "bool":
            if type(value) is not bool:
                raise ValueError(f"{label} needs a boolean")
            return [1 if value else 0]
        if kind == "float32":
            value = _finite_number(value, label)
            packed = struct.pack(">f", float(value))
            if struct.unpack(">f", packed)[0] != float(value):
                raise ValueError(f"{label} = {value!r:.40} is not exactly representable as float32")
            words = [int.from_bytes(packed[:2], "big"), int.from_bytes(packed[2:], "big")]
            return words if point["word_order"] == "big" else words[::-1]
        raw = _decimals_raw(value, point["decimals"], label)
        bits = 16 * point["request"]["words"]
        low, high = (0, 2 ** bits - 1) if kind.startswith("uint") else (-(2 ** (bits - 1)), 2 ** (bits - 1) - 1)
        if not low <= raw <= high:
            raise ValueError(f"{label} = {value!r:.40} is outside the {kind} register range")
        unsigned = raw % (2 ** bits)
        if bits == 16:
            return [unsigned]
        words = [unsigned >> 16, unsigned & 0xFFFF]
        return words if point["word_order"] == "big" else words[::-1]
    if kind in ("integer",):
        if type(value) is not int:
            raise ValueError(f"{label} needs an integer")
        if not -(2 ** 31) <= value <= 2 ** 31 - 1:
            raise ValueError(f"{label} = {value!r:.40} is outside the 32-bit integer range")
        return value
    if kind == "number":
        number = float(_finite_number(value, label))
        if not math.isfinite(number):
            raise ValueError(f"{label} = {value!r:.40} is outside the floating-point range")
        return number
    if kind == "boolean":
        if type(value) is not bool:
            raise ValueError(f"{label} needs a boolean")
        return value
    if kind == "string":
        limit = EPICS_MAX_STRING if profile == "epics-ca" else MAX_STRING
        if type(value) is not str or len(value.encode("utf-8")) > limit or not value.isprintable():
            raise ValueError(f"{label} needs a printable string of at most {limit} bytes")
        if profile == "epics-ca" and not value.isascii():
            raise ValueError(f"{label} needs an ASCII string")
        return value
    raise ValueError(f"{label}: unsupported point type {kind!r}")  # pragma: no cover - compiler refuses


def decode(point, raw):
    """The engineering value of a validated wire value (``ValueError`` for anything malformed)."""
    try:
        return _decode(point, raw)
    except (OverflowError, decimal.InvalidOperation) as exc:
        raise ValueError(f"{point['name']}: the wire value is outside the representable range") from exc


def _decode(point, raw):
    label = point["name"]
    kind = point["type"]
    request = point["request"]
    profile = request["profile"]
    if profile == "modbus":
        if type(raw) is not list or len(raw) != request["words"]:
            raise ValueError(f"{label}: expected a list of {request['words']} value(s)")
        if _MODBUS_TABLES[request["table"]] == "bit":
            if type(raw[0]) is not bool:
                raise ValueError(f"{label}: a bit read needs a boolean")
            return raw[0]
        if any(type(word) is not int or not 0 <= word <= 0xFFFF for word in raw):
            raise ValueError(f"{label}: register words must be integers in 0..65535")
        if kind == "bool":
            if raw[0] not in (0, 1):
                raise ValueError(f"{label}: register value {raw[0]} is neither 0 nor 1")
            return raw[0] == 1
        words = raw if point["word_order"] == "big" else raw[::-1]
        if kind == "float32":
            value = struct.unpack(">f", words[0].to_bytes(2, "big") + words[1].to_bytes(2, "big"))[0]
            if not math.isfinite(value):
                raise ValueError(f"{label}: float32 register value is not finite")
            return value
        unsigned = words[0] if len(words) == 1 else (words[0] << 16) | words[1]
        bits = 16 * len(words)
        signed = unsigned - 2 ** bits if kind.startswith("int") and unsigned >= 2 ** (bits - 1) else unsigned
        return _decimals_value(signed, point["decimals"])
    if profile == "alpaca":
        raw = alpaca_value(raw, label)
    if kind == "integer":
        if type(raw) is not int or not -(2 ** 31) <= raw <= 2 ** 31 - 1:
            raise ValueError(f"{label}: expected a 32-bit integer")
        return raw
    if kind == "number":
        if type(raw) is bool or type(raw) not in (int, float) or not math.isfinite(float(raw)):
            raise ValueError(f"{label}: expected a finite number")
        return float(raw)
    if kind == "boolean":
        if type(raw) is not bool:
            raise ValueError(f"{label}: expected a boolean")
        return raw
    if kind == "string":
        limit = EPICS_MAX_STRING if profile == "epics-ca" else MAX_STRING
        if type(raw) is not str or len(raw.encode("utf-8")) > limit:
            raise ValueError(f"{label}: expected a string of at most {limit} bytes")
        return raw
    raise ValueError(f"{label}: unsupported point type {kind!r}")  # pragma: no cover


def alpaca_error(response, label):
    """``(error_number, message)`` of an Alpaca response object (``ValueError`` when malformed)."""
    if type(response) is not dict or "ErrorNumber" not in response:
        raise ValueError(f"{label}: an Alpaca response must be an object with ErrorNumber")
    number = response["ErrorNumber"]
    if type(number) is not int or not 0 <= number <= 0xFFFF:
        raise ValueError(f"{label}: Alpaca ErrorNumber must be an integer in 0..65535")
    message = response.get("ErrorMessage", "")
    if type(message) is not str:
        raise ValueError(f"{label}: Alpaca ErrorMessage must be a string")
    return number, message[:200]


def alpaca_value(response, label):
    number, message = alpaca_error(response, label)
    if number != 0:
        raise ValueError(f"{label}: Alpaca error 0x{number:X}: {message}")
    if "Value" not in response:
        raise ValueError(f"{label}: Alpaca property response has no Value")
    return response["Value"]


def compare_key(point, value):
    """A value usable for exact comparison (the wire value for registers, the value itself otherwise)."""
    return json.dumps(encode(point, value), sort_keys=True)


# ---------------------------------------------------------------------------
# points
# ---------------------------------------------------------------------------

def _point(name, raw, profile, options):
    label = f"points[{name!r}]"
    common = {"access", "type", "source_ref", "description"}
    if profile == "modbus":
        spec = _keys(raw, common | {"table", "register", "words", "word_order", "decimals"},
                     {"access", "type", "source_ref", "table", "register"}, label)
        table = spec["table"]
        if table not in _MODBUS_TABLES:
            fail(f"{label}.table must be one of {sorted(_MODBUS_TABLES)}")
        register = _integer(spec["register"], f"{label}.register", 0, 0xFFFF)
        kind = spec["type"]
        if _MODBUS_TABLES[table] == "bit":
            if kind != "bool" or "words" in spec or "word_order" in spec or "decimals" in spec:
                fail(f"{label}: coils and discrete inputs are single bits of type 'bool' without words or decimals")
            words = 1
        else:
            if kind not in _MODBUS_TYPES:
                fail(f"{label}.type must be one of {sorted(_MODBUS_TYPES)}")
            words = spec.get("words", _MODBUS_TYPES[kind])
            if words != _MODBUS_TYPES[kind]:
                fail(f"{label}.words must be {_MODBUS_TYPES[kind]} for type {kind}")
        if register + words - 1 > 0xFFFF:
            fail(f"{label} extends beyond register 65535")
        word_order = spec.get("word_order")
        if words == 2:
            if word_order not in ("big", "little"):
                fail(f"{label}: a two-word value needs word_order 'big' (high word first) or 'little'")
        elif word_order is not None:
            fail(f"{label}: word_order applies to two-word values only")
        decimals = spec.get("decimals", 0)
        if kind in ("bool", "float32") and "decimals" in spec:
            fail(f"{label}: decimals apply to integer register types only")
        _integer(decimals, f"{label}.decimals", 0, 6)
        writable = spec["access"] in ("write", "read-write")
        if writable and table in ("input", "discrete"):
            fail(f"{label}: {table} tables are read-only in Modbus")
        if writable and words != 1:
            fail(f"{label}: multi-word writes are not supported (no source shows a function 16 write)")
        request = {"profile": "modbus", "table": table, "register": register, "words": words}
        point = {"word_order": word_order or "big", "decimals": decimals}
    elif profile == "epics-ca":
        spec = _keys(raw, common | {"pv"}, {"access", "type", "source_ref", "pv"}, label)
        if type(spec["pv"]) is not str or not _PV.fullmatch(spec["pv"]):
            fail(f"{label}.pv must be a PV name suffix of 1..60 characters (letters, digits, _ : . - {{ }} [ ])")
        if spec["type"] not in _EPICS_TYPES:
            fail(f"{label}.type must be one of {sorted(_EPICS_TYPES)}")
        kind = spec["type"]
        request = {"profile": "epics-ca", "pv": spec["pv"]}
        point = {}
    else:
        spec = _keys(raw, common | {"member", "method", "params", "field"}, {"source_ref", "member"}, label)
        member = spec["member"]
        if type(member) is not str or not _MEMBER.fullmatch(member):
            fail(f"{label}.member must be a lower-case Alpaca member name")
        request = {"profile": "alpaca", "device_type": options["device_type"],
                   "device_number": options["device_number"], "member": member}
        if spec.get("method", False) is True:
            if set(spec) & {"access", "type", "field"}:
                fail(f"{label}: a method point has params, not access, type or field")
            params = spec.get("params", {})
            if type(params) is not dict or len(params) > 8:
                fail(f"{label}.params must map at most 8 form fields to types")
            for form, kind in params.items():
                if not _FORM.fullmatch(form) or kind not in _ALPACA_TYPES:
                    fail(f"{label}.params[{form!r}] needs a capitalised form field and an Alpaca type")
            request["method"] = True
            _reference(spec["source_ref"], f"{label}.source_ref")
            return {"name": name, "request": request, "params": dict(params), "access": "invoke",
                    "type": "method", "source_ref": spec["source_ref"], "description": spec.get("description", "")}
        if spec.get("method", False) is not False or "params" in spec:
            fail(f"{label}: method must be true (with params) or absent")
        _keys(spec, set(spec), {"access", "type"}, label)
        if spec["type"] not in _ALPACA_TYPES:
            fail(f"{label}.type must be one of {sorted(_ALPACA_TYPES)}")
        kind = spec["type"]
        if spec["access"] in ("write", "read-write"):
            if type(spec.get("field")) is not str or not _FORM.fullmatch(spec["field"]):
                fail(f"{label}: a writable Alpaca property needs its capitalised PUT form field")
            request["field"] = spec["field"]
        elif "field" in spec:
            fail(f"{label}: field applies to writable properties only")
        point = {}
    if spec["access"] not in _ACCESS:
        fail(f"{label}.access must be one of {sorted(_ACCESS)}")
    _reference(spec["source_ref"], f"{label}.source_ref")
    description = spec.get("description", "")
    if type(description) is not str or len(description) > 200:
        fail(f"{label}.description must be a string of at most 200 characters")
    point.update({"name": name, "request": request, "type": kind, "access": spec["access"],
                  "source_ref": spec["source_ref"], "description": description})
    return point


def _readable(points, name, label):
    point = points.get(name) if type(name) is str else None
    if point is None or point["access"] not in ("read", "read-write"):
        fail(f"{label} must name a declared readable point")
    return point


def _writable(points, name, label):
    point = points.get(name) if type(name) is str else None
    if point is None or point["access"] not in ("write", "read-write"):
        fail(f"{label} must name a declared writable point")
    return point


def _value(point, value, label):
    try:
        encode(point, value)
    except ValueError as exc:
        fail(f"{label}: {exc}")
    return value


def _steps(raw, points, label, *, fixed):
    if type(raw) is not list or not 1 <= len(raw) <= MAX_STEPS:
        fail(f"{label} needs 1..{MAX_STEPS} steps")
    out = []
    for index, step in enumerate(raw):
        where = f"{label}[{index}]"
        if type(step) is dict and "write" in step:
            _keys(step, {"write", "value", "input"}, {"write"}, where)
            point = _writable(points, step["write"], where + ".write")
            if ("value" in step) == ("input" in step):
                fail(f"{where} needs exactly one of value or input")
            if "input" in step:
                if fixed:
                    fail(f"{where}: a stop or safe-state step takes no caller input")
                if type(step["input"]) is not str or not _NAME.fullmatch(step["input"]):
                    fail(f"{where}.input must name an action input field")
                out.append({"write": point["name"], "input": step["input"]})
            else:
                out.append({"write": point["name"], "value": _value(point, step["value"], where)})
        elif type(step) is dict and "invoke" in step:
            _keys(step, {"invoke", "args"}, {"invoke"}, where)
            point = points.get(step["invoke"]) if type(step["invoke"]) is str else None
            if point is None or point["access"] != "invoke":
                fail(f"{where}.invoke must name a declared Alpaca method point")
            args = step.get("args", {})
            if type(args) is not dict or set(args) != set(point["params"]):
                fail(f"{where}.args must give every declared form field of {point['name']} exactly once")
            compiled = {}
            for form, source in args.items():
                if type(source) is not dict or len(source) != 1 or not set(source) <= {"value", "input"}:
                    fail(f"{where}.args[{form!r}] must be {{'value': v}} or {{'input': name}}")
                if "input" in source:
                    if fixed or type(source["input"]) is not str or not _NAME.fullmatch(source["input"]):
                        fail(f"{where}.args[{form!r}]: invalid or disallowed input binding")
                    compiled[form] = {"input": source["input"]}
                else:
                    shape = {"name": f"{point['name']}.{form}", "type": point["params"][form],
                             "request": {"profile": "alpaca"}}
                    compiled[form] = {"value": _value(shape, source["value"], f"{where}.args[{form!r}]")}
            out.append({"invoke": point["name"], "args": compiled})
        else:
            fail(f"{where} must be a write or invoke step")
    return out


def _predicates(raw, points, label, *, required):
    if raw is None:
        raw = []
    if type(raw) is not list or len(raw) > MAX_CONFIRM or (required and not raw):
        fail(f"{label} needs {'1' if required else '0'}..{MAX_CONFIRM} confirmation predicates")
    out = []
    for index, item in enumerate(raw):
        where = f"{label}[{index}]"
        _keys(item, {"point", "equals", "in"}, {"point"}, where)
        point = _readable(points, item["point"], where + ".point")
        if point["type"] not in _EXACT:
            # Register integers (with or without decimals) compare as exact wire words; floating-point
            # values (float32 registers, EPICS/Alpaca numbers) cannot confirm a state exactly.
            fail(f"{where}: confirmation needs an exactly comparable point (integer, boolean or string)")
        if ("equals" in item) == ("in" in item):
            fail(f"{where} needs exactly one of equals or in")
        values = [item["equals"]] if "equals" in item else item["in"]
        if type(values) is not list or not 1 <= len(values) <= 8:
            fail(f"{where}.in needs 1..8 values")
        out.append({"point": point["name"], "in": [_value(point, value, where) for value in values]})
    return out


def _result(raw, points, label):
    raw = {} if raw is None else raw
    if type(raw) is not dict or len(raw) > 16:
        fail(f"{label} must map at most 16 output fields")
    out = {}
    for field, source in raw.items():
        where = f"{label}[{field!r}]"
        if not _NAME.fullmatch(field) or type(source) is not dict or len(source) != 1:
            fail(f"{where} must be {{'point': name}}, {{'input': name}} or {{'value': v}}")
        if "point" in source:
            out[field] = {"point": _readable(points, source["point"], where + ".point")["name"]}
        elif "input" in source and type(source["input"]) is str and _NAME.fullmatch(source["input"]):
            out[field] = {"input": source["input"]}
        elif "value" in source:
            plain(source["value"])
            out[field] = {"value": source["value"]}
        else:
            fail(f"{where} must be {{'point': name}}, {{'input': name}} or {{'value': v}}")
    return out


def _command(capability_id, raw, points, label):
    if type(raw) is not dict:
        fail(f"{label} must be an object")
    if "read" in raw:
        _keys(raw, {"read"}, {"read"}, label)
        fields = raw["read"]
        if type(fields) is not dict or not 1 <= len(fields) <= 16:
            fail(f"{label}.read must map 1..16 output fields to readable points")
        out = {}
        for field, name in fields.items():
            if type(field) is not str or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}(\.[A-Za-z][A-Za-z0-9_]{0,63})?",
                                                         field):
                fail(f"{label}.read keys must be output field names (one optional 'values.' level)")
            out[field] = _readable(points, name, f"{label}.read[{field!r}]")["name"]
        return {"kind": "read", "read": out}
    _keys(raw, {"steps", "confirm", "result"}, {"steps"}, label)
    return {"kind": "effect", "steps": _steps(raw["steps"], points, label + ".steps", fixed=False),
            "confirm": _predicates(raw.get("confirm"), points, label + ".confirm", required=False),
            "result": _result(raw.get("result"), points, label + ".result")}


def compile_tags(raw, *, reads=None, writes=None, commands=None, safety_bindings=None):
    """Detached configuration of one tag device (``DriverDefinitionError`` for anything outside the grammar)."""
    plain(raw)
    for label, value in (("reads", reads), ("writes", writes), ("commands", commands),
                         ("safety_bindings", safety_bindings)):
        plain({} if value is None else value)
    _keys(raw, {"profile", "points", "timeout_ms", "confirm_ms", "poll_ms", "device_type", "device_type_ref",
                "device_number"}, {"profile", "points"}, "tag_config")
    profile = raw["profile"]
    if type(profile) is not str or profile.lower() in UNSUPPORTED_PROFILES:
        fail(f"profile {profile!r} is not implemented (supported: {sorted(PROFILES)}); OPC UA and Tango are "
             "deliberately not profiles of this helper version")
    if profile not in PROFILES:
        fail(f"profile must be one of {sorted(PROFILES)}")
    options = {}
    if profile == "alpaca":
        if type(raw.get("device_type")) is not str or not _DEVICE_TYPE.fullmatch(raw["device_type"]):
            fail("the alpaca profile needs device_type (lower-case Alpaca device type)")
        options["device_type"] = raw["device_type"]
        options["device_number"] = _integer(raw.get("device_number"), "device_number", 0, 255)
        _reference(raw.get("device_type_ref"), "device_type_ref")
    elif set(raw) & {"device_type", "device_type_ref", "device_number"}:
        fail("device_type, device_type_ref and device_number belong to the alpaca profile")
    points_raw = raw["points"]
    if type(points_raw) is not dict or not 1 <= len(points_raw) <= MAX_POINTS:
        fail(f"points needs 1..{MAX_POINTS} entries")
    points = {}
    for name, spec in points_raw.items():
        if not _NAME.fullmatch(name):
            fail(f"point name {name!r} must be an identifier")
        points[name] = _point(name, spec, profile, options)
    requests = [json.dumps(point["request"], sort_keys=True) for point in points.values()]
    if len(set(requests)) != len(requests):
        fail("two points declare the same address")
    out = {"profile": profile, "points": points,
           "timeout_ms": _integer(raw.get("timeout_ms", 1000), "timeout_ms", 1, 10000),
           "confirm_ms": _integer(raw.get("confirm_ms", 0), "confirm_ms", 0, 1500),
           "poll_ms": _integer(raw.get("poll_ms", 50), "poll_ms", 10, 500)}
    out.update(options)
    if profile == "alpaca":
        out["device_type_ref"] = raw["device_type_ref"]
    reads = {} if reads is None else reads
    writes = {} if writes is None else writes
    commands = {} if commands is None else commands
    safety = {} if safety_bindings is None else safety_bindings
    if type(reads) is not dict or type(writes) is not dict or type(commands) is not dict or type(safety) is not dict:
        fail("reads, writes, commands and safety_bindings must be objects")
    compiled_reads = {}
    for name, spec in reads.items():
        _keys(spec, {"point"}, {"point"}, f"reads[{name!r}]")
        compiled_reads[name] = {"point": _readable(points, spec["point"], f"reads[{name!r}].point")["name"]}
    compiled_writes = {}
    for name, spec in writes.items():
        _keys(spec, {"point", "verify"}, {"point"}, f"writes[{name!r}]")
        point = _writable(points, spec["point"], f"writes[{name!r}].point")
        verify = spec.get("verify")
        if verify is not None:
            checked = _readable(points, verify, f"writes[{name!r}].verify")
            if checked["type"] != point["type"] or checked.get("decimals") != point.get("decimals"):
                fail(f"writes[{name!r}].verify must read a point of the same type and resolution")
        compiled_writes[name] = {"point": point["name"], "verify": verify}
    if len(commands) > MAX_COMMANDS:
        fail(f"at most {MAX_COMMANDS} commands")
    compiled_commands = {}
    for capability_id, spec in commands.items():
        compiled_commands[capability_id] = _command(capability_id, spec, points, f"commands[{capability_id!r}]")
    if set(safety) - {"estop"}:
        fail("safety_bindings supports only estop in this version (no interlock or native reset bindings)")
    estop = None
    if "estop" in safety:
        spec = _keys(safety["estop"], {"steps", "confirm"}, {"steps", "confirm"}, "safety_bindings.estop")
        estop = {"steps": _steps(spec["steps"], points, "safety_bindings.estop.steps", fixed=True),
                 "confirm": _predicates(spec["confirm"], points, "safety_bindings.estop.confirm", required=True)}
    out.update({"reads": compiled_reads, "writes": compiled_writes, "commands": compiled_commands,
                "estop": estop})
    return detached(out)


def stop_summary(estop):
    """The short native description of a compiled stop (``Bridge.estop_native``, at most 128 characters)."""
    if not estop:
        return None
    steps = ["write " + step["write"] + "=" + json.dumps(step["value"]) if "write" in step
             else "invoke " + step["invoke"] for step in estop["steps"]]
    checks = [item["point"] + " in " + json.dumps(item["in"]) for item in estop["confirm"]]
    return ("; ".join(steps) + "; confirm " + ", ".join(checks))[:128]


def fingerprint(value):
    """A stable digest key of a compiled value (used to detect runtime mutation of the declaration)."""
    return json.dumps(value, sort_keys=True, allow_nan=False)


def copy_config(value):
    return copy.deepcopy(value)
