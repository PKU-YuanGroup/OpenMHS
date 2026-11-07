"""Reset semantics (SAFE-041/042/043; findings SPEC-03, SDK-11, SURF-01 endpoint part).

Ports of ``sdk-core/e1.py`` / ``sdk-core-verify/v11.py`` (reset with nothing
latched), ``spec/probe4.py`` (reset with an open interlock, checked by the
runtime against a stub bridge that would happily reset) and the endpoint part of
``verify-integration-surfaces/reset_noallow.py`` (a reset releases the latch
only; it never resumes the motion the e-stop interrupted).
"""

from __future__ import annotations

import threading
import time
import unittest

from mhs.server import Capability, SafetyEnvelope

from ._support import (
    LONG,
    MOVE,
    STOP,
    NativeStopBridge,
    conveyor,
    error_code,
    in_thread,
    open_session,
    release_retry,
    stub_capabilities,
    stub_server,
    wait_until,
)


def _guarded(*interlocks: dict) -> SafetyEnvelope:
    return SafetyEnvelope(
        risk_class="R1",
        interlocks=list(interlocks),
        estop={"kind": "software", "latching": True, "latency_ms": 50},
        safe_state={"description": "axis stopped", "achieved_by": [STOP]},
    )


class ResetNotLatchedTests(unittest.TestCase):
    def test_e1_reset_without_latch_is_refused(self) -> None:
        server, rpc, device, session = conveyor()
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=2000)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.RESET_REFUSED")
        self.assertEqual(receipt["error"]["details"]["reason"], "not_latched")

    def test_v11_second_reset_is_refused(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        first = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(first["status"], "completed", first)
        second = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(second["status"], "rejected", second)
        self.assertEqual(second["error"]["details"]["reason"], "not_latched")
        self.assertEqual(bridge.count("reset"), 1, "the refused reset reached the bridge")


class ResetInterlockTests(unittest.TestCase):
    def test_conveyor_reset_with_open_door_is_refused(self) -> None:
        server, rpc, device, session = conveyor()
        rpc("mhs.command", session_id=session, capability_id="x-cap.mhs-test.set_door.v1",
            input={"state": "open"}, deadline_ms=2000)
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=2000)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.RESET_REFUSED")
        self.assertEqual(receipt["error"]["interlocks"], [{"id": "door_closed", "state": "open"}])
        self.assertTrue(server._latched[device.device_id])
        # While latched the test hook is an effectful command and is refused;
        # the operator closes the door physically.
        refused = rpc("mhs.command", session_id=session, capability_id="x-cap.mhs-test.set_door.v1",
                      input={"state": "closed"}, deadline_ms=2000)
        self.assertEqual(error_code(refused), "MHS.SAFETY.ESTOP_ENGAGED")
        device.bridge.sim.set_door("closed")
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertFalse(server._latched[device.device_id])

    def test_runtime_checks_interlocks_not_the_bridge(self) -> None:
        bridge = NativeStopBridge()
        bridge.interlock_states = {"door": "open"}
        server, rpc, device, _ = stub_server(bridge, safety=_guarded({"id": "door", "source": "hardware"}))
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.RESET_REFUSED")
        self.assertEqual(receipt["error"]["details"]["reason"], "interlock_open")
        self.assertEqual(bridge.count("reset"), 0, "the bridge reset ran although an interlock is open")
        self.assertTrue(server._latched[device.device_id])

    def test_unreported_interlock_counts_as_unknown(self) -> None:
        bridge = NativeStopBridge()  # reports no interlock at all
        server, rpc, device, _ = stub_server(bridge, safety=_guarded({"id": "door", "source": "simulated"}))
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["interlocks"], [{"id": "door", "state": "unknown"}])

    def test_unreadable_interlocks_count_as_unknown(self) -> None:
        bridge = NativeStopBridge()
        bridge.interlock_states = {"door": "closed"}
        server, rpc, device, _ = stub_server(bridge, safety=_guarded({"id": "door"}))
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        bridge.interlocks_error = OSError("bus timeout")
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["interlocks"], [{"id": "door", "state": "unknown"}])
        bridge.interlocks_error = None
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["cleared_interlocks"], ["door"])

    def test_reset_exempt_interlock_does_not_block(self) -> None:
        bridge = NativeStopBridge()
        bridge.interlock_states = {"door": "closed", "latch_clear": "open"}
        safety = _guarded({"id": "door"}, {"id": "latch_clear", "reset_exempt": True,
                                           "required_for": ["cap.motion.move.v1"]})
        server, rpc, device, _ = stub_server(bridge, safety=safety)
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(bridge.count("reset"), 1)


