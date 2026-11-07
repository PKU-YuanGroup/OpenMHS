"""One limit engine for OpenMHS: path grammar, closed rules, intersection, checking.

Plan 3.5 fixes a single grammar and a single engine for every numeric or
enumerated bound the runtime enforces:

* A **limit path** addresses a field of a capability input (or of a resource
  state document): ``field``, ``a.b``, ``a[*]`` (every element) or ``a[3]``
  (one element).  The tokenizer reads paths exactly like
  :func:`mhs.bridge.base.get_path`, but accepts only the strict grammar of
  ``defs.schema.json#/$defs/limitPath``.
* A **rule** is closed: ``{min, max, allowed, unit, reason, source, ref,
  names, per}``.  An unknown member (``maxx``, ``clamp``) is a load error, so a
  typo can never silently drop a bound.  ``min``/``max`` are scalars (applied
  to every element of a numeric array) or one value per element of a
  fixed-length array; an integer bound beyond +-(2**53-1) is refused, since
  canonical JSON cannot carry it.  ``per`` marks a cumulative budget, enforced
  by the runtime's cumulative check rather than per call.  The string
  ``"operator_required"`` defers the bound to the operator overlay.
* **Sources intersect**: :func:`compile_limits` combines the class, binding,
  device-envelope and operator-overlay rules for one input schema.  The
  effective maximum is the smallest maximum, the minimum the largest minimum,
  ``allowed`` the intersection; element names must agree.  Narrow-only sources
  (the overlay) may never widen what the regular sources allow; among
  themselves they simply intersect, so their order never matters.
* Everything that can be checked at load time is: an unresolvable path, an
  unknown rule member, a bound on a non-numeric field, a per-element bound on a
  scalar or a variable-length array, a bound of the wrong length, a unit other
  than the field's ``x-mhs-unit``, contradictory sources and a widening overlay
  all raise :class:`LimitConfigError`.
* :func:`check` evaluates every array element and nested leaf of a payload,
  skips absent optional fields, evaluates schema defaults of omitted fields and
  returns every :class:`Violation` (the runtime refuses with
  ``MHS.SAFETY.ENVELOPE_VIOLATION`` and the violation details).  Non-numeric,
  boolean, NaN and infinite values never pass a numeric bound.

The module is pure: it imports nothing from the server, the bridges or the
catalogue.  :func:`bound_keyword_paths` and :func:`strip_bound_keywords` support
the server's two-pass validation (schema bounds on limited fields are evaluated
after the limits, so an out-of-range command is a safety refusal rather than
``INPUT_INVALID``).
"""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping, Sequence

__all__ = [
    "Bound",
    "CUMULATIVE_WINDOWS",
    "CumulativeRule",
    "EffectiveLimits",
    "EffectiveRule",
    "LimitConfigError",
    "LimitField",
    "LimitRule",
    "LimitSource",
    "OPERATOR_REQUIRED",
    "Origin",
    "RULE_KEYS",
    "RULE_SOURCES",
    "Violation",
    "WILDCARD",
    "bound_keyword_paths",
    "check",
    "compile_limits",
    "envelope_sources",
    "format_path",
    "numeric_leaf_paths",
    "overlay_sources",
    "parse_path",
    "pattern_matches",
    "strip_bound_keywords",
    "unlimited_numeric_leaves",
]

#: The sentinel limit value that defers a bound to the operator overlay.
OPERATOR_REQUIRED = "operator_required"
#: The closed set of rule members (``defs.schema.json#/$defs/limitRule``).
RULE_KEYS = frozenset({"min", "max", "allowed", "unit", "reason", "source", "ref", "names", "per"})
#: Provenance of a bound; vendor_doc and upstream_code require ``ref``.
RULE_SOURCES = frozenset({"vendor_doc", "upstream_code", "class_default", "operator"})
#: Windows of a cumulative (``per``) budget.
CUMULATIVE_WINDOWS = frozenset({"rolling_1h", "rolling_24h", "rolling_7d", "session"})

_PATH_MAX = 256
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_INDEX = re.compile(r"[0-9]+")
_NUMERIC_KEYWORDS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")
_ENUM_KEYWORDS = ("enum", "const")
_MAX_DEPTH = 32
#: Largest integer JSON (and :mod:`mhs.canonical`) carries exactly as a number.
_JSON_INT_MAX = 2**53 - 1


class LimitConfigError(ValueError):
    """A limit declaration cannot be enforced as written (raised at load time).

    ``rule`` names the violated load-time rule (for example
    ``limit-path-resolves``, ``array-bound-length``, ``limit-unit-matches-field``,
    ``unknown-rule-member`` or ``overlay-narrows``); ``path`` is the limit path
    and ``source`` the label of the source that declared it.
    """

    def __init__(self, message: str, *, rule: str = "limit-invalid", path: str | None = None,
                 source: str | None = None, member: str | None = None):
        self.rule = rule
        self.path = path
        self.source = source
        self.member = member
        prefix = f"{source}: " if source else ""
        super().__init__(prefix + message)


# ---------------------------------------------------------------------------
# path grammar
# ---------------------------------------------------------------------------


class _Wildcard:
    """The ``[*]`` token of a limit path."""

    __slots__ = ()
    _instance: "_Wildcard | None" = None

    def __new__(cls) -> "_Wildcard":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "[*]"


#: Token for ``[*]`` in :func:`parse_path` results.
WILDCARD = _Wildcard()

Token = Any  # str (field), int (index) or WILDCARD


def parse_path(path: str) -> tuple[Token, ...]:
    """Tokenise a limit path: ``a.b[2].c`` -> ``("a", "b", 2, "c")``; ``[*]`` -> :data:`WILDCARD`.

    The tokens equal those of the bridge field-path reader for every valid
    limit path; anything outside the limit-path grammar raises
    :class:`LimitConfigError`.
    """
    if not isinstance(path, str) or not path:
        raise LimitConfigError("a limit path must be a non-empty string", rule="limit-path-grammar",
                               path=path if isinstance(path, str) else None)
    if len(path) > _PATH_MAX:
        raise LimitConfigError(f"limit path is longer than {_PATH_MAX} characters",
                               rule="limit-path-grammar", path=path)
    tokens: list[Token] = []
    pos = 0
    expect_name = True
    while pos < len(path):
        if expect_name:
            match = _NAME.match(path, pos)
            if match is None:
                raise LimitConfigError(f"bad limit path {path!r}: expected a field name at position {pos}",
                                       rule="limit-path-grammar", path=path)
            tokens.append(match.group(0))
            pos = match.end()
            expect_name = False
        elif path[pos] == "[":
            end = path.find("]", pos)
            inner = path[pos + 1:end] if end > 0 else ""
            if inner == "*":
                tokens.append(WILDCARD)
            elif _INDEX.fullmatch(inner):
                tokens.append(int(inner))
            else:
                raise LimitConfigError(f"bad limit path {path!r}: an index is [*] or [N] with N >= 0",
                                       rule="limit-path-grammar", path=path)
            pos = end + 1
        elif path[pos] == ".":
            pos += 1
            expect_name = True
        else:
            raise LimitConfigError(f"bad limit path {path!r}: unexpected {path[pos]!r} at position {pos}",
                                   rule="limit-path-grammar", path=path)
    if expect_name:
        raise LimitConfigError(f"bad limit path {path!r}: ends with '.'", rule="limit-path-grammar", path=path)
    return tuple(tokens)


