"""Machine-readable normative requirement matrix for the executable suite.

The suite's award is derived from this matrix, not from whichever test files
happen to be registered (SPEC-001).  Every *mandatory* method required at a
level is probed at dispatch (``presence.py``); a missing method caps the level at
the previous one.  Required warnings and skips never award a level
(CON-018/CON-027).

``applicability.json`` is the auditable inventory of all 580 numbered normative
requirements.  It records, for every id, its profile/level scope and either an
executable check or an explicit disposition with a spec basis.  Reports quote the
counts verbatim and never claim that the executable ladder covers all 580 ids.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

#: Methods flagged **M** in MHS-002 §3, introduced at each level (PROTO-016).
REQUIRED_METHODS: dict[str, tuple[str, ...]] = {
    "CL1": (
        "mhs.hello",
        "mhs.devices.list",
        "mhs.devices.get",
        "mhs.schema.get",
        "mhs.session.open",
        "mhs.session.close",
        "mhs.resource.read",
        "mhs.evidence.export",
    ),
    "CL2": (
        "mhs.command",
        "mhs.subscribe",
        "mhs.unsubscribe",
        "mhs.operations.get",
    ),
    "CL3": (
        "mhs.operations.cancel",
        "mhs.safety.status",
    ),
    "CL4": (),
    "CL5": (),
}

#: Tests a device mode excuses (documented, never silently dropped), keyed on
#: the mode of the device the test targets -- not on the claimed profile string,
#: which a caller chooses.  Hardware is never required to pass replay
#: (CON-017, CON-026c): FID-016 and FID-025 are skipped there and the skip does
#: not cap the level.  Wired into ``TestCase.is_required`` through
#: ``SuiteContext.exempt``.
MODE_EXEMPTIONS: dict[str, tuple[str, ...]] = {
    "hardware": ("FID-016", "FID-025"),
}
#: Former name (it was keyed on the profile and never consulted); kept as an alias.
PROFILE_EXEMPTIONS = MODE_EXEMPTIONS

APPLICABILITY_FILE = Path(__file__).with_name("applicability.json")
APPLICABILITY_VERSION = "1.0.0"


def required_methods(level: str) -> tuple[str, ...]:
    """Return every mandatory method at or below ``level``."""
    order = ("CL0", "CL1", "CL2", "CL3", "CL4", "CL5")
    if level not in order:
        return ()
    methods: list[str] = []
    for current in order[: order.index(level) + 1]:
        methods.extend(REQUIRED_METHODS.get(current, ()))
    return tuple(methods)


def methods_introduced_at(level: str) -> tuple[str, ...]:
    """Return the mandatory methods introduced *at* ``level`` (PROTO-016)."""

    return REQUIRED_METHODS.get(level, ())


def requirement_ids_for_methods(level: str) -> list[str]:
    """Normative anchors for the method-presence check."""
    return ["PROTO-016", "PROTO-017", "CON-014", "CON-018"] if required_methods(level) else []


@lru_cache(maxsize=1)
def applicability() -> dict[str, Any]:
    """Load and validate the 580-id applicability inventory."""

    document = json.loads(APPLICABILITY_FILE.read_text(encoding="utf-8"))
    errors = validate_applicability(document)
    if errors:
        raise RuntimeError("invalid conformance applicability inventory: " + "; ".join(errors[:5]))
    return document


def applicability_entries() -> dict[str, dict[str, Any]]:
    """Return ``{requirement_id: entry}`` for every numbered requirement."""

    return dict(applicability()["requirements"])


def validate_applicability(document: Mapping[str, Any] | None = None) -> list[str]:
    """Structural checks for the applicability inventory (returns errors)."""

    doc = document if document is not None else json.loads(APPLICABILITY_FILE.read_text(encoding="utf-8"))
    errors: list[str] = []
    requirements = doc.get("requirements")
    if not isinstance(requirements, Mapping):
        return ["requirements must be an object"]
    expected = int((doc.get("counts") or {}).get("normative_ids") or 0)
    if len(requirements) != expected:
        errors.append(f"requirements has {len(requirements)} entries, counts.normative_ids={expected}")
    seen_dispositions = {"executable", "out_of_profile", "editorial", "report_process", "level_not_claimed", "not_verified"}
    for requirement_id, entry in requirements.items():
        if not isinstance(entry, Mapping):
            errors.append(f"{requirement_id}: entry is not an object")
            continue
        if entry.get("id") != requirement_id:
            errors.append(f"{requirement_id}: id mismatch")
        disposition = entry.get("disposition")
        if disposition not in seen_dispositions:
            errors.append(f"{requirement_id}: unknown disposition {disposition!r}")
        if disposition == "executable" and not entry.get("checks"):
            errors.append(f"{requirement_id}: executable entry has no check")
        if disposition == "not_verified":
            if not entry.get("basis"):
                errors.append(f"{requirement_id}: not_verified entry needs a basis")
        elif not entry.get("basis"):
            errors.append(f"{requirement_id}: disposition needs a spec basis")
        if not entry.get("profiles"):
            errors.append(f"{requirement_id}: profiles is empty")
        if not isinstance(entry.get("levels"), list):
            errors.append(f"{requirement_id}: levels must be an array")
    counts = doc.get("counts") or {}
    tally = {key: 0 for key in seen_dispositions}
    for entry in requirements.values():
        if isinstance(entry, Mapping):
            tally[str(entry.get("disposition"))] = tally.get(str(entry.get("disposition")), 0) + 1
    for key, value in tally.items():
        if int(counts.get(key, -1)) != value:
            errors.append(f"counts.{key}={counts.get(key)!r} does not match inventory ({value})")
    return errors


def _entry_profile_scope(entry: Mapping[str, Any], profile: str) -> str:
    """Classify one requirement for one report profile."""

    disposition = str(entry.get("disposition"))
    if disposition == "executable":
        return "executable"
    if disposition in {"editorial", "report_process", "level_not_claimed"}:
        return disposition
    profiles = [str(item) for item in entry.get("profiles") or []]
    if disposition == "out_of_profile":
        if profiles and profile not in profiles:
            return "out_of_profile"
        # The inventory has a bridge/host/registry check this suite cannot run:
        # for that profile it is an unverified gap, not a profile exclusion.
        return "not_verified"
    return disposition


def applicability_summary(
    profile: str,
    level: str,
    executed_test_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Counts quoted in every report limitation.

    ``checked`` means the requirement has an executable check in this suite;
    ``tested`` means at least one such check ran in *this* report.  Requirements
    with no check are either explicitly dispositioned for this profile or counted
    as ``not_verified``.  ``checked + dispositioned + not_verified`` equals the
    normative total; ``tested`` is a subset of ``checked``.
    """

    entries = applicability_entries()
    executed = {str(item) for item in executed_test_ids}
    checked = tested = 0
    dispositioned = 0
    not_verified = 0
    breakdown = {
        "out_of_profile": 0,
        "editorial": 0,
        "report_process": 0,
        "level_not_claimed": 0,
    }
    for entry in entries.values():
        scope = _entry_profile_scope(entry, profile)
        if scope == "executable":
            checked += 1
            checks = {str(item) for item in entry.get("checks") or []}
            if checks & executed:
                tested += 1
            continue
        if scope == "not_verified":
            not_verified += 1
            continue
        dispositioned += 1
        breakdown[scope] = breakdown.get(scope, 0) + 1
    total = len(entries)
    return {
        "profile": profile,
        "level": level,
        "normative_ids": total,
        "checked": checked,
        "tested": tested,
        "dispositioned": dispositioned,
        "not_verified": not_verified,
        "breakdown": breakdown,
        "artifact": APPLICABILITY_FILE.name,
        "artifact_version": APPLICABILITY_VERSION,
    }