class ResetNeverResumesTests(unittest.TestCase):
    """reset_noallow (endpoint part): reset releases the latch and nothing else."""

    def test_reset_by_another_principal_does_not_resume_motion(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        operator = open_session(rpc, device, principal={"id": "operator", "kind": "human"})
        other = open_session(rpc, device, principal={"id": "model", "kind": "agent"})
        thread, holder = in_thread(lambda: rpc(
            "mhs.command", session_id=operator, capability_id=LONG, input={"ms": 3000},
            deadline_ms=5000))
        self.assertTrue(wait_until(lambda: bridge.state["moving"], timeout=2.0))
        rpc("mhs.safety.estop", session_id=operator, reason="operator panic", deadline_ms=1000)
        thread.join(3.0)
        self.assertEqual(holder["result"]["status"], "cancelled")
        calls_before = list(bridge.calls)
        pos_before = bridge.state["pos"]
        receipt = rpc("mhs.safety.reset", session_id=other, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertFalse(receipt["output"]["resumed"])
        self.assertFalse(bridge.state["moving"])
        self.assertEqual(bridge.state["pos"], pos_before)
        new_calls = bridge.calls[len(calls_before):]
        self.assertEqual([c for c in new_calls if c not in ("reset", "interlocks")], [],
                         f"reset issued native calls: {new_calls}")
        operation = next(iter(server._operations.values()))
        self.assertEqual(operation.final_receipt["status"], "cancelled")
        follow_up = rpc("mhs.command", session_id=operator, capability_id="cap.motion.move.v1",
                        input={"pos": 2}, deadline_ms=1000)
        self.assertEqual(follow_up["status"], "completed", "a new command is required and works")

    def test_reset_refused_while_an_uncooperative_operation_runs(self) -> None:
        release = threading.Event()

        class Stubborn(NativeStopBridge):
            def call(self, capability_id, args=None, ctx=None):  # noqa: ANN001
                if capability_id == "x-cap.test.stubborn.v1":
                    self._record(capability_id)
                    release.wait(3.0)  # ignores ctx.cancel_event
                    return {"done": True}
                return super().call(capability_id, args, ctx)

        stubborn = Capability("x-cap.test.stubborn.v1", "axis", input_schema={"type": "object"},
                              exclusive=True, constraints={"max_duration_ms": 5000})
        bridge = Stubborn()
        server, rpc, device, _ = stub_server(bridge, capabilities=stub_capabilities(extra=[stubborn]))
        session = open_session(rpc, device)
        thread, holder = in_thread(lambda: rpc(
            "mhs.command", session_id=session, capability_id="x-cap.test.stubborn.v1", input={},
            deadline_ms=5000))
        self.assertTrue(wait_until(lambda: bridge.count("x-cap.test.stubborn.v1") == 1, timeout=2.0))
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        refused = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["details"]["reason"], "operation_running")
        self.assertEqual(bridge.count("reset"), 0)
        release.set()
        thread.join(3.0)
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_operation_running_check_does_not_trust_a_declared_read_verb(self) -> None:
        """A running effectful class bound with verb='read' still blocks the reset."""
        release = threading.Event()

        class Stubborn(NativeStopBridge):
            def call(self, capability_id, args=None, ctx=None):  # noqa: ANN001
                if capability_id == "cap.motion.home.v1":
                    self._record(capability_id)
                    release.wait(3.0)  # ignores ctx.cancel_event
                    return {"homed": True}
                return super().call(capability_id, args, ctx)

        home = Capability("cap.motion.home.v1", "axis", input_schema={"type": "object"},
                          verb="read", exclusive=True, constraints={"max_duration_ms": 5000})
        bridge = Stubborn()
        server, rpc, device, _ = stub_server(bridge, capabilities=stub_capabilities(extra=[home]))
        session = open_session(rpc, device)
        try:
            thread, holder = in_thread(lambda: rpc(
                "mhs.command", session_id=session, capability_id="cap.motion.home.v1", input={},
                deadline_ms=5000))
            self.assertTrue(wait_until(lambda: bridge.count("cap.motion.home.v1") == 1, timeout=2.0))
            rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
            refused = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["details"]["reason"], "operation_running")
            self.assertEqual(bridge.count("reset"), 0)
        finally:
            release.set()
        thread.join(3.0)


