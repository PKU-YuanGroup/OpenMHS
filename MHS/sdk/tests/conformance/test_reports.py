"""Reports are recomputable and verifiable (CONF-03, CONF-12, CONF-14, FOLLOWUPS WP-07)."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from mhs.conformance import (
    build_report,
    finalize_report,
    recompute_level,
    run_suite,
    validate_report,
    verify_report_digest,
)
from mhs.conformance.__main__ import main as conformance_main
from mhs.conformance.inprocess import reference_factory, run_suite_inprocess
from mhs.conformance.report import CL0_NOT_ACHIEVED, compare_reports

from tests.conformance import support
from tests.conformance.support import client_for, entry

ROOT = Path(__file__).resolve().parents[4]
PUBLISHED = sorted((ROOT / "MHS/conformance/reports").glob("*.json")) + sorted(
    (ROOT / "MHS/sdk/docs/reports").glob("conformance-*.json")
)


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = conformance_main(list(argv))
        except SystemExit as exc:  # argparse usage errors
            code = int(exc.code or 0)
    return code, out.getvalue()


class ReportFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_suite_inprocess(reference_factory("lab"), profile="MHS-Sim", level="CL4")

    def test_tests_carry_required_and_spec_ref(self):
        for case in self.report["tests"]:
            self.assertIsInstance(case.get("required"), bool, case)
            self.assertTrue(case.get("spec_ref"), case)
        self.assertEqual(entry(self.report, "TSAFE-001")["spec_ref"].split(", ")[0], "SAFE-040")

    def test_subject_binds_the_manifests(self):
        subject = self.report["subject"]
        self.assertTrue(subject["manifest_digest"].startswith("sha256:"))
        again = run_suite_inprocess(reference_factory("lab"), profile="MHS-Sim", level="CL1")
        self.assertEqual(again["subject"]["manifest_digest"], subject["manifest_digest"])
        other = run_suite_inprocess(reference_factory("arm"), profile="MHS-Sim", level="CL1")
        self.assertNotEqual(other["subject"]["manifest_digest"], subject["manifest_digest"])

    def test_source_commit_is_recorded_when_given(self):
        commit = "0123456789abcdef0123456789abcdef01234567"
        report = run_suite_inprocess(reference_factory("arm"), profile="MHS-Sim", level="CL1",
                                     source_commit=commit)
        self.assertEqual(report["subject"]["source_commit"], commit)
        self.assertEqual(validate_report(report), [])

    def test_disclaimers_are_present(self):
        ids = [item["id"] for item in self.report["disclaimers"]]
        self.assertIn("not_certified", ids)
        self.assertIn("not_affiliated", ids)
        self.assertIn("simulation_only", ids)
        text = " ".join(item["text"] for item in self.report["disclaimers"])
        self.assertIn("not a safety certification", text)
        self.assertIn("MHS.SAFETY.NOT_CERTIFIED", text)

    def test_coverage_counts_required_tests_only(self):
        required = sum(1 for case in self.report["tests"] if case["required"])
        self.assertEqual(self.report["coverage"]["required"], required)
        self.assertLess(required, len(self.report["tests"]))

    def test_report_is_valid_and_level_recomputes(self):
        self.assertEqual(validate_report(self.report), [])
        self.assertEqual(recompute_level(self.report), self.report["level_achieved"])


class BuildReportTests(unittest.TestCase):
    def test_build_report_without_environment(self):
        report = build_report(profile="MHS-Sim", level_claimed="CL1", level_achieved="CL1",
                              subject={"kind": "endpoint", "id": "x", "mhs_version": "1.0"},
                              tests=[{"id": "PROTO-013", "status": "pass", "level": "CL1", "required": True}])
        self.assertIn("os", report["environment"])
        self.assertTrue(verify_report_digest(report))


class ForgedReportTests(unittest.TestCase):
    """CONF-03: a self-consistent but forged report is caught."""

    @classmethod
    def setUpClass(cls):
        cls.report = run_suite_inprocess(support.null_sim_factory, profile="MHS-Sim", level="CL4")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _write(self, name, report):
        path = self.dir / name
        path.write_text(json.dumps(report), encoding="utf-8")
        return str(path)

    def forged(self):
        forged = copy.deepcopy(self.report)
        forged["level_achieved"] = "CL4"
        forged["tests"] = [case for case in forged["tests"] if case["status"] == "pass"]
        return finalize_report(forged)

    def test_genuine_report_is_lower_than_cl4(self):
        self.assertNotEqual(self.report["level_achieved"], "CL4")

    def test_forged_report_fails_validation(self):
        forged = self.forged()
        self.assertTrue(verify_report_digest(forged))
        errors = validate_report(forged)
        self.assertTrue(errors)

    def test_raised_level_with_failing_tests_fails_validation(self):
        forged = copy.deepcopy(self.report)
        forged["level_achieved"] = "CL4"
        errors = validate_report(finalize_report(forged))
        self.assertTrue(any("level_achieved" in item for item in errors), errors)

    def test_achieved_above_claimed_is_invalid(self):
        forged = copy.deepcopy(self.report)
        self.assertNotEqual(forged["level_achieved"], "CL0")
        forged["level_claimed"] = "CL0"
        errors = validate_report(finalize_report(forged))
        self.assertTrue(any("level_claimed" in item for item in errors), errors)

    def test_cleared_required_flag_is_invalid(self):
        forged = copy.deepcopy(self.report)
        for case in forged["tests"]:
            if case["id"] == "PROTO-013":
                case["required"] = False
        errors = validate_report(finalize_report(forged))
        self.assertTrue(any("PROTO-013" in item for item in errors), errors)

    def test_verify_cli_rejects_the_forged_report(self):
        code, output = run_cli("verify", self._write("forged.json", self.forged()),
                               "--factory", "tests.conformance.support:null_sim_factory")
        self.assertEqual(code, 1, output)
        self.assertIn("MISMATCH", output)

    def test_verify_cli_accepts_the_genuine_report(self):
        code, output = run_cli("verify", self._write("genuine.json", self.report),
                               "--factory", "tests.conformance.support:null_sim_factory")
        self.assertEqual(code, 0, output)

    def test_downgraded_suite_version_does_not_relax_validation(self):
        """Verifier forged_c: suite_version 1.1.0, flags and disclaimers stripped, passing tests only."""

        forged = copy.deepcopy(self.report)
        forged["suite_version"] = "1.1.0"
        forged["level_achieved"] = "CL4"
        forged.pop("disclaimers", None)
        forged["tests"] = [case for case in forged["tests"] if case["status"] == "pass"]
        for case in forged["tests"]:
            case.pop("required", None)
        errors = validate_report(finalize_report(forged))
        self.assertTrue(errors)
        # 07b: the schema requires disclaimers, and no pre-1.2.0 report is accepted any more.
        self.assertTrue(any("disclaimers" in item or "1.2.0" in item for item in errors), errors)
        forged["disclaimers"] = copy.deepcopy(self.report["disclaimers"])
        errors = validate_report(finalize_report(forged))
        self.assertTrue(any("1.2.0" in item for item in errors), errors)

    def test_missing_manifest_digest_is_invalid(self):
        """Verifier forged_e_nodigest: a strict report must stay bound to the tested driver."""

        forged = copy.deepcopy(self.report)
        del forged["subject"]["manifest_digest"]
        errors = validate_report(finalize_report(forged))
        self.assertTrue(any("manifest_digest" in item for item in errors), errors)

    def test_compare_reports_pins_suite_version_and_manifest_digest(self):
        other_suite = copy.deepcopy(self.report)
        other_suite["suite_version"] = "1.1.0"
        mismatches, _notes = compare_reports(other_suite, self.report)
        self.assertTrue(any("suite_version" in item for item in mismatches), mismatches)
        no_digest = copy.deepcopy(self.report)
        del no_digest["subject"]["manifest_digest"]
        mismatches, _notes = compare_reports(no_digest, self.report)
        self.assertTrue(any("manifest_digest" in item for item in mismatches), mismatches)
        self.assertEqual(compare_reports(self.report, self.report)[0], [])


class FailedCL0ReportTests(unittest.TestCase):
    """CON-018: a report whose CL0 failed must say so; the statement cannot be stripped."""

    @classmethod
    def setUpClass(cls):
        cls.report = run_suite(client_for(support.thermostat_server(risk="R0")), profile="MHS-Sim", level="CL2")

    def test_report_is_valid_and_states_no_level(self):
        self.assertEqual(validate_report(self.report), [])
        self.assertTrue(self.report["limitations"][0].startswith(CL0_NOT_ACHIEVED))

    def test_stripping_the_statement_is_invalid(self):
        forged = copy.deepcopy(self.report)
        forged["limitations"] = [item for item in forged["limitations"] if not item.startswith(CL0_NOT_ACHIEVED)]
        errors = validate_report(finalize_report(forged))
        self.assertTrue(any("CL0" in item for item in errors), errors)

    def test_compare_reports_flags_an_award_difference(self):
        passing = run_suite(client_for(support.thermostat_server()), profile="MHS-Sim", level="CL2")
        mismatches, _notes = compare_reports(self.report, passing)
        self.assertTrue(any("level awarded" in item for item in mismatches), mismatches)


class PublishedReportTests(unittest.TestCase):
    def test_published_reports_still_validate(self):
        self.assertTrue(PUBLISHED)
        for path in PUBLISHED:
            with self.subTest(report=path.name):
                report = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(validate_report(report), [])
                self.assertEqual(recompute_level(report), report["level_achieved"])


class CliTests(unittest.TestCase):
    def test_cli_lists_failing_and_capping_ids(self):
        code, output = run_cli("--factory", "tests.conformance.support:null_factory", "--profile", "MHS-Device",
                               "--level", "CL3", "--allow-actuation")
        self.assertEqual(code, 5, output)
        self.assertIn("capped at", output)
        self.assertIn("TCAP-003", output)

    def test_cli_exits_below_target_when_cl0_fails(self):
        for factory in ("r0_thermostat_factory", "typo_thermostat_factory"):
            with self.subTest(factory=factory):
                code, output = run_cli("--factory", f"tests.conformance.support:{factory}", "--level", "CL0")
                self.assertEqual(code, 5, output)
                self.assertIn("no level achieved", output)

    def test_cli_passing_cl0_exits_zero(self):
        code, output = run_cli("--factory", "tests.conformance.support:thermostat_factory", "--level", "CL0")
        self.assertEqual(code, 0, output)

    def test_cli_rejects_unknown_levels(self):
        code, _ = run_cli("--reference", "arm", "--level", "CL9")
        self.assertEqual(code, 2)

    def test_cli_writes_a_valid_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "arm.json"
            code, output = run_cli("--reference", "arm", "--level", "CL1", "--out", str(target))
            self.assertEqual(code, 0, output)
            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(validate_report(report), [])


class PlainClientTests(unittest.TestCase):
    def test_run_suite_over_a_client_reports_fields(self):
        report = run_suite(client_for(support.heater_server()[0]), profile="MHS-Sim", level="CL2")
        self.assertEqual(validate_report(report), [])
        self.assertIn("manifest_digest", report["subject"])


if __name__ == "__main__":
    unittest.main()
