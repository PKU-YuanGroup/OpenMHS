"""Deadlines, long-running work and driver signals (WP-04 step 4e; plan 3.7).

Ports of the reviewer repros:

* sdk-core ``e2.py`` (SDK-09): a command that outlived its ``deadline_ms`` was
  cancelled by the deadline, and the evidence then held two receipts for one
  ``command_id`` (``unknown``, then the late ``cancelled``/``completed``) with
  nothing tying the second to the first;
* fit-lab-instruments ``t_long.py`` (FIT-06): an hour-long
  ``cap.thermal.setpoint.v1`` ramp was cancelled at the 500 ms client deadline
  and answered ``unknown`` instead of a running operation.

Plan 3.7: ``deadline_ms`` bounds only the wait for the response and never
cancels execution.  A ``long_running`` binding answers ``running`` with its
``operation_id`` and keeps executing within ``max_duration_ms``; any other
command answers ``unknown`` + ``MHS.OUTCOME.TIMEOUT`` (``retryable: false``).
Every command ends with exactly one final receipt: a late outcome after
``unknown`` replaces the stored receipt and is recorded as the reconciliation
of the unknown one.  Bridges signal outcomes with :mod:`mhs.signals`; any
other exception is ``MHS.ADAPTER.SHIM_FAILED`` with a redacted message.
"""

from __future__ import annotations

import asyncio
import threading
import time
import unittest
import warnings
from typing import Any

from mhs import canonical, signals
from mhs.bridge.base import Bridge, driver_failed
from mhs.evidence import verify_bundle
from mhs.schema import SchemaStore
from mhs.server import (
    Capability,
    Device,
    MHSServer,
    MHSStrictError,
    MHSStrictWarning,
    Resource,
    SafetyEnvelope,
)

from ._support import (
    LONG,
    MOVE,
    StubBridge,
    conveyor,
    error_code,
    open_session,
    stub_capabilities,
    stub_server,
    ulid,
    wait_until,
)

JOB = "x-cap.test.job.v1"
RAISE = "x-cap.test.raise.v1"
SETPOINT = "cap.thermal.setpoint.v1"
DELAY = "x-cap.mhs-test.delay.v1"
TERMINAL = frozenset({"completed", "failed", "rejected", "cancelled"})


class JobBridge(StubBridge):
    """A stub with a slow job (cooperative unless told otherwise) and a raising call."""

    def __init__(self) -> None:
        super().__init__()
        self.budgets: list[int] = []
        self.cancel_seen = threading.Event()
        self.raise_with: BaseException | None = None
        self.output: Any = {"ok": True}
        self.read_delay = 0.0

    def read(self, resource_id: str, fields=None, ctx=None):  # noqa: ANN001
        if self.read_delay:
            time.sleep(self.read_delay)
        return super().read(resource_id, fields, ctx)

    def call(self, capability_id: str, args=None, ctx=None):  # noqa: ANN001
        if capability_id == JOB:
            self._record(JOB)
            args = dict(args or {})
            self.budgets.append(ctx.remaining_ms())
            end = time.monotonic() + int(args.get("ms", 300)) / 1000.0
            while time.monotonic() < end:
                if ctx.cancel_event is not None and ctx.cancel_event.is_set():
                    self.cancel_seen.set()
                    if not args.get("ignore_cancel"):
                        raise signals.Cancelled("job cancelled")
                time.sleep(0.005)
            self.state["pos"] += 1
            return {"done": True}
        if capability_id == RAISE:
            self._record(RAISE)
            if self.raise_with is not None:
                raise self.raise_with
            return self.output
        return super().call(capability_id, args, ctx)


def job_capability(*, long_running: Any = True, max_duration_ms: Any = 5000, cancellable: bool = True,
                   exclusive: bool = False) -> Capability:
    constraints: dict[str, Any] = {"cancellable": cancellable}
    if long_running is not None:
        constraints["long_running"] = long_running
    if max_duration_ms is not None:
        constraints["max_duration_ms"] = max_duration_ms
    return Capability(JOB, "axis", input_schema={"type": "object", "properties": {
        "ms": {"type": "integer"}, "ignore_cancel": {"type": "boolean"}}},
        exclusive=exclusive, constraints=constraints)


def job_server(job: Capability | None = None, **kwargs: Any):
    extra = [job or job_capability(),
             Capability(RAISE, "axis", input_schema={"type": "object", "properties": {}})]
    bridge = JobBridge()
    server, rpc, device, bridge = stub_server(bridge, capabilities=stub_capabilities(extra=extra), **kwargs)
    return server, rpc, device, bridge, open_session(rpc, device)


def records_for(server: MHSServer, command_id: str) -> list[dict[str, Any]]:
    return [record for record in server.export_evidence()["receipts"]
            if record.get("command_id") == command_id]