class ResetRaceTests(unittest.TestCase):
    """An e-stop engaged while a reset is in flight is never cleared by that reset.

    Port of the verifier probe ``verify-WP-04/4a1/probes/p_race_reset.py``: the
    reset passed its checks and is inside ``bridge.reset()`` when the operator
    presses the e-stop again.
    """

    def _slow_reset_server(self, seconds: float):
        entered = threading.Event()

        class SlowReset(NativeStopBridge):
            def reset(self, ctx=None):  # noqa: ANN001
                self._record("reset")
                entered.set()
                time.sleep(seconds)
                return {"reset": True}

        server, rpc, device, bridge = stub_server(SlowReset())
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="first", deadline_ms=1000)
        return server, rpc, device, bridge, session, entered

    def test_estop_during_bridge_reset_survives_the_reset(self) -> None:
        server, rpc, device, bridge, session, entered = self._slow_reset_server(0.4)
        thread, holder = in_thread(lambda: rpc("mhs.safety.reset", session_id=session, deadline_ms=3000))
        self.assertTrue(entered.wait(2.0), "the reset never reached bridge.reset()")
        second = rpc("mhs.safety.estop", session_id=session, reason="second press", deadline_ms=1000)
        self.assertEqual(second["status"], "completed", second)
        self.assertTrue(second["output"]["latched"])
        thread.join(3.0)
        reset = holder["result"]
        # bridge.reset() ran, so the refusal is a 'failed' receipt (RESIDUAL-B: a
        # 'rejected' receipt means nothing was executed).
        self.assertEqual(reset["status"], "failed", reset)
        self.assertEqual(error_code(reset), "MHS.SAFETY.RESET_REFUSED")
        self.assertEqual(reset["error"]["details"]["reason"], "estop_during_reset")
        self.assertEqual(reset["error"]["details"]["bridge_reset"], "completed")
        self.assertTrue(reset["error"]["details"]["latched"])
        # The bridge reset ran (an unknown change): the revision advances, as for a completed reset.
        self.assertEqual(reset["state_revision_after"], reset["state_revision_before"] + 1, reset)
        self.assertTrue(server._latched[device.device_id], "the reset cleared an e-stop engaged during it")
        # The native stop is re-asserted after bridge.reset() returned, so the
        # device does not end up reset behind the second e-stop.
        calls = list(bridge.calls)
        last_reset = max(index for index, name in enumerate(calls) if name == "reset")
        self.assertIn("estop", calls[last_reset + 1:], calls)
        self.assertTrue(reset["error"]["details"]["stop_reasserted"])
        moved = rpc("mhs.command", session_id=session, capability_id=MOVE, input={"pos": 5},
                    deadline_ms=1000)
        self.assertEqual(moved["status"], "rejected", moved)
        self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(bridge.count(MOVE), 0)
        self.assertTrue(rpc("mhs.safety.status", deadline_ms=1000)["estop"]["engaged"])
        # A later reset, with no e-stop during it, releases the latch.
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=3000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertFalse(server._latched[device.device_id])

    @staticmethod
    def _reset_receipts(server) -> list:
        return [
            record for record in server.export_evidence().get("receipts", [])
            if isinstance(record, dict) and record.get("capability_id") == "cap.internal.safety_reset.v1"
        ]

    def test_estop_after_the_reset_timed_out_at_the_caller_survives(self) -> None:
        """The reset outlived its deadline (caller got TIMEOUT) and is still inside
        bridge.reset() when the e-stop is pressed: the late reset keeps the latch."""
        server, rpc, device, bridge, session, entered = self._slow_reset_server(0.4)
        response = rpc.raw("mhs.safety.reset", session_id=session, deadline_ms=50)
        self.assertEqual(error_code(response), "MHS.OUTCOME.TIMEOUT", response)
        self.assertTrue(entered.wait(2.0))
        rpc("mhs.safety.estop", session_id=session, reason="second press", deadline_ms=1000)
        self.assertTrue(wait_until(lambda: self._reset_receipts(server), timeout=3.0),
                        "the timed-out reset never finished")
        late = self._reset_receipts(server)[-1]
        self.assertEqual(late["status"], "failed", late)
        self.assertEqual(late["error"]["details"]["reason"], "estop_during_reset", late)
        self.assertTrue(server._latched[device.device_id],
                        "a late reset cleared an e-stop engaged after the caller's timeout")
        moved = rpc("mhs.command", session_id=session, capability_id=MOVE, input={"pos": 5},
                    deadline_ms=1000)
        self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(bridge.count(MOVE), 0)

    def test_reset_timed_out_before_reaching_the_bridge_is_not_performed(self) -> None:
        class SlowInterlocks(NativeStopBridge):
            def interlocks(self):
                self._record("interlocks")
                time.sleep(0.3)
                return [{"id": "door", "state": "closed"}]

        bridge = SlowInterlocks()
        server, rpc, device, _ = stub_server(bridge, safety=_guarded({"id": "door"}))
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        response = rpc.raw("mhs.safety.reset", session_id=session, deadline_ms=50)
        self.assertEqual(error_code(response), "MHS.OUTCOME.TIMEOUT", response)
        self.assertTrue(wait_until(lambda: self._reset_receipts(server), timeout=3.0))
        receipt = self._reset_receipts(server)[-1]
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["details"]["reason"], "deadline_exceeded")
        self.assertEqual(receipt["error"]["details"]["bridge_reset"], "not_called")
        self.assertEqual(receipt["command_id"], response["error"]["data"]["details"]["command_id"])
        self.assertEqual(bridge.count("reset"), 0)
        self.assertTrue(server._latched[device.device_id])


