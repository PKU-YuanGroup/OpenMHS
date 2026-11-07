"""Conformance report construction, digesting, validation, recomputation and comparison.

The report format is frozen by ``MHS/schema/conformance-report.schema.json``.
``report_digest`` is the canonical JCS SHA-256 digest of the report *without* the
``report_digest`` member, so anyone can recompute it offline.

A digest only proves that a report has not changed since someone computed it.
:func:`validate_report` therefore also recomputes ``level_achieved`` from the
per-test ``required`` flags and the suite's level table (CON-019), refuses
unknown test ids, flags required tests whose ``required`` flag was cleared,
required tests that are missing, missing ``required`` flags and the mandatory
disclaimers (CON-003).  Every report is validated this way: the last reports
of the lenient suites (before 1.2.0, without flags or disclaimers) were
regenerated in WP-07 milestone 07b, so a report that claims an older suite
version is refused instead of being read leniently (a downgraded version
string can no longer relax validation).  :func:`compare_reports` compares a
report with a fresh re-run of the suite (``python -m mhs.conformance verify``).

The schema has no "no level" value, so ``level_achieved: CL0`` is also the
floor of a report whose required CL0 tests failed.  Such a report leads its
``limitations`` with a line starting with :data:`CL0_NOT_ACHIEVED`;
:func:`level_awarded` returns ``None`` for it (CON-018: no level is awarded
when a required test fails), and :func:`semantic_errors` rejects a strict
report that hides the failure.
"""

from __future__ import annotations

import copy
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from mhs import canonical

REPORT_VERSION = "1.1.0"
#: 1.3.0 (WP-07 milestone 07b): SAFE-014 requires MHS.SAFETY.ENVELOPE_VIOLATION
#: for every limited path, resolved like the runtime; OP-001 pins the revision rule.
#: 1.4.0 (RE-ENABLE-AND-TERMINAL-STOP.md, GOV-026 MINOR): TSAFE-001 also checks a declared
#: re-enable (CORE-086) and a declared terminal e-stop (CORE-087, SAFE-048); SAFE-041 skips a
#: terminal device; the runner gives the test after a terminal e-stop a new endpoint (CON-022).
#: Every test id and every assertion on a device that declares neither field is unchanged (CON-013).
#: 1.4.1 (SAFE031-INPUT-FREE-PERMITS.md, GOV-026 PATCH, a test bug): SAFE-031 no longer skips a gated
#: binding whose input schema admits only the empty object (no second valid input exists, so the
#: distinct-input presentation is recorded as not applicable); it tests the refusal without a permit,
#: a presentation with an undeclared field (refused before any effect, permit kept), other gated
#: input-free bindings of the device, acceptance and single use.  Every other binding is tested as in
#: 1.4.0, byte for byte; no test id was added, retired or reused.
SUITE_VERSION = "1.4.1"
SUITE_NAME = "mhs-conformance"
REPORT_SCHEMA = "conformance-report.schema.json"

#: The oldest suite whose reports are accepted: they carry ``required`` flags,
#: ``spec_ref``, ``subject.manifest_digest`` and disclaimers.
_STRICT_FROM = (1, 2, 0)
#: Test ids of suite 1.1.0, the last lenient suite (kept for tools that
#: inspect old reports; a report of that suite is no longer valid).
SUITE_1_1_TEST_IDS = frozenset((
    "ADPT-005", "EVID-010", "EVID-015", "EVID-016", "FID-005", "FID-016", "FID-025", "MODE-002", "MODE-005",
    "OP-001", "OP-003", "OP-004", "OP-005", "OP-011", "OP-013", "PROTO-011", "PROTO-013", "PROTO-014",
    "PROTO-021", "PROTO-023", "PROTO-024", "PROTO-027", "PROTO-030", "SAFE-001", "SAFE-011", "SAFE-014",
    "SAFE-031", "SAFE-050", "SESS-001", "SESS-005", "TPROTO-901", "TPROTO-902", "TPROTO-903", "TSAFE-001",
))
#: First words of the ``limitations`` line of a report whose required CL0 tests did not pass.
CL0_NOT_ACHIEVED = "NO LEVEL ACHIEVED:"

