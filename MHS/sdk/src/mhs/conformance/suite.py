"""Conformance suite runner: ``run_suite(client, profile, level) -> report``.

The runner drives a *connected* MHS client (or, through
:func:`mhs.conformance.inprocess.run_suite_inprocess`, fresh in-process
endpoints) through the stable test registry in :mod:`mhs.conformance.tests_core`,
computes the highest contiguously achieved level and emits a schema-shaped
``conformance-report`` whose level and digest can be recomputed offline.

A level is *achieved* only when every required test at or below it passes; a
required ``warn``, ``fail`` or ``skip`` stops the ladder (CON-018).  Optional
tests run for extra coverage but never demote the claimed level; they are
reported with ``required: false`` and mentioned in ``limitations``.  When a
required CL0 test fails no level is achieved at all: the report still says
``level_achieved: CL0`` (the schema floor) but leads its ``limitations`` with
``NO LEVEL ACHIEVED: ...`` and :func:`mhs.conformance.report.level_awarded`
returns ``None``.

Requests are validated first: only endpoint profiles (``MHS-Sim``,
``MHS-Device``, ``MHS-Bridge``; CON-004) and levels ``CL0``..``CL4`` (CON-006)
are accepted; anything else raises :class:`ValueError`.  ``CL0`` runs the
static manifest checks only.

Operator options: ``allow_actuation`` lets actuating tests run against
hardware or hybrid devices (CON-031).  Without it, actuating tests are
skipped, which caps the level at CL1 whenever such a device binds an
actuating capability; negative tests run only in-process, where the harness
blocks every write/invoke at the hardware bridge, and are skipped over any
other transport; a send guard keeps any bound actuating command from such a
device.  ``read_only`` sends no command at all: only ``none`` tests run, so no
CL2+ level is awarded (CON-022).  ``fixtures`` supplies test inputs;
``approvals`` supplies operator approval records for permits (the suite never
invents them on hardware).

Every report carries a deterministic limitation line with the
applicability-inventory counts, so a level award is never presented as full
coverage of the numbered requirements (SPEC-001).
"""

from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from mhs.conformance.model import ENDPOINT_PROFILES, LEVELS, PROFILES
from mhs.conformance.report import (
    SUITE_VERSION,
    build_report,
    cl0_blockers,
    cl0_limitation,
    default_disclaimers,
    environment,
    level_awarded,
    manifest_digest,
    save_report,
    validate_report,
)
from mhs.conformance.requirements import coverage_disclosure
from mhs.conformance.synth import load_fixtures
from mhs.conformance.tests_core import (
    RunLog,
    RunOptions,
    SuiteContext,
    TestCase,
    TestOutcome,
    cases_for_level,
    normalize_code,
)

__all__ = [
    "RUN_SUITE_SIGNATURE",
    "capping_tests",
    "conformance_summary",
    "execute",
    "level_from_results",
    "run_suite",
]

RUN_SUITE_SIGNATURE = "run_suite(client, profile='MHS-Sim', level='CL3') -> dict"
TRACEABILITY_FILE = Path(__file__).with_name("traceability.json")


@lru_cache(maxsize=1)
def _traceability_document() -> dict[str, Any]:
    try:
        document = json.loads(TRACEABILITY_FILE.read_text(encoding="utf-8"))
        return document if isinstance(document, dict) else {}
    except (OSError, ValueError):
        return {}


def _traceability() -> dict[str, list[str]]:
    tests = _traceability_document().get("tests") or {}
    return {str(key): [str(item) for item in value] for key, value in tests.items()}


def spec_ref(test_id: str) -> str:
    """Requirement id(s) a test checks, as recorded in ``traceability.json``.

    A grouped test that checks no numbered requirement cites the spec section
    recorded under ``sections`` instead.
    """

    refs = _traceability().get(test_id)
    if not refs:
        section = (_traceability_document().get("sections") or {}).get(test_id)
        refs = [str(section)] if section else [test_id]
    text = ", ".join(refs)
    return text if len(text) <= 200 else text[:197] + "..."