def coverage_disclosure(
    profile: str,
    level: str,
    executed_test_ids: Iterable[str] = (),
) -> str:
    """One deterministic limitation line for a conformance report."""

    summary = applicability_summary(profile, level, executed_test_ids)
    breakdown = summary["breakdown"]
    return (
        "requirement coverage (MHS-001 §5, SPEC-001): "
        f"{summary['normative_ids']} normative ids; "
        f"checked={summary['checked']} tested={summary['tested']} "
        f"dispositioned={summary['dispositioned']} "
        f"(out_of_profile={breakdown['out_of_profile']}, editorial={breakdown['editorial']}, "
        f"report_process={breakdown['report_process']}, level_not_claimed={breakdown['level_not_claimed']}) "
        f"not_verified={summary['not_verified']}; "
        "the award covers only the executed checks and is not a claim of full "
        f"normative coverage (inventory: mhs/conformance/{summary['artifact']})."
    )


def disposition_basis(requirement_id: str) -> str:
    """Spec basis recorded for a requirement (empty when unknown)."""

    entry = applicability_entries().get(requirement_id)
    return str((entry or {}).get("basis") or "")


def checks_for(requirement_id: str) -> tuple[str, ...]:
    """Executable checks recorded for a requirement (empty when none)."""

    entry = applicability_entries().get(requirement_id) or {}
    return tuple(str(item) for item in entry.get("checks") or [])