__all__ = [
    "CL0_NOT_ACHIEVED",
    "DISCLAIMER_TEXT",
    "REPORT_SCHEMA",
    "REPORT_VERSION",
    "SUITE_NAME",
    "SUITE_VERSION",
    "build_report",
    "cl0_blockers",
    "cl0_limitation",
    "compare_reports",
    "default_disclaimers",
    "environment",
    "finalize_report",
    "level_awarded",
    "load_report",
    "manifest_digest",
    "recompute_level",
    "report_digest",
    "save_report",
    "semantic_errors",
    "validate_report",
    "verify_report_digest",
]

#: CON-003 / MHS-001 §8.5 disclaimer texts, by ``disclaimers[].id``.
DISCLAIMER_TEXT: dict[str, str] = {
    "not_certified": (
        "MHS conformance is a behavioural test result, not a safety certification. "
        "MHS.SAFETY.NOT_CERTIFIED: MHS is not a safety-rated channel; an independent hardware "
        "emergency stop is required."
    ),
    "simulation_only": (
        "Simulation conformance does not establish equivalence to the physical device; see the "
        "fidelity gaps in the device manifest."
    ),
    "contract_checked_only": (
        "A fake or simulated backend standing in for hardware was tested: this is contract_checked "
        "evidence only, never an MHS-Device hardware level."
    ),
    "self_issued": (
        "Self-issued report (issuer.kind self): it records the subject's own run of the suite; recompute "
        "it with 'python -m mhs.conformance verify'."
    ),
}


def _non_affiliation() -> str:
    try:
        from mhs._ids import NON_AFFILIATION

        return str(NON_AFFILIATION)
    except Exception:  # noqa: BLE001 - identifiers are optional for a standalone suite
        return "OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic."


def default_disclaimers(manifests: Iterable[Mapping[str, Any]] = (), *, issuer_kind: str = "self") -> list[dict[str, str]]:
    """The disclaimers every report carries, plus the ones its device modes call for."""

    manifests = [item for item in manifests if isinstance(item, Mapping)]
    out = [{"id": "not_certified", "text": DISCLAIMER_TEXT["not_certified"]},
           {"id": "not_affiliated", "text": _non_affiliation()}]
    if any(item.get("mode") in ("simulated", "hybrid", "replay") for item in manifests):
        out.append({"id": "simulation_only", "text": DISCLAIMER_TEXT["simulation_only"]})
    if any(item.get("mode") == "simulated" and (item.get("models")
                                               or (item.get("fidelity") or {}).get("engine") == "fake")
           for item in manifests):
        out.append({"id": "contract_checked_only", "text": DISCLAIMER_TEXT["contract_checked_only"]})
    if issuer_kind == "self":
        out.append({"id": "self_issued", "text": DISCLAIMER_TEXT["self_issued"]})
    return out


def environment(*, endpoint_ids: Iterable[str] = (), notes: str | None = None) -> dict[str, Any]:
    """Build the ``environment`` block for a report."""

    block: dict[str, Any] = {
        "os": f"{platform.system()} {platform.release()}".strip(),
        "python": sys.version.split()[0],
        "date": canonical.now_rfc3339(),
        "suite": f"{SUITE_NAME} {SUITE_VERSION}",
        "endpoint_ids": [str(item) for item in endpoint_ids],
    }
    if notes:
        block["notes"] = str(notes)
    return block


_make_environment = environment


def report_digest(report: Mapping[str, Any]) -> str:
    """Recompute the canonical report digest.

    MHS-001 section 7.2: ``sha256(JCS(report_body))`` where ``report_body`` is the
    report with ``report_digest`` removed and ``issuer.signature`` (when present)
    removed from the issuer object.
    """

    body = {str(key): value for key, value in report.items() if key != "report_digest"}
    issuer = body.get("issuer")
    if isinstance(issuer, Mapping) and "signature" in issuer:
        body["issuer"] = {str(k): v for k, v in issuer.items() if k != "signature"}
    return canonical.digest(body)


