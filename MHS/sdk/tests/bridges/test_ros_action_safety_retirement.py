"""Private v2 regressions for bounded retirement of terminal safety goals.

These controlled ROS peers exercise the actual bridge and stock Server/Client.
No ROS installation, socket, hardware factory, or SDK monkeypatch is used.
"""

from __future__ import annotations

import re
import copy
import threading
import time
import unittest
import uuid

from mhs import signals
from mhs.bridge.base import BridgeContext
from mhs.bridge import ros_actions
from mhs.bridge.ros import RecordingRosTransport
from mhs.driver import Action, Field, RosDriver, close_server
from mhs.errors import MHSError
from tests.bridges import test_ros_action_safety as support
from tests.driver import support as server_support


class RetirementPeer(support.FrankaPeer):
    """Complete ordinary moves; retain the source-shaped independent StopAction."""

    def __init__(self, profile, *, automatic_stop=True):
        super().__init__(profile, automatic_stop=automatic_stop)
        self.automatic_move = True
        self.fail_cleanup = False
        self.pause_cleanup = False
        self.cleanup_entered = threading.Event()
        self.cleanup_release = threading.Event()
        self.on_reset = None

    def handle(self, message):
        if message.get("op") in ("unsubscribe", "unadvertise"):
            if self.fail_cleanup:
                raise TimeoutError("controlled passive cleanup failure")
            if self.pause_cleanup:
                self.pause_cleanup = False
                self.cleanup_entered.set()
                if not self.cleanup_release.wait(1):
                    raise TimeoutError("controlled cleanup was not released")
        if message.get("service") == "/reset" and self.on_reset is not None:
            return self.on_reset(message)
        result = super().handle(message)
        if support.action_name(message) == support.MOVE_NAME and self.automatic_move:
            return support.terminal(self.profile, message)
        return result


