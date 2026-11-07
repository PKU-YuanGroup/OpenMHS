"""A session's expiry stops its running operations (MISSED fit-robots-ros ttl_probe).

Port of ``verify-fit-robots-ros/ttl_probe.py``: with ``ttl_s=1`` a 10 s
mobile-base command ran to completion, because expiry was only noticed lazily
when the session was used again.  00-architecture §6.5: expiry transitions any
running operation to cancellation-to-safe-state.
"""

from __future__ import annotations

import threading
import time
import unittest
from typing import Any

from mhs.bridge.base import Bridge
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope

from ._support import STOP, Rpc, error_code, in_thread, open_session, stub_server, wait_until

BASE = "cap.motion.mobile_base.v1"


class MobileBase(Bridge):
    """Publishes velocity until cancelled (polls ``ctx.cancel_event`` every 10 ms)."""

    def __init__(self, device_id: str) -> None:
        super().__init__(device_id=device_id)
        self.started: float | None = None
        self.cancelled_at: float | None = None
        self.stops: list[float] = []

    def read(self, resource_id: str, fields=None, ctx=None):  # noqa: ANN001
        return {"moving": self.started is not None and self.cancelled_at is None}

    def call(self, capability_id: str, args=None, ctx=None):  # noqa: ANN001
        if capability_id == STOP:
            self.stops.append(time.monotonic())
            return {"stopped": True}
        self.started = time.monotonic()
        event = getattr(ctx, "cancel_event", None)
        for _ in range(1000):
            if event is not None and event.is_set():
                self.cancelled_at = time.monotonic()
                return {"status": "cancelled"}
            time.sleep(0.01)
        return {"done": True}


class SessionExpiryTests(unittest.TestCase):
    def _server(self) -> tuple[MHSServer, Rpc, Device, MobileBase]:
        device_id = "mhs://localhost/expiry/base"
        bridge = MobileBase(device_id)
        device = Device(
            device_id, "Mobile base", mode="hardware",
            resources=[Resource("base", "robot.mobile_base", state_schema={"type": "object"})],
            capabilities=[
                Capability(BASE, "base", exclusive=True, constraints={"max_duration_ms": 20000}),
                Capability(STOP, "base", input_schema={"type": "object", "properties": {}}),
            ],
            safety=SafetyEnvelope(risk_class="R2", estop={"kind": "software", "latching": True,
                                                          "latency_ms": 50},
                                  safe_state={"description": "base stopped", "achieved_by": [STOP]}),
            bridge=bridge,
        )
        server = MHSServer("mhs://localhost/expiry", [device], log_ready=False)
        rpc = Rpc(server)
        rpc("mhs.hello", protocol_versions=["1.0"])
        return server, rpc, device, bridge

    def test_ttl_probe_expiry_cancels_the_running_motion_within_one_second(self) -> None:
        server, rpc, device, bridge = self._server()
        session = rpc("mhs.session.open", device_ids=[device.device_id], mode="hardware",
                      ttl_s=1)["session_id"]
        expires = server._sessions[session].expires_at
        thread, holder = in_thread(lambda: rpc(
            "mhs.command", session_id=session, capability_id=BASE,
            input={"linear_velocity": 0.1, "angular_velocity": 0, "duration_s": 10},
            deadline_ms=20000))
        self.assertTrue(wait_until(lambda: bridge.started is not None, timeout=2.0))
        # Nobody touches the session again: the endpoint must notice on its own.
        self.assertTrue(wait_until(lambda: bridge.cancelled_at is not None, timeout=4.0),
                        "session expiry did not cancel the running motion")
        lag = time.time() - expires
        self.assertLess(lag, 1.0 + 0.1, f"motion cancelled {lag:.2f} s after the session expired")
        self.assertTrue(wait_until(lambda: bool(bridge.stops), timeout=1.0),
                        "the safe-state action did not run")
        thread.join(5.0)
        self.assertEqual(holder["result"]["status"], "cancelled", holder["result"])
        self.assertEqual(holder["result"]["cancellation"]["reason"], "session expired")
        # The session itself still reports EXPIRED, not NOT_FOUND.
        response = rpc.raw("mhs.resource.read", session_id=session, deadline_ms=1000)
        self.assertEqual(error_code(response), "MHS.SESSION.EXPIRED")

    def test_a_live_session_keeps_running(self) -> None:
        server, rpc, device, bridge = self._server()
        session = rpc("mhs.session.open", device_ids=[device.device_id], mode="hardware",
                      ttl_s=60)["session_id"]
        thread, holder = in_thread(lambda: rpc(
            "mhs.command", session_id=session, capability_id=BASE, input={}, deadline_ms=20000))
        self.assertTrue(wait_until(lambda: bridge.started is not None, timeout=2.0))
        time.sleep(1.3)
        self.assertIsNone(bridge.cancelled_at)
        self.assertEqual(bridge.stops, [])
        rpc("mhs.safety.estop", session_id=session, reason="test cleanup", deadline_ms=1000)
        thread.join(5.0)

    def test_heartbeat_postpones_the_expiry(self) -> None:
        server, rpc, device, bridge = stub_server()
        session = open_session(rpc, device, ttl_s=1)
        for _ in range(3):
            time.sleep(0.5)
            rpc("mhs.session.heartbeat", session_id=session)
        self.assertFalse(getattr(server._sessions[session], "released", False))
        self.assertEqual(rpc("mhs.resource.read", session_id=session, deadline_ms=1000)["device_id"],
                         device.device_id)