def manifest_digest(manifests: Iterable[Mapping[str, Any]]) -> str:
    """Digest of the device contracts under test (CON-040/041 re-issue triggers).

    Volatile members are left out so the same driver gives the same digest on
    every run: ``instance_id``, resource ``state`` and ``revision``, the
    ``conformance`` claim (which cites a report), ``provenance`` and
    ``signatures``.  Devices are ordered by ``device_id``.
    """

    views = []
    for manifest in manifests:
        if not isinstance(manifest, Mapping):
            continue
        view = {key: copy.deepcopy(value) for key, value in manifest.items()
                if key not in ("instance_id", "conformance", "provenance", "signatures")}
        resources = []
        for resource in view.get("resources") or []:
            if isinstance(resource, Mapping):
                resources.append({key: value for key, value in resource.items() if key not in ("state", "revision")})
        view["resources"] = resources
        views.append(view)
    views.sort(key=lambda item: str(item.get("device_id")))
    return canonical.digest(views)


def build_report(
    *,
    profile: str,
    level_claimed: str,
    level_achieved: str,
    subject: Mapping[str, Any],
    tests: Sequence[Mapping[str, Any]],
    environment: Mapping[str, Any] | None = None,
    limitations: Sequence[str] = (),
    issuer_kind: str = "self",
    issuer_name: str = "mhs reference conformance suite",
    disclaimers: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble a schema-shaped report with ``coverage``, disclaimers and ``report_digest``.

    ``coverage.required`` counts the tests whose ``required`` flag is true
    (every test, for entries without the flag).
    """

    entries = [dict(item) for item in tests]
    passed = sum(1 for item in entries if item.get("status") == "pass")
    failed = sum(1 for item in entries if item.get("status") == "fail")
    skipped = sum(1 for item in entries if item.get("status") == "skip")
    required = sum(1 for item in entries if item.get("required", True))
    report: dict[str, Any] = {
        "report_version": REPORT_VERSION,
        "suite_version": SUITE_VERSION,
        "profile": profile,
        "subject": dict(subject),
        "level_claimed": level_claimed,
        "level_achieved": level_achieved,
        "tests": entries,
        "environment": dict(environment if environment is not None else _make_environment()),
        "coverage": {
            "required": required,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        },
        "issuer": {"kind": issuer_kind, "name": issuer_name},
        "limitations": list(limitations),
        "disclaimers": [dict(item) for item in disclaimers] if disclaimers is not None
        else default_disclaimers(issuer_kind=issuer_kind),
    }
    report["report_digest"] = report_digest(report)
    return report


def finalize_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``report`` with a freshly recomputed digest."""

    final = copy.deepcopy(dict(report))
    final.pop("report_digest", None)
    final["report_digest"] = report_digest(final)
    return final


def verify_report_digest(report: Mapping[str, Any]) -> bool:
    """True when ``report_digest`` matches the canonical recomputation."""

    digest = report.get("report_digest")
    if not isinstance(digest, str):
        return False
    return digest == report_digest(report)


# ---------------------------------------------------------------------------
# recomputation
# ---------------------------------------------------------------------------


def _version_tuple(value: Any) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(value).split("-")[0].split(".")[:3])
    except (TypeError, ValueError):
        return (0, 0, 0)


def _strict(report: Mapping[str, Any]) -> bool:
    """Every report is validated strictly (07b: no lenient pre-1.2.0 report remains)."""

    return True


def _post_1_1_ids(report: Mapping[str, Any]) -> list[str]:
    return sorted({str(entry.get("id")) for entry in report.get("tests") or []
                   if isinstance(entry, Mapping) and str(entry.get("id")) not in SUITE_1_1_TEST_IDS})


def _registry() -> dict[str, Any]:
    from mhs.conformance.tests_core import TESTS

    return {case.id: case for case in TESTS}