def check_request(profile: str, level: str) -> None:
    """Refuse profiles and levels this runner cannot honestly test (CON-004, CON-006)."""

    if profile not in PROFILES:
        raise ValueError(f"unknown conformance profile {profile!r}; expected one of {', '.join(PROFILES)}")
    if profile not in ENDPOINT_PROFILES:
        raise ValueError(
            f"{profile} is not an endpoint profile (CON-004): this runner tests endpoint subjects under "
            f"{', '.join(ENDPOINT_PROFILES)}; no {profile} suite exists yet"
        )
    if level not in LEVELS:
        raise ValueError(f"unknown conformance level {level!r}; expected one of {', '.join(LEVELS[:-1])}")
    if level == "CL5":
        raise ValueError("CL5 (orchestration) is not implemented by this runner; endpoint subjects are "
                         "limited to CL4 (CON-006)")


def level_from_results(
    cases: Sequence[TestCase],
    results: Mapping[str, Mapping[str, Any]],
    *,
    context: Any,
    claimed: str,
) -> str:
    """Highest contiguous level whose required tests all pass (CL0 is the floor)."""

    achieved = "CL0"
    if claimed not in LEVELS:
        return achieved
    for index in range(0, LEVELS.index(claimed) + 1):
        level = LEVELS[index]
        required = [
            case
            for case in cases
            if case.level == level and case.is_required(context) and case.applies(context.profile)
        ]
        if not required:
            continue
        # CON-018: only a pass awards; required warn, fail or skip caps the
        # level.  A warning is an observation for the reviewer, not a waiver.
        verdicts = [results.get(case.id, {}).get("status") for case in required]
        if verdicts and all(verdict == "pass" for verdict in verdicts):
            achieved = level
        else:
            break
    return achieved


def capping_tests(report: Mapping[str, Any]) -> tuple[str | None, list[tuple[str, str]]]:
    """``(blocked level, [(test id, status)])`` -- the required tests that stop the ladder."""

    tests = [item for item in report.get("tests") or [] if isinstance(item, Mapping)]
    claimed = str(report.get("level_claimed"))
    if claimed not in LEVELS:
        return None, []
    for level in LEVELS[: LEVELS.index(claimed) + 1]:
        blocking = [(str(item.get("id")), str(item.get("status"))) for item in tests
                    if item.get("level") == level and item.get("required", True) and item.get("status") != "pass"]
        if blocking:
            return level, blocking
    return None, []


def _hardware_gate(case: TestCase, ctx: SuiteContext) -> TestOutcome | None:
    if ctx.options.read_only and case.actuation != "none":
        return TestOutcome.skipped("read-only run (CON-022): no command is sent")
    if case.actuation == "effect" and not ctx.actuation_allowed:
        with ctx.run_log.lock:
            ctx.run_log.gated.append(case.id)
        return TestOutcome.skipped(
            f"hardware/hybrid device(s) {', '.join(ctx.hardware_ids)}: actuating tests need the operator's "
            "--allow-actuation (CON-031)"
        )
    if case.actuation == "negative" and not ctx.negative_tests_contained:
        # A negative test sends a command the device would execute if the endpoint failed to
        # refuse it; only the in-process harness can stop such a command before the device.
        with ctx.run_log.lock:
            ctx.run_log.gated.append(case.id)
        return TestOutcome.skipped(
            f"hardware/hybrid device(s) {', '.join(ctx.hardware_ids)}: this negative test sends a command the "
            "device would execute if the endpoint failed to refuse it, and this transport cannot block it "
            "before the device; it needs the operator's --allow-actuation, or an in-process run whose "
            "harness blocks it at the bridge (CON-031)"
        )
    return None


def _run_case(case: TestCase, context: SuiteContext | None, base: SuiteContext,
              failure: BaseException | None = None) -> dict[str, Any]:
    started = time.monotonic()
    if failure is not None or context is None:
        outcome = TestOutcome.failed(f"could not build a fresh endpoint for group {case.group}: "
                                     f"{type(failure).__name__}: {failure}")
    else:
        outcome = _hardware_gate(case, context)
        if outcome is None:
            context.current_test = case.id
            try:
                outcome = case.fn(context)
                if not isinstance(outcome, TestOutcome):
                    outcome = TestOutcome.failed(f"test returned {type(outcome).__name__}, not TestOutcome")
            except BaseException as exc:  # noqa: BLE001 - every failure mode becomes a verdict
                code = getattr(exc, "code", None)
                outcome = TestOutcome.failed(
                    f"{type(exc).__name__}: {getattr(exc, 'message', None) or exc}",
                    mhs_code=code if isinstance(code, str) else None,
                )
            finally:
                context.current_test = None
    duration_ms = round((time.monotonic() - started) * 1000.0, 3)
    entry: dict[str, Any] = {
        "id": case.id,
        "name": case.name,
        "status": outcome.status,
        "level": case.level,
        "required": bool(case.is_required(base)),
        "spec_ref": spec_ref(case.id),
        "duration_ms": duration_ms,
    }
    if outcome.detail:
        entry["detail"] = outcome.detail[:2000]
    if outcome.mhs_code:
        entry["mhs_code"] = normalize_code(outcome.mhs_code)
    evidence: dict[str, Any] = {}
    if outcome.request_digest:
        evidence["request_digest"] = outcome.request_digest
    if outcome.response_digest:
        evidence["response_digest"] = outcome.response_digest
    if outcome.note:
        evidence["note"] = outcome.note
    if evidence:
        entry["evidence"] = evidence
    return entry


