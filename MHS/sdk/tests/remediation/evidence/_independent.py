"""Independent recomputation oracles for the CODE/PROTO remediation tests.

This module deliberately does **not** import :mod:`mhs.canonical`: it is a
second, small implementation of the RFC 8785 rules used to check the library's
output rather than echo it.  Numbers use a shortest-round-trip search over
Python ``format()`` precisions (instead of ``repr``); strings and object-key
ordering are implemented from the RFC text; chain digests are recomputed with
:mod:`hashlib` over those independent bytes.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping


class IndependentCanonicalError(ValueError):
    """Raised for values RFC 8785 cannot represent."""


_MAX_INT = 2**53 - 1

_SHORT = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
}


def _encode_string(value: str) -> str:
    out = ['"']
    for char in value:
        code = ord(char)
        if char == '"':
            out.append('\\"')
        elif char == "\\":
            out.append("\\\\")
        elif code < 0x20:
            out.append(_SHORT.get(code) or "\\u%04x" % code)
        elif 0xD800 <= code <= 0xDFFF:
            raise IndependentCanonicalError("lone surrogate in string")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _shortest_digits(value: float) -> tuple[str, int]:
    """Find the shortest round-trip digit string using ``format`` precision."""
    magnitude = abs(value)
    text = ""
    for precision in range(1, 18):
        candidate = format(magnitude, f".{precision}g")
        if float(candidate) == magnitude:
            text = candidate.lower()
            break
    else:  # pragma: no cover - 17 significant digits always suffice
        text = repr(magnitude)
    if "e" in text:
        mantissa, _, exponent_text = text.partition("e")
        exponent = int(exponent_text)
        whole, _, fraction = mantissa.partition(".")
        digits = whole + fraction
        exponent += len(whole) - 1
    else:
        whole, _, fraction = text.partition(".")
        digits = whole + fraction
        exponent = len(whole) - 1
    significant = digits.lstrip("0")
    exponent -= len(digits) - len(significant)
    return (significant.rstrip("0") or "0"), exponent


def _encode_number(value: int | float) -> str:
    if isinstance(value, bool):
        raise IndependentCanonicalError("bool is not a number")
    if isinstance(value, int):
        if abs(value) > _MAX_INT:
            raise IndependentCanonicalError("integer outside IEEE-754 exact range")
        return str(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise IndependentCanonicalError("non-finite number")
    if value == 0:
        return "0"
    digits, exponent = _shortest_digits(value)
    count = len(digits)
    point = exponent + 1
    if -6 <= exponent <= 20:
        if point >= count:
            body = digits + "0" * (point - count)
        elif point > 0:
            body = digits[:point] + "." + digits[point:]
        else:
            body = "0." + "0" * (-point) + digits
    else:
        mantissa = digits if count == 1 else digits[0] + "." + digits[1:]
        body = f"{mantissa}e{'+' if exponent >= 0 else '-'}{abs(exponent)}"
    return ("-" if value < 0 else "") + body


def _encode(value: Any, out: list[str]) -> None:
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, str):
        out.append(_encode_string(value))
    elif isinstance(value, (int, float)):
        out.append(_encode_number(value))
    elif isinstance(value, (list, tuple)):
        out.append("[")
        for index, item in enumerate(value):
            if index:
                out.append(",")
            _encode(item, out)
        out.append("]")
    elif isinstance(value, Mapping):
        keyed: list[tuple[bytes, str, Any]] = []
        for key, item in value.items():
            if not isinstance(key, str):
                raise IndependentCanonicalError("non-string object key")
            keyed.append((key.encode("utf-16-be"), key, item))
        out.append("{")
        for index, (_sort, key, item) in enumerate(sorted(keyed, key=lambda row: row[0])):
            if index:
                out.append(",")
            out.append(_encode_string(key))
            out.append(":")
            _encode(item, out)
        out.append("}")
    else:
        raise IndependentCanonicalError(f"unsupported type {type(value).__name__}")


def independent_jcs(value: Any) -> bytes:
    """Return independently encoded RFC 8785 bytes for ``value``."""
    out: list[str] = []
    _encode(value, out)
    return "".join(out).encode("utf-8")


def independent_genesis_digest(document: Mapping[str, Any]) -> str:
    """Recompute ``digest_0`` from a genesis document."""
    core = {
        key: value
        for key, value in document.items()
        if key not in ("digest", "seq", "kind")
    }
    return "sha256:" + hashlib.sha256(independent_jcs(core)).hexdigest()


def independent_record_digest(record: Mapping[str, Any], prev_digest: str) -> str:
    """Recompute ``sha256(JCS(record without evidence) || prev_digest)``."""
    core = {key: value for key, value in record.items() if key != "evidence"}
    payload = independent_jcs(core) + prev_digest.encode("ascii")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def recompute_chain(
    genesis_document: Mapping[str, Any],
    receipts: Iterable[Mapping[str, Any]],
) -> tuple[list[str], str]:
    """Return ``(record_digests, terminal_head)`` for a genesis + receipts."""
    prev = independent_genesis_digest(genesis_document)
    digests: list[str] = []
    for record in receipts:
        prev = independent_record_digest(record, prev)
        digests.append(prev)
    return digests, prev