def wait_done(server: MHSServer, operation_id: str, timeout: float = 5.0) -> dict[str, Any]:
    operation = server._operations[operation_id]
    if not operation.done.wait(timeout):
        raise AssertionError(f"operation {operation_id} did not finish within {timeout}s")
    assert operation.final_receipt is not None, operation
    return operation.final_receipt


class OneFinalReceiptMixin:
    def assert_one_final_receipt(self, server: MHSServer, device: Device, command_id: str,
                                 *, statuses: list[str]) -> dict[str, Any]:
        records = records_for(server, command_id)
        self.assertEqual([record["status"] for record in records], statuses, records)
        finals = [record for record in records if record["status"] in TERMINAL]
        self.assertEqual(len(finals), 1, records)
        final = finals[0]
        self.assertIs(records[-1], final, "the final receipt is the last record of the command")
        unknown = [record for record in records if record["status"] == "unknown"]
        reconciles = (final.get("x-vendor") or {}).get("reconciles")
        if unknown:
            # The late outcome is recorded as the reconciliation of the unknown receipt.
            self.assertIsInstance(reconciles, dict, final)
            self.assertEqual(reconciles["receipt_id"], unknown[-1]["receipt_id"], final)
            self.assertEqual(reconciles["status"], "unknown", final)
        else:
            self.assertIsNone(reconciles, final)
        stored = server._receipts.get((device.device_id, command_id))
        if final["status"] == "rejected":
            self.assertIsNone(stored, "a rejected outcome frees the command id")
        else:
            self.assertIsNotNone(stored)
            self.assertEqual(stored[1]["receipt_id"], final["receipt_id"], "the stored receipt is the final one")
        report = verify_bundle(server.export_evidence())
        self.assertTrue(report.valid, report.errors)
        return final


