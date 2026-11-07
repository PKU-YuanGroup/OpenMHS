"""Explicit cancellation follows the binding admitted for this operation.

The controlled bridge holds the native owner until a test releases it or the
real operation event is observed. No server method or cancellation event is
replaced. Response deadlines, protective stops and retained receipts keep their
separate contracts.
"""

from __future__ import annotations

import threading
import time
import unittest

from mhs import signals
from mhs.errors import MHSError
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope

from ._support import FIDELITY, STOP, Rpc, StubBridge, error_code, open_session, ulid, wait_until
from .test_long_running import JOB, records_for, wait_done
from tests.surfaces._support import client


class HeldJob(StubBridge):
    def __init__(self):
        super().__init__()
        self.release = threading.Event()
        self.entered = threading.Event()
        self.cancel_seen = threading.Event()
        self.ignore_cancel = False
        self.finish_error = None
        self.native_resources = []

    def call(self, capability_id, args=None, ctx=None):
        if capability_id != JOB:
            return super().call(capability_id, args, ctx)
        self._record(JOB)
        self.native_resources.append(ctx.resource)
        self.entered.set()
        while not self.release.wait(0.002):
            if ctx.cancel_event.is_set():
                self.cancel_seen.set()
                if not self.ignore_cancel:
                    raise signals.Cancelled("controlled native acknowledgement")
        if self.finish_error is not None:
            raise self.finish_error
        return {"done": True}