def conformance_summary(report: Mapping[str, Any]) -> str:
    """One-screen human summary: counts, failing tests and the tests that cap the level."""

    tests = report.get("tests") or []
    counts: dict[str, int] = {}
    for case in tests:
        status = str(case.get("status"))
        counts[status] = counts.get(status, 0) + 1
    try:
        awarded = level_awarded(report)
    except Exception:  # noqa: BLE001 - a summary never crashes
        awarded = report.get("level_achieved")
    achieved = report.get("level_achieved") if awarded is not None else "none"
    lines = [
        f"profile={report.get('profile')} claimed={report.get('level_claimed')} "
        f"achieved={achieved} tests={len(tests)} "
        f"pass={counts.get('pass', 0)} fail={counts.get('fail', 0)} "
        f"skip={counts.get('skip', 0)} warn={counts.get('warn', 0)}",
        f"subject={((report.get('subject') or {}).get('id'))}",
        f"report_digest={report.get('report_digest')}",
    ]
    blocked, capping = capping_tests(report)
    listing = ", ".join(f"{test_id} ({status})" for test_id, status in capping)
    if capping and awarded is None:
        lines.append(f"no level achieved: CL0 is blocked by {listing} (level_achieved CL0 is only the "
                     "report's schema floor)")
    elif capping:
        lines.append(f"capped at {report.get('level_achieved')}: {blocked} is blocked by {listing}")
    failures = [case for case in tests if case.get("status") == "fail"]
    for case in failures[:12]:
        flag = "" if case.get("required", True) else " [optional]"
        lines.append(f"  FAIL {case.get('id')}{flag}: {case.get('detail')}")
    for case in [case for case in tests if case.get("status") == "skip" and case.get("required")][:8]:
        lines.append(f"  SKIP {case.get('id')} [required]: {case.get('detail')}")
    return "\n".join(lines)


def run_suite(
    client: Any,
    profile: str = "MHS-Sim",
    level: str = "CL3",
    *,
    save_path: str | os.PathLike[str] | None = None,
    strict: bool = True,
    limitations: Sequence[str] = (),
    include_optional: bool = True,
    allow_actuation: bool = False,
    read_only: bool = False,
    fixtures: Any = None,
    approvals: Sequence[Mapping[str, Any]] | None = None,
    source_commit: str | None = None,
    harness: Any = None,
) -> dict[str, Any]:
    """Run the executable conformance suite against a connected MHS client.

    Parameters
    ----------
    client:
        A connected ``mhs.client.MHSClient`` (or any duck-typed object with the
        same high-level methods).  Every test runs against this one endpoint;
        use :func:`mhs.conformance.inprocess.run_suite_inprocess` for fresh
        endpoints per test group.
    profile:
        ``MHS-Sim``, ``MHS-Device`` or ``MHS-Bridge`` (endpoint subjects).
    level:
        Claimed level, ``CL0``..``CL4``; tests at or below it are executed.
    save_path:
        Optional path to persist the (validated) report.
    strict:
        Raise when the generated report fails validation (default) so an
        invalid report can never be presented as a conformance claim.
    allow_actuation, read_only, fixtures, approvals:
        Operator options, see the module docstring.
    source_commit:
        Pinned upstream commit of the driver under test (``subject.source_commit``).
    harness:
        An :class:`mhs.conformance.inprocess.Harness` on the server behind
        ``client`` (enables call recording and fault injection).
    """

    return execute(
        lambda group: (client, harness),
        profile=profile, level=level, fresh_groups=False, save_path=save_path, strict=strict,
        limitations=limitations, include_optional=include_optional, allow_actuation=allow_actuation,
        read_only=read_only, fixtures=fixtures, approvals=approvals, source_commit=source_commit,
    )


