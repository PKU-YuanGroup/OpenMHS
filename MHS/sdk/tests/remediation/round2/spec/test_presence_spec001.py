"""SPEC-001 regression tests: dispatch-level presence and applicability honesty.

These tests are independent of the published report files.  They reproduce the
lead's false-award counterexample (an empty-param probe satisfied by a generic
pre-dispatch error), verify the one-deletion-at-a-time meta-tests, and check that
the coverage inventory is complete and disclosed rather than silently counted.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from mhs.client import MHSClient
from mhs.conformance import TESTS, level_from_results, run_suite
from mhs.conformance.presence import (
    GENERIC_PRE_DISPATCH_CODES,
    METHOD_PROBES,
    check_method_presence,
    probe_method,
)
from mhs.conformance.requirements import (
    APPLICABILITY_FILE,
    REQUIRED_METHODS,
    applicability,
    applicability_entries,
    applicability_summary,
    coverage_disclosure,
    methods_introduced_at,
)
from mhs.conformance.tests_core import TestCase, TestOutcome, _cancellation_applies
from mhs.errors import MHSError
from mhs.reference import build_endpoint, build_server

ROOT = Path(__file__).resolve().parents[6]
TRACEABILITY = ROOT / "MHS/sdk/src/mhs/conformance/traceability.json"


class Loopback:
    """In-process JSON-RPC transport; no sockets and no filesystem state."""

    def __init__(self, server):
        self.server = server
        self.requests: list[tuple[str, dict]] = []

    def request(self, message, timeout=None):
        self.requests.append((message.get("method"), dict(message.get("params") or {})))
        response = self.server.handle(message)
        return response.to_dict() if hasattr(response, "to_dict") else response

    def close(self):
        pass


def _server_without(*methods: str):
    spec = build_endpoint("conveyor", test_profile=True)
    server = build_server(spec, log_ready=False)
    # _METHODS is class-level; copy it per instance so deletion is local.
    server._METHODS = dict(server._METHODS)
    for method in methods:
        server._METHODS.pop(method, None)
    return spec, server, MHSClient(Loopback(server))


def _run(removed: tuple[str, ...] = ()) -> dict:
    spec, server, client = _server_without(*removed)
    try:
        return run_suite(client, profile="MHS-Sim", level="CL4")
    finally:
        client.close()
        spec.close()


class ProbeTableTests(unittest.TestCase):
    def test_every_mandatory_method_has_a_probe(self):
        for level in ("CL1", "CL2", "CL3"):
            for method in methods_introduced_at(level):
                self.assertIn(method, METHOD_PROBES, method)
                probe = METHOD_PROBES[method]
                self.assertIn(probe.kind, ("result", "semantic"))
                self.assertTrue(probe.basis, method)

    def test_all_mandatory_methods_are_probed(self):
        probed = {method for methods in REQUIRED_METHODS.values() for method in methods}
        self.assertEqual(probed, set(METHOD_PROBES))

    def test_blocking_probes_carry_deadline(self):
        from mhs.server import _BLOCKING_METHODS

        ctx = _FakeContext()
        for method in METHOD_PROBES:
            if method not in _BLOCKING_METHODS:
                continue
            params = _probe_params(ctx, method)
            self.assertIsInstance(params.get("deadline_ms"), int, method)
            self.assertGreaterEqual(params["deadline_ms"], 1, method)

    def test_probes_do_not_mutate(self):
        from mhs.server import _BLOCKING_METHODS

        forbidden = {
            "mhs.resource.write",
            "mhs.snapshot",
            "mhs.restore",
            "mhs.safety.estop",
            "mhs.safety.reset",
            "mhs.safety.permit",
            "mhs.composition.run",
            "mhs.registry.search",
        }
        self.assertFalse(set(METHOD_PROBES) & forbidden)
        # The only commands issued are to an absent capability/operation, and
        # session.open is closed again by probe_method.
        self.assertIn("mhs.command", METHOD_PROBES)
        self.assertIn("mhs.command", _BLOCKING_METHODS)


class PreDispatchIsNotPresenceTests(unittest.TestCase):
    def test_generic_pre_dispatch_rejection_is_not_presence(self):
        class Client:
            def request(self, method, params):
                raise MHSError("MHS.PROTOCOL.DEADLINE_INVALID", "blocking methods require deadline_ms")

        ctx = _FakeContext(client=Client())
        outcome = probe_method(ctx, "mhs.operations.cancel")
        self.assertEqual(outcome.status, "unverified")
        self.assertIn("MHS.PROTOCOL.DEADLINE_INVALID", GENERIC_PRE_DISPATCH_CODES)

    def test_method_not_found_is_missing(self):
        class Client:
            def request(self, method, params):
                raise MHSError("MHS.PROTOCOL.METHOD_NOT_FOUND", "unknown method")

        ctx = _FakeContext(client=Client())
        outcome = probe_method(ctx, "mhs.operations.cancel")
        self.assertEqual(outcome.status, "missing")

    def test_semantic_error_reaches_dispatch(self):
        class Client:
            def request(self, method, params):
                raise MHSError("MHS.OPERATION.UNKNOWN", "unknown operation")

        ctx = _FakeContext(client=Client())
        outcome = probe_method(ctx, "mhs.operations.cancel")
        self.assertEqual(outcome.status, "present")
        self.assertEqual(outcome.code, "MHS.OPERATION.UNKNOWN")

    def test_mixed_batch_cannot_hide_missing_method(self):
        class Client:
            def request(self, method, params):
                raise MHSError("MHS.PROTOCOL.METHOD_NOT_FOUND", "unknown method")

        ctx = _FakeContext(client=Client())
        missing, unverified, results = check_method_presence(ctx, ["mhs.operations.cancel"])
        self.assertEqual(missing, ["mhs.operations.cancel"])
        self.assertEqual(unverified, [])
        self.assertEqual(len(results), 1)


class DeletionMetaTests(unittest.TestCase):
    """One method at a time: the level that requires it must not be awarded."""

    def assert_probe_failed(self, report: dict, test_id: str) -> None:
        case = next(item for item in report["tests"] if item["id"] == test_id)
        self.assertEqual(case["status"], "fail", case)

    def test_positive_control_still_awards_cl4(self):
        report = _run(())
        self.assertEqual(report["level_achieved"], "CL4")
        self.assertEqual(report["level_claimed"], "CL4")

    def test_deleting_cancel_caps_at_cl2(self):
        report = _run(("mhs.operations.cancel",))
        self.assertEqual(report["level_achieved"], "CL2")
        self.assert_probe_failed(report, "TPROTO-903")
        op011 = next(item for item in report["tests"] if item["id"] == "OP-011")
        self.assertEqual(op011["status"], "fail")

    def test_deleting_subscribe_caps_at_cl1(self):
        report = _run(("mhs.subscribe",))
        self.assertEqual(report["level_achieved"], "CL1")
        self.assert_probe_failed(report, "TPROTO-902")

    def test_deleting_operations_get_caps_at_cl1(self):
        report = _run(("mhs.operations.get",))
        self.assertEqual(report["level_achieved"], "CL1")
        self.assert_probe_failed(report, "TPROTO-902")

    def test_old_counterexample_empty_params_does_not_satisfy_presence(self):
        # The exact old oracle: empty params hit the deadline check first.  The
        # dispatch-level probe for a deleted method must still see METHOD_NOT_FOUND.
        report = _run(("mhs.operations.cancel",))
        op011 = next(item for item in report["tests"] if item["id"] == "OP-011")
        self.assertIn("METHOD_NOT_FOUND", op011["detail"])
        self.assertEqual(report["level_achieved"], "CL2")


class CancellationObligationTests(unittest.TestCase):
    def test_cancellation_required_only_when_declared(self):
        conveyor = build_endpoint("conveyor", test_profile=True)
        lab = build_endpoint("lab")
        try:
            self.assertTrue(any(
                (cap.get("constraints") or {}).get("cancellable")
                for device in conveyor.devices
                for cap in device.get("capabilities", [])
            ))
            self.assertFalse(any(
                (cap.get("constraints") or {}).get("cancellable")
                for device in lab.devices
                for cap in device.get("capabilities", [])
            ))
        finally:
            conveyor.close()
            lab.close()

    def test_required_skip_of_cancellation_caps_level(self):
        cases = [
            TestCase("OP-011", "cancel", "CL3", lambda ctx: TestOutcome.skipped("no safe state")),
        ]
        results = {"OP-011": {"status": "skip"}}
        self.assertEqual(
            level_from_results(
                cases, results, context=SimpleNamespace(profile="MHS-Sim"), claimed="CL3"
            ),
            "CL0",
        )

    def test_cancellation_predicate_matches_bindings(self):
        spec, server, client = _server_without()
        try:
            from mhs.conformance.tests_core import SuiteContext

            ctx = SuiteContext(client, profile="MHS-Sim", requested_level="CL4")
            ctx.load()
            self.assertTrue(_cancellation_applies(ctx))
        finally:
            client.close()
            spec.close()


class ApplicabilityInventoryTests(unittest.TestCase):
    def test_inventory_covers_all_normative_ids(self):
        entries = applicability_entries()
        # 580 + CAP-046 (MHS-A-001 renumbered, WP-09) + SAFE-048 (terminal e-stop, RE-ENABLE-AND-TERMINAL-STOP)
        # + SAFE-049 (sensed-confirmation stop, SENSED-CONFIRMATION-STOP; no conformance-suite check: not_verified)
        self.assertEqual(len(entries), 583)
        counts = applicability()["counts"]
        self.assertEqual(
            counts["executable"]
            + counts["out_of_profile"]
            + counts["editorial"]
            + counts["report_process"]
            + counts["level_not_claimed"]
            + counts["not_verified"],
            583,
        )
        self.assertGreater(counts["not_verified"], 0)
        self.assertLess(counts["executable"], 583)

    def test_every_executable_check_is_a_registered_test(self):
        test_ids = {case.id for case in TESTS}
        for requirement_id, entry in applicability_entries().items():
            if entry["disposition"] != "executable":
                continue
            self.assertTrue(entry["checks"], requirement_id)
            for check in entry["checks"]:
                self.assertIn(check, test_ids, f"{requirement_id} -> {check}")

    def test_traceability_and_inventory_agree(self):
        trace = json.loads(TRACEABILITY.read_text(encoding="utf-8"))["tests"]
        entries = applicability_entries()
        for test_id in (case.id for case in TESTS):
            self.assertIn(test_id, trace, f"missing traceability entry for {test_id}")
        for test_id, requirement_ids in trace.items():
            for requirement_id in requirement_ids:
                self.assertIn(requirement_id, entries, requirement_id)
                self.assertIn(test_id, entries[requirement_id]["checks"], requirement_id)

    def test_summary_counts_are_disclosed_not_inflated(self):
        executed = [case.id for case in TESTS]
        summary = applicability_summary("MHS-Sim", "CL4", executed)
        # Suite 1.2.0 (WP-07a): 51 requirements have an executable check (38 before
        # the static, e-stop and suite self-checks were added; TCAP-001/TCAP-002
        # check no numbered requirement and are not counted); 52 since TSAFE-001 also checks SAFE-048
        # (RE-ENABLE-AND-TERMINAL-STOP).
        self.assertEqual(summary["checked"], 52)
        self.assertEqual(summary["normative_ids"], 583)
        self.assertEqual(
            summary["checked"] + summary["dispositioned"] + summary["not_verified"],
            summary["normative_ids"],
        )
        line = coverage_disclosure("MHS-Sim", "CL4", executed)
        self.assertIn("checked=52", line)
        self.assertIn("not_verified=269", line)
        self.assertIn("not a claim of full normative coverage", line)

    def test_report_contains_coverage_limitation(self):
        report = _run(())
        matching = [
            item for item in report["limitations"] if "requirement coverage" in item
        ]
        self.assertEqual(len(matching), 1, report["limitations"])
        self.assertIn("checked=52", matching[0])
        self.assertIn("not_verified=269", matching[0])

    def test_artifact_is_machine_readable(self):
        document = json.loads(APPLICABILITY_FILE.read_text(encoding="utf-8"))
        self.assertEqual(document["artifact"], "mhs-conformance-applicability")
        self.assertEqual(document["counts"]["normative_ids"], 583)
        self.assertEqual(len(document["requirements"]), 583)


class _FakeClient:
    def request(self, method, params):
        raise MHSError("MHS.PROTOCOL.METHOD_NOT_FOUND", "unknown method")


class _FakeContext:
    def __init__(self, client=None):
        self.client = client or _FakeClient()
        self.primary_device = {
            "device_id": "mhs://fake/device",
            "capabilities": [{"capability_id": "cap.world.step.v1"}],
        }
        self.primary_capability = {"capability_id": "cap.world.step.v1"}
        self.primary_resource = "state"
        self._session = "mhs_s_fake"

    def ensure_session(self):
        return self._session


def _probe_params(ctx, method):
    from mhs.conformance import presence

    return presence._probe_params(ctx, method, METHOD_PROBES[method])


if __name__ == "__main__":
    unittest.main()