class RosActionSafetyRetirementTests(unittest.TestCase):
    # Reuse helpers without inheriting or exposing another TestCase to discovery.
    bridge = support.RosActionSafetyTests.bridge
    server = support.RosActionSafetyTests.server
    worker = support.RosActionSafetyTests.worker
    joined = support.RosActionSafetyTests.joined
    drain = support.RosActionSafetyTests.drain

    def test_active_and_archived_results_share_typed_duplicate_rules(self):
        for profile in support.PROFILES:
            for safety in (False, True):
                for changed in (False, True):
                    with self.subTest(profile=profile, safety=safety, changed=changed):
                        pending = ros_actions.PendingAction(
                            "controlled-goal", support.STOP_NAME,
                            support.binding(profile)["type"], profile, sent=True, safety=safety)
                        first = support.terminal(profile, pending.goal({}))
                        second = copy.deepcopy(first)
                        if changed:
                            values = second["msg"]["result"] if profile == support.PROFILES[0] else second["values"]
                            values["success"] = 1
                        self.assertTrue(pending.receive(first, 1.0))
                        archived = ros_actions.SafetyActionTerminal.from_pending(pending)
                        self.assertTrue(pending.receive(second, 2.0))
                        self.assertEqual(pending.error is not None, changed)
                        self.assertEqual(archived.check(second) is not None, changed)
                        self.assertIs(pending.response["values"]["success"], True)

    def test_stock_active_typed_duplicate_never_confirms_safety(self):
        class BarrierTransport(RecordingRosTransport):
            def __init__(self, handler):
                super().__init__(handler)
                self.active_id = None
                self.delivered = 0
                self.processed = threading.Event()

            def recv(self, *, timeout_s=None):
                # The third recv starts only after both preceding terminals
                # were applied under the stock bridge's receive condition.
                if self.delivered == 2:
                    self.processed.set()
                message = super().recv(timeout_s=timeout_s)
                ident = (message.get("msg", {}).get("status", {}).get("goal_id", {}).get("id")
                         if message.get("op") == "publish" else message.get("id"))
                if ident == self.active_id:
                    self.delivered += 1
                return message

        for profile in support.PROFILES:
            for duplicate in (True, 1):
                for route in ("estop", "safe-command"):
                    with self.subTest(profile=profile, duplicate_type=type(duplicate).__name__, route=route):
                        peer = support.FrankaPeer(profile, automatic_stop=False)
                        peer.transport = BarrierTransport(peer.handle)
                        barriers = []
                        def stop(goal):
                            transport = peer.transport
                            transport.active_id = support.goal_id(goal)
                            transport.delivered = 0
                            transport.processed.clear()
                            transport.feed(support.terminal(profile, goal, success=True))
                            transport.feed(support.terminal(profile, goal, success=duplicate))
                            if not transport.processed.wait(0.4):
                                raise RuntimeError("two terminals were not processed before native send returned")
                            barriers.append(transport.delivered)
                        peer.on_stop = stop
                        cfg = support.config(profile)
                        cfg["commands"][support.READ]["result"] = {"map": {"success": "output.success"}}
                        cls = type("TypedTerminalDriver", (RosDriver,), {
                            "device_id": "typed-terminal", "device_kind": "instrument", "risk": "R0",
                            "ros_version": 1 if profile == support.PROFILES[0] else 2,
                            "timeout_s": 0.5, "commands": cfg["commands"],
                            "actions": {
                                support.MOVE: Action(name="move", output={"success": Field("boolean")}),
                                support.SAFE: Action(name="stop", safe_state=True, output={"success": Field("boolean")}),
                                support.READ: Action(name="read", output={"success": Field("boolean")})},
                            "safety_bindings": cfg["safety_bindings"],
                            "backends": {"fake": lambda: peer.transport}})
                        driver = cls(backend="fake")
                        server, client = server_support.serve(driver)
                        try:
                            self.assertEqual(client.command(support.READ, {})["status"], "completed")
                            receipt = client.estop() if route == "estop" else client.command(support.SAFE, {})
                            positive = type(duplicate) is bool
                            self.assertTrue(barriers)
                            self.assertTrue(all(count == 2 for count in barriers))
                            self.assertIs(driver.inner.safety_status()["safe_state"]["achieved"], positive)
                            expected_status = "completed" if positive else ("failed" if route == "estop" else "unknown")
                            self.assertEqual(receipt["status"], expected_status, receipt)
                            if route == "estop":
                                self.assertIs(receipt["output"]["safe_state_achieved"], positive)
                        finally:
                            close_server(server)

    def wait_terminal(self, bridge, goal):
        ident = support.goal_id(goal)
        with bridge._condition:
            self.assertTrue(bridge._condition.wait_for(
                lambda: ident in bridge._actions and bridge._actions[ident].response is not None,
                timeout=1), ident)

    def wait_history_error(self, bridge):
        with bridge._condition:
            self.assertTrue(bridge._condition.wait_for(
                lambda: bridge._safety_history_error is not None, timeout=1))
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])

    def unknown_then_terminal(self, peer, bridge):
        count = len(peer.named_goals(support.STOP_NAME))
        with self.assertRaises(signals.OutcomeUnknown):
            bridge.call(support.SAFE, {}, BridgeContext(deadline_ms=20))
        goal = peer.wait_goal(support.STOP_NAME, count + 1)
        peer.complete(goal)
        self.wait_terminal(bridge, goal)
        return goal

    def assert_motion_fenced(self, peer, bridge):
        before = len(peer.named_goals(support.MOVE_NAME))
        with self.assertRaises(MHSError):
            bridge.call(support.MOVE, {}, BridgeContext(deadline_ms=100))
        self.assertEqual(len(peer.named_goals(support.MOVE_NAME)), before)

    def assert_sticky_fault(self, peer, bridge, *, expect_retry=True):
        self.wait_history_error(bridge)
        fault = bridge._safety_history_error
        sent = len(peer.named_goals(support.STOP_NAME))
        try:
            result = bridge.safe_state(BridgeContext(deadline_ms=100))
        except (MHSError, signals.DriverFailed, signals.OutcomeUnknown):
            pass
        else:
            self.assertFalse(result["achieved"])
        with self.assertRaises((MHSError, signals.DriverFailed, signals.OutcomeUnknown)):
            bridge.reset(BridgeContext(deadline_ms=100))
        self.assertIs(bridge._safety_history_error, fault)
        self.assertEqual(len(peer.named_goals(support.STOP_NAME)), sent + int(expect_retry))
        self.assert_motion_fenced(peer, bridge)

    def test_stock_forty_unknown_late_cycles_keep_fence_then_estop_reset_recovers(self):
        self.assertEqual(ros_actions.MAX_SAFETY_HISTORY, 16)
        for profile in support.PROFILES:
            with self.subTest(profile=profile):
                peer = RetirementPeer(profile, automatic_stop=False)
                driver, client = self.server(peer, include_safe=True, stop_timeout_ms=20)
                bridge = driver.inner
                ids = []
                generations = []
                for index in range(40):
                    receipt = client.command(support.SAFE, {}, deadline_ms=500)
                    self.assertEqual(receipt["status"], "unknown", (index, receipt))
                    goal = peer.wait_goal(support.STOP_NAME, index + 1)
                    ids.append(support.goal_id(goal))
                    peer.complete(goal)
                    self.wait_terminal(bridge, goal)
                    self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
                    refused = client.command(support.MOVE, {}, deadline_ms=500)
                    self.assertNotEqual(refused["status"], "completed", (index, refused))
                    self.assertFalse(peer.named_goals(support.MOVE_NAME))
                    self.assertLessEqual(len(bridge._actions), ros_actions.MAX_SAFETY_ACTIONS)
                    self.assertLessEqual(len(bridge._safety_history), ros_actions.MAX_SAFETY_HISTORY)
                    generations.append(bridge._safety_reconcile_generation)
                self.assertEqual(len(set(ids)), 40)
                parsed_ids = [re.fullmatch(r"mhs-safety-([0-9a-f]{32})-([1-9][0-9]*)", ident) for ident in ids]
                self.assertTrue(all(parsed_ids), ids)
                nonces = {match.group(1) for match in parsed_ids}
                self.assertEqual(len(nonces), 1)
                self.assertEqual(uuid.UUID(hex=next(iter(nonces))).version, 4)
                serials = [int(match.group(2)) for match in parsed_ids]
                self.assertEqual(serials, sorted(set(serials)))
                self.assertLessEqual(serials[-1], 2**63 - 1)
                self.assertEqual(generations, sorted(generations))
                self.assertGreater(generations[-1], generations[0])
                self.assertTrue(bridge._safety_reconciliation_needed)
                peer.automatic_stop = True
                stopped = client.estop()
                self.assertTrue(stopped["output"]["safe_state_achieved"], stopped)
                self.assertTrue(bridge._safety_reconciliation_needed)
                self.assertGreaterEqual(bridge._safety_retired_through, 40)
                self.assertEqual(len(bridge._safety_history), ros_actions.MAX_SAFETY_HISTORY)
                self.assertNotIn(ids[0], bridge._safety_history)
                self.assertEqual(client.reset()["result"]["status"], "completed")
                self.assertFalse(bridge._safety_reconciliation_needed)
                self.assertFalse(bridge._actions)
                moved = client.command(support.MOVE, {}, deadline_ms=500)
                self.assertEqual(moved["status"], "completed", moved)
                self.assertEqual(len(peer.named_goals(support.MOVE_NAME)), 1)
                self.assertFalse(peer.cancels)

    def test_reclaimed_unknown_fences_write_and_action_until_explicit_reset(self):
        for profile in support.PROFILES:
            with self.subTest(profile=profile):
                peer = RetirementPeer(profile, automatic_stop=False)
                cfg = support.config(profile)
                cfg["writes"] = {"main": {"params": {"gain": {
                    "service": "/set_gain", "args": {"value": {"from": "input.value"}},
                    "success": {"path": "success", "equals": True}}}}}
                bridge = self.bridge(peer, cfg)
                old = self.unknown_then_terminal(peer, bridge)
                peer.automatic_stop = True
                self.assertTrue(bridge.safe_state()["achieved"])
                self.assertNotIn(support.goal_id(old), bridge._actions)
                self.assertTrue(bridge._safety_reconciliation_needed)
                self.assert_motion_fenced(peer, bridge)
                before = len(peer.transport.sent)
                with self.assertRaises(MHSError):
                    bridge.write("main", {"gain": 2})
                self.assertEqual(len(peer.transport.sent), before)
                bridge.reset()
                self.assertFalse(bridge._safety_reconciliation_needed)
                self.assertEqual(bridge.write("main", {"gain": 2}), {"applied": {"gain": 2}})
                self.assertEqual(bridge.call(support.MOVE, {}), {"success": True})

    def test_reset_reclaims_before_its_snapshot_without_self_generation_conflict(self):
        for profile in support.PROFILES:
            with self.subTest(profile=profile):
                peer = RetirementPeer(profile, automatic_stop=False)
                bridge = self.bridge(peer)
                old = self.unknown_then_terminal(peer, bridge)
                self.assertIn(support.goal_id(old), bridge._actions)
                peer.automatic_stop = True
                bridge.reset()
                self.assertNotIn(support.goal_id(old), bridge._actions)
                self.assertIn(support.goal_id(old), bridge._safety_history)
                self.assertFalse(bridge._safety_reconciliation_needed)
                self.assertEqual(len(peer.named_goals(support.STOP_NAME)), 2)
                self.assertEqual(bridge.call(support.MOVE, {}), {"success": True})

    def test_normal_successes_roll_history_and_recent_duplicate_is_harmless(self):
        for profile in support.PROFILES:
            with self.subTest(profile=profile):
                peer = RetirementPeer(profile)
                bridge = self.bridge(peer)
                watermarks = []
                for _ in range(40):
                    self.assertTrue(bridge.safe_state()["achieved"])
                    watermarks.append(bridge._safety_retired_through)
                    self.assertLessEqual(len(bridge._safety_history), ros_actions.MAX_SAFETY_HISTORY)
                self.assertEqual(watermarks, sorted(set(watermarks)))
                self.assertFalse(bridge._actions)
                self.assertFalse(bridge._safety_reconciliation_needed)
                latest = peer.named_goals(support.STOP_NAME)[-1]
                duplicate = support.terminal(profile, latest)
                values = duplicate["msg"]["result"] if profile == support.PROFILES[0] else duplicate["values"]
                # Object key order is irrelevant to the normalized terminal fingerprint.
                reordered = dict(reversed(list(values.items())))
                if profile == support.PROFILES[0]:
                    duplicate["msg"]["result"] = reordered
                else:
                    duplicate["values"] = reordered
                peer.transport.feed(duplicate)
                self.drain(bridge)
                self.assertIsNone(bridge._safety_history_error)
                self.assertTrue(bridge.safety_status()["safe_state"]["achieved"])
                self.assertEqual(len(peer.named_goals(support.STOP_NAME)), 40)

    def test_recent_bad_result_is_sticky_for_successful_and_reclaimed_goals(self):
        for profile in support.PROFILES:
            for was_unknown in (False, True):
                for mutation in ("contradiction", "malformed", "wrong_endpoint", "boolean_status", "typed_value"):
                    with self.subTest(profile=profile, was_unknown=was_unknown, mutation=mutation):
                        peer = RetirementPeer(profile, automatic_stop=not was_unknown)
                        bridge = self.bridge(peer)
                        if was_unknown:
                            old = self.unknown_then_terminal(peer, bridge)
                            peer.automatic_stop = True
                            self.assertTrue(bridge.safe_state()["achieved"])
                        else:
                            self.assertTrue(bridge.safe_state()["achieved"])
                            old = peer.wait_goal(support.STOP_NAME)
                        self.assertIn(support.goal_id(old), bridge._safety_history)
                        message = support.terminal(profile, old, success=mutation != "contradiction")
                        if profile == support.PROFILES[0]:
                            if mutation == "malformed":
                                message["msg"]["result"] = []
                            elif mutation == "wrong_endpoint":
                                message["topic"] = "/other/result"
                            elif mutation == "boolean_status":
                                message["msg"]["status"]["status"] = True
                            elif mutation == "typed_value":
                                message["msg"]["result"]["success"] = 1
                        else:
                            if mutation == "malformed":
                                message["values"] = []
                            elif mutation == "wrong_endpoint":
                                message["action"] = "/other"
                            elif mutation == "boolean_status":
                                message["status"] = True
                            elif mutation == "typed_value":
                                message["values"]["success"] = 1
                        peer.transport.feed(message)
                        self.assert_sticky_fault(peer, bridge)

    def test_expired_history_status_and_feedback_are_ignored_but_result_faults(self):
        for profile in support.PROFILES:
            with self.subTest(profile=profile):
                peer = RetirementPeer(profile)
                bridge = self.bridge(peer)
                for _ in range(40):
                    self.assertTrue(bridge.safe_state()["achieved"])
                old = peer.named_goals(support.STOP_NAME)[0]
                ident = support.goal_id(old)
                self.assertNotIn(ident, bridge._safety_history)
                if profile == support.PROFILES[0]:
                    peer.transport.feed({"op": "publish", "topic": support.STOP_NAME + "/status", "msg": {
                        "status_list": [{"goal_id": {"id": ident}, "status": 3}]}})
                    peer.transport.feed({"op": "publish", "topic": support.STOP_NAME + "/feedback", "msg": {
                        "status": {"goal_id": {"id": ident}, "status": 3}, "feedback": {}}})
                else:
                    peer.transport.feed({"op": "action_feedback", "action": support.STOP_NAME,
                                         "id": ident, "values": {}})
                self.drain(bridge)
                self.assertIsNone(bridge._safety_history_error)
                self.assertTrue(bridge.safety_status()["safe_state"]["achieved"])
                # Even an identical result cannot be proved identical after eviction.
                peer.complete(old)
                self.assert_sticky_fault(peer, bridge)

    def test_unsettled_and_error_records_are_never_evicted_for_admission(self):
        for profile in support.PROFILES:
            for malformed in (False, True):
                with self.subTest(profile=profile, malformed=malformed):
                    peer = RetirementPeer(profile, automatic_stop=False)
                    bridge = self.bridge(peer)
                    with self.assertRaises(signals.OutcomeUnknown):
                        bridge.call(support.SAFE, {}, BridgeContext(deadline_ms=20))
                    old = peer.wait_goal(support.STOP_NAME)
                    ident = support.goal_id(old)
                    record = bridge._actions[ident]
                    if malformed:
                        message = support.terminal(profile, old)
                        if profile == support.PROFILES[0]:
                            message["msg"]["status"]["status"] = "3"
                        else:
                            message["status"] = "4"
                        peer.transport.feed(message)
                        with bridge._condition:
                            self.assertTrue(bridge._condition.wait_for(lambda: record.error is not None, timeout=1))
                    for _ in range(ros_actions.MAX_SAFETY_HISTORY + 2):
                        with self.assertRaises((MHSError, signals.DriverFailed, signals.OutcomeUnknown)):
                            bridge.safe_state(BridgeContext(deadline_ms=100))
                    self.assertIs(bridge._actions[ident], record)
                    self.assertNotIn(ident, bridge._safety_history)
                    self.assertEqual(len(peer.named_goals(support.STOP_NAME)), 1)
                    with self.assertRaises(MHSError):
                        bridge.reset()
                    self.assert_motion_fenced(peer, bridge)

    def test_active_ordinary_goal_survives_forty_independent_safety_retirements(self):
        for profile in support.PROFILES:
            with self.subTest(profile=profile):
                peer = RetirementPeer(profile)
                peer.automatic_move = False
                bridge = self.bridge(peer)
                thread, outcome = self.worker(lambda: bridge.call(
                    support.MOVE, {}, BridgeContext(deadline_ms=3000)))
                goal = peer.wait_goal(support.MOVE_NAME)
                ident = support.goal_id(goal)
                record = bridge._actions[ident]
                for _ in range(40):
                    self.assertFalse(bridge.safe_state()["achieved"])
                    self.assertIs(bridge._actions[ident], record)
                    self.assertIsNone(record.response)
                    self.assertFalse(record.abandoned)
                    self.assertLessEqual(len(bridge._safety_history), ros_actions.MAX_SAFETY_HISTORY)
                peer.complete(goal)
                self.joined(thread, outcome)
                self.assertNotIn("error", outcome)
                self.assertEqual(outcome["result"], {"success": True})
                self.assertTrue(bridge.safe_state()["achieved"])
                self.assertEqual(len(peer.named_goals(support.MOVE_NAME)), 1)

    def test_reset_refuses_contradiction_to_archived_goal_during_fresh_stop(self):
        for profile in support.PROFILES:
            with self.subTest(profile=profile):
                peer = RetirementPeer(profile, automatic_stop=False)
                bridge = self.bridge(peer)
                old = self.unknown_then_terminal(peer, bridge)
                thread, outcome = self.worker(lambda: bridge.reset(BridgeContext(deadline_ms=500)))
                fresh = peer.wait_goal(support.STOP_NAME, 2)
                self.assertNotIn(support.goal_id(old), bridge._actions)
                self.assertIn(support.goal_id(old), bridge._safety_history)
                peer.complete(old, success=False)
                self.wait_history_error(bridge)
                peer.complete(fresh)
                self.joined(thread, outcome)
                self.assertIn("error", outcome)
                self.assertTrue(bridge._safety_reconciliation_needed)
                self.assert_sticky_fault(peer, bridge)

    def test_reset_refuses_archived_contradiction_arriving_with_reset_service_reply(self):
        for profile in support.PROFILES:
            with self.subTest(profile=profile):
                peer = RetirementPeer(profile, automatic_stop=False)
                cfg = support.config(profile)
                cfg["safety_bindings"]["reset"] = {
                    "service": "/reset", "success": {"path": "success", "equals": True}}
                bridge = self.bridge(peer, cfg)
                old = self.unknown_then_terminal(peer, bridge)
                peer.automatic_stop = True
                peer.on_reset = lambda message: [support.terminal(profile, old, success=False), {
                    "op": "service_response", "id": message["id"], "service": "/reset",
                    "result": True, "values": {"success": True}}]
                with self.assertRaises((MHSError, signals.DriverFailed, signals.OutcomeUnknown)):
                    bridge.reset(BridgeContext(deadline_ms=500))
                self.assertEqual(sum(message.get("service") == "/reset" for message in peer.transport.sent), 1)
                self.assertTrue(bridge._safety_reconciliation_needed)
                self.assert_sticky_fault(peer, bridge)

    def test_ros1_retirement_cleanup_precedes_next_endpoint_setup(self):
        peer = RetirementPeer(support.PROFILES[0], automatic_stop=False)
        bridge = self.bridge(peer)
        old = self.unknown_then_terminal(peer, bridge)
        old_id = support.goal_id(old)
        peer.automatic_stop = True
        self.assertTrue(bridge.safe_state()["achieved"])
        new_id = support.goal_id(peer.wait_goal(support.STOP_NAME, 2))
        old_setup = [message for message in peer.transport.sent if message.get("op") in ("subscribe", "advertise")
                     and message.get("id", "").startswith(old_id + ":")]
        old_cleanup = [(index, message) for index, message in enumerate(peer.transport.sent)
                       if message.get("op") in ("unsubscribe", "unadvertise")
                       and message.get("id", "").startswith(old_id + ":")]
        new_setup = [index for index, message in enumerate(peer.transport.sent)
                     if message.get("op") in ("subscribe", "advertise")
                     and message.get("id", "").startswith(new_id + ":")]
        self.assertEqual({message["id"] for message in old_setup}, {message["id"] for _, message in old_cleanup})
        self.assertEqual(len(old_cleanup), len(old_setup))
        self.assertLess(max(index for index, _ in old_cleanup), min(new_setup))

    def test_reset_retirement_cannot_overlap_a_fresh_safety_setup(self):
        peer = RetirementPeer(support.PROFILES[0], automatic_stop=False)
        bridge = self.bridge(peer)
        self.unknown_then_terminal(peer, bridge)
        entered, release = threading.Event(), threading.Event()
        arm = [True]

        # A transport may prepare before taking the bridge wire lock. Hold only
        # the reset's first cleanup preparation, leaving an independent stop
        # free to reveal an incorrect concurrent setup.
        def prepare(*, timeout_s):
            if threading.current_thread().name == "retirement-reset" and arm[0]:
                arm[0] = False
                entered.set()
                if not release.wait(1):
                    raise TimeoutError("controlled retirement was not released")
        peer.transport.prepare = prepare
        outcome = {}
        def reset():
            try:
                outcome["result"] = bridge.reset(BridgeContext(deadline_ms=500))
            except BaseException as exc:
                outcome["error"] = exc
        thread = threading.Thread(target=reset, name="retirement-reset", daemon=True)
        self.addCleanup(release.set)
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            before = len(peer.transport.sent)
            with self.assertRaises((MHSError, signals.DriverFailed, signals.OutcomeUnknown)):
                bridge.safe_state(BridgeContext(deadline_ms=5))
            # Stop is boundedly refused while cleanup owns the safety lane;
            # no new subscription, advertisement or goal may overtake teardown.
            self.assertEqual(len(peer.transport.sent), before)
            self.assertEqual(len(peer.named_goals(support.STOP_NAME)), 1)
        finally:
            peer.automatic_stop = True
            release.set()
            thread.join(1)
        self.assertFalse(thread.is_alive(), outcome)
        self.assertNotIn("error", outcome)
        self.assertFalse(bridge._safety_reconciliation_needed)
        self.assertEqual(len(peer.named_goals(support.STOP_NAME)), 2)

    def test_reset_cannot_retire_after_close_cancellation_or_expired_deadline(self):
        for profile in support.PROFILES:
            for guard in ("closed", "cancelled", "expired"):
                with self.subTest(profile=profile, guard=guard):
                    peer = RetirementPeer(profile, automatic_stop=False)
                    bridge = self.bridge(peer)
                    old = self.unknown_then_terminal(peer, bridge)
                    ident = support.goal_id(old)
                    record = bridge._actions[ident]
                    context = BridgeContext(deadline_ms=500)
                    if guard == "closed":
                        bridge.close()
                    elif guard == "cancelled":
                        cancelled = threading.Event()
                        cancelled.set()
                        context.cancel_event = cancelled
                    else:
                        context.extra["deadline_at"] = time.monotonic() - 1
                    before = len(peer.transport.sent)
                    with self.assertRaises((MHSError, signals.Cancelled, signals.DriverFailed)):
                        bridge.reset(context)
                    self.assertEqual(len(peer.transport.sent), before)
                    self.assertIs(bridge._actions[ident], record)
                    self.assertNotIn(ident, bridge._safety_history)
                    self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])

    def test_ros1_cleanup_does_not_hold_receiver_condition(self):
        peer = RetirementPeer(support.PROFILES[0], automatic_stop=False)
        bridge = self.bridge(peer)
        self.unknown_then_terminal(peer, bridge)
        peer.automatic_stop = True
        peer.pause_cleanup = True
        thread, outcome = self.worker(lambda: bridge.safe_state(BridgeContext(deadline_ms=500)))
        self.addCleanup(peer.cleanup_release.set)
        self.assertTrue(peer.cleanup_entered.wait(1))
        acquired = bridge._condition.acquire(timeout=0.2)
        if acquired:
            bridge._condition.release()
        peer.cleanup_release.set()
        self.joined(thread, outcome)
        self.assertTrue(acquired, "retirement cleanup held the receiver condition")
        self.assertNotIn("error", outcome)
        self.assertTrue(outcome["result"]["achieved"])

    def test_ros1_cleanup_failure_is_sticky_and_does_not_admit_next_goal(self):
        peer = RetirementPeer(support.PROFILES[0], automatic_stop=False)
        bridge = self.bridge(peer)
        self.unknown_then_terminal(peer, bridge)
        peer.automatic_stop = True
        peer.fail_cleanup = True
        with self.assertRaises((MHSError, signals.DriverFailed, signals.OutcomeUnknown)):
            bridge.safe_state()
        self.assertEqual(len(peer.named_goals(support.STOP_NAME)), 1)
        self.assertTrue(bridge._safety_reconciliation_needed)
        self.assert_sticky_fault(peer, bridge, expect_retry=False)

    def test_close_during_retirement_cleanup_has_no_latent_setup_or_goal(self):
        peer = RetirementPeer(support.PROFILES[0], automatic_stop=False)
        bridge = self.bridge(peer)
        self.unknown_then_terminal(peer, bridge)
        peer.automatic_stop = True
        peer.pause_cleanup = True
        thread, outcome = self.worker(lambda: bridge.safe_state(BridgeContext(deadline_ms=500)))
        self.addCleanup(peer.cleanup_release.set)
        self.assertTrue(peer.cleanup_entered.wait(1))
        bridge.close()
        before = len(peer.transport.sent)
        peer.cleanup_release.set()
        self.joined(thread, outcome)
        self.assertIn("error", outcome)
        self.assertEqual(len(peer.transport.sent), before)
        self.assertEqual(len(peer.named_goals(support.STOP_NAME)), 1)
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])


if __name__ == "__main__":
    unittest.main()