class ReviewerReproTests(OneFinalReceiptMixin, unittest.TestCase):
    def test_e2_a_timed_out_command_keeps_running_and_reconciles(self) -> None:
        """sdk-core e2.py: unknown at the deadline, then exactly one final receipt."""
        server, rpc, device, session = conveyor()
        command_id = ulid()
        started = time.monotonic()
        receipt = rpc("mhs.command", session_id=session, capability_id=DELAY, input={"ms": 600},
                      deadline_ms=200, command_id=command_id)
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertEqual(receipt["status"], "unknown", receipt)
        self.assertEqual(error_code(receipt), "MHS.OUTCOME.TIMEOUT", receipt)
        self.assertIs(receipt["error"]["retryable"], False, receipt)
        self.assertNotIn("cancellation", receipt, "the deadline never cancels execution")
        details = receipt["error"]["details"]
        self.assertEqual(details["operation_id"], receipt["operation_id"])
        self.assertIs(details["cancellation_requested"], False)
        self.assertEqual(details["reason"], "deadline_exceeded")
        # Until it ends, the operation (and a replay of the command) shows its live state.
        live = rpc("mhs.operations.get", session_id=session, operation_id=receipt["operation_id"],
                   deadline_ms=1000)
        self.assertEqual(live["status"], "running", live)
        self.assertEqual(live["x-vendor"]["unknown_receipt_id"], receipt["receipt_id"])
        self.assertNotEqual(live["receipt_id"], receipt["receipt_id"])
        self.assertNotIn("error", live)
        replay = rpc("mhs.command", session_id=session, capability_id=DELAY, input={"ms": 600},
                     deadline_ms=200, command_id=command_id)
        self.assertEqual((replay["status"], replay["replayed"]), ("running", True), replay)

        final = wait_done(server, receipt["operation_id"])
        self.assertEqual(final["status"], "completed", final)
        self.assertIs(final["output"]["cancelled"], False, final)
        self.assertGreaterEqual(final["output"]["slept_ms"], 600)
        fetched = rpc("mhs.operations.get", session_id=session, operation_id=receipt["operation_id"],
                      deadline_ms=1000)
        self.assertEqual(fetched["receipt_id"], final["receipt_id"])
        self.assert_one_final_receipt(server, device, command_id, statuses=["unknown", "completed"])
        retry = rpc("mhs.command", session_id=session, capability_id=DELAY, input={"ms": 600},
                    deadline_ms=200, command_id=command_id)
        self.assertEqual((retry["status"], retry["replayed"]), ("completed", True), retry)
        self.assertEqual(retry["receipt_id"], final["receipt_id"])

    def test_e2_an_explicit_cancel_of_the_legacy_delay_is_cancelled(self) -> None:
        """e2.py E-cancel: the conveyor delay returns the legacy {'cancelled': True}."""
        server, rpc, device, session = conveyor()
        command_id = ulid()
        holder: dict[str, Any] = {}
        thread = threading.Thread(target=lambda: holder.update(r=rpc(
            "mhs.command", session_id=session, capability_id=DELAY, input={"ms": 1500},
            deadline_ms=3000, command_id=command_id)))
        thread.start()
        self.assertTrue(wait_until(lambda: any(op.command_id == command_id for op in server._operations.values())))
        operation_id = next(op.operation_id for op in server._operations.values() if op.command_id == command_id)
        time.sleep(0.05)
        rpc("mhs.operations.cancel", session_id=session, operation_id=operation_id, deadline_ms=2000)
        thread.join(5.0)
        self.assertEqual(holder["r"]["status"], "cancelled", holder)
        self.assert_one_final_receipt(server, device, command_id, statuses=["cancelled"])

    def test_t_long_a_long_running_setpoint_returns_running_and_completes(self) -> None:
        """fit-lab-instruments t_long.py: the ramp keeps running past the client deadline."""

        class Cryostat(Bridge):
            def __init__(self) -> None:
                super().__init__(device_id="mhs://localhost:7608/cryo")
                self.T = 300.0
                self.cancelled = False
                self.budget_ms: int | None = None

            def read(self, rid, fields=None, ctx=None):  # noqa: ANN001
                return {"setpoint": self.T}

            def call(self, cid, args, ctx=None):  # noqa: ANN001
                self.budget_ms = ctx.remaining_ms()
                for _ in range(60):  # "wait until the temperature is stable" (hours in reality)
                    if ctx is not None and ctx.cancelled():
                        self.cancelled = True
                        return {"setpoint": args["target_temperature"], "reached": False}
                    time.sleep(0.01)
                self.T = args["target_temperature"]
                return {"setpoint": self.T, "reached": True}

        bridge = Cryostat()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", MHSStrictWarning)
            dev = Device("mhs://localhost:7608/cryo", "cryostat", mode="hardware",
                         resources=[Resource("zone", "thermal.zone")],
                         capabilities=[Capability(SETPOINT, "zone", verb="write", input_schema={
                             "type": "object",
                             "properties": {"target_temperature": {"type": "number"}, "wait": {"type": "boolean"}},
                             "required": ["target_temperature"]},
                             constraints={"max_duration_ms": 3600000, "cancellable": True, "long_running": True})],
                         safety=SafetyEnvelope(risk_class="R2"), bridge=bridge)
            srv = MHSServer(endpoint_id="mhs://localhost:7608", devices=[dev], log_ready=False)

        def rpc(method: str, params: dict[str, Any]) -> dict[str, Any]:
            response = srv.handle({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
            response = response.to_dict() if hasattr(response, "to_dict") else response
            return response.get("result", response.get("error"))

        rpc("mhs.hello", {"mhs_versions": ["1.0"], "client": {"name": "t", "version": "0"}})
        sid = rpc("mhs.session.open", {"device_ids": [dev.device_id], "mode": "hardware",
                                       "principal": {"id": "t", "kind": "agent"}})["session_id"]
        command_id = canonical.ulid()
        params = {"session_id": sid, "device_id": dev.device_id, "capability_id": SETPOINT,
                  "input": {"target_temperature": 4.2, "wait": True}, "deadline_ms": 200,
                  "command_id": command_id}
        started = time.monotonic()
        receipt = rpc("mhs.command", params)
        self.assertLess(time.monotonic() - started, 0.45)
        self.assertEqual(receipt["status"], "running", receipt)
        self.assertRegex(receipt["operation_id"], r"^op_[0-9A-HJKMNP-TV-Z]{26}$")
        self.assertNotIn("error", receipt)
        self.assertEqual(SchemaStore().validate(receipt, "receipt.schema.json"), [])
        # The bridge's budget is the execution bound, not the 200 ms response deadline.
        self.assertGreater(bridge.budget_ms, 3_000_000)
        replay = rpc("mhs.command", params)
        self.assertEqual((replay["status"], replay["replayed"]), ("running", True), replay)
        self.assertEqual(replay["operation_id"], receipt["operation_id"])

        final = wait_done(srv, receipt["operation_id"])
        self.assertFalse(bridge.cancelled, "the deadline must not cancel a long-running ramp")
        self.assertEqual(bridge.T, 4.2)
        self.assertEqual(final["status"], "completed", final)
        self.assertTrue(final["output"]["reached"])
        self.assertEqual(rpc("mhs.operations.get", {"session_id": sid, "operation_id": receipt["operation_id"],
                                                    "deadline_ms": 1000})["status"], "completed")
        self.assert_one_final_receipt(srv, dev, command_id, statuses=["completed"])
        self.assertEqual((final["state_revision_before"], final["state_revision_after"]), (0, 1))


class LongRunningTests(OneFinalReceiptMixin, unittest.TestCase):
    def test_a_long_running_job_answers_running_then_completes(self) -> None:
        server, rpc, device, bridge, session = job_server()
        command_id = ulid()
        receipt = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 400},
                      deadline_ms=100, command_id=command_id)
        self.assertEqual(receipt["status"], "running", receipt)
        self.assertEqual(receipt["progress"], {"percent": 0})
        self.assertNotIn("state_revision_after", receipt)
        self.assertEqual(records_for(server, command_id), [], "a running receipt is not evidence")
        listed = rpc("mhs.operations.list", session_id=session)["operations"]
        self.assertEqual([op["state"] for op in listed if op["operation_id"] == receipt["operation_id"]],
                         ["running"])
        final = wait_done(server, receipt["operation_id"])
        self.assertEqual(final["status"], "completed", final)
        self.assertFalse(bridge.cancel_seen.is_set())
        self.assertGreater(bridge.budgets[0], 4000, "the bridge is bounded by max_duration_ms")
        self.assert_one_final_receipt(server, device, command_id, statuses=["completed"])

    def test_a_quick_long_running_job_completes_inside_the_deadline(self) -> None:
        server, rpc, device, bridge, session = job_server()
        receipt = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 20},
                      deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_an_estop_cancels_a_long_running_job(self) -> None:
        server, rpc, device, bridge, session = job_server()
        command_id = ulid()
        receipt = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 3000},
                      deadline_ms=50, command_id=command_id)
        self.assertEqual(receipt["status"], "running", receipt)
        rpc("mhs.safety.estop", session_id=session, reason="test", deadline_ms=1000)
        final = wait_done(server, receipt["operation_id"])
        self.assertEqual(final["status"], "cancelled", final)
        self.assert_one_final_receipt(server, device, command_id, statuses=["cancelled"])
        rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)

    def test_operations_cancel_cancels_a_long_running_job(self) -> None:
        server, rpc, device, bridge, session = job_server()
        command_id = ulid()
        receipt = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 3000},
                      deadline_ms=50, command_id=command_id)
        cancelled = rpc("mhs.operations.cancel", session_id=session, operation_id=receipt["operation_id"],
                        deadline_ms=2000)
        self.assertEqual(cancelled["status"], "cancelled", cancelled)
        self.assertEqual(cancelled["cancellation"]["reason"], "cancelled by client")
        self.assert_one_final_receipt(server, device, command_id, statuses=["cancelled"])

    def test_max_duration_bounds_a_cooperative_job(self) -> None:
        server, rpc, device, bridge, session = job_server(job_capability(max_duration_ms=300))
        command_id = ulid()
        receipt = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 3000},
                      deadline_ms=100, command_id=command_id)
        self.assertEqual(receipt["status"], "running", receipt)
        final = wait_done(server, receipt["operation_id"], timeout=3.0)
        self.assertEqual(final["status"], "cancelled", final)
        self.assertEqual(final["cancellation"]["reason"], "max_duration_ms exceeded")
        self.assert_one_final_receipt(server, device, command_id, statuses=["cancelled"])

    def test_max_duration_bounds_a_job_that_ignores_cancellation(self) -> None:
        server, rpc, device, bridge, session = job_server(job_capability(max_duration_ms=200))
        command_id = ulid()
        receipt = rpc("mhs.command", session_id=session, capability_id=JOB,
                      input={"ms": 1200, "ignore_cancel": True}, deadline_ms=80, command_id=command_id)
        self.assertEqual(receipt["status"], "running", receipt)
        operation_id = receipt["operation_id"]
        self.assertTrue(wait_until(
            lambda: (server._receipts.get((device.device_id, command_id)) or (None, {}))[1].get("status") == "unknown",
            timeout=2.0))
        unknown = server._receipts[(device.device_id, command_id)][1]
        self.assertEqual(error_code(unknown), "MHS.OUTCOME.TIMEOUT")
        self.assertEqual(unknown["error"]["details"]["reason"], "max_duration_exceeded")
        self.assertEqual(unknown["error"]["details"]["max_duration_ms"], 200)
        self.assertIs(unknown["error"]["retryable"], False)
        self.assertEqual(unknown["cancellation"]["reason"], "max_duration_ms exceeded")
        self.assertTrue(bridge.cancel_seen.is_set(), "the execution bound requests cancellation")
        live = rpc("mhs.operations.get", session_id=session, operation_id=operation_id, deadline_ms=1000)
        self.assertEqual(live["status"], "running", live)
        self.assertEqual(live["x-vendor"]["unknown_receipt_id"], unknown["receipt_id"])
        final = wait_done(server, operation_id)
        self.assertEqual(final["status"], "completed", final)
        self.assert_one_final_receipt(server, device, command_id, statuses=["unknown", "completed"])

    def test_a_long_running_binding_without_a_bound_gets_the_endpoint_bound(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", MHSStrictWarning)
            server, rpc, device, bridge, session = job_server(job_capability(max_duration_ms=None))
        receipt = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 150},
                      deadline_ms=50)
        self.assertEqual(receipt["status"], "running", receipt)
        wait_done(server, receipt["operation_id"])
        self.assertGreater(bridge.budgets[0], 500_000)
        self.assertLessEqual(bridge.budgets[0], 600_000)

    def test_a_replay_while_running_returns_the_running_receipt(self) -> None:
        server, rpc, device, bridge, session = job_server()
        command_id = ulid()
        first = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 400},
                    deadline_ms=50, command_id=command_id)
        again = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 400},
                    deadline_ms=50, command_id=command_id)
        self.assertEqual((again["status"], again["replayed"]), ("running", True), again)
        self.assertEqual(again["operation_id"], first["operation_id"])
        self.assertEqual(bridge.count(JOB), 1)
        wait_done(server, first["operation_id"])
        self.assert_one_final_receipt(server, device, command_id, statuses=["completed"])


