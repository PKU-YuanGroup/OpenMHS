"""Executable OpenMHS conformance suite (MHS-001).

Public API (frozen in ``MHS/sdk/INTERFACE.md``)::

    from mhs.conformance import run_suite

    report = run_suite(connect(...), profile="MHS-Sim", level="CL3")

    from mhs.conformance.inprocess import run_suite_inprocess

    report = run_suite_inprocess(build_server, profile="MHS-Sim", level="CL3")

The report matches ``MHS/schema/conformance-report.schema.json``; its
``report_digest`` is the canonical JCS SHA-256 digest recomputed over the report
without that member, and :func:`validate_report` recomputes ``level_achieved``
from the per-test ``required`` flags; :func:`level_awarded` is ``None`` when a
required CL0 test failed (the report then leads its ``limitations`` with
``NO LEVEL ACHIEVED:``).  Stable test IDs live in :mod:`mhs.conformance.tests_core`.
"""

from __future__ import annotations

from mhs.conformance.requirements import (
    applicability,
    applicability_entries,
    applicability_summary,
    coverage_disclosure,
    validate_applicability,
)
from mhs.conformance.report import (
    CL0_NOT_ACHIEVED,
    REPORT_SCHEMA,
    REPORT_VERSION,
    SUITE_NAME,
    SUITE_VERSION,
    build_report,
    compare_reports,
    default_disclaimers,
    environment,
    finalize_report,
    level_awarded,
    load_report,
    manifest_digest,
    recompute_level,
    report_digest,
    save_report,
    validate_report,
    verify_report_digest,
)
from mhs.conformance.suite import conformance_summary, level_from_results, run_suite
from mhs.conformance.tests_core import LEVELS, TESTS, TestCase, TestOutcome, cases_for_level


def run_suite_inprocess(*args, **kwargs):  # noqa: ANN002, ANN003 - thin re-export
    """See :func:`mhs.conformance.inprocess.run_suite_inprocess`."""

    from mhs.conformance.inprocess import run_suite_inprocess as _run

    return _run(*args, **kwargs)


__all__ = [
    "CL0_NOT_ACHIEVED",
    "LEVELS",
    "REPORT_SCHEMA",
    "REPORT_VERSION",
    "SUITE_NAME",
    "SUITE_VERSION",
    "TESTS",
    "TestCase",
    "TestOutcome",
    "applicability",
    "applicability_entries",
    "applicability_summary",
    "build_report",
    "cases_for_level",
    "compare_reports",
    "conformance_summary",
    "coverage_disclosure",
    "default_disclaimers",
    "environment",
    "finalize_report",
    "level_awarded",
    "level_from_results",
    "load_report",
    "manifest_digest",
    "recompute_level",
    "report_digest",
    "run_suite",
    "run_suite_inprocess",
    "save_report",
    "validate_applicability",
    "validate_report",
    "verify_report_digest",
]