def format_path(tokens: Sequence[Token]) -> str:
    """Inverse of :func:`parse_path` (also formats concrete element paths)."""
    out = ""
    for token in tokens:
        if token is WILDCARD:
            out += "[*]"
        elif isinstance(token, int):
            out += f"[{token}]"
        else:
            out += ("." if out else "") + str(token)
    return out


def pattern_matches(pattern: str, capability_id: str) -> bool:
    """Capability pattern matching: an exact id or a trailing ``.*`` glob (``cap.thermal.*``)."""
    if not isinstance(pattern, str) or not isinstance(capability_id, str):
        return False
    if pattern.endswith(".*"):
        return capability_id.startswith(pattern[:-1])
    return pattern == capability_id


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------


def _is_number(value: Any) -> bool:
    """A finite JSON number; an integer beyond the double range is not one (never an OverflowError)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _is_bound_number(value: Any) -> bool:
    """A finite number a limit rule may state: integers stay within the canonical JSON range."""
    if not _is_number(value):
        return False
    return not (isinstance(value, int) and abs(value) > _JSON_INT_MAX)


def _json_equal(left: Any, right: Any) -> bool:
    """JSON equality: 1 == 1.0, but True is not 1."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return type(left) is type(right) and left == right


def _fmt(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(value)


@dataclass(frozen=True)
class LimitRule:
    """One closed limit rule, validated on construction.

    ``min``/``max`` are a number or a tuple of numbers (one per array element);
    ``allowed`` a tuple of scalars; ``names`` a tuple of element names.
    """

    min: Any = None
    max: Any = None
    allowed: tuple[Any, ...] | None = None
    unit: str | None = None
    reason: str | None = None
    source: str | None = None
    ref: str | None = None
    names: tuple[str, ...] | None = None
    per: str | None = None

    def __post_init__(self) -> None:
        # integers beyond 2**53-1 are refused: canonical JSON (reference files, error
        # details) cannot carry them as numbers, and no physical bound needs them
        for key in ("min", "max"):
            value = getattr(self, key)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                if not value or not all(_is_bound_number(item) for item in value):
                    raise LimitConfigError(f"{key} must be a finite number (integers within +-(2**53-1)) or a "
                                           "non-empty list of such numbers", rule="limit-rule-invalid", member=key)
                object.__setattr__(self, key, tuple(value))
            elif not _is_bound_number(value):
                raise LimitConfigError(f"{key} must be a finite number (integers within +-(2**53-1)) or a "
                                       "non-empty list of such numbers", rule="limit-rule-invalid", member=key)
        if self.allowed is not None:
            if (not isinstance(self.allowed, (list, tuple)) or not self.allowed
                    or not all(isinstance(item, (str, bool)) or _is_bound_number(item) for item in self.allowed)):
                raise LimitConfigError("allowed must be a non-empty list of strings, booleans or finite numbers "
                                       "(integers within +-(2**53-1))", rule="limit-rule-invalid", member="allowed")
            object.__setattr__(self, "allowed", tuple(self.allowed))
        for key, maximum in (("unit", None), ("reason", 500), ("ref", 500)):
            value = getattr(self, key)
            if value is None:
                continue
            if not isinstance(value, str) or (key != "reason" and not value) or (maximum and len(value) > maximum):
                raise LimitConfigError(f"{key} must be a string" + (f" of at most {maximum} characters" if maximum else ""),
                                       rule="limit-rule-invalid", member=key)
        if self.source is not None and self.source not in RULE_SOURCES:
            raise LimitConfigError(f"source must be one of {sorted(RULE_SOURCES)}, got {self.source!r}",
                                   rule="limit-rule-invalid", member="source")
        if self.source in ("vendor_doc", "upstream_code") and not self.ref:
            raise LimitConfigError(f"a {self.source} bound must cite ref (file:line or a manual page)",
                                   rule="limit-rule-invalid", member="ref")
        if self.names is not None:
            if (not isinstance(self.names, (list, tuple)) or not self.names
                    or not all(isinstance(item, str) and 0 < len(item) <= 64 for item in self.names)):
                raise LimitConfigError("names must be a non-empty list of element names",
                                       rule="limit-rule-invalid", member="names")
            object.__setattr__(self, "names", tuple(self.names))
        if self.per is not None:
            if self.per not in CUMULATIVE_WINDOWS:
                raise LimitConfigError(f"per must be one of {sorted(CUMULATIVE_WINDOWS)}, got {self.per!r}",
                                       rule="limit-rule-invalid", member="per")
            if not _is_number(self.max):
                raise LimitConfigError("a cumulative (per) rule needs a numeric scalar max (the budget)",
                                       rule="limit-rule-invalid", member="max")
        sized = [(key, len(getattr(self, key))) for key in ("min", "max", "names")
                 if isinstance(getattr(self, key), tuple)]
        lengths = {size for _key, size in sized}
        if len(lengths) > 1:
            counts = [sum(1 for _key, other in sized if other == size) for _key, size in sized]
            common = sized[counts.index(max(counts))][1]
            odd = next(key for key, size in sized if size != common)
            raise LimitConfigError(f"per-element min, max and names must have the same length ({odd} has "
                                   f"{len(getattr(self, odd))}, expected {common})",
                                   rule="array-bound-length", member=odd)
        if self.min is not None and self.max is not None and self.per is None:
            size = next(iter(lengths)) if lengths else 1
            for low, high in zip(_broadcast(self.min, size), _broadcast(self.max, size)):
                if low > high:
                    raise LimitConfigError(f"min {_fmt(self.min)} is above max {_fmt(self.max)}",
                                           rule="empty-range", member="min")

    @classmethod
    def parse(cls, value: Any) -> "LimitRule":
        """Build a rule from its JSON form; unknown members raise :class:`LimitConfigError`."""
        if not isinstance(value, Mapping):
            raise LimitConfigError(f"a limit is an object or {OPERATOR_REQUIRED!r}, got {_fmt(value)}",
                                   rule="limit-rule-invalid")
        if not value:
            raise LimitConfigError("a limit rule needs at least one member", rule="limit-rule-invalid")
        unknown = sorted(set(value) - RULE_KEYS)
        if unknown:
            raise LimitConfigError(f"unknown limit rule member(s) {unknown}; allowed: {sorted(RULE_KEYS)}",
                                   rule="unknown-rule-member", member=unknown[0])
        return cls(**{key: value[key] for key in value})

    @property
    def has_bound(self) -> bool:
        return self.min is not None or self.max is not None or self.allowed is not None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key in ("min", "max", "allowed", "unit", "names"):
            value = getattr(self, key)
            if value is not None:
                out[key] = list(value) if isinstance(value, tuple) else value
        for key in ("per", "reason", "source", "ref"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        return out


def _broadcast(value: Any, size: int) -> list[Any]:
    return list(value) if isinstance(value, tuple) else [value] * size


@dataclass(frozen=True)
class LimitSource:
    """One layer of limits: ``label`` names it in violations (class, binding, envelope, overlay).

    ``narrow_only`` sources may never widen the others.  ``partial`` sources may
    name paths that do not exist in this schema (an envelope pattern or class
    limits on a field the binding omits); those paths are skipped and listed
    in :attr:`EffectiveLimits.skipped`.  ``default_source`` is the provenance
    recorded for rules that do not state one (``class_default`` for class
    limits, ``operator`` for the overlay).
    """

    label: str
    limits: Mapping[str, Any] | None
    narrow_only: bool = False
    partial: bool = False
    default_source: str | None = None


@dataclass(frozen=True)
class Origin:
    """Where one effective bound comes from."""

    label: str
    source: str | None = None
    ref: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class Bound:
    """One effective bound value and its origin."""

    value: Any
    origin: Origin


# ---------------------------------------------------------------------------
# schema resolution
# ---------------------------------------------------------------------------


def _types(schema: Mapping[str, Any]) -> frozenset[str]:
    declared = schema.get("type")
    if isinstance(declared, str):
        return frozenset({declared})
    if isinstance(declared, list):
        return frozenset(item for item in declared if isinstance(item, str))
    return frozenset()


def _is_array(schema: Mapping[str, Any]) -> bool:
    types = _types(schema)
    return "array" in types or (not types and ("items" in schema or "prefixItems" in schema))


def _fixed_length(schema: Mapping[str, Any]) -> int | None:
    prefix = schema.get("prefixItems")
    if isinstance(prefix, list) and schema.get("items") is False:
        return len(prefix)
    low, high = schema.get("minItems"), schema.get("maxItems")
    if isinstance(low, int) and not isinstance(low, bool) and low == high:
        return low
    return None


def _escape(token: Any) -> str:
    return str(token).replace("~", "~0").replace("/", "~1")


@dataclass(frozen=True)
class LimitField:
    """The schema of the field a limit path addresses.

    For an array field bounds apply to its elements: ``element`` is the item
    schema, ``length`` the fixed length (or ``None``) and ``pointers`` the JSON
    pointers (into the input schema) of the schemas that hold the elements'
    bound keywords.
    """

    schema: Mapping[str, Any]
    chain: tuple[Mapping[str, Any], ...]
    pointers: tuple[str, ...]
    array: bool
    length: int | None
    nested: bool
    leaf_types: frozenset[str]
    unit: str | None

    @property
    def numeric(self) -> bool | None:
        """True for a numeric leaf, False for a typed non-numeric one, None if untyped."""
        if not self.leaf_types:
            return None
        return bool(self.leaf_types & {"number", "integer"})

    @property
    def nullable(self) -> bool:
        return "null" in self.leaf_types


class _Unresolved(Exception):
    pass


class _Resolver:
    """Resolve limit paths in one schema (local ``$ref`` and ``allOf`` are followed)."""

    def __init__(self, root: Mapping[str, Any]):
        self.root = root
        self.cache: dict[tuple[Token, ...], LimitField] = {}

    def expand(self, node: Any, pointer: str, depth: int = 0) -> list[tuple[Mapping[str, Any], str]]:
        if not isinstance(node, Mapping) or depth > _MAX_DEPTH:
            return []
        out = [(node, pointer)]
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#"):
            target, target_pointer = self.root, ""
            for raw in [part for part in ref[1:].split("/") if part]:
                key = raw.replace("~1", "/").replace("~0", "~")
                target = target.get(key) if isinstance(target, Mapping) else None
                target_pointer += "/" + raw
            out.extend(self.expand(target, target_pointer, depth + 1))
        branches = node.get("allOf")
        if isinstance(branches, list):
            for index, branch in enumerate(branches):
                out.extend(self.expand(branch, f"{pointer}/allOf/{index}", depth + 1))
        return out

    def step(self, nodes: list[tuple[Mapping[str, Any], str]], token: Token) -> list[tuple[Mapping[str, Any], str]]:
        found: list[tuple[Mapping[str, Any], str]] = []
        for node, pointer in nodes:
            if isinstance(token, str):
                properties = node.get("properties")
                if isinstance(properties, Mapping) and isinstance(properties.get(token), Mapping):
                    found.extend(self.expand(properties[token], f"{pointer}/properties/{_escape(token)}"))
                continue
            if not _is_array(node):
                continue
            length = _fixed_length(node)
            if isinstance(token, int) and length is not None and token >= length:
                continue
            prefix = node.get("prefixItems")
            if isinstance(token, int) and isinstance(prefix, list) and token < len(prefix):
                found.extend(self.expand(prefix[token], f"{pointer}/prefixItems/{token}"))
            elif isinstance(node.get("items"), Mapping):
                found.extend(self.expand(node["items"], f"{pointer}/items"))
            elif token is WILDCARD and isinstance(prefix, list):
                for index, item in enumerate(prefix):
                    found.extend(self.expand(item, f"{pointer}/prefixItems/{index}"))
            else:
                found.append(({}, f"{pointer}/items"))
        return found

    def field(self, tokens: tuple[Token, ...]) -> LimitField:
        cached = self.cache.get(tokens)
        if cached is not None:
            return cached
        nodes = self.expand(self.root, "")
        chain: list[Mapping[str, Any]] = []
        for token in tokens:
            nodes = self.step(nodes, token)
            if not nodes:
                raise _Unresolved()
            chain.append(_merged(nodes))
        target = chain[-1] if chain else _merged(nodes)
        if _is_array(target):
            elements = self.step(nodes, WILDCARD)
            nested = False
            leaves = elements
            depth = 0
            while leaves and _is_array(_merged(leaves)) and depth < _MAX_DEPTH:
                nested = True
                leaves = self.step(leaves, WILDCARD)
                depth += 1
            leaf = _merged(leaves) if leaves else {}
            unit = leaf.get("x-mhs-unit") if isinstance(leaf.get("x-mhs-unit"), str) else target.get("x-mhs-unit")
            result = LimitField(
                schema=target, chain=tuple(chain), pointers=tuple(dict.fromkeys(p for _, p in leaves)),
                array=True, length=_fixed_length(target), nested=nested, leaf_types=_types(leaf),
                unit=unit if isinstance(unit, str) else None,
            )
        else:
            unit = target.get("x-mhs-unit")
            result = LimitField(
                schema=target, chain=tuple(chain), pointers=tuple(dict.fromkeys(p for _, p in nodes)),
                array=False, length=None, nested=False, leaf_types=_types(target),
                unit=unit if isinstance(unit, str) else None,
            )
        self.cache[tokens] = result
        return result


def _merged(nodes: list[tuple[Mapping[str, Any], str]]) -> Mapping[str, Any]:
    """Shallow merge of the schemas that describe one field (first one wins)."""
    if len(nodes) == 1:
        return nodes[0][0]
    merged: dict[str, Any] = {}
    for node, _pointer in reversed(nodes):
        merged.update(node)
    merged.pop("$ref", None)
    merged.pop("allOf", None)
    return merged


# ---------------------------------------------------------------------------
# effective limits
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectiveRule:
    """The intersection of every source's rule for one limit path.

    ``min``/``max`` are a :class:`Bound`, a tuple of per-element bounds, or
    ``None``.  ``operator_required`` is true when some source deferred the bound
    to the operator; ``filled`` when a narrow-only source supplied it.
    """

    path: str
    tokens: tuple[Token, ...]
    field: LimitField
    min: Any = None
    max: Any = None
    allowed: tuple[Any, ...] | None = None
    allowed_origin: Origin | None = None
    unit: str | None = None
    names: tuple[str, ...] | None = None
    operator_required: bool = False
    filled: bool = False
    labels: tuple[str, ...] = ()
    reason: str | None = None

    @property
    def has_bound(self) -> bool:
        return self.min is not None or self.max is not None or self.allowed is not None

    @property
    def unset(self) -> bool:
        """True when the bound is ``operator_required`` and no overlay supplied it."""
        return self.operator_required and not self.filled

    @property
    def per_element(self) -> bool:
        return isinstance(self.min, tuple) or isinstance(self.max, tuple)

    def bound_at(self, kind: str, index: int | None) -> Bound | None:
        """The ``min``/``max`` bound for element ``index`` (``None`` for a scalar field)."""
        bound = getattr(self, kind)
        if isinstance(bound, tuple):
            if index is None or index >= len(bound):
                return None
            return bound[index]
        return bound

    def origins(self) -> list[Origin]:
        out: list[Origin] = []
        for kind in ("max", "min"):
            bound = getattr(self, kind)
            for item in (bound if isinstance(bound, tuple) else (bound,)):
                if item is not None and item.origin not in out:
                    out.append(item.origin)
        if self.allowed_origin is not None and self.allowed_origin not in out:
            out.append(self.allowed_origin)
        return out

    def to_json(self) -> dict[str, Any] | str:
        """The effective rule as a closed limit rule (``operator_required`` while unset)."""
        if self.unset:
            return OPERATOR_REQUIRED
        out: dict[str, Any] = {}
        for kind in ("min", "max"):
            bound = getattr(self, kind)
            if isinstance(bound, tuple):
                out[kind] = [item.value for item in bound]
            elif bound is not None:
                out[kind] = bound.value
        if self.allowed is not None:
            out["allowed"] = list(self.allowed)
        if self.unit is not None:
            out["unit"] = self.unit
        if self.names is not None:
            out["names"] = list(self.names)
        origins = self.origins()
        primary = origins[0] if origins else None
        # The reason belongs to the source of the primary bound; a reason-only
        # rule (no bound) keeps the first declared reason.
        reason = primary.reason if primary is not None else self.reason
        if reason:
            out["reason"] = reason
        if primary is not None and primary.source is not None:
            out["source"] = primary.source
        if primary is not None and primary.ref:
            # a ref without a source says where an unclaimed bound came from (a fake backend's action space)
            out["ref"] = primary.ref
        return out


@dataclass(frozen=True)
class CumulativeRule:
    """A cumulative budget (``per``): enforced over a window, not per call."""

    path: str
    per: str
    max: Bound
    unit: str | None = None


@dataclass(frozen=True)
class EffectiveLimits:
    """The compiled limits of one input schema."""

    schema: Mapping[str, Any]
    rules: Mapping[str, EffectiveRule]
    cumulative: tuple[CumulativeRule, ...] = ()
    unset: tuple[str, ...] = ()
    skipped: tuple[tuple[str, str], ...] = ()
    narrowed: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()

    def rule(self, path: str) -> EffectiveRule | None:
        try:
            return self.rules.get(_canonical_key(path, self.schema))
        except LimitConfigError:
            return None

    def to_json(self) -> dict[str, Any]:
        """``{limit path: rule | "operator_required"}`` (per-call rules only)."""
        out: dict[str, Any] = {}
        for path, rule in self.rules.items():
            value = rule.to_json()
            if value:
                out[path] = value
        return out


class _Builder:
    def __init__(self, path: str, tokens: tuple[Token, ...], field_: LimitField):
        self.path = path
        self.tokens = tokens
        self.field = field_
        self.min: Any = None
        self.max: Any = None
        self.allowed: tuple[Any, ...] | None = None
        self.allowed_origin: Origin | None = None
        self.unit: str | None = None
        self.names: tuple[str, ...] | None = None
        self.operator_required = False
        self.filled = False
        self.labels: list[str] = []
        self.reason: str | None = None

    def build(self) -> EffectiveRule:
        return EffectiveRule(
            path=self.path, tokens=self.tokens, field=self.field, min=self.min, max=self.max,
            allowed=self.allowed, allowed_origin=self.allowed_origin, unit=self.unit, names=self.names,
            operator_required=self.operator_required, filled=self.filled, labels=tuple(self.labels),
            reason=self.reason,
        )


def _canonical_key(path: str, schema: Mapping[str, Any]) -> str:
    tokens = parse_path(path)
    if tokens and tokens[-1] is WILDCARD:
        try:
            parent = _Resolver(schema).field(tokens[:-1])
        except _Unresolved:
            return path
        if parent.array:
            return format_path(tokens[:-1])
    return format_path(tokens)


def _as_sources(sources: Any, narrow_only: bool) -> list[LimitSource]:
    if sources is None:
        return []
    if isinstance(sources, LimitSource):
        sources = [sources]
    elif isinstance(sources, Mapping):
        sources = list(sources.items())
    out: list[LimitSource] = []
    for item in sources:
        if isinstance(item, LimitSource):
            source = item
        elif isinstance(item, (tuple, list)) and len(item) == 2 and isinstance(item[0], str):
            source = LimitSource(item[0], item[1])
        else:
            raise TypeError("limit sources are LimitSource objects or (label, limit map) pairs")
        if narrow_only and not source.narrow_only:
            source = LimitSource(source.label, source.limits, True, source.partial, source.default_source)
        out.append(source)
    return out


def compile_limits(
    input_schema: Mapping[str, Any] | None,
    sources: Iterable[Any] | Mapping[str, Any],
    narrow_only_sources: Iterable[Any] | Mapping[str, Any] = (),
) -> EffectiveLimits:
    """Intersect the limit sources of one input schema; raise :class:`LimitConfigError` on any defect.

    ``sources`` and ``narrow_only_sources`` are :class:`LimitSource` objects,
    ``(label, limit map)`` pairs or a ``{label: limit map}`` mapping.  A limit
    map is ``{limit path: rule | "operator_required"}``.  The regular sources
    are applied first, in order, then the narrow-only ones.  Every narrow-only
    rule is compared with what the regular sources allow (for the same values,
    also under a related key of the same array) and refused when it is wider;
    narrow-only rules never need to narrow each other, they intersect like any
    other source, so their order never changes the result.  ``narrowed`` lists,
    for every narrow-only rule, what it narrows relative to the regular sources.
    """
    schema: Mapping[str, Any] = input_schema if isinstance(input_schema, Mapping) else {}
    resolver = _Resolver(schema)
    builders: dict[str, _Builder] = {}
    cumulative: dict[tuple[str, str], CumulativeRule] = {}
    skipped: list[tuple[str, str]] = []
    narrowed: list[str] = []
    labels: list[str] = []
    ordered = _as_sources(sources, False) + _as_sources(narrow_only_sources, True)
    baseline: _Baseline | None = None
    for source in [item for item in ordered if not item.narrow_only] + [item for item in ordered if item.narrow_only]:
        if source.narrow_only and baseline is None:
            # what the regular sources allow; narrow-only rules are judged against this only
            baseline = _Baseline(
                {path: _Snapshot(path, item.tokens, item.field, item.min, item.max, item.allowed)
                 for path, item in builders.items()},
                dict(cumulative),
            )
        if source.limits is None:
            continue
        if not isinstance(source.limits, Mapping):
            raise LimitConfigError("limits must be an object keyed by limit path", source=source.label)
        if source.label not in labels:
            labels.append(source.label)
        for raw_path in source.limits:
            _apply(resolver, builders, cumulative, skipped, narrowed, source, raw_path, source.limits[raw_path],
                   baseline)
    rules = {path: builders[path].build() for path in sorted(builders)}
    unset = tuple(path for path, rule in rules.items() if rule.unset)
    return EffectiveLimits(
        schema=schema, rules=rules,
        cumulative=tuple(cumulative[key] for key in sorted(cumulative)),
        unset=unset, skipped=tuple(skipped), narrowed=tuple(narrowed), labels=tuple(labels),
    )


@dataclass(frozen=True)
class _Snapshot:
    """The bounds one key had after the regular sources (narrow-only rules are judged against it)."""

    path: str
    tokens: tuple[Token, ...]
    field: LimitField
    min: Any
    max: Any
    allowed: tuple[Any, ...] | None


@dataclass(frozen=True)
class _Baseline:
    rules: Mapping[str, _Snapshot]
    cumulative: Mapping[tuple[str, str], CumulativeRule]


def _apply(resolver: _Resolver, builders: dict[str, _Builder], cumulative: dict[tuple[str, str], CumulativeRule],
           skipped: list[tuple[str, str]], narrowed: list[str], source: LimitSource, raw_path: Any, value: Any,
           baseline: _Baseline | None = None) -> None:
    label = source.label
    if source.narrow_only and baseline is None:
        baseline = _Baseline({}, {})
    try:
        tokens = parse_path(raw_path)
    except LimitConfigError as exc:
        raise LimitConfigError(str(exc), rule=exc.rule, path=exc.path, source=label) from None
    element_path = bool(tokens) and not isinstance(tokens[-1], str)
    try:
        if tokens[-1] is WILDCARD and resolver.field(tokens[:-1]).array:
            tokens = tokens[:-1]
        field_ = resolver.field(tokens)
    except _Unresolved:
        if source.partial:
            skipped.append((label, raw_path))
            return
        raise LimitConfigError(f"limit path {raw_path!r} does not resolve in the input schema",
                               rule="limit-path-resolves", path=raw_path, source=label) from None
    key = format_path(tokens)
    builder = builders.get(key)
    # a narrow-only rule is also compared with the regular rules of the same array
    # under another key (``a`` bounds every ``a[N]``, ``a[N]`` bounds element N of ``a``)
    related = _related(baseline.rules, key, tokens, field_) if baseline is not None else []
    base = baseline.rules.get(key) if baseline is not None else None
    if isinstance(value, str) and value == OPERATOR_REQUIRED:
        if source.narrow_only:
            raise LimitConfigError(f"{raw_path}: an overlay supplies bounds; it cannot itself be operator_required",
                                   rule="overlay-supplies-bounds", path=raw_path, source=label)
        if builder is None:
            builder = builders[key] = _Builder(key, tokens, field_)
        builder.operator_required = True
        if label not in builder.labels:
            builder.labels.append(label)
        return
    try:
        rule = LimitRule.parse(value)
    except LimitConfigError as exc:
        raise LimitConfigError(f"{raw_path}: {exc}", rule=exc.rule, path=raw_path, source=label,
                               member=exc.member) from None
    _check_rule(rule, field_, raw_path, label, element_path)
    origin = Origin(label, rule.source or source.default_source, rule.ref, rule.reason)
    if rule.per is not None:
        _merge_cumulative(cumulative, key, rule, origin, source, raw_path, narrowed,
                          baseline.cumulative if baseline is not None else None)
        return
    if builder is None:
        builder = builders[key] = _Builder(key, tokens, field_)
    _merge(builder, rule, origin, source, raw_path, narrowed, related, base)


def _element_tokens(tokens: tuple[Token, ...], field_: LimitField) -> tuple[Token, ...]:
    """The tokens of the values a rule bounds: a (flat) array rule bounds ``a[*]``."""
    return tokens + (WILDCARD,) if field_.array and not field_.nested else tokens


def _overlap(left: tuple[Token, ...], right: tuple[Token, ...]) -> bool:
    """True when two element paths can address the same value (``[*]`` meets any index)."""
    if len(left) != len(right):
        return False
    for one, other in zip(left, right):
        if isinstance(one, str) or isinstance(other, str):
            if not (isinstance(one, str) and isinstance(other, str) and one == other):
                return False
        elif one is not WILDCARD and other is not WILDCARD and one != other:
            return False
    return True


def _related(rules: Mapping[str, Any], key: str, tokens: tuple[Token, ...], field_: LimitField) -> list[Any]:
    """The other keys (builders or snapshots) whose values overlap the values ``tokens`` bounds."""
    mine = _element_tokens(tokens, field_)
    return [other for path, other in rules.items()
            if path != key and _overlap(mine, _element_tokens(other.tokens, other.field))]


def _at(value: Any, index: int | None) -> Any:
    if isinstance(value, tuple):
        return value[index] if index is not None and index < len(value) else None
    return value


def _pairs(builder: "_Builder", value: Any, other: Any, kind: str) -> Iterator[tuple[Any, Bound]]:
    """``(new value, existing bound)`` for every element that ``value`` (at ``builder``) and ``other`` both bound."""
    bound = getattr(other, kind)
    if bound is None:
        return
    mine = _element_tokens(builder.tokens, builder.field)
    theirs = _element_tokens(other.tokens, other.field)
    last, other_last = (mine[-1] if mine else None), (theirs[-1] if theirs else None)
    if last is WILDCARD and other_last is WILDCARD:
        sizes = [len(item) for item in (value, bound) if isinstance(item, tuple)]
        pairs = [(_at(value, index), _at(bound, index)) for index in range(max(sizes) if sizes else 1)]
    elif last is WILDCARD and isinstance(other_last, int):
        pairs = [(_at(value, other_last), bound)]
    elif isinstance(last, int) and other_last is WILDCARD:
        pairs = [(value, _at(bound, last))]
    else:
        pairs = [(value, bound)]
    for new, old in pairs:
        if new is not None and isinstance(old, Bound):
            yield new, old


def _check_rule(rule: LimitRule, field_: LimitField, raw_path: str, label: str, element_path: bool) -> None:
    def fail(message: str, rule_id: str, member: str | None = None) -> LimitConfigError:
        return LimitConfigError(f"{raw_path}: {message}", rule=rule_id, path=raw_path, source=label, member=member)

    per_element = [key for key in ("min", "max", "names") if isinstance(getattr(rule, key), tuple)]
    for key in per_element:
        if key == "names" and not field_.array:
            raise fail("names apply to an array field", "array-bound-length", key)
        if key == "names":
            continue
        if element_path or not field_.array:
            raise fail(f"per-element {key} needs an array field (not a single value)", "array-bound-length", key)
        if field_.nested:
            raise fail(f"per-element {key} needs an array of numbers", "array-bound-length", key)
    for key in per_element:
        if field_.length is None:
            raise fail(f"per-element {key} needs a fixed-length array (minItems == maxItems)", "array-bound-length", key)
        size = len(getattr(rule, key))
        if size != field_.length:
            raise fail(f"{key} has {size} values for an array of length {field_.length}", "array-bound-length", key)
    if (rule.min is not None or rule.max is not None or rule.per is not None) and field_.numeric is False:
        raise fail(f"min/max bound a numeric field; this field is {sorted(field_.leaf_types)}", "limit-type")
    if rule.per is not None and field_.array:
        raise fail("a cumulative (per) budget applies to a numeric scalar field", "limit-type", "per")
    if rule.allowed is not None and field_.leaf_types and not field_.leaf_types - {"object", "array"}:
        raise fail(f"allowed applies to scalar values; this field is {sorted(field_.leaf_types)}", "limit-type",
                   "allowed")
    if rule.allowed is not None and field_.leaf_types:
        for item in rule.allowed:
            if not _value_has_type(item, field_.leaf_types):
                raise fail(f"allowed value {_fmt(item)} does not match the field type {sorted(field_.leaf_types)}",
                           "limit-type", "allowed")
    if rule.unit is not None and field_.unit is not None and rule.unit != field_.unit:
        raise fail(f"limit unit {rule.unit!r} differs from the field's x-mhs-unit {field_.unit!r} "
                   "(conversions are never implicit)", "limit-unit-matches-field", "unit")


def _value_has_type(value: Any, types: frozenset[str]) -> bool:
    if isinstance(value, bool):
        return "boolean" in types
    if isinstance(value, int):
        return bool(types & {"integer", "number"})
    if isinstance(value, float):
        return "number" in types or ("integer" in types and value.is_integer())
    if isinstance(value, str):
        return "string" in types
    return False


def _log(narrowed: list[str], line: str) -> None:
    if line not in narrowed:
        narrowed.append(line)


def _narrow_bound(builder: _Builder, kind: str, new_value: Any, tighter: Any, base: _Snapshot | None,
                  related: Sequence[Any], fail: Any, narrowed: list[str]) -> None:
    """Refuse a narrow-only ``min``/``max`` wider than the regular sources; log what it narrows."""
    size = builder.field.length or 1
    priors: list[Any] = []
    for other in related:
        for new, old in _pairs(builder, new_value, other, kind):
            if tighter(old.value, new):
                raise fail(f"{kind} {_fmt(new)} widens {_fmt(old.value)} that {other.path} has from "
                           f"{old.origin.label}", "overlay-narrows", kind)
            priors.append(old.value)
    current = getattr(base, kind) if base is not None else None
    if current is None:
        one_value = WILDCARD not in _element_tokens(builder.tokens, builder.field)
        if one_value and priors:
            prior = min(priors) if kind == "max" else max(priors)
            if tighter(new_value, prior):
                _log(narrowed, f"{builder.path}.{kind}: {_fmt(prior)} -> {_fmt(new_value)}")
        else:
            _log(narrowed, f"{builder.path}.{kind}: unbounded -> {_fmt(new_value)}")
        return
    if not isinstance(new_value, tuple) and not isinstance(current, tuple):
        if tighter(current.value, new_value):
            raise fail(f"{kind} {_fmt(new_value)} widens {_fmt(current.value)} from {current.origin.label}",
                       "overlay-narrows", kind)
        if tighter(new_value, current.value):
            _log(narrowed, f"{builder.path}.{kind}: {_fmt(current.value)} -> {_fmt(new_value)}")
        return
    old_items = list(current) if isinstance(current, tuple) else [current] * size
    for index, (old, new) in enumerate(zip(old_items, _broadcast(new_value, size))):
        if tighter(old.value, new):
            raise fail(f"{kind}[{index}] {_fmt(new)} widens {_fmt(old.value)} from {old.origin.label}",
                       "overlay-narrows", kind)
        if tighter(new, old.value):
            _log(narrowed, f"{builder.path}[{index}].{kind}: {_fmt(old.value)} -> {_fmt(new)}")


def _narrow_allowed(builder: _Builder, allowed: tuple[Any, ...], base: _Snapshot | None, related: Sequence[Any],
                    fail: Any, narrowed: list[str]) -> None:
    """Refuse a narrow-only ``allowed`` that adds values to the regular sources; log what it narrows."""
    prior: tuple[Any, ...] | None = None
    for other in related:
        if other.allowed is None:
            continue
        extra = [item for item in allowed if not any(_json_equal(item, old) for old in other.allowed)]
        if extra:
            raise fail(f"allowed adds {_fmt(extra)} to {_fmt(list(other.allowed))} that {other.path} has",
                       "overlay-narrows", "allowed")
        if prior is None or len(other.allowed) < len(prior):
            prior = other.allowed
    current = base.allowed if base is not None else None
    if current is None:
        if prior is None:
            _log(narrowed, f"{builder.path}.allowed: any -> {_fmt(list(allowed))}")
        elif len(allowed) < len(prior):
            _log(narrowed, f"{builder.path}.allowed: {_fmt(list(prior))} -> {_fmt(list(allowed))}")
        return
    extra = [item for item in allowed if not any(_json_equal(item, old) for old in current)]
    if extra:
        raise fail(f"allowed adds {_fmt(extra)} to {_fmt(list(current))}", "overlay-narrows", "allowed")
    kept = [item for item in current if any(_json_equal(item, new) for new in allowed)]
    if len(kept) != len(current):
        _log(narrowed, f"{builder.path}.allowed: {_fmt(list(current))} -> {_fmt(kept)}")


def _merge(builder: _Builder, rule: LimitRule, origin: Origin, source: LimitSource, raw_path: str,
           narrowed: list[str], related: Sequence[Any] = (), base: _Snapshot | None = None) -> None:
    """Intersect ``rule`` into ``builder``; a narrow-only rule is first judged against the regular sources."""
    label = source.label

    def fail(message: str, rule_id: str, member: str | None = None) -> LimitConfigError:
        return LimitConfigError(f"{raw_path}: {message}", rule=rule_id, path=raw_path, source=label, member=member)

    if rule.unit is not None:
        if builder.unit is None:
            builder.unit = rule.unit
        elif builder.unit != rule.unit:
            raise fail(f"unit {rule.unit!r} disagrees with {builder.unit!r} from another source",
                       "limit-unit-matches-field", "unit")
    elif builder.unit is None and builder.field.unit is not None and rule.has_bound:
        builder.unit = builder.field.unit
    if rule.names is not None:
        if builder.names is None:
            builder.names = rule.names
        elif builder.names != rule.names:
            raise fail(f"element names {list(rule.names)} disagree with {list(builder.names)}", "names-agree", "names")
    if rule.reason and builder.reason is None:
        builder.reason = rule.reason
    size = builder.field.length or 1
    for kind, tighter in (("max", lambda new, old: new < old), ("min", lambda new, old: new > old)):
        new_value = getattr(rule, kind)
        if new_value is None:
            continue
        if source.narrow_only:
            _narrow_bound(builder, kind, new_value, tighter, base, related, fail, narrowed)
        current = getattr(builder, kind)
        if current is None:
            setattr(builder, kind, tuple(Bound(item, origin) for item in new_value) if isinstance(new_value, tuple)
                    else Bound(new_value, origin))
            continue
        if not isinstance(new_value, tuple) and not isinstance(current, tuple):
            if tighter(new_value, current.value):
                setattr(builder, kind, Bound(new_value, origin))
            continue
        old_items = list(current) if isinstance(current, tuple) else [current] * size
        setattr(builder, kind, tuple(Bound(new, origin) if tighter(new, old.value) else old
                                     for old, new in zip(old_items, _broadcast(new_value, size))))
    if rule.allowed is not None:
        if source.narrow_only:
            _narrow_allowed(builder, rule.allowed, base, related, fail, narrowed)
        if builder.allowed is None:
            builder.allowed = rule.allowed
            builder.allowed_origin = origin
        else:
            kept = tuple(item for item in builder.allowed if any(_json_equal(item, new) for new in rule.allowed))
            if not kept:
                raise fail(f"allowed {_fmt(list(rule.allowed))} has no value in common with "
                           f"{_fmt(list(builder.allowed))}", "empty-range", "allowed")
            if len(kept) != len(builder.allowed):
                builder.allowed = kept
                builder.allowed_origin = origin
    if builder.min is not None and builder.max is not None:
        lows = builder.min if isinstance(builder.min, tuple) else [builder.min] * size
        highs = builder.max if isinstance(builder.max, tuple) else [builder.max] * size
        for index, (low, high) in enumerate(zip(lows, highs)):
            if low.value > high.value:
                where = f"[{index}]" if size > 1 or builder.field.array else ""
                raise fail(f"sources leave no valid value{where}: min {_fmt(low.value)} ({low.origin.label}) is above "
                           f"max {_fmt(high.value)} ({high.origin.label})", "empty-range")
    if source.narrow_only and rule.has_bound:
        builder.filled = True
    if label not in builder.labels:
        builder.labels.append(label)


def _merge_cumulative(cumulative: dict[tuple[str, str], CumulativeRule], key: str, rule: LimitRule, origin: Origin,
                      source: LimitSource, raw_path: str, narrowed: list[str],
                      baseline: Mapping[tuple[str, str], CumulativeRule] | None = None) -> None:
    slot = (key, str(rule.per))
    current = cumulative.get(slot)
    if source.narrow_only:
        base = (baseline or {}).get(slot)
        if base is None:
            _log(narrowed, f"{key}.max per {rule.per}: unbounded -> {_fmt(rule.max)}")
        elif rule.max > base.max.value:
            raise LimitConfigError(f"{raw_path}: cumulative max {_fmt(rule.max)} per {rule.per} widens "
                                   f"{_fmt(base.max.value)}", rule="overlay-narrows", path=raw_path,
                                   source=source.label, member="max")
        elif rule.max < base.max.value:
            _log(narrowed, f"{key}.max per {rule.per}: {_fmt(base.max.value)} -> {_fmt(rule.max)}")
    if current is None:
        cumulative[slot] = CumulativeRule(key, str(rule.per), Bound(rule.max, origin), rule.unit)
    elif rule.max < current.max.value:
        cumulative[slot] = CumulativeRule(key, str(rule.per), Bound(rule.max, origin), rule.unit or current.unit)


# ---------------------------------------------------------------------------
# runtime check
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    """One value outside its effective limit.

    ``path`` is the concrete path (``joint_positions[2]``), ``kind`` the failed
    check (``min``, ``max``, ``allowed``, ``type`` for a value that cannot be
    compared, ``length`` for an element without a per-element bound), ``bound``
    the limit value, ``source`` the label of the source that set it and
    ``element_name`` the declared name of the element.
    """

    path: str
    kind: str
    bound: Any
    value: Any
    unit: str | None = None
    source: str | None = None
    element_name: str | None = None
    limit_path: str | None = None
    reason: str | None = None
    provenance: str | None = None
    ref: str | None = None

    def to_details(self) -> dict[str, Any]:
        """The ``details`` of an ``MHS.SAFETY.ENVELOPE_VIOLATION`` error (always canonical JSON)."""
        out: dict[str, Any] = {"path": self.path, "kind": self.kind, "bound": _plain_value(self.bound),
                               "value": _plain_value(self.value)}
        for key in ("unit", "source", "element_name", "limit_path", "reason"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        if self.provenance is not None:
            out["provenance"] = {"source": self.provenance, **({"ref": self.ref} if self.ref else {})}
        return out

    def message(self) -> str:
        name = f" ({self.element_name})" if self.element_name else ""
        unit = f" {self.unit}" if self.unit else ""
        if self.kind == "allowed":
            return f"{self.path}{name}={_fmt(_plain_value(self.value))} is not one of {_fmt(self.bound)}"
        if self.kind == "type":
            return f"{self.path}{name}={_fmt(_plain_value(self.value))} is not a finite number"
        if self.kind == "length":
            return f"{self.path}{name} has no per-element bound (the array has more than {self.bound} elements)"
        word = "minimum" if self.kind == "min" else "maximum"
        return f"{self.path}{name}={_fmt(self.value)}{unit} is outside the {word} {_fmt(self.bound)}{unit}"


def _plain_value(value: Any, depth: int = 0) -> Any:
    """``value`` as canonical JSON can carry it: non-finite floats and integers beyond 2**53-1 become strings."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > _JSON_INT_MAX:
        return str(value)   # beyond what canonical JSON carries as a number
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if depth >= _MAX_DEPTH:
        return repr(value)
    if isinstance(value, (list, tuple)):
        return [_plain_value(item, depth + 1) for item in value]
    if isinstance(value, Mapping) and all(isinstance(key, str) for key in value):
        return {key: _plain_value(item, depth + 1) for key, item in value.items()}
    return repr(value)


class _Mismatch:
    def __init__(self, value: Any):
        self.value = value


def _addressed(value: Any, tokens: tuple[Token, ...], chain: tuple[Mapping[str, Any], ...],
               index: int = 0, concrete: tuple[Token, ...] = ()) -> Iterator[tuple[tuple[Token, ...], Any]]:
    if index == len(tokens):
        yield concrete, value
        return
    token = tokens[index]
    if value is None:
        return
    if isinstance(token, str):
        if not isinstance(value, Mapping):
            yield concrete, _Mismatch(value)
            return
        if token in value:
            child = value[token]
        elif "default" in chain[index]:
            child = copy.deepcopy(chain[index]["default"])
        else:
            return
        yield from _addressed(child, tokens, chain, index + 1, concrete + (token,))
        return
    if not isinstance(value, (list, tuple)):
        yield concrete, _Mismatch(value)
        return
    if token is WILDCARD:
        for position, item in enumerate(value):
            yield from _addressed(item, tokens, chain, index + 1, concrete + (position,))
    elif token < len(value):
        yield from _addressed(value[token], tokens, chain, index + 1, concrete + (token,))


def _leaves(value: Any, concrete: tuple[Token, ...], depth: int = 0) -> Iterator[tuple[tuple[Token, ...], Any]]:
    if isinstance(value, (list, tuple)) and depth < _MAX_DEPTH:
        for position, item in enumerate(value):
            yield from _leaves(item, concrete + (position,), depth + 1)
    else:
        yield concrete, value


def check(payload: Any, effective: EffectiveLimits) -> list[Violation]:
    """Return every violation of ``effective`` in ``payload`` (an empty list means within limits)."""
    violations: list[Violation] = []
    for rule in effective.rules.values():
        if not rule.has_bound:
            continue
        for concrete, value in _addressed(payload, rule.tokens, rule.field.chain):
            if isinstance(value, _Mismatch):
                violations.append(_violation(rule, concrete, "type", None, value.value, None))
                continue
            if not rule.field.array:
                _check_leaf(rule, concrete, value, None, violations)
                continue
            if value is None and rule.field.nullable:
                continue
            if not isinstance(value, (list, tuple)):
                violations.append(_violation(rule, concrete, "type", None, value, None))
                continue
            limit = len(rule.min) if isinstance(rule.min, tuple) else len(rule.max) if isinstance(rule.max, tuple) else None
            for position, item in enumerate(value):
                where = concrete + (position,)
                if limit is not None and position >= limit:
                    violations.append(_violation(rule, where, "length", limit, item, position))
                    continue
                for leaf_path, leaf in _leaves(item, where):
                    _check_leaf(rule, leaf_path, leaf, position, violations)
    return violations


def _check_leaf(rule: EffectiveRule, concrete: tuple[Token, ...], value: Any, index: int | None,
                violations: list[Violation]) -> None:
    if value is None and rule.field.nullable:
        return
    lower, upper = rule.bound_at("min", index), rule.bound_at("max", index)
    if lower is not None or upper is not None:
        if not _is_number(value):
            violations.append(_violation(rule, concrete, "type", None, value, index, lower or upper))
        elif lower is not None and value < lower.value:
            violations.append(_violation(rule, concrete, "min", lower.value, value, index, lower))
        elif upper is not None and value > upper.value:
            violations.append(_violation(rule, concrete, "max", upper.value, value, index, upper))
    if rule.allowed is not None and not any(_json_equal(value, item) for item in rule.allowed):
        violations.append(_violation(rule, concrete, "allowed", list(rule.allowed), value, index, None,
                                     rule.allowed_origin))


def _violation(rule: EffectiveRule, concrete: tuple[Token, ...], kind: str, bound: Any, value: Any,
               index: int | None, bound_obj: Bound | None = None, origin: Origin | None = None) -> Violation:
    origin = origin or (bound_obj.origin if bound_obj is not None else None)
    if origin is None:
        origins = rule.origins()
        origin = origins[0] if origins else None
    name = rule.names[index] if rule.names is not None and index is not None and index < len(rule.names) else None
    return Violation(
        path=format_path(concrete), kind=kind, bound=bound, value=value, unit=rule.unit,
        source=origin.label if origin else None, element_name=name, limit_path=rule.path,
        reason=origin.reason if origin is not None else rule.reason,
        provenance=origin.source if origin else None, ref=origin.ref if origin else None,
    )


# ---------------------------------------------------------------------------
# two-pass validation and coverage helpers
# ---------------------------------------------------------------------------


def bound_keyword_paths(effective: EffectiveLimits) -> tuple[str, ...]:
    """JSON pointers (into the input schema) of field schemas covered by a bound.

    The server validates structure first with the bound keywords
    (``minimum``/``maximum``/``exclusive*``, and ``enum``/``const`` where the
    limit has ``allowed``) removed at these pointers, then checks the limits,
    then validates the full schema.
    """
    pointers: list[str] = []
    for rule in effective.rules.values():
        if rule.has_bound:
            pointers.extend(rule.field.pointers)
    return tuple(sorted(dict.fromkeys(pointers)))


def strip_bound_keywords(effective: EffectiveLimits, schema: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """A deep copy of the input schema without the bound keywords of limited fields."""
    document = copy.deepcopy(dict(schema if schema is not None else effective.schema))
    for rule in effective.rules.values():
        if not rule.has_bound:
            continue
        keywords = (_NUMERIC_KEYWORDS if (rule.min is not None or rule.max is not None) else ()) + (
            _ENUM_KEYWORDS if rule.allowed is not None else ())
        for pointer in rule.field.pointers:
            node: Any = document
            for raw in [part for part in pointer.split("/") if part]:
                key = raw.replace("~1", "/").replace("~0", "~")
                if isinstance(node, list) and key.isdigit():
                    node = node[int(key)] if int(key) < len(node) else None
                elif isinstance(node, dict):
                    node = node.get(key)
                else:
                    node = None
                if node is None:
                    break
            if isinstance(node, dict):
                for keyword in keywords:
                    node.pop(keyword, None)
    return document


def numeric_leaf_paths(schema: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Limit paths of every numeric leaf of ``schema`` (a numeric array counts as one leaf)."""
    out: list[str] = []
    if isinstance(schema, Mapping):
        resolver = _Resolver(schema)
        _numeric_walk(resolver, resolver.expand(schema, ""), (), out, 0)
    return tuple(out)


def _numeric_walk(resolver: _Resolver, nodes: list[tuple[Mapping[str, Any], str]], prefix: tuple[Token, ...],
                  out: list[str], depth: int) -> None:
    if depth > _MAX_DEPTH or not nodes:
        return
    merged = _merged(nodes)
    if prefix and _is_array(merged):
        field_ = resolver.field(prefix)
        if field_.numeric:
            out.append(format_path(prefix))
            return
        elements = resolver.step(nodes, WILDCARD)
        _numeric_walk(resolver, elements, prefix + (WILDCARD,), out, depth + 1)
        return
    if prefix and _types(merged) & {"number", "integer"}:
        out.append(format_path(prefix))
        return
    names: list[str] = []
    for node, _pointer in nodes:
        properties = node.get("properties")
        if isinstance(properties, Mapping):
            names.extend(name for name in properties if name not in names)
    for name in names:
        if _NAME.fullmatch(name):
            _numeric_walk(resolver, resolver.step(nodes, name), prefix + (name,), out, depth + 1)


def unlimited_numeric_leaves(effective: EffectiveLimits) -> tuple[str, ...]:
    """Numeric leaves of the schema with no bound and no ``operator_required`` declaration.

    A leaf counts as limited when a rule on its own path, or on the whole array
    it belongs to, has a ``min``, ``max`` or ``allowed`` bound (the runtime's
    ``MHS.SAFETY.LIMITS_UNSET`` rule for hardware writes and invocations).
    """
    covered = {path for path, rule in effective.rules.items() if rule.has_bound or rule.operator_required}
    return tuple(path for path in numeric_leaf_paths(effective.schema) if path not in covered)


# ---------------------------------------------------------------------------
# manifest helpers
# ---------------------------------------------------------------------------


def envelope_sources(envelope: Mapping[str, Any] | None, capability_id: str) -> list[LimitSource]:
    """The device-envelope limit maps that apply to ``capability_id``.

    An exact capability id gives a strict source (every path must resolve); a
    pattern (``cap.thermal.*``) gives a partial one, because a pattern covers
    capabilities whose inputs differ.
    """
    out: list[LimitSource] = []
    if not isinstance(envelope, Mapping):
        return out
    for pattern in sorted(envelope):
        if not pattern_matches(pattern, capability_id):
            continue
        exact = pattern == capability_id
        out.append(LimitSource("envelope" if exact else f"envelope:{pattern}", envelope[pattern], partial=not exact))
    return out


def overlay_sources(site_limits: Mapping[str, Any] | None, device_id: str, capability_id: str, *,
                    parameter_paths: bool = False, partial_parameters: bool = False) -> list[LimitSource]:
    """The narrow-only operator-overlay sources (``site-limits.json``) for one binding.

    Entries keyed by the capability id apply to it; with ``parameter_paths``
    (the binding of ``cap.device.configure.v1``) the device's parameter-path
    entries apply as well.  Rules without a ``source`` are recorded as
    ``operator``.
    """
    if not isinstance(site_limits, Mapping):
        return []
    devices = site_limits.get("devices")
    entry = devices.get(device_id) if isinstance(devices, Mapping) else None
    if not isinstance(entry, Mapping):
        return []
    out: list[LimitSource] = []
    if isinstance(entry.get(capability_id), Mapping):
        out.append(LimitSource("overlay", entry[capability_id], narrow_only=True, default_source="operator"))
    if parameter_paths:
        params = {key: value for key, value in entry.items() if not key.startswith(("cap.", "x-cap."))}
        if params:
            out.append(LimitSource("overlay", params, narrow_only=True, partial=partial_parameters,
                                   default_source="operator"))
    return out