class _FailingStop(MobileBase):
    def call(self, capability_id: str, args=None, ctx=None):  # noqa: ANN001
        if capability_id == STOP:
            self.stops.append(time.monotonic())
            raise RuntimeError("stop failed in the test fixture")
        return super().call(capability_id, args, ctx)


class _Stubborn(MobileBase):
    """Ignores ``ctx.cancel_event``: only the safe-state actions stop it."""

    def call(self, capability_id: str, args=None, ctx=None):  # noqa: ANN001
        if capability_id == STOP:
            return super().call(capability_id, args, ctx)
        self.started = time.monotonic()
        time.sleep(1.5)
        return {"done": True}


class ExpiryRaceTests(unittest.TestCase):
    """Verifier 4a2 minors: the expiry timer against heartbeats and lazy expiry."""

    def _server(self, bridge_cls: type = MobileBase) -> tuple[MHSServer, Rpc, Device, MobileBase]:
        server, rpc, device, _bridge = SessionExpiryTests._server(self)  # type: ignore[arg-type]
        bridge = bridge_cls(device.device_id)
        device.bridge = bridge
        return server, rpc, device, bridge

    def test_a_heartbeat_never_revives_a_session_the_timer_released(self) -> None:
        server, rpc, device, _bridge = self._server()
        session = rpc("mhs.session.open", device_ids=[device.device_id], mode="hardware",
                      ttl_s=60)["session_id"]
        original = server._session

        def racing(session_id: Any):
            found = original(session_id)
            # The expiry timer fires between the heartbeat's lookup and its extension.
            found.expires_at = time.time() - 0.001
            server._reap_expired_sessions()
            return found

        server._session = racing
        try:
            response = rpc.raw("mhs.session.heartbeat", session_id=session)
        finally:
            del server._session
        self.assertEqual(error_code(response), "MHS.SESSION.EXPIRED", response)
        self.assertTrue(server._sessions[session].released)
        self.assertEqual(error_code(rpc.raw("mhs.resource.read", session_id=session, deadline_ms=1000)),
                         "MHS.SESSION.EXPIRED")

    def test_a_released_session_is_expired_even_with_time_left(self) -> None:
        server, rpc, device, _bridge = self._server()
        session = rpc("mhs.session.open", device_ids=[device.device_id], mode="hardware",
                      ttl_s=60)["session_id"]
        server._sessions[session].released = True
        for method, params in (("mhs.resource.read", {"deadline_ms": 1000}),
                               ("mhs.session.heartbeat", {}),
                               ("mhs.command", {"capability_id": BASE, "input": {}, "deadline_ms": 1000})):
            with self.subTest(method):
                response = rpc.raw(method, session_id=session, **params)
                self.assertEqual(error_code(response), "MHS.SESSION.EXPIRED", response)

    def test_lazy_expiry_also_drives_the_device_safe(self) -> None:
        """A request that notices the expiry before the timer does still runs
        the safe-state actions (00-architecture §6.5), also for a bridge that
        ignores the cancellation."""
        server, rpc, device, bridge = self._server(_Stubborn)
        session = rpc("mhs.session.open", device_ids=[device.device_id], mode="hardware",
                      ttl_s=60)["session_id"]
        thread, _holder = in_thread(lambda: rpc(
            "mhs.command", session_id=session, capability_id=BASE, input={}, deadline_ms=20000))
        self.assertTrue(wait_until(lambda: bridge.started is not None, timeout=2.0))
        server._sessions[session].expires_at = time.time() - 0.001  # the timer sleeps ~60 s
        response = rpc.raw("mhs.resource.read", session_id=session, deadline_ms=1000)
        self.assertEqual(error_code(response), "MHS.SESSION.EXPIRED")
        self.assertTrue(wait_until(lambda: bool(bridge.stops), timeout=1.0),
                        "the safe-state action did not run on lazy expiry")
        self.assertTrue(thread.is_alive(), "the stubborn call should still be running")
        thread.join(5.0)

    def test_failed_expiry_safe_state_actions_are_logged(self) -> None:
        server, rpc, device, bridge = self._server(_FailingStop)
        session = rpc("mhs.session.open", device_ids=[device.device_id], mode="hardware",
                      ttl_s=1)["session_id"]
        with self.assertLogs("mhs.server", level="WARNING") as logs:
            thread, _holder = in_thread(lambda: rpc(
                "mhs.command", session_id=session, capability_id=BASE, input={}, deadline_ms=20000))
            self.assertTrue(wait_until(lambda: bridge.started is not None, timeout=2.0))
            self.assertTrue(wait_until(
                lambda: any("failed" in line and STOP in line for line in logs.output), timeout=4.0),
                logs.output)
        thread.join(5.0)
        self.assertTrue(bridge.stops)


if __name__ == "__main__":
    unittest.main()