class OperationCancellabilityTests(unittest.TestCase):
    def endpoint(self, *, bindings=(("axis", False),), long_running=True, max_duration_ms=5000):
        bridge = HeldJob()
        capabilities = [Capability(STOP, "axis", input_schema={"type": "object"})]
        for resource, cancellable in bindings:
            constraints = {"long_running": long_running, "max_duration_ms": max_duration_ms}
            if cancellable is not None:
                constraints["cancellable"] = cancellable
            capabilities.append(Capability(JOB, resource, input_schema={"type": "object"},
                                           constraints=constraints))
        device = Device(bridge.device_id, "Controlled cancellation", mode="simulated",
                        resources=[Resource(r, "motion.axis", state_schema={"type": "object"})
                                   for r in dict.fromkeys(["axis", *(r for r, _ in bindings)])],
                        capabilities=capabilities, bridge=bridge, fidelity=dict(FIDELITY),
                        safety=SafetyEnvelope(risk_class="R1",
                            estop={"kind": "software", "latching": True, "latency_ms": 50},
                            safe_state={"description": "stopped", "achieved_by": [STOP]}))
        server = MHSServer("mhs://localhost/cancel-contract", [device], strict=True, log_ready=False)
        rpc = Rpc(server)
        rpc("mhs.hello", protocol_versions=["1.0"])
        session = open_session(rpc, device, principal={"id": "agent:owner", "kind": "agent"})

        def cleanup():
            bridge.release.set()
            for operation in tuple(server._operations.values()):
                operation.done.wait(2)
            server.close()
        self.addCleanup(cleanup)
        return server, rpc, device, bridge, session

    def start(self, server, rpc, device, bridge, session, resource="axis"):
        receipt = rpc("mhs.command", session_id=session, device_id=device.device_id,
                      capability_id=JOB, resource=resource, input={}, deadline_ms=15, command_id=ulid())
        self.assertIn(receipt["status"], {"running", "unknown"}, receipt)
        self.assertTrue(bridge.entered.wait(1))
        operation = server._operations[receipt["operation_id"]]
        self.assertFalse(operation.done.is_set())
        self.assertEqual(operation.resource, resource)
        self.assertFalse(operation.cancel_event.is_set(), "a response deadline is not cancellation")
        return operation

    def cancel(self, rpc, session, operation, deadline_ms=20):
        return rpc.raw("mhs.operations.cancel", session_id=session, operation_id=operation.operation_id,
                       deadline_ms=deadline_ms, reason="explicit client cancellation")

    def assert_refused(self, server, rpc, bridge, session, operation):
        retained = operation.receipt
        evidence = records_for(server, operation.command_id)
        for _ in range(2):
            started = time.monotonic()
            response = self.cancel(rpc, session, operation, deadline_ms=3000)
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertEqual(error_code(response), "MHS.OPERATION.NOT_CANCELLABLE", response)
            self.assertFalse(operation.cancel_event.is_set())
            self.assertFalse(bridge.cancel_seen.is_set())
            self.assertIsNone(operation.cancel_reason)
            self.assertIs(operation.receipt, retained)
            self.assertIsNone(operation.final_receipt)
            self.assertFalse(operation.done.is_set())
            self.assertIs(server._operations[operation.operation_id], operation)
            self.assertEqual(records_for(server, operation.command_id), evidence)

    def test_false_or_omitted_flag_refuses_without_touching_live_owner(self):
        for declared in (False, None):
            for long_running in (True, False):
                with self.subTest(declared=declared, long_running=long_running):
                    setup = self.endpoint(bindings=(("axis", declared),), long_running=long_running)
                    server, rpc, device, bridge, session = setup
                    operation = self.start(*setup)
                    self.assert_refused(server, rpc, bridge, session, operation)
                    bridge.release.set()
                    self.assertEqual(wait_done(server, operation.operation_id)["status"], "completed")
                    replay = rpc("mhs.command", session_id=session, capability_id=JOB, resource="axis",
                                 input={}, deadline_ms=1000, command_id=operation.command_id)
                    self.assertEqual((replay["status"], replay["replayed"]), ("completed", True))
                    self.assertEqual(bridge.count(JOB), 1)

    def test_cancellable_owner_still_receives_and_acknowledges_cancel(self):
        setup = self.endpoint(bindings=(("axis", True),))
        server, rpc, device, bridge, session = setup
        operation = self.start(*setup)
        response = self.cancel(rpc, session, operation, deadline_ms=1000)
        self.assertEqual(response["result"]["status"], "cancelled", response)
        self.assertTrue(bridge.cancel_seen.is_set())
        self.assertTrue(operation.cancel_event.is_set())
        self.assertEqual(len(records_for(server, operation.command_id)), 1)

    def test_unacknowledged_cancel_is_bounded_pending_and_keeps_owner(self):
        setup = self.endpoint(bindings=(("axis", True),))
        server, rpc, device, bridge, session = setup
        bridge.ignore_cancel = True
        operation = self.start(*setup)
        started = time.monotonic()
        response = self.cancel(rpc, session, operation)["result"]
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertEqual(response["status"], "running")
        self.assertIs(response["cancellation"]["safe_state_achieved"], False)
        self.assertIsNone(operation.final_receipt)
        self.assertTrue(bridge.cancel_seen.wait(1))
        self.assertIs(server._operations[operation.operation_id], operation)

    def test_same_capability_on_other_resource_does_not_grant_cancellation(self):
        for bindings in ((("axis", True), ("other", False)), (("other", False), ("axis", True))):
            with self.subTest(bindings=bindings):
                setup = self.endpoint(bindings=bindings)
                server, rpc, device, bridge, session = setup
                operation = self.start(*setup, resource="other")
                self.assert_refused(server, rpc, bridge, session, operation)
                self.assertEqual(bridge.native_resources, ["other"])

    def test_same_capability_on_other_resource_does_not_remove_cancellation(self):
        setup = self.endpoint(bindings=(("axis", False), ("other", True)))
        server, rpc, device, bridge, session = setup
        operation = self.start(*setup, resource="other")
        self.assertEqual(self.cancel(rpc, session, operation, 1000)["result"]["status"], "cancelled")
        self.assertTrue(bridge.cancel_seen.is_set())

    def test_later_binding_mutation_cannot_grant_cancellation(self):
        setup = self.endpoint()
        server, rpc, device, bridge, session = setup
        operation = self.start(*setup)
        device.capability(JOB, "axis").constraints["cancellable"] = True
        self.assert_refused(server, rpc, bridge, session, operation)

    def test_later_binding_mutation_does_not_change_admitted_cancellation(self):
        setup = self.endpoint(bindings=(("axis", True),))
        server, rpc, device, bridge, session = setup
        operation = self.start(*setup)
        device.capability(JOB, "axis").constraints["cancellable"] = False
        self.assertEqual(self.cancel(rpc, session, operation, 1000)["result"]["status"], "cancelled")
        self.assertTrue(bridge.cancel_seen.is_set())

    def test_finished_noncancellable_operation_returns_exact_retained_receipt(self):
        for status, exception in (("completed", None), ("failed", RuntimeError("controlled failure")),
                                  ("rejected", signals.Busy()), ("cancelled", signals.Cancelled())):
            with self.subTest(status=status):
                setup = self.endpoint()
                server, rpc, device, bridge, session = setup
                bridge.finish_error = exception
                operation = self.start(*setup)
                bridge.release.set()
                final = wait_done(server, operation.operation_id)
                self.assertEqual(final["status"], status, final)
                evidence = records_for(server, operation.command_id)
                for _ in range(2):
                    self.assertEqual(self.cancel(rpc, session, operation)["result"], final)
                self.assertIs(operation.final_receipt, final)
                self.assertFalse(operation.cancel_event.is_set())
                self.assertIsNone(operation.cancel_reason)
                self.assertEqual(records_for(server, operation.command_id), evidence)
                self.assertEqual(bridge.count(JOB), 1)

    def test_session_and_principal_visibility_precede_refusal_and_terminal_replay(self):
        setup = self.endpoint()
        server, rpc, device, bridge, session = setup
        operation = self.start(*setup)
        stranger = open_session(rpc, device, principal={"id": "agent:stranger", "kind": "agent"})
        same_owner = open_session(rpc, device, principal={"id": "agent:owner", "kind": "agent"})
        for target in (operation.operation_id, "op_not_retained"):
            response = rpc.raw("mhs.operations.cancel", session_id=stranger, operation_id=target, deadline_ms=20)
            self.assertEqual(error_code(response), "MHS.OPERATION.UNKNOWN")
        self.assertEqual(error_code(self.cancel(rpc, same_owner, operation)), "MHS.OPERATION.NOT_CANCELLABLE")
        invalid_session = self.cancel(rpc, "mhs_s_not_retained", operation)
        self.assertNotEqual(error_code(invalid_session), "MHS.OPERATION.NOT_CANCELLABLE")
        self.assertIn("error", invalid_session)
        bridge.release.set()
        final = wait_done(server, operation.operation_id)
        self.assertEqual(error_code(self.cancel(rpc, stranger, operation)), "MHS.OPERATION.UNKNOWN")
        self.assertEqual(self.cancel(rpc, same_owner, operation)["result"], final)
        self.assertFalse(operation.cancel_event.is_set())

    def test_estop_still_reaches_noncancellable_operation_and_stop_path(self):
        setup = self.endpoint()
        server, rpc, device, bridge, session = setup
        operation = self.start(*setup)
        self.assert_refused(server, rpc, bridge, session, operation)
        rpc("mhs.safety.estop", session_id=session, reason="protective control", deadline_ms=1000)
        self.assertEqual(wait_done(server, operation.operation_id)["status"], "cancelled")
        self.assertTrue(bridge.cancel_seen.is_set())
        self.assertTrue(operation.cancel_event.is_set())
        self.assertGreater(bridge.count(STOP), 0)
        self.assertTrue(operation.cancel_reason.startswith("emergency stop:"))

    def test_execution_bound_keeps_noncancellable_owner_without_cancel_signal(self):
        setup = self.endpoint(max_duration_ms=80)
        server, rpc, device, bridge, session = setup
        operation = self.start(*setup)
        self.assertTrue(wait_until(lambda: operation.unknown_recorded.is_set(), timeout=1))
        self.assertEqual(operation.unknown_receipt["status"], "unknown")
        details = operation.unknown_receipt["error"]["details"]
        self.assertEqual(details["reason"], "max_duration_exceeded")
        self.assertIs(details["cancellation_requested"], False)
        self.assert_refused(server, rpc, bridge, session, operation)
        bridge.release.set()
        self.assertEqual(wait_done(server, operation.operation_id)["status"], "completed")
        self.assertEqual([r["status"] for r in records_for(server, operation.command_id)], ["unknown", "completed"])

    def test_stock_client_exposes_normative_error_without_cancelling_native_work(self):
        setup = self.endpoint()
        server, rpc, device, bridge, session = setup
        operation = self.start(*setup)
        stock = client(server)
        with self.assertRaises(MHSError) as caught:
            stock.cancel(operation.operation_id, session_id=session, deadline_ms=20)
        self.assertEqual(caught.exception.code, "MHS.OPERATION.NOT_CANCELLABLE")
        self.assertFalse(operation.cancel_event.is_set())
        self.assertFalse(bridge.cancel_seen.is_set())


if __name__ == "__main__":
    unittest.main()
