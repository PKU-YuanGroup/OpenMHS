"""Conformance suite tests: levels, report schema/digest, traceability, stability."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.endpoints import support  # noqa: F401 - puts the SDK on sys.path

from mhs import connect
from mhs.conformance import (
    TESTS,
    report_digest,
    run_suite,
    validate_report,
    verify_report_digest,
)

REPORTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "reports"
PUBLISHED_DIR = Path(__file__).resolve().parents[3] / "conformance" / "reports"
TRACEABILITY = Path(__file__).resolve().parents[2] / "src" / "mhs" / "conformance" / "traceability.json"


class ConformanceSuiteTests(unittest.TestCase):
    def test_conveyor_achieves_cl4_with_a_schema_valid_report(self) -> None:
        with support.EndpointHandle("conveyor", test_profile=True) as endpoint:
            client = connect(endpoint.url)
            try:
                report = run_suite(client, profile="MHS-Sim", level="CL4")
            finally:
                client.close()
        self.assertEqual(report["level_claimed"], "CL4")
        self.assertEqual(report["level_achieved"], "CL4")
        self.assertEqual(validate_report(report), [])
        self.assertTrue(verify_report_digest(report))
        self.assertEqual(report["report_digest"], report_digest(report))
        statuses = {case["id"]: case["status"] for case in report["tests"]}
        for required_id in ("PROTO-013", "OP-001", "OP-003", "OP-004", "SAFE-001", "TSAFE-001", "EVID-015", "FID-016"):
            self.assertIn(required_id, statuses)
            self.assertIn(statuses[required_id], ("pass", "warn"), required_id)

    def test_lab_achieves_cl2(self) -> None:
        with support.EndpointHandle("lab") as endpoint:
            client = connect(endpoint.url)
            try:
                report = run_suite(client, profile="MHS-Sim", level="CL2")
            finally:
                client.close()
        self.assertEqual(report["level_achieved"], "CL2")
        self.assertEqual(validate_report(report), [])
        ids = {case["id"] for case in report["tests"]}
        self.assertIn("OP-001", ids)
        self.assertNotIn("SAFE-001", ids)  # CL3 tests are not run for a CL2 claim

    def test_test_ids_are_unique_and_traceable(self) -> None:
        ids = [case.id for case in TESTS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all("-" in test_id for test_id in ids))
        document = json.loads(TRACEABILITY.read_text(encoding="utf-8"))
        trace, sections = document["tests"], document.get("sections") or {}
        for case in TESTS:
            self.assertIn(case.id, trace, f"missing traceability entry for {case.id}")
            # A grouped test that checks no numbered requirement cites a spec section instead.
            self.assertTrue(trace[case.id] or (case.id.startswith("T") and sections.get(case.id)), case.id)
        # grouped ids map to requirement ids that are not the test id itself;
        # TSAFE-001 cites only what it checks (latch latency, no auto-resume, the
        # declared re-enable of SAFE-042 and the declared terminal e-stop of
        # SAFE-048, RE-ENABLE-AND-TERMINAL-STOP) and the refused-reset rule has its
        # own test (CONF-07).
        self.assertEqual(trace["TSAFE-001"], ["SAFE-040", "SAFE-042", "SAFE-048"])
        self.assertEqual(trace["SAFE-041"], ["SAFE-041"])

    def test_reports_on_disk_are_valid_and_current(self) -> None:
        # WP-07 07b: the conveyor and lab copies under docs/reports were byte-identical
        # duplicates of MHS/conformance/reports and moved to _archive/sdk-docs-reports/.
        expected = {
            PUBLISHED_DIR / "conveyor-cl4.json": "CL4",
            REPORTS_DIR / "conformance-arm-2dof-seeded.json": "CL4",
            REPORTS_DIR / "conformance-replay-recorded.json": "CL2",
        }
        # The lab and arm reports carry their level in the file name (lab-cl2 -> lab-cl4 and
        # arm-cl3 -> arm-cl4 in WP-06 06c): exactly one each, named after level_achieved.
        for subject in ("lab", "arm"):
            found = sorted(PUBLISHED_DIR.glob(f"{subject}-cl[0-4].json"))
            self.assertEqual(len(found), 1, f"{subject}: {found}")
            expected[found[0]] = found[0].stem.rsplit("-", 1)[1].upper()
        for path, level in expected.items():
            filename = path.name
            self.assertTrue(path.exists(), f"missing report {filename}")
            report = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(report["level_achieved"], level, filename)
            self.assertEqual(validate_report(report), [], filename)
            self.assertTrue(verify_report_digest(report), filename)


if __name__ == "__main__":
    unittest.main()