def execute(
    connect: Callable[[str], tuple[Any, Any]],
    *,
    profile: str = "MHS-Sim",
    level: str = "CL3",
    fresh_groups: bool = True,
    save_path: str | os.PathLike[str] | None = None,
    strict: bool = True,
    limitations: Sequence[str] = (),
    include_optional: bool = True,
    allow_actuation: bool = False,
    read_only: bool = False,
    fixtures: Any = None,
    approvals: Sequence[Mapping[str, Any]] | None = None,
    source_commit: str | None = None,
) -> dict[str, Any]:
    """Run the suite; ``connect(group)`` returns ``(client, harness_or_None)`` for a test group.

    With ``fresh_groups`` every mutating group (``OP``, ``SAFE``, ``FID``) gets
    its own ``connect`` call; otherwise all tests share the ``base`` endpoint.

    A declared terminal e-stop (``safety.estop.terminal``, CORE-087) cannot be
    reset on the endpoint that engaged it (CON-022): with ``fresh_groups`` the
    test after one gets a new ``connect`` call of its group; on one shared
    endpoint the tests that e-stop (``TestCase.estops``) run after every other
    test that sends a command.
    """

    check_request(profile, level)
    if source_commit is not None:
        import re

        if not re.fullmatch(r"[0-9a-f]{40}([0-9a-f]{24})?", str(source_commit)):
            raise ValueError(f"source_commit {source_commit!r} is not a full lowercase git commit id")
    fixture_set = load_fixtures(fixtures)
    options = RunOptions(
        allow_actuation=bool(allow_actuation),
        read_only=bool(read_only),
        fixtures=fixture_set,
        approvals=[dict(item) for item in approvals] if approvals else None,
    )
    log = RunLog()

    def make(group: str) -> SuiteContext:
        client, harness = connect(group)
        context = SuiteContext(client, profile=profile, requested_level=level, options=options,
                               harness=harness, run_log=log)
        context.load()
        try:
            context.ensure_session()
        except BaseException as exc:  # noqa: BLE001 - reported through the tests that need a session
            context.notes.append(f"session.open failed: {getattr(exc, 'code', None) or exc!r}")
        return context

    base = make("base")
    contexts: dict[str, SuiteContext] = {"base": base}
    #: contexts whose endpoint a terminal e-stop ended (CORE-087); kept for their notes and sessions
    retired: list[SuiteContext] = []
    failures: dict[str, BaseException] = {}

    def context_for(case: TestCase) -> SuiteContext | None:
        group = case.group if fresh_groups else "base"
        if group in failures:
            return None
        if group not in contexts:
            try:
                contexts[group] = make(group)
            except BaseException as exc:  # noqa: BLE001 - the group's tests report it
                failures[group] = exc
                return None
        return contexts[group]

    cases = [case for case in cases_for_level(level) if case.applies(profile)]
    if not include_optional:
        cases = [case for case in cases if case.is_required(base)]
    results: dict[str, dict[str, Any]] = {}
    ordered = [item for item in cases if not item.post] + [item for item in cases if item.post]
    if not fresh_groups and _declares_terminal(base):
        # CON-022: one shared endpoint cannot be given back after a terminal e-stop (CORE-087), so the tests
        # that e-stop run after every other test that sends a command, and before the suite's self-checks.
        ordered = ([item for item in ordered if not item.post and not item.estops]
                   + [item for item in ordered if not item.post and item.estops]
                   + [item for item in ordered if item.post])
    try:
        for case in ordered:
            context = context_for(case)
            group = case.group if fresh_groups else "base"
            results[case.id] = _run_case(case, context, base, failures.get(group))
            if fresh_groups and context is not None and context.terminated and contexts.get(group) is context:
                # CON-022 / CORE-087: no reset undoes a terminal e-stop; the next test of the group gets a new
                # endpoint instead of this one.
                retired.append(contexts.pop(group))
    finally:
        for context in list(contexts.values()) + retired:
            context.close()
    entries = [results[case.id] for case in cases]

    achieved = level_from_results(cases, results, context=base, claimed=level)
    notes: list[str] = []
    blockers = cl0_blockers({"tests": entries})
    # CON-018: the schema has no "no level" value, so a failed CL0 is stated first.
    lead = [cl0_limitation(blockers)] if blockers else []
    for context in list(contexts.values()) + retired:
        notes.extend(context.notes)
    if log.terminal_stops:
        engaged = ", ".join(dict.fromkeys(f"{test_id} ({device_id})" for test_id, device_id in log.terminal_stops))
        notes.append(f"a declared terminal e-stop (CORE-087) was engaged by {engaged}: "
                     + ("every later test ran on a new endpoint (CON-022)" if fresh_groups else
                        "the tests that e-stop ran after every other test on this shared endpoint (CON-022)"))
    for entry in entries:
        if entry["status"] == "skip" and entry["required"]:
            notes.append(f"{entry['id']} skipped but required for {entry['level']}")
    optional_failures = sorted(entry["id"] for entry in entries if entry["status"] == "fail" and not entry["required"])
    if optional_failures:
        notes.append("optional test failures (do not demote the level): " + ", ".join(optional_failures))
    warnings = sorted(entry["id"] for entry in entries if entry["status"] == "warn")
    if warnings:
        notes.append("warnings: " + ", ".join(warnings))
    skipped = sorted(entry["id"] for entry in entries if entry["status"] == "skip")
    if skipped:
        notes.append("skipped tests: " + ", ".join(skipped))
    if base.hardware_ids and not options.allow_actuation:
        contained = ("negative tests ran with the harness blocking every hardware write/invoke at the bridge"
                     if base.negative_tests_contained else "negative tests were not sent either")
        if base.actuation_capped:
            notes.append("hardware/hybrid subject run without --allow-actuation: actuating tests were not run "
                         f"and {contained} (CON-031); the level is capped at CL1")
        else:
            notes.append("hardware/hybrid subject run without --allow-actuation: its hardware devices bind no "
                         f"actuating capability, so no actuating test applies; {contained} (CON-031)")
    if options.read_only:
        notes.append("read-only run (CON-022): no command was sent, so no CL2+ level is awarded")
    coverage_limitation = coverage_disclosure(profile, level, [str(entry.get("id")) for entry in entries])
    transport = "in-process, fresh endpoint per group" if fresh_groups else (
        "in-process" if base.harness is not None else "client")
    if retired:
        transport += " and after each terminal e-stop"
    run_notes = (
        f"profile {profile}; suite {SUITE_VERSION}; transport {transport}; "
        f"allow_actuation={str(options.allow_actuation).lower()}; read_only={str(options.read_only).lower()}; "
        f"fixtures={fixture_set.digest or 'none'}; approvals={'operator' if options.approvals else 'none'}"
    )
    subject: dict[str, Any] = {
        "kind": "endpoint",
        "id": base.endpoint_id or base.primary_device.get("device_id", "mhs://unknown"),
        "mhs_version": str(base.hello.get("mhs_version") or "1.0"),
        "manifest_digest": manifest_digest(base.devices),
    }
    if source_commit:
        subject["source_commit"] = str(source_commit)
    report = build_report(
        profile=profile,
        level_claimed=level,
        level_achieved=achieved,
        subject=subject,
        tests=entries,
        environment=environment(
            endpoint_ids=[manifest.get("device_id") for manifest in base.devices],
            notes=run_notes,
        ),
        limitations=lead + list(limitations) + _dedupe(notes) + [coverage_limitation],
        disclaimers=default_disclaimers(base.devices),
    )
    errors = validate_report(report)
    if errors:
        if strict:
            raise RuntimeError("generated conformance report is not valid: " + "; ".join(errors[:8]))
        report = build_report(
            profile=profile,
            level_claimed=level,
            level_achieved=achieved,
            subject=report["subject"],
            tests=entries,
            environment=report["environment"],
            limitations=list(report.get("limitations") or []) + ["report validation errors: " + "; ".join(errors[:5])],
            disclaimers=report["disclaimers"],
        )
    if save_path is not None:
        save_report(report, save_path, validate=False)
    return report


def _declares_terminal(context: SuiteContext) -> bool:
    """True when a device of the endpoint declares a terminal e-stop (``safety.estop.terminal``, CORE-087)."""

    for manifest in context.devices:
        estop = ((manifest.get("safety") or {}).get("estop") or {}) if isinstance(manifest, Mapping) else {}
        if isinstance(estop, Mapping) and "terminal" in estop:
            return True
    return False


def _dedupe(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
