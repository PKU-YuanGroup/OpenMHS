"""Retirement-boundary races and bounded protective retries on controlled peers.

The interpretation wrapper only schedules real peer traffic after delegating to
the original method. It never substitutes a native result or bridge decision.
"""

from __future__ import annotations

from contextlib import contextmanager
import threading
import time
import unittest
from unittest.mock import patch

from mhs import signals
from mhs.bridge.base import BridgeContext
from mhs.bridge.ros import RecordingRosTransport
from mhs.driver import Action, Field, RosDriver, close_server
from mhs.errors import MHSError
from tests.bridges import test_ros_action_safety as fixture
from tests.bridges.test_ros_action_safety_retirement import RetirementPeer
from tests.driver import support


class FifoTransport(RecordingRosTransport):
    """An ignored marker plus the next recv proves prior frames were processed."""

    def __init__(self, handler):
        super().__init__(handler)
        self.marker_received = False
        self.marker_processed = threading.Event()

    def recv(self, *, timeout_s=None):
        if self.marker_received:
            self.marker_received = False
            self.marker_processed.set()
        message = super().recv(timeout_s=timeout_s)
        if message.get("op") == "test_fifo_marker":
            self.marker_received = True
        return message

    def drain(self):
        self.marker_processed.clear()
        self.feed({"op": "test_fifo_marker"})
        if not self.marker_processed.wait(0.5):
            raise AssertionError("receiver did not process the FIFO marker")


class BoundaryPeer(RetirementPeer):
    def __init__(self, profile, target, success=True, status=None):
        super().__init__(profile)
        self.target = target
        self.first_success = success
        self.first_status = status
        self.transport = FifoTransport(self.handle)

    def handle(self, message):
        result = super().handle(message)
        if fixture.action_name(message) == self.target and len(self.named_goals(self.target)) == 1:
            return fixture.terminal(self.profile, message, success=self.first_success,
                                    status=self.first_status)
        return result


