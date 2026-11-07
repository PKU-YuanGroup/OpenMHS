"""Canonical JSON, digests, ULIDs, timestamps and state hashing.

Everything in MHS that must be reproducible off the wire is built on this
module: receipts bind to ``input_digest``; states bind to ``state_hash``; the
evidence chain is a sequence of SHA-256 digests over canonical JSON; and the
``sha256:...`` digest strings are the currency of conformance reports.

Canonicalisation is **RFC 8785 (JSON Canonicalization Scheme, JCS)**:

* object keys are sorted by UTF-16 code units (RFC 8785 §3.2.3).  This is the
  ECMAScript ordering: an astral (non-BMP) key encoded as a surrogate pair
  sorts before BMP keys in the range U+E000..U+FFFF, unlike Python's code-point
  ordering;
* strings use the ECMAScript/JSON escaping rules: only ``"``, ``\\`` and the
  control characters U+0000..U+001F are escaped (``\\b``, ``\\t``, ``\\n``,
  ``\\f``, ``\\r`` where applicable, lowercase ``\\u00xx`` otherwise).  All
  other characters, including non-BMP characters, are emitted literally and
  encoded as UTF-8 (no surrogate escapes).  Lone surrogate code points are
  rejected because they are not Unicode scalar values and cannot be emitted as
  UTF-8;
* numbers are serialised with ECMAScript ``Number::toString`` semantics
  (RFC 8785 §3.2.2.3): shortest round-trip digits, fixed notation when the
  decimal exponent is in ``-6..20`` and ``1e+21``/``1e-7`` exponential notation
  otherwise, ``-0`` -> ``0``, and ``NaN``/``Infinity`` rejected;
* JSON integers are emitted as decimal only when they are exactly representable
  as IEEE-754 doubles, i.e. ``abs(n) <= 2**53 - 1``.  Larger Python integers
  raise :class:`CanonicalJSONError`: MHS revisions, sequence numbers and other
  counters above that boundary **MUST be carried as decimal strings** (see
  MHS-002 §6 / MHS-003 CAP-027), never as bare JSON numbers;
* no insignificant whitespace, no BOM, no trailing newline.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, MutableMapping

__all__ = [
    "CanonicalJSONError",
    "DigestError",
    "INTEGER_MAX",
    "jcs",
    "jcs_json",
    "digest",
    "digest_bytes",
    "digest_text",
    "is_digest",
    "sha256_hex",
    "ulid",
    "ulid_timestamp_ms",
    "is_ulid",
    "now_ms",
    "now_rfc3339",
    "parse_rfc3339",
    "rfc3339_from_ms",
    "state_hash",
    "remove_pointers",
    "json_pointer_get",
    "json_pointer_set",
    "json_pointer_delete",
    "deep_merge",
    "ZERO_DIGEST",
]

#: The all-zero digest, useful as a "no previous record" sentinel.
ZERO_DIGEST = "sha256:" + "0" * 64

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
_SHORT_ESCAPES = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
}

#: Largest integer magnitude that is exactly representable as an IEEE-754
#: double (2**53 - 1).  Larger JSON integers cannot be canonicalised without
#: losing information, so MHS carries revisions/sequence numbers above this
#: boundary as decimal strings instead.
INTEGER_MAX = 2**53 - 1


class CanonicalJSONError(ValueError):
    """Raised when a value cannot be represented as canonical JSON."""


class DigestError(ValueError):
    """Raised for malformed digest strings."""


# ---------------------------------------------------------------------------
# Canonical JSON
# ---------------------------------------------------------------------------


def _has_lone_surrogate(value: str) -> bool:
    """Return True when ``value`` contains a UTF-16 surrogate code point."""
    return any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def _encode_string(value: str) -> str:
    """Return the JSON string literal for ``value`` (RFC 8785 §3.2.2.2).

    Only quote, reverse solidus and U+0000..U+001F are escaped.  Non-BMP
    characters are emitted literally (UTF-8 at the byte layer); lone surrogates
    are rejected.
    """
    out = ['"']
    for char in value:
        code = ord(char)
        if char == '"':
            out.append('\\"')
        elif char == "\\":
            out.append("\\\\")
        elif code < 0x20:
            out.append(_SHORT_ESCAPES.get(code) or "\\u%04x" % code)
        elif 0xD800 <= code <= 0xDFFF:
            raise CanonicalJSONError(
                "canonical JSON cannot encode lone surrogate code point "
                f"U+{code:04X} (not a Unicode scalar value)"
            )
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _decimal_parts(value: float) -> tuple[str, int]:
    """Return shortest round-trip ``(digits, exponent)`` for a finite float.

    ``value == 0.<digits> * 10**(exponent+1)``; for example ``0.002`` becomes
    ``("2", -3)`` and ``333333333.3333333`` becomes ``("3333333333333333", 8)``.
    Python's ``repr`` already yields the shortest digit sequence that parses
    back to the same double, which is what ECMAScript ``Number::toString``
    requires; only the layout differs.
    """
    text = repr(abs(value))
    if "e" in text or "E" in text:
        mantissa, _, exponent_text = text.lower().partition("e")
        exponent = int(exponent_text)
        integer, _, fraction = mantissa.partition(".")
        digits_all = integer + fraction
        exponent += len(integer) - 1
    else:
        integer, _, fraction = text.partition(".")
        digits_all = integer + fraction
        exponent = len(integer) - 1
    significant = digits_all.lstrip("0")
    exponent -= len(digits_all) - len(significant)
    digits = significant.rstrip("0") or "0"
    return digits, exponent


def _encode_float(value: float) -> str:
    """Return ECMAScript ``Number::toString`` text for a finite non-zero float."""
    digits, exponent = _decimal_parts(value)
    count = len(digits)
    point = exponent + 1  # 0 < point <= count means "digits with a decimal point"
    if -6 <= exponent <= 20:
        if point >= count:
            text = digits + "0" * (point - count)
        elif point > 0:
            text = digits[:point] + "." + digits[point:]
        else:
            text = "0." + "0" * (-point) + digits
    else:
        mantissa = digits if count == 1 else digits[0] + "." + digits[1:]
        sign = "+" if exponent >= 0 else "-"
        text = f"{mantissa}e{sign}{abs(exponent)}"
    return ("-" if value < 0 else "") + text


def _encode_number(value: int | float) -> str:
    """Return the canonical JSON text for a JSON number."""
    if isinstance(value, bool):  # pragma: no cover - guarded by caller
        raise CanonicalJSONError("bool is not a number")
    if isinstance(value, int):
        if abs(value) > INTEGER_MAX:
            raise CanonicalJSONError(
                f"integer {value} is not exactly representable as an IEEE-754 "
                "double; MHS revisions and counters above 2**53-1 MUST be "
                "carried as decimal strings"
            )
        return str(value)
    if not math.isfinite(value):
        raise CanonicalJSONError(f"non-finite number {value!r} is not valid JSON")
    if value == 0:
        # Normalise -0.0 to 0 to keep digests stable (ECMAScript String(-0)).
        return "0"
    return _encode_float(value)


def _encode(value: Any, out: list[str]) -> None:
    """Append canonical JSON text for ``value`` to ``out``."""
    if value is None:
        out.append("null")
        return
    if value is True:
        out.append("true")
        return
    if value is False:
        out.append("false")
        return
    if isinstance(value, str):
        out.append(_encode_string(value))
        return
    if isinstance(value, (int, float)):
        out.append(_encode_number(value))
        return
    if isinstance(value, (list, tuple)):
        out.append("[")
        for index, item in enumerate(value):
            if index:
                out.append(",")
            _encode(item, out)
        out.append("]")
        return
    if isinstance(value, Mapping):
        pairs = list(value.items())
        for key, _item in pairs:
            _utf16_sort_key(key)
        out.append("{")
        for index, (key, item) in enumerate(
            sorted(pairs, key=lambda pair: _utf16_sort_key(pair[0]))
        ):
            if index:
                out.append(",")
            out.append(_encode_string(key))
            out.append(":")
            _encode(item, out)
        out.append("}")
        return
    raise CanonicalJSONError(
        f"value of type {type(value).__name__} is not JSON serialisable"
    )


def _utf16_sort_key(key: Any) -> bytes:
    """Return a sort key implementing RFC 8785's UTF-16 code-unit ordering."""
    if not isinstance(key, str):
        raise CanonicalJSONError(
            f"object keys must be strings, got {type(key).__name__}"
        )
    if _has_lone_surrogate(key):
        raise CanonicalJSONError(
            "canonical JSON cannot encode an object key with a lone surrogate "
            "code point"
        )
    return key.encode("utf-16-be")