class DeadlineTests(OneFinalReceiptMixin, unittest.TestCase):
    def test_the_deadline_never_cancels_a_cancellable_command(self) -> None:
        server, rpc, device, bridge, session = job_server(job_capability(long_running=None))
        command_id = ulid()
        receipt = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 300},
                      deadline_ms=60, command_id=command_id)
        self.assertEqual(receipt["status"], "unknown", receipt)
        self.assertEqual(error_code(receipt), "MHS.OUTCOME.TIMEOUT")
        self.assertIs(receipt["error"]["retryable"], False)
        self.assertNotIn("cancellation", receipt)
        self.assertEqual(receipt["error"]["details"]["reason"], "deadline_exceeded")
        self.assertEqual(receipt["error"]["details"]["max_duration_ms"], 5000)
        final = wait_done(server, receipt["operation_id"])
        self.assertEqual(final["status"], "completed", final)
        self.assertFalse(bridge.cancel_seen.is_set(), "the deadline cancelled the command")
        self.assertGreater(bridge.budgets[0], 4000, "the bridge budget is the execution bound")
        self.assert_one_final_receipt(server, device, command_id, statuses=["unknown", "completed"])

    def test_the_stub_long_capability_is_not_cancelled_by_its_deadline(self) -> None:
        server, rpc, device, bridge = stub_server()
        session = open_session(rpc, device)
        command_id = ulid()
        receipt = rpc("mhs.command", session_id=session, capability_id=LONG, input={"ms": 250},
                      deadline_ms=50, command_id=command_id)
        self.assertEqual(receipt["status"], "unknown", receipt)
        final = wait_done(server, receipt["operation_id"])
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(final["output"]["slept_ms"], 250)

    def test_a_max_duration_below_the_deadline_cancels_a_cooperative_command(self) -> None:
        server, rpc, device, bridge, session = job_server(job_capability(long_running=None, max_duration_ms=150))
        command_id = ulid()
        started = time.monotonic()
        receipt = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 3000},
                      deadline_ms=3000, command_id=command_id)
        self.assertLess(time.monotonic() - started, 1.5, "bounded by max_duration_ms, not the deadline")
        self.assertEqual(receipt["status"], "cancelled", receipt)
        self.assertEqual(receipt["cancellation"]["reason"], "max_duration_ms exceeded")
        self.assert_one_final_receipt(server, device, command_id, statuses=["cancelled"])

    def test_a_max_duration_below_the_deadline_is_the_reported_bound(self) -> None:
        server, rpc, device, bridge, session = job_server(job_capability(long_running=None, max_duration_ms=150))
        command_id = ulid()
        started = time.monotonic()
        receipt = rpc("mhs.command", session_id=session, capability_id=JOB,
                      input={"ms": 900, "ignore_cancel": True}, deadline_ms=3000, command_id=command_id)
        self.assertLess(time.monotonic() - started, 1.5, "bounded by max_duration_ms, not the deadline")
        self.assertEqual(receipt["status"], "unknown", receipt)
        details = receipt["error"]["details"]
        self.assertEqual(details["reason"], "max_duration_exceeded")
        self.assertEqual((details["max_duration_ms"], details["deadline_ms"]), (150, 3000))
        self.assertIs(details["cancellation_requested"], True)
        self.assertIn("150 ms", receipt["error"]["message"])
        self.assertNotIn("3000 ms deadline", receipt["error"]["message"])
        self.assertEqual(receipt["cancellation"]["reason"], "max_duration_ms exceeded")
        self.assertTrue(bridge.cancel_seen.is_set())
        final = wait_done(server, receipt["operation_id"])
        self.assertEqual(final["status"], "completed", final)
        self.assert_one_final_receipt(server, device, command_id, statuses=["unknown", "completed"])

    def _slow_interlock_server(self, delay_s: float):
        class SlowInterlocks(JobBridge):
            def interlocks(self):
                time.sleep(delay_s)
                return [{"id": "door", "state": "closed"}]

        safety = SafetyEnvelope(risk_class="R1", estop={"kind": "software", "latching": True, "latency_ms": 50},
                                safe_state={"description": "axis stopped", "achieved_by": ["cap.motion.stop.v1"]},
                                interlocks=[{"id": "door", "required_for": [JOB]}])
        server, rpc, device, bridge = stub_server(
            SlowInterlocks(), safety=safety,
            capabilities=stub_capabilities(extra=[job_capability(long_running=None)]))
        return server, rpc, device, bridge, open_session(rpc, device)

    def test_the_deadline_counts_from_the_request(self) -> None:
        """PROTO-011: slow pre-checks (an interlock read) use up the same budget."""
        server, rpc, device, bridge, session = self._slow_interlock_server(0.3)
        started = time.monotonic()
        receipt = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 600},
                      deadline_ms=450)
        elapsed = time.monotonic() - started
        self.assertEqual(receipt["status"], "unknown", receipt)
        self.assertLess(elapsed, 0.65, "the response deadline started after the pre-checks")
        wait_done(server, receipt["operation_id"])

    def test_a_deadline_that_passes_in_the_pre_checks_dispatches_nothing(self) -> None:
        """OP-012: not yet accepted when the deadline passed -> no effect, a truthful refusal."""
        server, rpc, device, bridge, session = self._slow_interlock_server(0.35)
        command_id = ulid()
        receipt = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 50},
                      deadline_ms=200, command_id=command_id)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.OUTCOME.TIMEOUT")
        self.assertEqual(receipt["error"]["details"]["reason"], "deadline_exceeded_before_dispatch")
        self.assertIs(receipt["error"]["retryable"], True)
        self.assertEqual(bridge.count(JOB), 0)
        self.assertFalse(server._device_locks.get(device.device_id, threading.Lock()).locked())
        retry = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 50},
                    deadline_ms=3000, command_id=command_id)
        self.assertEqual((retry["status"], retry["replayed"]), ("completed", False), retry)

    def test_the_unknown_receipt_does_not_wait_for_a_slow_state_read(self) -> None:
        """4d r2 verifier q3: the deadline receipt read the state without a bound."""
        server, rpc, device, bridge, session = job_server(job_capability(long_running=None))
        bridge.read_delay = 0.6
        started = time.monotonic()
        receipt = rpc("mhs.command", session_id=session, capability_id=JOB, input={"ms": 1500},
                      deadline_ms=400)
        elapsed = time.monotonic() - started
        self.assertEqual(receipt["status"], "unknown", receipt)
        self.assertLess(elapsed, 0.65, f"answered after {elapsed:.2f}s for a 400 ms deadline")
        bridge.read_delay = 0.0
        wait_done(server, receipt["operation_id"])

    def test_exactly_one_final_receipt_when_completion_races_the_deadline(self) -> None:
        server, rpc, device, bridge, session = job_server(job_capability(long_running=None))
        command_ids = [ulid() for _ in range(40)]
        receipts: dict[str, dict[str, Any]] = {}

        def run(index: int, command_id: str) -> None:
            receipts[command_id] = rpc("mhs.command", session_id=session, capability_id=JOB,
                                       input={"ms": 30 + index % 7 * 5}, deadline_ms=45 + index % 5 * 5,
                                       command_id=command_id)

        threads = [threading.Thread(target=run, args=(i, cid)) for i, cid in enumerate(command_ids)]
        [thread.start() for thread in threads]
        [thread.join(10.0) for thread in threads]
        for command_id in command_ids:
            receipt = receipts[command_id]
            if receipt["status"] == "rejected":
                # OP-012: a thread that was not scheduled for longer than its deadline (a loaded machine) finds the deadline
                # passed in the pre-checks; nothing was dispatched, no operation exists and the command id is free.
                self.assertEqual(error_code(receipt), "MHS.OUTCOME.TIMEOUT", receipt)
                self.assertEqual(receipt["error"]["details"]["reason"], "deadline_exceeded_before_dispatch", receipt)
                self.assert_one_final_receipt(server, device, command_id, statuses=["rejected"])
                continue
            wait_done(server, receipt["operation_id"])
            expected = ["completed"] if receipt["status"] == "completed" else ["unknown", "completed"]
            with self.subTest(command_id=command_id, answered=receipt["status"]):
                self.assertIn(receipt["status"], ("completed", "unknown"), receipt)
                self.assert_one_final_receipt(server, device, command_id, statuses=expected)


