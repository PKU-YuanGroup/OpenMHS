"""E-stop preemption (SAFE-040; finding SDK-02, MISSED fit-robots-ros estop_probe).

Ports of ``sdk-core/e3b.py`` (an e-stop must cancel the running operation),
the cancellation part of ``sdk-core/e2.py`` and part (b) of ``sdk-core/e7.py``
(a command that passed its pre-checks before the e-stop must not execute after
it).
"""

from __future__ import annotations

import threading
import time
import unittest

from mhs.bridge.base import Bridge
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope, _Context

from ._support import (
    LONG,
    Rpc,
    STOP,
    NativeStopBridge,
    conveyor,
    error_code,
    in_thread,
    open_session,
    stub_server,
    ulid,
    wait_until,
)

DELAY = "x-cap.mhs-test.delay.v1"


class EstopCancelsRunningOperationTests(unittest.TestCase):
    def test_e3b_estop_cancels_a_cooperative_operation(self) -> None:
        server, rpc, device, session = conveyor()
        thread, holder = in_thread(lambda: rpc(
            "mhs.command", session_id=session, capability_id=DELAY, input={"ms": 1000},
            deadline_ms=10000))
        self.assertTrue(wait_until(lambda: len(server._operations) == 1, timeout=2.0))
        operation = next(iter(server._operations.values()))
        time.sleep(0.05)
        estop = rpc("mhs.safety.estop", session_id=session, reason="test", deadline_ms=1000)
        self.assertEqual(estop["status"], "completed", estop)
        self.assertTrue(operation.cancel_event.is_set(), "e-stop did not cancel the running operation")
        self.assertIn(operation.operation_id, estop["output"]["cancelled_operations"])
        thread.join(2.0)
        self.assertFalse(thread.is_alive())
        self.assertLess(holder["elapsed"], 0.9, "the cooperative operation ran to completion")
        self.assertEqual(holder["result"]["status"], "cancelled", holder["result"])
        self.assertEqual(operation.final_receipt["status"], "cancelled")
        self.assertIn("emergency stop", holder["result"]["cancellation"]["reason"])

    def test_e2_operations_cancel_gives_a_cancelled_receipt(self) -> None:
        server, rpc, device, session = conveyor()
        thread, holder = in_thread(lambda: rpc(
            "mhs.command", session_id=session, capability_id=DELAY, input={"ms": 1500},
            deadline_ms=3000))
        self.assertTrue(wait_until(lambda: len(server._operations) == 1, timeout=2.0))
        operation_id = next(iter(server._operations))
        cancelled = rpc("mhs.operations.cancel", session_id=session, operation_id=operation_id,
                        deadline_ms=2000)
        thread.join(3.0)
        self.assertEqual(cancelled["status"], "cancelled", cancelled)
        self.assertEqual(holder["result"]["status"], "cancelled", holder["result"])

    def test_stub_long_operation_is_cancelled_and_native_stop_called(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        session = open_session(rpc, device)
        thread, holder = in_thread(lambda: rpc(
            "mhs.command", session_id=session, capability_id=LONG, input={"ms": 3000},
            deadline_ms=5000))
        self.assertTrue(wait_until(lambda: bridge.state["moving"], timeout=2.0))
        estop = rpc("mhs.safety.estop", session_id=session, reason="operator", deadline_ms=1000)
        self.assertEqual(estop["status"], "completed", estop)
        thread.join(2.0)
        self.assertEqual(holder["result"]["status"], "cancelled", holder["result"])
        self.assertEqual(bridge.count("estop"), 1)
        self.assertGreaterEqual(bridge.count(STOP), 1)
        moved_after = bridge.count("cap.motion.move.v1")
        self.assertEqual(moved_after, 0)


class StreamingDriverTests(unittest.TestCase):
    """Port of ``verify-fit-robots-ros/estop_probe.py``: a streaming mobile-base
    bridge that publishes velocity at 10 Hz and polls ``ctx.cancel_event``."""

    def test_estop_stops_a_streaming_hardware_command(self) -> None:
        log: list[tuple[str, float]] = []

        class Base(Bridge):
            def call(self, cap, args, ctx=None):  # noqa: ANN001
                if cap == STOP:
                    log.append(("stop", time.monotonic()))
                    return {"stopped": True}
                event = getattr(ctx, "cancel_event", None)
                for _ in range(40):  # cmd_vel at 10 Hz for 4 s
                    if event is not None and event.is_set():
                        log.append(("cancel_seen", time.monotonic()))
                        return {"stopped": True}
                    log.append(("publish", time.monotonic()))
                    time.sleep(0.1)
                return {"done": True}

            def read(self, rid, fields=None, ctx=None):  # noqa: ANN001
                return {}

            def estop(self, reason="", ctx=None):  # noqa: ANN001
                log.append(("estop", time.monotonic()))
                return {"engaged": True}

        device = Device(
            "mhs://localhost/safety/base", mode="hardware",
            resources=[Resource("base", "robot.mobile_base")],
            capabilities=[Capability("cap.motion.mobile_base.v1", "base"), Capability(STOP, "base")],
            safety=SafetyEnvelope(risk_class="R2", estop={"kind": "both", "latching": True,
                                                          "physical_ref": "red button on the base"},
                                  safe_state={"description": "zero velocity", "achieved_by": [STOP]}),
            bridge=Base(device_id="mhs://localhost/safety/base"),
        )
        server = MHSServer("mhs://localhost/safety", [device], log_ready=False)
        rpc = Rpc(server)
        rpc("mhs.hello", protocol_versions=["1.0"])
        session = rpc("mhs.session.open", device_ids=[device.device_id], mode="hardware",
                      capabilities=["cap.motion.*"])["session_id"]
        thread, holder = in_thread(lambda: rpc(
            "mhs.command", session_id=session, capability_id="cap.motion.mobile_base.v1",
            input={"linear_velocity": 0.1, "duration_s": 4}, deadline_ms=20000))
        time.sleep(0.5)
        estop = rpc("mhs.safety.estop", session_id=session, reason="test", deadline_ms=2000)
        self.assertEqual(estop["status"], "completed", estop)
        thread.join(3.0)
        self.assertFalse(thread.is_alive())
        self.assertLess(holder["elapsed"], 2.0, "the streaming command ran on after the e-stop")
        estop_at = next(t for kind, t in log if kind == "estop")
        published_after = sum(1 for kind, t in log if kind == "publish" and t > estop_at)
        self.assertLessEqual(published_after, 1, log)
        self.assertTrue(any(kind == "cancel_seen" for kind, _ in log))
        self.assertTrue(any(kind == "stop" for kind, _ in log), "the safe-state action did not run")


class EstopPrecheckRaceTests(unittest.TestCase):
    """e7(b): the latch is re-checked atomically with the start of execution."""

    def test_command_in_precheck_when_estop_lands_is_refused(self) -> None:
        server, rpc, device, session = conveyor()
        bridge = device.bridge
        original = bridge.interlocks

        def slow_interlocks():
            time.sleep(0.1)  # a real device answers an interlock query in 10-100 ms
            return original()

        bridge.interlocks = slow_interlocks
        tick0 = rpc("mhs.resource.read", session_id=session, deadline_ms=2000)["state"].get("tick")
        thread, holder = in_thread(lambda: rpc(
            "mhs.command", session_id=session, capability_id="cap.world.step.v1", input={"ticks": 50},
            deadline_ms=3000))
        time.sleep(0.02)
        estop = rpc("mhs.safety.estop", session_id=session, reason="operator", deadline_ms=1000)
        self.assertTrue(estop["output"]["latched"])
        thread.join(3.0)
        command = holder["result"]
        tick1 = rpc("mhs.resource.read", session_id=session, deadline_ms=2000)["state"].get("tick")
        self.assertEqual(command["status"], "rejected", command)
        self.assertEqual(error_code(command), "MHS.SAFETY.ESTOP_ENGAGED", command)
        self.assertEqual(tick0, tick1, "the world advanced after the e-stop")

    def test_stub_precheck_race_never_reaches_the_bridge(self) -> None:
        safety = SafetyEnvelope(
            risk_class="R1",
            interlocks=[{"id": "guard", "required_for": ["cap.motion.move.v1"], "source": "simulated"}],
            estop={"kind": "software", "latching": True, "latency_ms": 50},
            safe_state={"description": "axis stopped", "achieved_by": [STOP]},
        )

        class SlowInterlocks(NativeStopBridge):
            def interlocks(self):
                self._record("interlocks")
                time.sleep(0.1)
                return [{"id": "guard", "state": "closed"}]

        server, rpc, device, bridge = stub_server(SlowInterlocks(), safety=safety)
        session = open_session(rpc, device)
        thread, holder = in_thread(lambda: rpc(
            "mhs.command", session_id=session, capability_id="cap.motion.move.v1", input={"pos": 9},
            deadline_ms=3000))
        self.assertTrue(wait_until(lambda: bridge.count("interlocks") >= 1, timeout=1.0))
        rpc("mhs.safety.estop", session_id=session, reason="operator", deadline_ms=1000)
        thread.join(3.0)
        self.assertEqual(error_code(holder["result"]), "MHS.SAFETY.ESTOP_ENGAGED", holder["result"])
        self.assertEqual(bridge.count("cap.motion.move.v1"), 0)

    def test_operation_cancelled_before_dispatch_never_reaches_the_bridge(self) -> None:
        """An e-stop that lands after registration but before the worker calls the bridge.

        The operation is registered (the e-stop sees it and sets its
        cancel_event) but its worker has not reached ``bridge.call`` yet; the
        call must not be dispatched to a bridge that may not poll the event.
        """
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        session = server._sessions[open_session(rpc, device)]
        capability = device._by_capability[LONG]
        cancel_event = threading.Event()
        cancel_event.set()  # what _engage_estop does to a registered operation
        command_id = ulid()
        ctx = _Context(command_id=command_id, session_id=session.session_id, device_id=device.device_id,
                       resource=capability.resource, deadline_ms=1000, mode=device.mode,
                       cancel_event=cancel_event)
        operation = server._start_operation(
            session=session, device=device, capability=capability, bridge=bridge, ctx=ctx,
            command_id=command_id, input_payload={"ms": 200}, input_digest="digest",
            deadline_ms=1000, held_lock=None, cancel_event=cancel_event,
        )
        self.assertIsNotNone(operation)
        self.assertTrue(wait_until(lambda: operation.final_receipt is not None, timeout=2.0))
        self.assertEqual(operation.final_receipt["status"], "cancelled", operation.final_receipt)
        self.assertEqual(bridge.count(LONG), 0, "a cancelled operation was dispatched to the bridge")


if __name__ == "__main__":
    unittest.main()