class RosActionSafetySettlementTests(unittest.TestCase):
    bridge = fixture.RosActionSafetyTests.bridge
    worker = fixture.RosActionSafetyTests.worker
    joined = fixture.RosActionSafetyTests.joined

    @contextmanager
    def stock(self, peer):
        cfg = fixture.config(peer.profile)
        cfg["commands"][fixture.READ]["result"] = {"map": {"success": "output.success"}}
        cls = type("SettlementDriver", (RosDriver,), {
            "device_id": "settlement-test", "device_kind": "instrument", "risk": "R0",
            "ros_version": 1 if peer.profile == fixture.PROFILES[0] else 2,
            "timeout_s": 0.5, "commands": cfg["commands"],
            "actions": {
                fixture.MOVE: Action(name="move", output={"success": Field("boolean")}),
                fixture.SAFE: Action(name="stop", safe_state=True, output={"success": Field("boolean")}),
                fixture.READ: Action(name="read", output={"success": Field("boolean")})},
            "safety_bindings": cfg["safety_bindings"],
            "backends": {"fake": lambda: peer.transport}})
        driver = cls(backend="fake")
        server, client = support.serve(driver)
        try:
            self.assertEqual(client.command(fixture.READ, {})["status"], "completed")
            yield driver.inner, client
        finally:
            close_server(server)

    @contextmanager
    def boundary(self, bridge, peer, mutation):
        original = bridge._action_result
        observed = []

        def interpret(spec, pending, **kwargs):
            try:
                return original(spec, pending, **kwargs)
            finally:
                if pending.name == peer.target and not observed:
                    goal = next(g for g in peer.named_goals(peer.target)
                                if fixture.goal_id(g) == pending.ident)
                    packet = fixture.terminal(peer.profile, goal, success=peer.first_success,
                                              status=peer.first_status)
                    values = packet["msg"]["result"] if peer.profile == fixture.PROFILES[0] else packet["values"]
                    if mutation == "typed":
                        values["success"] = int(peer.first_success)
                    elif mutation == "contradiction":
                        values["success"] = not peer.first_success
                    elif mutation == "protocol-error":
                        packet = {"op": "status", "level": "error", "id": pending.ident}
                    elif mutation == "disconnect":
                        peer.transport.close()
                    if mutation != "disconnect":
                        peer.transport.feed(packet)
                        peer.transport.drain()
                    else:
                        with bridge._condition:
                            self.assertTrue(bridge._condition.wait_for(
                                lambda: pending.error is not None, timeout=0.5))
                    with bridge._condition:
                        observed.append((pending.ident, pending.error))

        with patch.object(bridge, "_action_result", interpret):
            yield observed

    def exercise_boundary(self, outcome, mutations):
        for profile in fixture.PROFILES:
            for target, capability in ((fixture.STOP_NAME, fixture.SAFE), (fixture.MOVE_NAME, fixture.MOVE)):
                status = None
                success = outcome == "success"
                if outcome == "native-failure":
                    status = 4 if profile == fixture.PROFILES[0] else 6
                elif outcome == "cancelled":
                    status = 2 if profile == fixture.PROFILES[0] else 5
                for mutation in mutations:
                    with self.subTest(profile=profile, target=target, outcome=outcome, mutation=mutation):
                        peer = BoundaryPeer(profile, target, success, status)
                        with self.stock(peer) as (bridge, client):
                            with self.boundary(bridge, peer, mutation) as observed:
                                receipt = client.command(capability, {})
                            self.assertEqual(len(observed), 1)
                            ident, error = observed[0]
                            if mutation == "identical":
                                self.assertIsNone(error)
                                self.assertEqual(receipt["status"], "completed" if success else "failed", receipt)
                                self.assertNotIn(ident, bridge._actions)
                                self.assertEqual(ident in bridge._safety_history, target == fixture.STOP_NAME)
                                continue
                            self.assertIsNotNone(error)
                            self.assertEqual(receipt["status"], "unknown", receipt)
                            pending = bridge._actions[ident]
                            self.assertTrue(pending.sent and pending.abandoned)
                            self.assertIs(pending.error, error)
                            self.assertNotIn(ident, bridge._safety_history)
                            self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
                            before_move = len(peer.named_goals(fixture.MOVE_NAME))
                            self.assertNotEqual(client.command(fixture.MOVE, {})["status"], "completed")
                            self.assertEqual(len(peer.named_goals(fixture.MOVE_NAME)), before_move)
                            before_stop = len(peer.named_goals(fixture.STOP_NAME))
                            self.assertNotEqual(client.command(fixture.SAFE, {})["status"], "completed")
                            if target == fixture.STOP_NAME or mutation == "disconnect":
                                self.assertEqual(len(peer.named_goals(fixture.STOP_NAME)), before_stop)
                            else:
                                # A distinct, settled stop may protect against the
                                # ordinary action; it cannot resolve that action.
                                self.assertEqual(len(peer.named_goals(fixture.STOP_NAME)), before_stop + 1)
                            self.assertEqual(client.reset()["result"]["status"], "rejected")
                            self.assertIn(ident, bridge._actions)

    def test_success_interpretation_cannot_drop_late_error(self):
        self.exercise_boundary("success", ("identical", "typed", "contradiction", "protocol-error", "disconnect"))

    def test_application_failure_interpretation_cannot_drop_late_error(self):
        self.exercise_boundary("application-failure", ("identical", "typed", "contradiction"))

    def test_native_failure_interpretation_cannot_drop_late_error(self):
        self.exercise_boundary("native-failure", ("identical", "typed"))

    def test_cancelled_interpretation_cannot_drop_late_error(self):
        self.exercise_boundary("cancelled", ("identical", "typed"))

    def test_confirmed_interruption_cannot_drop_error_after_cancelled_interpretation(self):
        for profile in fixture.PROFILES:
            for mutation in ("identical", "typed"):
                with self.subTest(profile=profile, mutation=mutation):
                    peer = BoundaryPeer(profile, fixture.MOVE_NAME, False,
                                        2 if profile == fixture.PROFILES[0] else 5)
                    cancelled = threading.Event()
                    original = peer.handle
                    def handle(message):
                        if fixture.action_name(message) == fixture.MOVE_NAME:
                            cancelled.set()
                        return original(message)
                    peer.transport.handler = handle
                    bridge = self.bridge(peer)
                    expected = signals.Cancelled if mutation == "identical" else signals.OutcomeUnknown
                    with self.boundary(bridge, peer, mutation) as observed:
                        with self.assertRaises(expected):
                            bridge.call(fixture.MOVE, {}, BridgeContext(cancel_event=cancelled))
                    self.assertEqual(len(observed), 1)
                    ident, error = observed[0]
                    self.assertEqual(error is None, mutation == "identical")
                    self.assertEqual(ident in bridge._actions, mutation != "identical")
                    self.assertEqual(bridge.safety_status()["safe_state"]["achieved"], mutation == "identical")
                    self.assertEqual(len(peer.named_goals(fixture.STOP_NAME)), 2)

    def fault_history(self, bridge, peer):
        self.assertTrue(bridge.safe_state()["achieved"])
        old = peer.named_goals(fixture.STOP_NAME)[0]
        peer.complete(old, success=1)
        bridge.call(fixture.READ, {})
        self.assertIsNotNone(bridge._safety_history_error)
        self.assertFalse(bridge._actions)
        return bridge._safety_history_error

    def test_history_fault_allows_bounded_protection_but_never_confirmation_or_reset(self):
        for profile in fixture.PROFILES:
            with self.subTest(profile=profile):
                peer = RetirementPeer(profile)
                with self.stock(peer) as (bridge, client):
                    error = self.fault_history(bridge, peer)
                    count = len(peer.named_goals(fixture.STOP_NAME))
                    for _ in range(20):
                        self.assertFalse(bridge.safe_state(BridgeContext(deadline_ms=100))["achieved"])
                    self.assertEqual(len(peer.named_goals(fixture.STOP_NAME)), count + 20)
                    self.assertIs(bridge._safety_history_error, error)
                    self.assertLessEqual(len(bridge._safety_history), 16)
                    self.assertTrue(bridge._safety_reconciliation_needed)
                    self.assertNotEqual(client.command(fixture.MOVE, {})["status"], "completed")
                    self.assertNotEqual(client.command(fixture.SAFE, {})["status"], "completed")
                    self.assertEqual(len(peer.named_goals(fixture.STOP_NAME)), count + 21)
                    self.assertEqual(client.reset()["result"]["status"], "rejected")
                    self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])

    def test_stock_background_retry_transmits_after_history_fault_without_confirming(self):
        for profile in fixture.PROFILES:
            with self.subTest(profile=profile):
                peer = RetirementPeer(profile)
                with self.stock(peer) as (bridge, client):
                    error = self.fault_history(bridge, peer)
                    count = len(peer.named_goals(fixture.STOP_NAME))
                    receipt = client.estop()
                    self.assertEqual(receipt["status"], "failed", receipt)
                    self.assertFalse(receipt["output"]["safe_state_achieved"])
                    peer.wait_goal(fixture.STOP_NAME, count + 3)
                    state = client.rpc("mhs.safety.status", {"device_id": client.device_id, "deadline_ms": 100})
                    self.assertTrue(state["estop"]["engaged"])
                    self.assertFalse(state["estop"]["confirmed"])
                    self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
                    self.assertIs(bridge._safety_history_error, error)
                    self.assertEqual(client.reset()["result"]["status"], "rejected")

    def test_failed_passive_retirement_still_blocks_new_setup_on_an_open_connection(self):
        for prior_history_fault in (False, True):
            with self.subTest(prior_history_fault=prior_history_fault):
                peer = RetirementPeer(fixture.PROFILES[0])
                bridge = self.bridge(peer)
                if prior_history_fault:
                    self.fault_history(bridge, peer)
                arm = [False]
                def prepare(*, timeout_s):
                    if arm[0]:
                        arm[0] = False
                        raise TimeoutError("controlled passive retirement preparation failure")
                def stop(goal):
                    arm[0] = True
                    return fixture.terminal(peer.profile, goal)
                peer.transport.prepare = prepare
                peer.on_stop = stop
                self.assertFalse(bridge.safe_state()["achieved"])
                peer.on_stop = None
                self.assertIsNone(bridge._fatal)
                self.assertIsNotNone(bridge._safety_history_error)
                before = len(peer.transport.sent)
                for _ in range(3):
                    with self.assertRaises((MHSError, signals.DriverFailed, signals.OutcomeUnknown)):
                        bridge.safe_state(BridgeContext(deadline_ms=100))
                self.assertEqual(len(peer.transport.sent), before)
                # Diagnostics still work on this connection; this is not merely
                # the fatal transport guard preventing another native goal.
                self.assertEqual(bridge.call(fixture.READ, {}), {})

    def test_history_retry_respects_close_cancellation_and_expired_deadline(self):
        for profile in fixture.PROFILES:
            for guard in ("closed", "cancelled", "expired"):
                with self.subTest(profile=profile, guard=guard):
                    peer = RetirementPeer(profile)
                    bridge = self.bridge(peer)
                    self.fault_history(bridge, peer)
                    context = BridgeContext(deadline_ms=500)
                    if guard == "closed":
                        bridge.close()
                    elif guard == "cancelled":
                        context.cancel_event = threading.Event()
                        context.cancel_event.set()
                    else:
                        context.extra["deadline_at"] = time.monotonic() - 1
                    before = len(peer.transport.sent)
                    with self.assertRaises((MHSError, signals.Cancelled, signals.DriverFailed)):
                        bridge.safe_state(context)
                    self.assertEqual(len(peer.transport.sent), before)

    def test_history_fault_does_not_preempt_an_unsettled_protective_retry(self):
        for profile in fixture.PROFILES:
            for erroneous in (False, True):
                with self.subTest(profile=profile, erroneous=erroneous):
                    peer = RetirementPeer(profile)
                    bridge = self.bridge(peer)
                    error = self.fault_history(bridge, peer)
                    peer.automatic_stop = False
                    with self.assertRaises(signals.OutcomeUnknown):
                        bridge.call(fixture.SAFE, {}, BridgeContext(deadline_ms=20))
                    goal = peer.named_goals(fixture.STOP_NAME)[-1]
                    if erroneous:
                        peer.transport.feed({"op": "status", "level": "error", "id": fixture.goal_id(goal)})
                        bridge.call(fixture.READ, {})
                    count = len(peer.named_goals(fixture.STOP_NAME))
                    for _ in range(3):
                        with self.assertRaises((MHSError, signals.DriverFailed, signals.OutcomeUnknown)):
                            bridge.safe_state(BridgeContext(deadline_ms=20))
                    self.assertEqual(len(peer.named_goals(fixture.STOP_NAME)), count)
                    self.assertIs(bridge._safety_history_error, error)
                    self.assertIn(fixture.goal_id(goal), bridge._actions)
                    if not erroneous:
                        peer.complete(goal)
                        bridge.call(fixture.READ, {})
                        peer.automatic_stop = True
                        self.assertFalse(bridge.safe_state()["achieved"])
                        self.assertEqual(len(peer.named_goals(fixture.STOP_NAME)), count + 1)
                    self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])


if __name__ == "__main__":
    unittest.main()