def _entry_required(entry: Mapping[str, Any], case: Any) -> bool:
    if "required" in entry:
        return bool(entry["required"])
    if case is None:
        return True
    if isinstance(case.required, bool):
        return case.required
    # Pre-1.2 reports carry no flag: a context-dependent test that ran counts as required.
    return entry.get("status") != "skip"


def recompute_level(report: Mapping[str, Any]) -> str:
    """The highest contiguous level whose required tests all pass (CON-018/CON-019)."""

    from mhs.conformance.model import LEVELS

    claimed = str(report.get("level_claimed"))
    if claimed not in LEVELS:
        return "CL0"
    registry = _registry()
    by_level: dict[str, list[Mapping[str, Any]]] = {}
    for entry in report.get("tests") or []:
        if not isinstance(entry, Mapping):
            continue
        case = registry.get(str(entry.get("id")))
        level = str(entry.get("level") or (case.level if case is not None else "CL0"))
        by_level.setdefault(level, []).append(entry)
    achieved = "CL0"
    for level in LEVELS[: LEVELS.index(claimed) + 1]:
        required = [entry for entry in by_level.get(level, [])
                    if _entry_required(entry, registry.get(str(entry.get("id"))))]
        if not required:
            continue  # same rule as suite.level_from_results
        if all(entry.get("status") == "pass" for entry in required):
            achieved = level
        else:
            break
    return achieved


def cl0_blockers(report: Mapping[str, Any]) -> list[tuple[str, str]]:
    """``[(test id, status)]`` of the required CL0 tests that did not pass (empty: CL0 holds)."""

    registry = _registry()
    out: list[tuple[str, str]] = []
    for entry in report.get("tests") or []:
        if not isinstance(entry, Mapping):
            continue
        case = registry.get(str(entry.get("id")))
        level = str(entry.get("level") or (case.level if case is not None else "CL0"))
        if level != "CL0" or not _entry_required(entry, case):
            continue
        if entry.get("status") != "pass":
            out.append((str(entry.get("id")), str(entry.get("status"))))
    return out


def cl0_limitation(blockers: Sequence[tuple[str, str]]) -> str:
    """The leading ``limitations`` line of a report whose required CL0 tests did not pass."""

    listing = ", ".join(f"{test_id} ({status})" for test_id, status in blockers)
    return (f"{CL0_NOT_ACHIEVED} required CL0 test(s) did not pass: {listing}; level_achieved CL0 is the "
            "schema floor of this report, not an award (CON-018)")


def level_awarded(report: Mapping[str, Any]) -> str | None:
    """The level a report actually awards: :func:`recompute_level`, or ``None`` when CL0 itself failed."""

    if cl0_blockers(report):
        return None
    return recompute_level(report)


