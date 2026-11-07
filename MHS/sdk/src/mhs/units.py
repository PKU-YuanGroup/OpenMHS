"""UCUM unit parsing and conversion for OpenMHS (CAP-022; stdlib only).

Every quantity on the wire carries a UCUM code in ``x-mhs-unit``.  This module
is the single converter the SDK uses: limits compare units with it, bridges
convert at the native boundary with it, and the catalogue tests check that every
code in ``capabilities.json`` parses.

The parser covers the UCUM case-sensitive grammar used by OpenMHS:

* atoms with metric prefixes (``mm``, ``uL``, ``kPa``, ``mW``, ``kOhm``, ``GHz``);
* products with ``.`` and quotients with ``/``, evaluated left to right as UCUM
  requires (``N.m``, ``uL/s``, ``K/min``, ``mL/min``), a leading ``/``
  (``/min``), parentheses and integer exponents (``m/s2``, ``s-1``);
* ``%`` (ratio 0.01), ``1`` and integer factors, and ``{annotations}`` (which
  carry no dimension).

Factors are kept as exact fractions, so decimal conversions are exact
(``convert(1, "m/s", "mm/s") == 1000``).  Temperature offsets apply only to an
absolute temperature (a single ``K``, ``Cel`` or ``[degF]`` atom) and never to
a field marked ``x-mhs-delta`` (a temperature difference such as a tolerance).

Conversion never guesses: an unknown code, a dimension mismatch, or an explicit
factor or offset that contradicts the derived one raises :class:`UnitError`.
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping

__all__ = [
    "BASE_DIMENSIONS",
    "Unit",
    "UnitError",
    "UnknownUnitError",
    "compatible",
    "conversion",
    "convert",
    "convert_unit",
    "dimension",
    "field_is_delta",
    "is_known",
    "known_atoms",
    "parse",
]

#: Order of the exponents in :attr:`Unit.dims`.  ``rad`` is a base dimension,
#: as in UCUM, so an angle never converts to a plain ratio.
BASE_DIMENSIONS = ("m", "kg", "s", "A", "K", "mol", "cd", "rad")

_TOLERANCE = 1e-9


class UnitError(ValueError):
    """A unit code is unknown, or a conversion is dimensionally or numerically invalid."""


class UnknownUnitError(UnitError):
    """A unit code does not parse or names an atom outside the supported table."""


def _dims(**exponents: int) -> tuple[int, ...]:
    return tuple(int(exponents.get(name, 0)) for name in ("L", "M", "T", "I", "TH", "N", "J", "ANG"))


_NONE = _dims()

# atom -> (factor to the coherent SI base unit, dimension vector, metric?, offset)
# The offset (in kelvin) applies only to an absolute temperature conversion.
_ATOMS: dict[str, tuple[Fraction, tuple[int, ...], bool, Fraction]] = {}


def _atom(code: str, factor: Any, dims: tuple[int, ...], metric: bool, offset: Any = 0) -> None:
    _ATOMS[code] = (Fraction(factor), dims, metric, Fraction(offset))


# base units
_atom("m", 1, _dims(L=1), True)
_atom("g", Fraction(1, 1000), _dims(M=1), True)
_atom("s", 1, _dims(T=1), True)
_atom("A", 1, _dims(I=1), True)
_atom("K", 1, _dims(TH=1), True)
_atom("mol", 1, _dims(N=1), True)
_atom("cd", 1, _dims(J=1), True)
_atom("rad", 1, _dims(ANG=1), True)
# time (non-metric)
_atom("min", 60, _dims(T=1), False)
_atom("h", 3600, _dims(T=1), False)
_atom("d", 86400, _dims(T=1), False)
# angle
_atom("deg", Fraction(math.pi) / 180, _dims(ANG=1), False)
# volume
_atom("L", Fraction(1, 1000), _dims(L=3), True)
_atom("l", Fraction(1, 1000), _dims(L=3), True)
# temperature (absolute scales carry an offset to kelvin)
_atom("Cel", 1, _dims(TH=1), False, Fraction(27315, 100))
_atom("[degF]", Fraction(5, 9), _dims(TH=1), False, Fraction(45967, 100) * Fraction(5, 9))
# derived SI units
_atom("Hz", 1, _dims(T=-1), True)
_atom("N", 1, _dims(M=1, L=1, T=-2), True)
_atom("Pa", 1, _dims(M=1, L=-1, T=-2), True)
_atom("J", 1, _dims(M=1, L=2, T=-2), True)
_atom("W", 1, _dims(M=1, L=2, T=-3), True)
_atom("C", 1, _dims(T=1, I=1), True)
_atom("V", 1, _dims(M=1, L=2, T=-3, I=-1), True)
_atom("Ohm", 1, _dims(M=1, L=2, T=-3, I=-2), True)
_atom("S", 1, _dims(M=-1, L=-2, T=3, I=2), True)
_atom("F", 1, _dims(M=-1, L=-2, T=4, I=2), True)
_atom("T", 1, _dims(M=1, T=-2, I=-1), True)
# pressure
_atom("bar", 100000, _dims(M=1, L=-1, T=-2), True)
_atom("Torr", Fraction(101325, 760), _dims(M=1, L=-1, T=-2), False)
_atom("atm", 101325, _dims(M=1, L=-1, T=-2), False)
_atom("m[Hg]", Fraction("133322.387415"), _dims(M=1, L=-1, T=-2), True)
_atom("[psi]", Fraction("6894.757293168361"), _dims(M=1, L=-1, T=-2), False)
# acceleration of free fall
_atom("[g]", Fraction("9.80665"), _dims(L=1, T=-2), False)
# dimensionless ratios
_atom("%", Fraction(1, 100), _NONE, False)
_atom("[ppm]", Fraction(1, 10**6), _NONE, False)
_atom("[ppb]", Fraction(1, 10**9), _NONE, False)

_PREFIXES: dict[str, Fraction] = {
    "Y": Fraction(10) ** 24, "Z": Fraction(10) ** 21, "E": Fraction(10) ** 18,
    "P": Fraction(10) ** 15, "T": Fraction(10) ** 12, "G": Fraction(10) ** 9,
    "M": Fraction(10) ** 6, "k": Fraction(10) ** 3, "h": Fraction(10) ** 2,
    "da": Fraction(10), "d": Fraction(1, 10), "c": Fraction(1, 100),
    "m": Fraction(1, 1000), "u": Fraction(1, 10**6), "n": Fraction(1, 10**9),
    "p": Fraction(1, 10**12), "f": Fraction(1, 10**15), "a": Fraction(1, 10**18),
    "z": Fraction(1, 10**21), "y": Fraction(1, 10**24),
}
# longest prefix first so "da" wins over "d"
_PREFIX_ORDER = sorted(_PREFIXES, key=len, reverse=True)

_DIM_SYMBOLS = BASE_DIMENSIONS


@dataclass(frozen=True)
class Unit:
    """A parsed UCUM code: an exact factor to SI base units and a dimension vector."""

    code: str
    factor: Fraction
    dims: tuple[int, ...]
    #: Offset to kelvin; non-zero only for an absolute temperature atom.
    offset: Fraction = Fraction(0)
    #: True when the code is one temperature atom with exponent 1 (K, Cel, [degF]
    #: or a prefixed K), so an absolute conversion applies the offset.
    absolute_temperature: bool = False

    @property
    def dimension(self) -> str:
        """The dimension as a UCUM-like product of base units, e.g. ``m.s-2``; ``1`` if none."""
        parts = []
        for symbol, exponent in zip(_DIM_SYMBOLS, self.dims):
            if exponent:
                parts.append(symbol if exponent == 1 else f"{symbol}{exponent}")
        return ".".join(parts) or "1"

    @property
    def dimensionless(self) -> bool:
        return not any(self.dims)


# -- parser ------------------------------------------------------------------


class _Parser:
    """Recursive-descent parser for the UCUM case-sensitive term syntax."""

    def __init__(self, code: str):
        self.code = code
        self.pos = 0

    def fail(self, message: str) -> UnknownUnitError:
        return UnknownUnitError(f"invalid UCUM code {self.code!r}: {message}")

    def peek(self) -> str:
        return self.code[self.pos] if self.pos < len(self.code) else ""

    def parse(self) -> tuple[Fraction, tuple[int, ...], list[str]]:
        if not self.code:
            raise self.fail("empty code")
        if self.peek() == "/":
            self.pos += 1
            factor, dims, atoms = self.term()
            factor, dims = 1 / factor, tuple(-d for d in dims)
        else:
            factor, dims, atoms = self.term()
        if self.pos != len(self.code):
            raise self.fail(f"unexpected {self.peek()!r} at position {self.pos}")
        return factor, dims, atoms

    def term(self) -> tuple[Fraction, tuple[int, ...], list[str]]:
        factor, dims, atoms = self.component()
        while self.peek() in (".", "/"):
            operator = self.peek()
            self.pos += 1
            right_factor, right_dims, right_atoms = self.component()
            atoms = atoms + right_atoms
            if operator == ".":
                factor *= right_factor
                dims = tuple(a + b for a, b in zip(dims, right_dims))
            else:
                factor /= right_factor
                dims = tuple(a - b for a, b in zip(dims, right_dims))
        return factor, dims, atoms

    def component(self) -> tuple[Fraction, tuple[int, ...], list[str]]:
        char = self.peek()
        if char == "(":
            self.pos += 1
            result = self.term()
            if self.peek() != ")":
                raise self.fail("unbalanced parenthesis")
            self.pos += 1
            self.annotation()
            return result
        if char == "{":
            self.annotation()
            return Fraction(1), _NONE, []
        start = self.pos
        while self.pos < len(self.code) and self.code[self.pos] not in "./(){}":
            if self.code[self.pos] == "[":
                end = self.code.find("]", self.pos)
                if end < 0:
                    raise self.fail("unterminated [")
                self.pos = end + 1
            elif self.code[self.pos].isspace():
                raise self.fail("whitespace is not allowed")
            else:
                self.pos += 1
        text = self.code[start:self.pos]
        self.annotation()
        if not text:
            raise self.fail(f"missing unit at position {start}")
        return _simple(text, self.fail)

    def annotation(self) -> None:
        if self.peek() == "{":
            end = self.code.find("}", self.pos)
            if end < 0:
                raise self.fail("unterminated {")
            self.pos = end + 1


def _split_exponent(text: str) -> tuple[str, int]:
    """Split a trailing signed integer exponent off ``text`` (``s2`` -> ``s``, 2)."""
    index = len(text)
    while index > 0 and text[index - 1].isdigit():
        index -= 1
    if index == len(text):
        return text, 1
    if index > 0 and text[index - 1] in "+-":
        index -= 1
    if index == 0:  # a bare (signed) integer is a factor, not an exponent
        return text, 1
    return text[:index], int(text[index:])


def _simple(text: str, fail) -> tuple[Fraction, tuple[int, ...], list[str]]:
    if text.isdigit():
        if int(text) == 0:
            raise fail("a unit factor must be a positive integer")
        return Fraction(int(text)), _NONE, []
    body, exponent = _split_exponent(text)
    if body.isdigit() or exponent == 0:
        raise fail(f"{text!r} is not a unit")
    factor, dims, atom = _lookup(body, fail)
    return factor ** exponent, tuple(d * exponent for d in dims), [atom] if exponent == 1 else [f"{atom}^{exponent}"]


def _lookup(body: str, fail) -> tuple[Fraction, tuple[int, ...], str]:
    entry = _ATOMS.get(body)
    if entry is not None:
        return entry[0], entry[1], body
    for prefix in _PREFIX_ORDER:
        if body.startswith(prefix) and len(body) > len(prefix):
            atom = body[len(prefix):]
            entry = _ATOMS.get(atom)
            if entry is not None and entry[2]:
                return _PREFIXES[prefix] * entry[0], entry[1], atom
    raise fail(f"unknown unit atom {body!r}")


def parse(code: str) -> Unit:
    """Parse a UCUM code; raises :class:`UnknownUnitError` when it is not supported."""
    if not isinstance(code, str):
        raise UnknownUnitError(f"a UCUM code must be a string, got {type(code).__name__}")
    return _parse(code)


@functools.lru_cache(maxsize=1024)
def _parse(code: str) -> Unit:
    if code == "1":
        return Unit(code, Fraction(1), _NONE)
    factor, dims, atoms = _Parser(code).parse()
    absolute = len(atoms) == 1 and atoms[0] in ("K", "Cel", "[degF]") and dims == _dims(TH=1)
    offset = _ATOMS[atoms[0]][3] if absolute else Fraction(0)
    return Unit(code, factor, dims, offset, absolute)


def is_known(code: Any) -> bool:
    """True when ``code`` parses as a supported UCUM code."""
    try:
        parse(code)
    except UnitError:
        return False
    return True


def known_atoms() -> tuple[str, ...]:
    """The supported unit atoms (prefixable ones accept the UCUM metric prefixes)."""
    return tuple(sorted(_ATOMS))


def dimension(code: str) -> str:
    """The dimension of ``code`` as a product of base units (``m.s-2``)."""
    return parse(code).dimension


def compatible(left: str, right: str) -> bool:
    """True when both codes parse and share a dimension (so they convert)."""
    try:
        return parse(left).dims == parse(right).dims
    except UnitError:
        return False


def field_is_delta(field_schema: Mapping[str, Any] | None) -> bool:
    """True when a field schema is marked ``x-mhs-delta`` (a difference, not a level)."""
    return bool(isinstance(field_schema, Mapping) and field_schema.get("x-mhs-delta"))


def conversion(src: str, dst: str, *, delta: bool = False) -> tuple[float, float]:
    """Return ``(factor, offset)`` so that ``dst_value = src_value * factor + offset``.

    The offset is non-zero only between two absolute temperature scales and
    only when ``delta`` is false.
    """
    factor, offset = _exact_conversion(src, dst, delta)
    return _as_float(factor, "factor", src, dst), _as_float(offset, "offset", src, dst)


def _as_float(value: Fraction, label: str, src: str, dst: str) -> float:
    """``value`` as a float; :class:`UnitError` when the double range cannot represent it."""
    try:
        result = float(value)
    except OverflowError:
        result = math.inf
    if not math.isfinite(result) or (result == 0 and value != 0):
        raise UnitError(f"the {label} of {src!r} -> {dst!r} is outside the double range")
    return result


def _exact_conversion(src: str, dst: str, delta: bool) -> tuple[Fraction, Fraction]:
    left, right = parse(src), parse(dst)
    if left.dims != right.dims:
        raise UnitError(
            f"cannot convert {src!r} ({left.dimension}) to {dst!r} ({right.dimension})"
        )
    factor = left.factor / right.factor
    offset = Fraction(0)
    if not delta and left.absolute_temperature and right.absolute_temperature:
        offset = (left.offset - right.offset) / right.factor
    return factor, offset


def convert(
    value: float,
    src: str,
    dst: str,
    factor: float | None = None,
    *,
    offset: float | None = None,
    delta: bool = False,
) -> float:
    """Convert ``value`` from UCUM code ``src`` to ``dst``.

    ``factor`` (and ``offset``), when given, are the conversion a binding
    declares; each must equal the derived one within a relative tolerance of
    1e-9, otherwise :class:`UnitError` is raised (a binding can never declare a
    silently wrong conversion).  ``delta`` marks a temperature difference: no
    offset is applied (``x-mhs-delta`` fields).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"unit conversion requires a number, got {type(value).__name__}")
    if not _finite(value):
        raise UnitError("cannot convert a non-finite value (or an integer beyond the double range)")
    derived_factor, derived_offset = _exact_conversion(src, dst, delta)
    if factor is not None:
        _check_declared("factor", factor, derived_factor, src, dst)
    if offset is not None:
        _check_declared("offset", offset, derived_offset, src, dst)
    try:
        if derived_offset == 0:
            result = float(value * derived_factor) if isinstance(value, int) else value * float(derived_factor)
        else:
            result = float(Fraction(value) * derived_factor + derived_offset)
    except OverflowError:
        result = math.inf
    if not math.isfinite(result):
        raise UnitError(f"{_brief(value)} {src} is outside the double range in {dst}")
    return result


def _brief(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= 40 else text[:37] + "..."


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(value)
    except OverflowError:   # an int too large for a double
        return False


def _check_declared(label: str, declared: Any, derived: Fraction, src: str, dst: str) -> None:
    if isinstance(declared, bool) or not isinstance(declared, (int, float)) or not _finite(declared):
        raise UnitError(f"declared unit {label} must be a finite number, got {_brief(declared)}")
    expected = _as_float(derived, label, src, dst)
    # purely relative for any non-zero value (a tiny factor such as fL -> L is not
    # "close" to 0); an absolute slack only where the derived value is exactly 0
    if not math.isclose(float(declared), expected, rel_tol=_TOLERANCE, abs_tol=1e-12 if derived == 0 else 0.0):
        raise UnitError(
            f"declared {label} {declared!r} contradicts {src!r} -> {dst!r} (expected {expected!r})"
        )


def convert_unit(value: float, from_unit: str, to_unit: str) -> float:
    """Compatibility spelling of :func:`convert` used by the bridge runtime."""
    return convert(value, from_unit, to_unit)