def jcs(obj: Any) -> bytes:
    """Return RFC 8785 canonical JSON for ``obj`` as UTF-8 bytes.

    Raises :class:`CanonicalJSONError` for non-JSON values, lone surrogates,
    integers outside the IEEE-754 exact range, and ``NaN``/infinities.  The
    result contains no insignificant whitespace.
    """
    out: list[str] = []
    _encode(obj, out)
    return "".join(out).encode("utf-8")


def jcs_json(obj: Any) -> str:
    """Return canonical JSON for ``obj`` as a Unicode string."""
    return jcs(obj).decode("utf-8")


# ---------------------------------------------------------------------------
# Digests
# ---------------------------------------------------------------------------


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hex SHA-256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def digest_bytes(data: bytes) -> str:
    """Return ``"sha256:<hex>"`` for raw ``data``."""
    return "sha256:" + sha256_hex(data)


def digest_text(text: str) -> str:
    """Return ``"sha256:<hex>"`` for UTF-8 encoded ``text``."""
    return digest_bytes(text.encode("utf-8"))


def digest(obj: Any) -> str:
    """Return the ``sha256:...`` digest of the canonical JSON form of ``obj``."""
    return digest_bytes(jcs(obj))


def is_digest(value: Any) -> bool:
    """Return True when ``value`` is a well-formed ``sha256:<64 hex>`` digest."""
    return isinstance(value, str) and _DIGEST_RE.match(value) is not None