def semantic_errors(report: Mapping[str, Any]) -> list[str]:
    """Checks a third party can run on a report without the subject (CON-001/CON-003/CON-019)."""

    from mhs.conformance.model import LEVELS

    errors: list[str] = []
    claimed = report.get("level_claimed")
    achieved = report.get("level_achieved")
    if claimed not in LEVELS or achieved not in LEVELS:
        return [f"unknown level (claimed {claimed!r}, achieved {achieved!r})"]
    if LEVELS.index(str(achieved)) > LEVELS.index(str(claimed)):
        errors.append(f"level_achieved {achieved} exceeds level_claimed {claimed} (CON-019)")
    recomputed = recompute_level(report)
    if recomputed != achieved:
        errors.append(f"level_achieved {achieved} does not follow from the required test results "
                      f"(recomputed {recomputed})")
    registry = _registry()
    strict = _strict(report)
    if _version_tuple(report.get("suite_version")) < _STRICT_FROM:
        newer = _post_1_1_ids(report)
        errors.append(f"suite_version {report.get('suite_version')!r} is older than 1.2.0: reports of the lenient "
                      "suites carry no required flags or disclaimers and are no longer accepted"
                      + (f" (and this one contains tests introduced in suite 1.2.0: {', '.join(newer[:6])})"
                         if newer else "") + "; re-run the suite")
    tests = [entry for entry in report.get("tests") or [] if isinstance(entry, Mapping)]
    ids = set()
    for index, entry in enumerate(tests):
        test_id = str(entry.get("id"))
        ids.add(test_id)
        case = registry.get(test_id)
        if case is None:
            errors.append(f"tests[{index}] {test_id} is not a test of this suite")
            continue
        if entry.get("required") is False and case.always_required:
            errors.append(f"{test_id} is required in every context; required=false is invalid")
        if strict:
            if "required" not in entry:
                errors.append(f"{test_id} has no required flag")
            if entry.get("level") not in (None, case.level):
                errors.append(f"{test_id} is a {case.level} test, not {entry.get('level')}")
    if strict:
        profile = str(report.get("profile"))
        for case in registry.values():
            if (case.always_required and case.applies(profile) and case.level in LEVELS
                    and LEVELS.index(case.level) <= LEVELS.index(str(claimed)) and case.id not in ids):
                errors.append(f"required test {case.id} ({case.level}) is missing from the report")
        disclaimers = report.get("disclaimers")
        if not isinstance(disclaimers, list) or not any(
                isinstance(item, Mapping) and item.get("id") == "not_certified" for item in disclaimers):
            errors.append("the report carries no not_certified disclaimer (CON-003)")
        coverage = report.get("coverage")
        required = sum(1 for entry in tests if entry.get("required"))
        if isinstance(coverage, Mapping) and coverage.get("required") not in (None, required):
            errors.append(f"coverage.required={coverage.get('required')} but {required} test(s) are required")
        subject = report.get("subject") if isinstance(report.get("subject"), Mapping) else {}
        if subject.get("kind") == "endpoint" and not subject.get("manifest_digest"):
            errors.append("subject.manifest_digest is missing: an endpoint report must bind the device "
                          "manifests it tested (CON-040/041)")
        blockers = cl0_blockers(report)
        limitations = [str(item) for item in report.get("limitations") or []]
        stated = [item for item in limitations if item.startswith(CL0_NOT_ACHIEVED)]
        if blockers and not stated:
            errors.append("required CL0 test(s) did not pass ("
                          + ", ".join(f"{test_id} {status}" for test_id, status in blockers)
                          + f") but the report does not state that no level was achieved ('{CL0_NOT_ACHIEVED}' "
                          "limitation, CON-018)")
        elif stated and not blockers:
            errors.append(f"the report states '{CL0_NOT_ACHIEVED}' although every required CL0 test passed")
    return errors


