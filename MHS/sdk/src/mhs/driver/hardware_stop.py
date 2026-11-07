"""A user-authorized hardware stop cited to a fetched companion (user decision 4, 2026-11-05).

A hardware ``Driver`` may set ``companion_stop`` to exactly two entries, one ``stop`` and one
``readback``. Each names a member that is not on the package clone's surface, a
``companion:<alias>/<path>:<LINE>`` ref, and a ``shows`` token that those lines contain as a word.
The card's companion must set ``hardware_stop`` true and ``lock``. The members are exempt from the
package surface only then, and every call of them must be in the e-stop phase, the stop before the
read-back, with at least one such pair. ROS companion scope is unchanged. A class that declares
this still needs a human ``reviewed_by`` with scope ``hardware`` before a hardware backend may
start (:func:`mhs.driver.loader.review_problem`); nothing here signs one.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .upstream import parse_source_ref

_MEMBER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KEYS = frozenset({"role", "member", "ref", "shows"})


def declares_companion_stop(cls: Any) -> bool:
    """True when ``cls`` sets a non-empty ``companion_stop`` (a malformed value still counts).

    An empty tuple or an absent attribute does not. The loader then refuses a hardware backend
    until a human signs ``reviewed_by`` with scope ``hardware``.
    """
    raw = getattr(cls, "companion_stop", None)
    return raw is not None and raw != () and raw != []


def check_hardware_stop(ctx: Any, gate: Any, surface_names: set[str]) -> set[str]:
    """Report companion-stop defects and return members exempt from the package surface.

    Returns an empty set when the class declares nothing, or when the declaration is not one the
    card authorizes (those names stay ``NOT_UPSTREAM``). A declaration that is authorized is
    exempt even when a later call-order error fails the gate.
    """
    cls = getattr(ctx, "cls", None)
    if cls is None or not declares_companion_stop(cls):
        return set()
    entries, shape_errors = _parse(getattr(cls, "companion_stop", None))
    for text in shape_errors:
        gate.error("HARDWARE_STOP_SCOPE", text, "driver.py")
    if shape_errors:
        return set()
    mode = _mode(ctx, cls)
    if mode != "hardware":
        gate.error("HARDWARE_STOP_SCOPE", "companion_stop is only for a driver whose mode is hardware", "driver.py")
        return set()
    family = getattr(ctx, "family", None)
    if family not in ("direct", "python-object"):
        gate.error("HARDWARE_STOP_SCOPE", "companion_stop is only for a direct or python-object driver"
                   + (f" (this one is {family})" if family else " (its family is unknown)"), "driver.py")
        return set()
    by_role = {item["role"]: item for item in entries}
    exempt: set[str] = set()
    authorized = True
    for item in entries:
        parsed = parse_source_ref(item["ref"])
        source = ctx.companions.get(parsed[0]) if parsed is not None and parsed[0] is not None else None
        if source is None or not getattr(source, "hardware_stop", False) or not getattr(source, "lock", None):
            gate.error("HARDWARE_STOP_SCOPE", f"{item['member']} cites {item['ref']!r}, which is not a lock "
                       "companion declared hardware_stop on the card", "driver.py")
            authorized = False
            continue
        if item["member"] in surface_names:
            gate.error("HARDWARE_STOP_SURFACE", f"{item['member']} is a member of the package clone; a companion "
                       "stop member is one the package clone does not define", item["member"])
            authorized = False
            continue
        if not _shows(source, parsed[1], item["shows"]):
            gate.error("HARDWARE_STOP_REF", f"{item['member']} cites {item['ref']!r}, which does not show "
                       f"{item['shows']!r} as a word", item["member"], str(item["ref"]))
            authorized = False
            continue
        exempt.add(item["member"])
    if not authorized or len(exempt) != 2:
        return set()
    _check_calls(ctx, gate, by_role["stop"]["member"], by_role["readback"]["member"])
    return exempt


def _mode(ctx: Any, cls: Any) -> Any:
    model = getattr(ctx, "model", None)
    mode = getattr(model, "mode", None) if model is not None else None
    return getattr(cls, "mode", None) if mode is None else mode


def _parse(raw: Any) -> tuple[list[dict[str, str]], list[str]]:
    if not isinstance(raw, (tuple, list)) or len(raw) != 2 or not all(isinstance(item, Mapping) for item in raw):
        return [], ["companion_stop must be exactly two objects, one role stop and one role readback"]
    errors: list[str] = []
    entries: list[dict[str, str]] = []
    for index, item in enumerate(raw):
        extra = set(item) - _KEYS
        role, member, ref, shows = item.get("role"), item.get("member"), item.get("ref"), item.get("shows")
        where = f"companion_stop[{index}]"
        if extra:
            errors.append(f"{where} has unknown keys {sorted(extra)}")
        if role not in ("stop", "readback"):
            errors.append(f"{where} role must be stop or readback")
        if not isinstance(member, str) or _MEMBER.match(member) is None or member.startswith("_"):
            errors.append(f"{where} member must be a public identifier")
        parsed = parse_source_ref(ref) if isinstance(ref, str) else None
        if parsed is None or parsed[0] is None:
            errors.append(f"{where} ref must be companion:<alias>/path:LINE")
        if not isinstance(shows, str) or "\n" in shows or not 2 <= len(shows) <= 80:
            errors.append(f"{where} shows must be one token of 2 to 80 characters")
        if not errors:
            entries.append({"role": str(role), "member": str(member), "ref": str(ref), "shows": str(shows)})
    if not errors and sorted(item["role"] for item in entries) != ["readback", "stop"]:
        errors.append("companion_stop needs exactly one stop entry and one readback entry")
    if not errors and entries[0]["member"] == entries[1]["member"]:
        errors.append("companion_stop stop and readback must name different members")
    return ([] if errors else entries), errors


def _shows(source: Any, ref: Any, token: str) -> bool:
    tree = getattr(source, "tree", None)
    if tree is None:
        return False
    document = tree.read_text(ref.path)
    if not isinstance(document, str):
        return False
    lines = document.splitlines()
    if ref.end > len(lines) or ref.line < 1:
        return False
    cited = "\n".join(lines[ref.line - 1:ref.end])
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", cited) is not None


def _check_calls(ctx: Any, gate: Any, stop_name: str, read_name: str) -> None:
    names = {stop_name, read_name}
    confirmed = False
    logs = getattr(ctx, "logs", None) or []
    for log in logs:
        relevant = [call for call in getattr(log, "calls", ())
                    if getattr(call, "kind", "call") == "call" and getattr(call, "name", None) in names]
        for call in relevant:
            if call.phase != "estop":
                gate.error("HARDWARE_STOP_SCOPE", f"{call.name} was called in phase {call.phase}; a companion stop "
                           "member runs only during the e-stop", call.name)
        seen_stop = False
        for call in relevant:
            if call.phase != "estop":
                continue
            if call.name == stop_name:
                seen_stop = True
            elif call.name == read_name:
                if not seen_stop:
                    gate.error("HARDWARE_STOP_UNCONFIRMED", "the read-back ran before the stop during the e-stop",
                               read_name)
                else:
                    confirmed = True
    if not confirmed:
        gate.error("HARDWARE_STOP_UNCONFIRMED", "the e-stop did not call the stop member and then the read-back "
                   "member", stop_name)