class ResetWhileStopPathRunsTests(unittest.TestCase):
    """A reset never runs alongside the stop path of an unconfirmed e-stop.

    Port of the verifier probe ``verify-WP-04/4a1/r1/probes/q_reset_unconfirmed.py``
    (the native e-stop is still in flight) plus the background-retry case: the
    retry of a failed e-stop does not call the device while ``bridge.reset()``
    runs.
    """

    def test_reset_refused_while_the_native_estop_is_in_flight(self) -> None:
        release = threading.Event()
        self.addCleanup(release.set)

        class Hung(NativeStopBridge):
            def estop(self, reason: str = "", ctx=None):  # noqa: ANN001
                self._record("estop")
                release.wait(3.0)
                self._record("estop_returned")
                return {"estop": "engaged"}

        bridge = Hung()
        server, rpc, device, _ = stub_server(bridge)
        session = open_session(rpc, device)
        estop = rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        self.assertEqual(estop["status"], "failed", estop)
        self.assertEqual(error_code(estop), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        refused = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(error_code(refused), "MHS.SAFETY.RESET_REFUSED")
        self.assertEqual(refused["error"]["details"]["reason"], "stop_path_pending", refused)
        self.assertEqual(bridge.count("reset"), 0, "the refused reset reached the bridge")
        self.assertTrue(server._latched[device.device_id])
        moved = rpc("mhs.command", session_id=session, capability_id=MOVE, input={"pos": 3},
                    deadline_ms=1000)
        self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(bridge.count(MOVE), 0)
        release.set()
        self.assertTrue(wait_until(
            lambda: server._estop_state[device.device_id]["confirmed"] is True, timeout=3.0))
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        marker = len(bridge.calls)
        moved = rpc("mhs.command", session_id=session, capability_id=MOVE, input={"pos": 3},
                    deadline_ms=1000)
        self.assertEqual(moved["status"], "completed", moved)
        time.sleep(0.1)
        late = [name for name in bridge.calls[marker:] if name in ("estop", "estop_returned", STOP)]
        self.assertEqual(late, [], f"the old stop path ran after the reset: {bridge.calls[marker:]}")

    def test_background_retry_never_runs_during_bridge_reset(self) -> None:
        class FailsAndSlowReset(NativeStopBridge):
            def estop(self, reason: str = "", ctx=None):  # noqa: ANN001
                self._record("estop")
                raise RuntimeError("serial link down")

            def reset(self, ctx=None):  # noqa: ANN001
                self._record("reset")
                time.sleep(0.8)  # the retry would run at 0.25 s and 0.75 s
                self._record("reset_done")
                return {"reset": True}

        bridge = FailsAndSlowReset()
        server, rpc, device, _ = stub_server(bridge)
        session = open_session(rpc, device)
        estop = rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        self.assertTrue(estop["error"]["details"]["retrying"], estop)
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=3000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertFalse(server._latched[device.device_id])
        calls = list(bridge.calls)
        start, end = calls.index("reset"), calls.index("reset_done")
        self.assertNotIn("estop", calls[start:end], f"the retry called the device during reset: {calls}")
        time.sleep(0.4)
        self.assertNotIn("estop", bridge.calls[end:], "the retry outlived the reset")

    def test_overdue_bridge_reset_cannot_release_the_latch_under_a_running_retry(self) -> None:
        """bridge.reset() outlives its deadline: the retry resumes, and the late
        reset then refuses to release the latch while that retry is in flight."""
        retry_release = threading.Event()

        class SlowRetryAndReset(NativeStopBridge):
            def estop(self, reason: str = "", ctx=None):  # noqa: ANN001
                self._record("estop")
                if self.count("estop") > 1:
                    retry_release.wait(3.0)  # the retry hangs
                raise RuntimeError("serial link down")

            def reset(self, ctx=None):  # noqa: ANN001
                self._record("reset")
                time.sleep(1.0)
                self._record("reset_done")
                return {"reset": True}

        bridge = SlowRetryAndReset()
        server, rpc, device, _ = stub_server(bridge)
        session = open_session(rpc, device)
        self.addCleanup(release_retry, server, rpc, device, session)
        self.addCleanup(retry_release.set)  # runs first (LIFO)
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        response = rpc.raw("mhs.safety.reset", session_id=session, deadline_ms=300)
        self.assertEqual(error_code(response), "MHS.OUTCOME.TIMEOUT", response)
        self.assertTrue(wait_until(lambda: bridge.count("estop") >= 2, timeout=0.9),
                        f"the retry stayed held back past the reset's deadline: {bridge.calls}")
        self.assertEqual(bridge.count("reset_done"), 0, "bridge.reset() returned too early for the test")
        self.assertTrue(wait_until(lambda: bridge.count("reset_done") == 1, timeout=3.0))
        self.assertTrue(wait_until(lambda: ResetRaceTests._reset_receipts(server), timeout=2.0))
        late = ResetRaceTests._reset_receipts(server)[-1]
        self.assertEqual(late["status"], "failed", late)  # bridge.reset() ran
        self.assertEqual(late["error"]["details"]["reason"], "stop_path_pending", late)
        self.assertEqual(late["error"]["details"]["bridge_reset"], "completed", late)
        self.assertTrue(server._latched[device.device_id])
        moved = rpc("mhs.command", session_id=session, capability_id=MOVE, input={"pos": 1},
                    deadline_ms=1000)
        self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED")


if __name__ == "__main__":
    unittest.main()