def compare_reports(original: Mapping[str, Any], rerun: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Compare a report with a re-run of the suite; returns ``(mismatches, notes)``.

    Mismatches are differences that change what the report claims: profile,
    levels, the set of tests, the verdict or requiredness of a required test, and
    the manifest digest.  Status differences of optional tests are notes.
    """

    mismatches: list[str] = []
    notes: list[str] = []
    for key in ("suite_version", "report_version", "profile", "level_claimed", "level_achieved"):
        if original.get(key) != rerun.get(key):
            mismatches.append(f"{key}: report {original.get(key)!r}, re-run {rerun.get(key)!r}")
    try:
        awarded = (level_awarded(original), level_awarded(rerun))
    except Exception:  # noqa: BLE001 - a malformed report is a mismatch, never a crash
        awarded = ("unknown", None)
    if awarded[0] != awarded[1]:
        mismatches.append(f"level awarded: report {awarded[0] or 'none (CL0 not achieved)'}, "
                          f"re-run {awarded[1] or 'none (CL0 not achieved)'}")
    first = {str(entry.get("id")): entry for entry in original.get("tests") or [] if isinstance(entry, Mapping)}
    second = {str(entry.get("id")): entry for entry in rerun.get("tests") or [] if isinstance(entry, Mapping)}
    missing = sorted(set(second) - set(first))
    extra = sorted(set(first) - set(second))
    if missing:
        mismatches.append("tests missing from the report: " + ", ".join(missing))
    if extra:
        mismatches.append("tests the re-run did not produce: " + ", ".join(extra))
    for test_id in sorted(set(first) & set(second)):
        a, b = first[test_id], second[test_id]
        required = bool(b.get("required", True))
        if "required" in a and bool(a.get("required")) != required:
            mismatches.append(f"{test_id}: required {a.get('required')} in the report, {required} in the re-run")
        if a.get("status") != b.get("status"):
            line = f"{test_id}: {a.get('status')} in the report, {b.get('status')} in the re-run"
            (mismatches if required else notes).append(line)
    left = (original.get("subject") or {}).get("manifest_digest")
    right = (rerun.get("subject") or {}).get("manifest_digest")
    if left and right and left != right:
        mismatches.append(f"subject.manifest_digest: report {left}, re-run {right}")
    elif not left and _strict(original):
        mismatches.append("subject.manifest_digest is missing: the report is not bound to the tested driver")
    elif not left:
        notes.append("the report has no subject.manifest_digest; the tested driver cannot be pinned")
    return mismatches, notes


def validate_report(report: Mapping[str, Any], *, schema_dir: str | os.PathLike[str] | None = None) -> list[str]:
    """Validate a report: schema, digest, and the recomputable claims (see :func:`semantic_errors`).

    Returns a list of human-readable errors (empty when valid).  Falls back to a
    structural check when the schema validator or the schema file is missing, so
    the suite still reports *something* outside a full checkout.
    """

    errors: list[str] = []
    try:
        from mhs.schema import SchemaStore, find_schema_dir

        root = Path(schema_dir) if schema_dir is not None else find_schema_dir()
        if root is not None:
            store = SchemaStore(root=str(root))
            errors = [str(item) for item in store.validate(report, REPORT_SCHEMA)]
    except Exception:  # noqa: BLE001 - validator is optional for a standalone suite
        errors = []
    if errors:
        return errors
    errors = _structural_errors(report)
    if errors:
        return errors
    try:
        return semantic_errors(report)
    except Exception as exc:  # noqa: BLE001 - a malformed report is an error, never a crash
        return [f"report could not be recomputed: {type(exc).__name__}: {exc}"]


def _structural_errors(report: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(report, Mapping):
        return ["report is not an object"]
    for field in (
        "report_version",
        "suite_version",
        "profile",
        "subject",
        "level_claimed",
        "level_achieved",
        "tests",
        "environment",
        "report_digest",
    ):
        if field not in report:
            errors.append(f"missing required member {field!r}")
    tests = report.get("tests")
    if isinstance(tests, list):
        if not tests:
            errors.append("tests must not be empty")
        for index, case in enumerate(tests):
            if not isinstance(case, Mapping):
                errors.append(f"tests[{index}] is not an object")
                continue
            case_id = case.get("id")
            if not isinstance(case_id, str) or "-" not in case_id:
                errors.append(f"tests[{index}].id is not AREA-NNN shaped")
            if case.get("status") not in ("pass", "fail", "skip", "warn"):
                errors.append(f"tests[{index}].status is invalid")
    else:
        errors.append("tests is not an array")
    env = report.get("environment")
    if isinstance(env, Mapping):
        for field in ("os", "date", "suite"):
            if field not in env:
                errors.append(f"environment.{field} is missing")
    if not verify_report_digest(report):
        errors.append("report_digest does not match the recomputed canonical digest")
    return errors


def save_report(
    report: Mapping[str, Any],
    path: str | os.PathLike[str],
    *,
    validate: bool = True,
) -> dict[str, Any]:
    """Validate (optionally) and atomically write a report; returns ``{path, valid, errors}``."""

    errors = validate_report(report) if validate else []
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(target)
    return {"path": str(target), "valid": not errors, "errors": errors}


def load_report(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load a previously written report."""

    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path!r} does not contain a JSON object")
    return document
