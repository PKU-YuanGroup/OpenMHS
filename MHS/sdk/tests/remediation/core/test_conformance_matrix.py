"""Regression tests for SPEC-001: the award is derived from a requirement matrix."""

from __future__ import annotations

import unittest

from mhs import connect
from mhs.conformance import level_from_results, run_suite
from mhs.conformance.tests_core import TestCase, TestOutcome
from mhs.reference import build_endpoint, build_server


class AwardReducerTests(unittest.TestCase):
    def _cases(self):
        return [
            TestCase("PROTO-013", "hello", "CL1", lambda ctx: TestOutcome.passed()),
            TestCase("PROTO-030", "operations", "CL2", lambda ctx: TestOutcome.passed()),
        ]

    def test_required_warning_does_not_award(self):
        cases = self._cases()
        context = type("Ctx", (), {"profile": "MHS-Sim"})()
        results = {
            "PROTO-013": {"status": "warn", "detail": "warning is not a pass"},
            "PROTO-030": {"status": "pass"},
        }
        self.assertEqual(
            level_from_results(cases, results, context=context, claimed="CL2"), "CL0"
        )

    def test_required_skip_does_not_award(self):
        cases = self._cases()
        context = type("Ctx", (), {"profile": "MHS-Sim"})()
        results = {
            "PROTO-013": {"status": "skip"},
            "PROTO-030": {"status": "pass"},
        }
        self.assertEqual(
            level_from_results(cases, results, context=context, claimed="CL2"), "CL0"
        )

    def test_all_passes_award(self):
        cases = self._cases()
        context = type("Ctx", (), {"profile": "MHS-Sim"})()
        results = {
            "PROTO-013": {"status": "pass"},
            "PROTO-030": {"status": "pass"},
        }
        self.assertEqual(
            level_from_results(cases, results, context=context, claimed="CL2"), "CL2"
        )


class MissingRequiredMethodTests(unittest.TestCase):
    """A CL4 endpoint with deleted required methods must not keep CL4/CL1."""

    def test_missing_methods_cap_the_award(self):
        spec = build_endpoint(
            "conveyor", endpoint_id="mhs://broken.local:7400", test_profile=False
        )
        server = build_server(spec, log_ready=False)
        handle = server.start_http("127.0.0.1", 0)
        client = connect(handle.url)
        try:
            # _METHODS is a class-level routing table: copy it onto this instance
            # so deleting methods cannot corrupt other tests in the process.
            server._METHODS = dict(server._METHODS)
            for method in (
                "mhs.subscribe", "mhs.unsubscribe", "mhs.schema.get",
                "mhs.operations.get", "mhs.operations.cancel",
            ):
                server._METHODS.pop(method, None)
            report = run_suite(client, profile="MHS-Sim", level="CL4")
            self.assertNotIn(report["level_achieved"], ("CL1", "CL2", "CL3", "CL4"))
            failed = [t for t in report["tests"] if t["id"] == "TPROTO-901"]
            self.assertTrue(failed)
            self.assertEqual(failed[0]["status"], "fail")
            self.assertEqual(failed[0]["mhs_code"], "MHS.PROTOCOL.METHOD_NOT_FOUND")
        finally:
            client.close()
            handle.shutdown()
            spec.close()


if __name__ == "__main__":
    unittest.main()
