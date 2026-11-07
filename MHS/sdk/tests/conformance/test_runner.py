"""Runner semantics: profiles, levels, repeatability, principal and safety of the run (CONF-04/09/14)."""

from __future__ import annotations

import unittest

from mhs.client import MHSClient
from mhs.conformance import run_suite, validate_report
from mhs.conformance.inprocess import Harness, Loopback, reference_factory, run_suite_inprocess
from mhs.conformance.report import CL0_NOT_ACHIEVED, level_awarded
from mhs.conformance.suite import capping_tests, conformance_summary
from mhs.conformance.tests_core import SuiteContext
from mhs.errors import MHSError

from tests.conformance import support
from tests.conformance.support import client_for, entry


class ProfileAndLevelTests(unittest.TestCase):
    """CONF-04: profiles and levels are validated, CL0 is implemented."""

    def test_unknown_profiles_and_levels_are_rejected(self):
        for profile, level in (("MHS-Host", "CL3"), ("MHS-Registry", "CL3"), ("MHS-Nope", "CL3"),
                               ("MHS-Sim", "CL9"), ("MHS-Sim", "cl3"), ("MHS-Sim", "CL5")):
            with self.subTest(profile=profile, level=level):
                with self.assertRaises(ValueError):
                    run_suite(client_for(support.thermostat_server()), profile=profile, level=level)

    def test_cl0_produces_a_valid_static_report(self):
        report = run_suite_inprocess(reference_factory("conveyor"), profile="MHS-Sim", level="CL0")
        self.assertEqual(report["level_achieved"], "CL0")
        self.assertEqual(validate_report(report), [])
        ids = {case["id"] for case in report["tests"]}
        self.assertIn("ADPT-005", ids)
        self.assertTrue(all(case["level"] == "CL0" for case in report["tests"]))

    def test_profile_is_checked_against_device_mode(self):
        simulated = run_suite(client_for(support.heater_server()[0]), profile="MHS-Device", level="CL1")
        self.assertEqual(entry(simulated, "TCON-001")["status"], "fail")
        self.assertEqual(simulated["level_achieved"], "CL0")
        hardware = run_suite(client_for(support.hardware_heater()[0]), profile="MHS-Sim", level="CL1")
        self.assertEqual(entry(hardware, "TCON-001")["status"], "fail")
        matching = run_suite(client_for(support.hardware_heater()[0]), profile="MHS-Device", level="CL1")
        self.assertEqual(entry(matching, "TCON-001")["status"], "pass")


class _CorruptHashClient(MHSClient):
    """Returns reads whose state_hash does not verify (a CL1 failure on a CL0-clean subject)."""

    def read(self, *args, **kwargs):
        result = dict(super().read(*args, **kwargs))
        result["state_hash"] = "sha256:" + "0" * 64
        return result


class CL0FailureTests(unittest.TestCase):
    """CON-018 / CONF-04: a failed CL0 is never presented as an achieved CL0."""

    FIXTURES = (("risk floor", lambda: support.thermostat_server(risk="R0"), "CAP-017"),
                ("typo class id", lambda: support.thermostat_server(variant="typo"), "CAP-035"))

    def test_failed_cl0_claim_is_not_achieved(self):
        for label, build, blocker in self.FIXTURES:
            with self.subTest(fixture=label):
                report = run_suite(client_for(build()), profile="MHS-Sim", level="CL0")
                self.assertEqual(entry(report, blocker)["status"], "fail")
                self.assertEqual(report["level_achieved"], "CL0")  # the schema floor, not an award
                self.assertIsNone(level_awarded(report))
                marked = [item for item in report["limitations"] if item.startswith(CL0_NOT_ACHIEVED)]
                self.assertEqual(len(marked), 1, report["limitations"])
                self.assertIn(blocker, marked[0])
                self.assertEqual(report["limitations"][0], marked[0])
                self.assertEqual(validate_report(report), [])
                self.assertIn("no level achieved", conformance_summary(report))

    def test_failed_cl0_is_distinguishable_from_a_failed_cl1(self):
        failed_cl0 = run_suite(client_for(support.thermostat_server(risk="R0")), profile="MHS-Sim", level="CL2")
        self.assertEqual(capping_tests(failed_cl0)[0], "CL0")
        self.assertIsNone(level_awarded(failed_cl0))
        client = _CorruptHashClient(Loopback(support.thermostat_server()))
        client.hello()
        failed_cl1 = run_suite(client, profile="MHS-Sim", level="CL2")
        self.assertEqual(entry(failed_cl1, "PROTO-023")["status"], "fail")
        self.assertEqual(failed_cl1["level_achieved"], "CL0")
        self.assertEqual(level_awarded(failed_cl1), "CL0")
        self.assertFalse([item for item in failed_cl1["limitations"] if item.startswith(CL0_NOT_ACHIEVED)])
        self.assertEqual(validate_report(failed_cl1), [])

    def test_passing_cl0_is_awarded(self):
        report = run_suite(client_for(support.thermostat_server()), profile="MHS-Sim", level="CL0")
        self.assertEqual(level_awarded(report), "CL0")
        self.assertNotIn("no level achieved", conformance_summary(report))