class DriverSignalTests(OneFinalReceiptMixin, unittest.TestCase):
    def _raise(self, exc: BaseException | None, *, output: Any = None, deadline_ms: int = 1000):
        server, rpc, device, bridge, session = job_server()
        bridge.raise_with = exc
        if output is not None:
            bridge.output = output
        command_id = ulid()
        receipt = rpc("mhs.command", session_id=session, capability_id=RAISE, input={},
                      deadline_ms=deadline_ms, command_id=command_id)
        return server, rpc, device, bridge, session, command_id, receipt

    def test_any_other_exception_is_shim_failed_with_a_redacted_message(self) -> None:
        _s, _r, _d, _b, _ss, _c, receipt = self._raise(
            RuntimeError("connect to 10.0.0.7 as admin:hunter2 failed at /Users/alice/lab.py"))
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(error_code(receipt), "MHS.ADAPTER.SHIM_FAILED")
        text = repr(receipt["error"])
        for secret in ("hunter2", "10.0.0.7", "/Users/alice"):
            self.assertNotIn(secret, text)
        self.assertEqual(receipt["error"]["details"]["exception_type"], "RuntimeError")

    def test_driver_failed_is_a_failed_receipt_with_its_code(self) -> None:
        _s, _r, _d, _b, _ss, _c, receipt = self._raise(
            signals.DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "door not homed", native_code=17))
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(error_code(receipt), "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(receipt["error"]["message"], "door not homed")
        self.assertEqual(receipt["error"]["details"]["native_code"], 17)

    def test_a_bridge_driver_failed_signal_keeps_its_code(self) -> None:
        _s, _r, _d, _b, _ss, _c, receipt = self._raise(
            driver_failed("MHS.DEVICE.FAULTED", "over-temperature", native_code="E42"))
        self.assertEqual((receipt["status"], error_code(receipt)), ("failed", "MHS.DEVICE.FAULTED"), receipt)
        self.assertEqual(receipt["error"]["details"]["native_code"], "E42")

    def test_busy_is_rejected_and_frees_the_command_id(self) -> None:
        server, rpc, device, bridge, session, command_id, receipt = self._raise(
            signals.Busy("tray is moving", retry_after_ms=250))
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.DEVICE.BUSY")
        self.assertIs(receipt["error"]["retryable"], True)
        self.assertEqual(receipt["error"]["details"]["retry_after_ms"], 250)
        self.assertEqual(receipt["state_revision_before"], receipt["state_revision_after"])
        bridge.raise_with = None
        retry = rpc("mhs.command", session_id=session, capability_id=RAISE, input={},
                    deadline_ms=1000, command_id=command_id)
        self.assertEqual((retry["status"], retry["replayed"]), ("completed", False), retry)
        self.assertEqual(bridge.count(RAISE), 2)

    def test_outcome_unknown_is_an_unknown_receipt(self) -> None:
        _s, _r, _d, _b, _ss, _c, receipt = self._raise(signals.OutcomeUnknown("reply lost"))
        self.assertEqual(receipt["status"], "unknown", receipt)
        self.assertEqual(error_code(receipt), "MHS.OUTCOME.UNKNOWN")
        self.assertIs(receipt["error"]["retryable"], False)

    def test_cancelled_signals_are_cancelled_receipts(self) -> None:
        for exc in (signals.Cancelled("stopped"), asyncio.CancelledError(),
                    __import__("concurrent.futures").futures.CancelledError()):
            with self.subTest(exc=type(exc).__name__):
                server, _r, device, _b, _ss, command_id, receipt = self._raise(exc)
                self.assertEqual(receipt["status"], "cancelled", receipt)
                self.assertNotIn("error", receipt)
                self.assert_one_final_receipt(server, device, command_id, statuses=["cancelled"])

    def test_legacy_cancelled_outputs_are_cancelled_receipts(self) -> None:
        _s, _r, _d, _b, _ss, _c, receipt = self._raise(None, output={"status": "cancelled"})
        self.assertEqual(receipt["status"], "cancelled", receipt)

    def test_a_plain_mhs_error_keeps_its_code(self) -> None:
        from mhs.errors import MHSError

        _s, _r, _d, _b, _ss, _c, receipt = self._raise(
            MHSError("MHS.SAFETY.ENVELOPE_VIOLATION", "speed above the native limit", {"retryable": False}))
        self.assertEqual((receipt["status"], error_code(receipt)), ("failed", "MHS.SAFETY.ENVELOPE_VIOLATION"))

    def test_a_late_failure_after_unknown_reconciles(self) -> None:
        class LateFailure(JobBridge):
            def call(self, capability_id: str, args=None, ctx=None):  # noqa: ANN001
                if capability_id == RAISE:
                    time.sleep(0.25)
                    raise ValueError("secret detail")
                return super().call(capability_id, args, ctx)

        server, rpc, device, bridge = stub_server(LateFailure(), capabilities=stub_capabilities(extra=[
            Capability(RAISE, "axis", input_schema={"type": "object", "properties": {}})]))
        session = open_session(rpc, device)
        command_id = ulid()
        receipt = rpc("mhs.command", session_id=session, capability_id=RAISE, input={},
                      deadline_ms=50, command_id=command_id)
        self.assertEqual(receipt["status"], "unknown", receipt)
        final = wait_done(server, receipt["operation_id"])
        self.assertEqual((final["status"], error_code(final)), ("failed", "MHS.ADAPTER.SHIM_FAILED"))
        self.assertNotIn("secret", repr(final["error"]))
        self.assert_one_final_receipt(server, device, command_id, statuses=["unknown", "failed"])


class StrictLongRunningTests(unittest.TestCase):
    def _device(self, constraints: dict[str, Any], *, strict: bool) -> Device:
        return Device("mhs://localhost/strict/job", "job", mode="simulated",
                      resources=[Resource("axis", "motion.axis", state_schema={"type": "object"})],
                      capabilities=[Capability(JOB, "axis", input_schema={"type": "object", "properties": {}},
                                               output_schema={"type": "object"}, constraints=constraints)],
                      safety=SafetyEnvelope(risk_class="R0"),
                      fidelity={"engine": "t", "fidelity_level": "F0", "determinism": {"kind": "exact"},
                                "timestep_ms": 1, "realtime_factor": 0, "reset": "full",
                                "snapshot_restore": True, "gaps": ["test"]},
                      bridge=JobBridge(), strict=strict)

    def test_strict_mode_refuses_an_unbounded_or_malformed_long_running_binding(self) -> None:
        for constraints in ({"long_running": True}, {"long_running": "yes", "max_duration_ms": 1000}):
            with self.subTest(constraints=constraints):
                with self.assertRaises(MHSStrictError) as caught:
                    MHSServer("mhs://localhost/strict", [self._device(constraints, strict=True)],
                              log_ready=False, strict=True)
                findings = [f for f in caught.exception.findings if f.rule == "constraints-invalid"]
                self.assertTrue(findings, caught.exception.findings)
                self.assertEqual(findings[0].path, "constraints.long_running")

    def test_compatibility_mode_warns(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", MHSStrictWarning)
            MHSServer("mhs://localhost/strict", [self._device({"long_running": True}, strict=False)],
                      log_ready=False)
        self.assertTrue(any("long_running" in str(item.message) for item in caught),
                        [str(item.message) for item in caught])

    def test_a_bounded_long_running_binding_is_served_in_strict_mode(self) -> None:
        MHSServer("mhs://localhost/strict",
                  [self._device({"long_running": True, "max_duration_ms": 1000}, strict=True)],
                  log_ready=False, strict=True)


class CanonicalInputTests(unittest.TestCase):
    """Verifier 4c H2: an integer beyond 2**53 was MHS.INTERNAL.ERROR."""

    def test_an_input_that_is_not_canonical_json_is_input_invalid(self) -> None:
        server, rpc, device, bridge = stub_server()
        session = open_session(rpc, device)
        response = rpc.raw("mhs.command", session_id=session, capability_id=MOVE, input={"pos": 2 ** 60},
                           deadline_ms=1000)
        self.assertEqual(error_code(response), "MHS.CAPABILITY.INPUT_INVALID", response)
        self.assertEqual(bridge.count(MOVE), 0)
        write = rpc.raw("mhs.resource.write", session_id=session, resource_id="axis",
                        patch={"pos": 2 ** 60}, deadline_ms=1000)
        self.assertEqual(error_code(write), "MHS.CAPABILITY.INPUT_INVALID", write)
        permit = rpc.raw("mhs.safety.permit", session_id=session, capability_id=MOVE, resource="axis",
                         input={"pos": 2 ** 60}, input_digest="sha256:" + "0" * 64, ttl_s=60)
        self.assertEqual(error_code(permit), "MHS.CAPABILITY.INPUT_INVALID", permit)

    def test_an_estop_command_with_such_an_input_still_latches(self) -> None:
        estop = Capability("cap.motion.estop.v1", "axis", input_schema={"type": "object"})
        server, rpc, device, bridge = stub_server(capabilities=stub_capabilities(extra=[estop]))
        session = open_session(rpc, device)
        response = rpc.raw("mhs.command", session_id=session, capability_id="cap.motion.estop.v1",
                           input={"reason": "big", "n": 2 ** 60}, deadline_ms=1000)
        self.assertTrue(server._latched[device.device_id], response)
        self.assertIn("result", response, response)


if __name__ == "__main__":
    unittest.main()
