"""Safe-state and stop actions are always callable (SAFE-029; MISSED sdk-core vstop).

Port of ``sdk-core-verify/vstop.py``: ``cap.motion.stop.v1`` (and every
``safe_state.achieved_by`` action) is exempt from the e-stop latch, permits,
cumulative budgets and the exclusive device lease.
"""

from __future__ import annotations

import unittest

from mhs.server import Capability, SafetyEnvelope

from ._support import (
    LONG,
    STOP,
    NativeStopBridge,
    conveyor,
    error_code,
    in_thread,
    open_session,
    stub_capabilities,
    stub_server,
    wait_until,
)


class ConveyorStopTests(unittest.TestCase):
    def test_vstop_stop_is_callable_while_latched(self) -> None:
        server, rpc, device, session = conveyor()
        self.assertEqual(device.safety.safe_state["achieved_by"], [STOP])
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        receipt = rpc("mhs.command", session_id=session, capability_id=STOP, input={}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)
        step = rpc("mhs.command", session_id=session, capability_id="cap.world.step.v1",
                   input={"ticks": 1}, deadline_ms=2000)
        self.assertEqual(error_code(step), "MHS.SAFETY.ESTOP_ENGAGED")


class StubExemptionTests(unittest.TestCase):
    def _server(self, **kwargs):
        safety = SafetyEnvelope(
            risk_class="R1",
            requires_permit=["cap.motion.*"],
            envelope={"cap.motion.stop.v1": {"deceleration": {"max": 5, "per": "rolling_1h"}}},
            estop={"kind": "software", "latching": True, "latency_ms": 50},
            safe_state={"description": "axis stopped", "achieved_by": [STOP]},
        )
        stop_with_input = Capability(
            "x-cap.test.unused.v1", "axis", input_schema={"type": "object"})
        caps = stub_capabilities(stop_exclusive=True, extra=[stop_with_input])
        return stub_server(NativeStopBridge(), safety=safety, capabilities=caps, **kwargs)

    def test_stop_needs_no_permit(self) -> None:
        server, rpc, device, bridge = self._server()
        session = open_session(rpc, device)
        receipt = rpc("mhs.command", session_id=session, capability_id=STOP, input={}, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        moved = rpc("mhs.command", session_id=session, capability_id="cap.motion.move.v1",
                    input={"pos": 1}, deadline_ms=1000)
        self.assertEqual(error_code(moved), "MHS.SAFETY.PERMIT_INVALID",
                         "the permit gate still applies to ordinary motion")

    def test_exclusive_stop_runs_during_an_exclusive_operation(self) -> None:
        safety = SafetyEnvelope(
            risk_class="R1",
            estop={"kind": "software", "latching": True, "latency_ms": 50},
            safe_state={"description": "axis stopped", "achieved_by": [STOP]},
        )
        bridge = NativeStopBridge()
        server, rpc, device, _ = stub_server(bridge, safety=safety,
                                             capabilities=stub_capabilities(stop_exclusive=True))
        session = open_session(rpc, device)
        thread, holder = in_thread(lambda: rpc(
            "mhs.command", session_id=session, capability_id=LONG, input={"ms": 600},
            deadline_ms=5000))
        self.assertTrue(wait_until(lambda: bridge.state["moving"], timeout=2.0))
        receipt = rpc("mhs.command", session_id=session, capability_id=STOP, input={}, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertNotEqual(error_code(receipt), "MHS.DEVICE.BUSY")
        thread.join(3.0)

    def test_stop_is_exempt_from_cumulative_budgets(self) -> None:
        server, rpc, device, bridge = self._server()
        session = open_session(rpc, device)
        for _ in range(3):
            receipt = rpc("mhs.command", session_id=session, capability_id=STOP,
                          input={"deceleration": 4}, deadline_ms=1000)
            self.assertEqual(receipt["status"], "completed", receipt)


if __name__ == "__main__":
    unittest.main()