# ---------------------------------------------------------------------------
# ULID
# ---------------------------------------------------------------------------

_ULID_LOCK = threading.Lock()
_ulid_last_ms = 0
_ulid_last_random = 0


def _encode_ulid(ms: int, randomness: int) -> str:
    """Encode a 48-bit timestamp and 80-bit randomness as a Crockford ULID."""
    value = ((ms & ((1 << 48) - 1)) << 80) | (randomness & ((1 << 80) - 1))
    chars = []
    for _ in range(26):
        chars.append(_ULID_ALPHABET[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def ulid() -> str:
    """Return a monotonically increasing 26-character ULID string.

    Within the same millisecond successive calls increment the random part
    instead of repeating, so lexicographic order equals creation order.
    Thread-safe; no third-party dependencies.
    """
    global _ulid_last_ms, _ulid_last_random
    with _ULID_LOCK:
        now_ms = int(time.time() * 1000)
        if now_ms < _ulid_last_ms:  # clock moved backwards: keep monotonic
            now_ms = _ulid_last_ms
        if now_ms == _ulid_last_ms:
            _ulid_last_random += 1
            if _ulid_last_random >= (1 << 80):  # pragma: no cover - unreachable
                _ulid_last_ms += 1
                _ulid_last_random = 0
        else:
            _ulid_last_ms = now_ms
            _ulid_last_random = int.from_bytes(os.urandom(10), "big")
        return _encode_ulid(_ulid_last_ms, _ulid_last_random)


def ulid_timestamp_ms(value: str) -> int:
    """Return the Unix millisecond timestamp encoded in a ULID."""
    if not is_ulid(value):
        raise ValueError(f"not a ULID: {value!r}")
    number = 0
    for char in value[:10]:
        number = (number << 5) | _ULID_ALPHABET.index(char)
    return number


def is_ulid(value: Any) -> bool:
    """Return True when ``value`` is a 26-character Crockford ULID."""
    return isinstance(value, str) and _ULID_RE.match(value) is not None


# ---------------------------------------------------------------------------
# RFC 3339 timestamps
# ---------------------------------------------------------------------------


def now_rfc3339(*, timespec: str = "milliseconds") -> str:
    """Return the current UTC time as an RFC 3339 string with ``Z`` suffix.

    ``timespec`` is ``"milliseconds"`` (default, e.g. ``...58.900Z``) or
    ``"seconds"``.
    """
    moment = datetime.now(timezone.utc)
    if timespec == "seconds":
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def rfc3339_from_ms(epoch_ms: int) -> str:
    """Convert a Unix millisecond timestamp to an RFC 3339 UTC string."""
    moment = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def parse_rfc3339(value: str) -> datetime:
    """Parse an RFC 3339 date-time string into a timezone-aware datetime."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"not an RFC 3339 timestamp: {value!r}")
    text = value.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def now_ms() -> int:
    """Return the current Unix time in milliseconds."""
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# JSON pointers and state hashes
# ---------------------------------------------------------------------------


def _unescape_token(token: str) -> str:
    """Decode one JSON Pointer reference token."""
    return token.replace("~1", "/").replace("~0", "~")


def _pointer_tokens(pointer: str) -> list[str]:
    """Split a JSON Pointer into decoded tokens."""
    if pointer in ("", "#"):
        return []
    text = pointer[1:] if pointer.startswith("#") else pointer
    if text.startswith("/"):
        text = text[1:]
    return [_unescape_token(part) for part in text.split("/")] if text else []


def _escape_token(token: str) -> str:
    """Encode one JSON Pointer reference token."""
    return str(token).replace("~", "~0").replace("/", "~1")


def json_pointer_get(document: Any, pointer: str) -> Any:
    """Return the value at ``pointer`` inside ``document``; raise KeyError if absent."""
    node = document
    for token in _pointer_tokens(pointer):
        if isinstance(node, Mapping):
            if token not in node:
                raise KeyError(pointer)
            node = node[token]
        elif isinstance(node, (list, tuple)):
            index = int(token)
            node = node[index]
        else:
            raise KeyError(pointer)
    return node


def json_pointer_delete(document: Any, pointer: str) -> bool:
    """Delete the value at ``pointer`` in-place; return True when it existed."""
    tokens = _pointer_tokens(pointer)
    if not tokens:
        return False
    node: Any = document
    for token in tokens[:-1]:
        if isinstance(node, MutableMapping) and token in node:
            node = node[token]
        elif isinstance(node, list) and token.isdigit() and int(token) < len(node):
            node = node[int(token)]
        else:
            return False
    last = tokens[-1]
    if isinstance(node, MutableMapping) and last in node:
        del node[last]
        return True
    if isinstance(node, list) and last.isdigit() and int(last) < len(node):
        del node[int(last)]
        return True
    return False


def json_pointer_set(document: MutableMapping[str, Any], pointer: str, value: Any) -> None:
    """Set ``value`` at ``pointer`` inside ``document``, creating objects as needed."""
    tokens = _pointer_tokens(pointer)
    if not tokens:
        raise ValueError("cannot replace the document root with json_pointer_set")
    node: Any = document
    for token in tokens[:-1]:
        if isinstance(node, list):
            node = node[int(token)]
            continue
        if token not in node or not isinstance(node[token], (dict, list)):
            node[token] = {}
        node = node[token]
    node[tokens[-1]] = value


def remove_pointers(source: Any, pointers: Iterable[str] | None) -> Any:
    """Return a deep copy of ``source`` with each JSON Pointer removed.

    Missing pointers are ignored (state hash exclusions are advisory), which
    keeps hashing robust when optional volatile fields are absent.
    """
    result = copy.deepcopy(source)
    for pointer in pointers or ():
        try:
            json_pointer_delete(result, pointer)
        except (KeyError, IndexError, ValueError):  # pragma: no cover - defensive
            continue
    return result


def state_hash(state: Any, exclusions: Iterable[str] | None = None) -> str:
    """Return the canonical digest of a state document minus ``exclusions``.

    ``exclusions`` are JSON Pointers (e.g. ``"/mono_ms"``) to volatile fields
    that must not participate in the hash.  The result is
    ``"sha256:" + hex(SHA-256(JCS(state_without_exclusions)))``.
    """
    return digest(remove_pointers(state, exclusions))


# ---------------------------------------------------------------------------
# Deep merge (used by resource.write patches and state updates)
# ---------------------------------------------------------------------------


def deep_merge(base: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``patch`` into a copy of ``base``.

    Objects merge key-by-key; any non-object value (including lists) replaces
    the existing value; ``None`` in the patch sets the key to ``null`` rather
    than deleting it.
    """
    result: dict[str, Any] = copy.deepcopy(dict(base))
    for key, value in patch.items():
        if (
            key in result
            and isinstance(result[key], Mapping)
            and isinstance(value, Mapping)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result