class RepeatabilityTests(unittest.TestCase):
    """CONF-09: fresh in-process instances give identical results."""

    def test_three_inprocess_runs_are_identical(self):
        for name in ("conveyor", "lab", "arm"):
            with self.subTest(endpoint=name):
                runs = [run_suite_inprocess(reference_factory(name), profile="MHS-Sim", level="CL4")
                        for _ in range(3)]
                shapes = [[(case["id"], case["status"], case["required"], case.get("mhs_code"))
                           for case in report["tests"]] for report in runs]
                self.assertEqual(shapes[0], shapes[1])
                self.assertEqual(shapes[0], shapes[2])
                self.assertEqual(len({report["level_achieved"] for report in runs}), 1)
                self.assertEqual(len({report["subject"]["manifest_digest"] for report in runs}), 1)

    def test_loopback_and_harness_are_public(self):
        server, _backend = support.heater_server()
        harness = Harness(server)
        client = MHSClient(Loopback(server))
        client.hello()
        report = run_suite(client, profile="MHS-Sim", level="CL3", harness=harness)
        self.assertIn(report["level_achieved"], ("CL2", "CL3"))
        self.assertTrue(harness.records)


class SuitePrincipalTests(unittest.TestCase):
    """CONF-14 / CON-021: the suite runs under its own principal."""

    def test_receipts_carry_the_suite_principal(self):
        server = support.thermostat_server()
        client = client_for(server)
        run_suite(client, profile="MHS-Sim", level="CL2")
        response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "mhs.evidence.export", "params": {}})
        response = response.to_dict() if hasattr(response, "to_dict") else response
        receipts = (response["result"].get("bundle") or response["result"])["receipts"]
        principals = {((receipt.get("principal") or {}).get("id")) for receipt in receipts}
        self.assertEqual(principals, {"mhs-conformance"})


class _FailingPermitClient(MHSClient):
    def permit(self, *args, **kwargs):
        raise MHSError("MHS.SAFETY.APPROVAL_REQUIRED", "approval authority refused the permit")


class PermitErrorTests(unittest.TestCase):
    """CONF-14: a failed mhs.safety.permit reports the real error, not a NameError."""

    def test_permit_failure_detail(self):
        server, _backend = support.heater_server()
        server.devices[support.HEATER_ID].safety.requires_permit = ["cap.thermal.*"]
        client = _FailingPermitClient(support.Loopback(server))
        client.hello()
        report = run_suite(client, profile="MHS-Sim", level="CL3")
        case = entry(report, "SAFE-031")
        self.assertEqual(case["status"], "fail", case)
        self.assertNotIn("NameError", case["detail"])
        self.assertIn("APPROVAL_REQUIRED", case["detail"])


class ReadOnlyTests(unittest.TestCase):
    """CON-022: --read-only runs no CL2+ command tests."""

    def test_read_only_never_commands(self):
        server, backend = support.heater_server()
        client = client_for(server)
        report = run_suite(client, profile="MHS-Sim", level="CL3", read_only=True)
        self.assertNotIn("mhs.safety.estop", client.transport.methods)
        self.assertEqual(backend.actuations(), [])
        self.assertEqual(entry(report, "OP-001")["status"], "skip")
        self.assertIn(report["level_achieved"], ("CL0", "CL1"))

    def test_read_only_sends_no_command_at_all(self):
        """Verifier r2/acc_ro.py: the presence probes sent mhs.command and mhs.operations.cancel."""

        server, backend = support.hardware_heater(interlock=True)
        client = client_for(server)
        report = run_suite(client, profile="MHS-Device", level="CL4", read_only=True)
        for method in ("mhs.command", "mhs.operations.cancel", "mhs.safety.estop", "mhs.safety.reset",
                       "mhs.safety.permit", "mhs.restore"):
            self.assertNotIn(method, client.transport.methods)
        self.assertEqual(backend.actuations(), [])
        for test_id in ("TPROTO-902", "TPROTO-903", "PROTO-014"):
            self.assertEqual(entry(report, test_id)["status"], "skip", entry(report, test_id))
        self.assertEqual(report["level_achieved"], "CL1")


class ProbeSelectionTests(unittest.TestCase):
    """TESTS-03: the probe is chosen by catalogue verb, never by declaration order."""

    def _probe(self, server):
        ctx = SuiteContext(client_for(server), profile="MHS-Sim", requested_level="CL2")
        ctx.load()
        return ctx.primary_capability["capability_id"]

    def test_probe_ignores_order_and_read_verbs(self):
        self.assertEqual(self._probe(support.thermostat_server()), "cap.thermal.setpoint.v1")
        self.assertEqual(self._probe(support.thermostat_server(setpoint_first=True)), "cap.thermal.setpoint.v1")
        self.assertEqual(self._probe(support.heater_server(setpoint_first=False)[0]), "cap.thermal.setpoint.v1")

    def test_probe_skips_safe_state_actions(self):
        server, _backend = support.hardware_heater()
        self.assertEqual(self._probe(server), "cap.thermal.setpoint.v1")


if __name__ == "__main__":
    unittest.main()
