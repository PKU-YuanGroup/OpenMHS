"""Private action-backed safety regressions through the stock server and bridge.

The ROS-free peer follows the pinned Franka StopAction shape: an empty goal,
{success, error} result, and no cancellation callback that completes native work.
These tests do not load ROS, libfranka, or any physical device.
"""

from __future__ import annotations

import copy
import threading
import unittest
import uuid
from unittest.mock import patch

from mhs import signals
from mhs.bridge.base import BridgeContext
from mhs.bridge.ros import RecordingRosTransport, RosBridge
from mhs.driver import Action, Field, RosDriver, close_server
from mhs.errors import MHSError
from tests.driver import support

MOVE = "x-cap.test.action-safety-move.v1"
SAFE = "x-cap.test.action-safety-stop.v1"
READ = "x-cap.test.action-safety-read.v1"
PROFILES = ("ros1-actionlib", "ros2-native")
STOP_NAME = "/franka_gripper/stop"
MOVE_NAME = "/franka_gripper/move"


def binding(profile, name=STOP_NAME):
    kind = "Stop" if name == STOP_NAME else "Move"
    return {"action": name, "profile": profile,
            "type": f"franka_gripper/{kind}Action" if profile == PROFILES[0]
            else f"example/action/{kind}",
            "request": {} if name == STOP_NAME else {"width": 0.02, "speed": 0.1},
            "success": {"path": "success", "equals": True},
            "result": {"map": {"success": "output.success"}}}


def config(profile):
    return {"timeout_s": 0.5, "commands": {
        MOVE: binding(profile, MOVE_NAME),
        SAFE: {**binding(profile), "safe_state": True},
        READ: {"service": "/state", "operation": "read"}},
        "safety_bindings": {"estop": binding(profile)},
    }


def action_name(message, suffix="goal"):
    if message.get("op") == ("send_action_goal" if suffix == "goal" else "cancel_action_goal"):
        return message.get("action")
    if message.get("op") == "publish" and message.get("topic", "").endswith("/" + suffix):
        return message["topic"][:-(len(suffix) + 1)]
    return None


def goal_id(message):
    return message["msg"]["goal_id"]["id"] if message.get("op") == "publish" else message["id"]


def terminal(profile, goal, *, success=True, status=None):
    status = (3 if profile == PROFILES[0] else 4) if status is None else status
    values = {"success": success, "error": "" if success else "native unsuccessful"}
    name = action_name(goal)
    if profile == PROFILES[0]:
        return {"op": "publish", "topic": name + "/result", "msg": {
            "status": {"goal_id": {"id": goal_id(goal)}, "status": status}, "result": values}}
    return {"op": "action_result", "action": name, "id": goal_id(goal),
            "status": status, "result": True, "values": values}


class FrankaPeer:
    """Record native attempts; explicit terminal release is independent of cancel."""

    def __init__(self, profile, *, automatic_stop=True):
        self.profile = profile
        self.automatic_stop = automatic_stop
        self.stop_success = True
        self.stop_status = None
        self.on_stop = None
        self.goals = []
        self.cancels = []
        self.condition = threading.Condition()
        self.transport = RecordingRosTransport(self.handle)

    def handle(self, message):
        name = action_name(message)
        if name is not None:
            with self.condition:
                self.goals.append(copy.deepcopy(message))
                self.condition.notify_all()
            if name == STOP_NAME:
                if self.on_stop is not None:
                    return self.on_stop(message)
                if self.automatic_stop:
                    return terminal(self.profile, message, success=self.stop_success, status=self.stop_status)
        elif action_name(message, "cancel") is not None:
            with self.condition:
                self.cancels.append(copy.deepcopy(message))
                self.condition.notify_all()
            # The pinned Franka callbacks do not handle preempt requests.
            # A cancel frame alone deliberately does not produce a result.
        elif message.get("op") == "call_service":
            return {"op": "service_response", "id": message["id"], "service": message["service"],
                    "result": True, "values": {"success": True}}
        return None

    def named_goals(self, name):
        with self.condition:
            return [g for g in self.goals if action_name(g) == name]

    def wait_goal(self, name, count=1):
        with self.condition:
            if not self.condition.wait_for(lambda: len(self.named_goals(name)) >= count, timeout=1):
                raise AssertionError(f"did not receive goal {count} for {name}")
            return copy.deepcopy(self.named_goals(name)[count - 1])

    def complete(self, goal, **kwargs):
        self.transport.feed(terminal(self.profile, goal, **kwargs))


class RosActionSafetyTests(unittest.TestCase):
    def bridge(self, peer, cfg=None):
        schemas = {SAFE: {"output_schema": {"type": "object", "properties": {
            "success": {"type": "boolean"}}, "required": ["success"], "additionalProperties": False}}}
        bridge = RosBridge(cfg or config(peer.profile), transport=peer.transport, capability_schemas=schemas)
        self.addCleanup(bridge.close)
        return bridge

    def server(self, peer, *, include_safe=False, safe_output_type="boolean", stop_timeout_ms=None):
        cfg = config(peer.profile)
        if stop_timeout_ms is not None:
            cfg["commands"][SAFE]["timeout_ms"] = stop_timeout_ms
            cfg["safety_bindings"]["estop"]["timeout_ms"] = stop_timeout_ms
        actions = {MOVE: Action(name="move", output={"success": Field("boolean")},
                                long_running=True, cancellable=True, max_duration_ms=1000)}
        commands = {MOVE: cfg["commands"][MOVE]}
        if include_safe:
            actions[SAFE] = Action(name="stop", safe_state=True, output={"success": Field(safe_output_type)})
            commands[SAFE] = cfg["commands"][SAFE]
        cls = type("ActionSafetyDriver", (RosDriver,), {
            "device_id": "ros-action-safety-test", "device_kind": "instrument", "risk": "R0",
            "ros_version": 1 if peer.profile == PROFILES[0] else 2,
            "timeout_s": cfg["timeout_s"], "commands": commands, "actions": actions,
            "safety_bindings": cfg["safety_bindings"], "backends": {"fake": lambda: peer.transport},
        })
        driver = cls(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        return driver, client

    def worker(self, fn):
        outcome = {}
        def run():
            try:
                outcome["result"] = fn()
            except BaseException as exc:
                outcome["error"] = exc
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 1)
        return thread, outcome

    def joined(self, thread, outcome):
        thread.join(1)
        self.assertFalse(thread.is_alive(), outcome)
        return outcome

    def drain(self, bridge):
        # Service response is queued after prior frames, providing a receiver barrier.
        bridge.call(READ, {})

    def test_fixed_action_grammar_and_construction_are_strict(self):
        for profile in PROFILES:
            for placement in ("estop", "safe_state"):
                with self.subTest(profile=profile, placement=placement):
                    peer = FrankaPeer(profile)
                    cfg = config(profile)
                    cfg["safety_bindings"] = {placement: binding(profile)}
                    self.bridge(peer, cfg)
                    self.assertEqual(peer.transport.sent, [])
            invalid = []
            for placement in ("estop", "safe_state", "reset"):
                cfg = config(profile)
                cfg["safety_bindings"] = {placement: {
                    **binding(profile), "args": {"anything": {"from": "input.value"}}}}
                invalid.append(cfg)
            cfg = config(profile)
            cfg["safety_bindings"]["reset"] = binding(profile)
            invalid.append(cfg)
            cfg = config(profile)
            cfg["commands"][SAFE]["args"] = {"anything": {"from": "input.value"}}
            invalid.append(cfg)
            for absent in ("profile", "type", "success"):
                cfg = config(profile)
                del cfg["safety_bindings"]["estop"][absent]
                invalid.append(cfg)
            for cfg in invalid:
                with self.subTest(profile=profile, invalid=cfg):
                    transport = RecordingRosTransport()
                    with self.assertRaises(MHSError):
                        RosBridge(cfg, transport=transport)
                    self.assertEqual(transport.sent, [])

    def test_fixed_safe_command_rejects_caller_inputs_before_transport(self):
        for profile in PROFILES:
            peer = FrankaPeer(profile)
            bridge = self.bridge(peer)
            with self.assertRaises(MHSError):
                bridge.call(SAFE, {"force": True})
            self.assertEqual(peer.transport.sent, [])

    def test_stock_estop_confirms_exact_stop_result_and_keeps_latch(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                peer = FrankaPeer(profile)
                driver, client = self.server(peer)
                receipt = client.estop()
                self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
                self.assertTrue(driver.inner.safety_status()["safe_state"]["achieved"])
                goal = peer.wait_goal(STOP_NAME)
                self.assertEqual(goal["msg"]["goal"] if profile == PROFILES[0] else goal["args"], {})
                self.assertEqual(len(peer.named_goals(STOP_NAME)), 1)
                self.assertFalse(peer.cancels)
                refused = client.command(MOVE, {})
                self.assertEqual(support.code(refused), "MHS.SAFETY.ESTOP_ENGAGED", refused)
                self.assertFalse(peer.named_goals(MOVE_NAME))
                self.assertEqual(client.reset()["result"]["status"], "completed")

    def test_stock_success_status_requires_native_true_boolean(self):
        for profile in PROFILES:
            for success, status in ((False, None), (1, None), (True, 4 if profile == PROFILES[0] else 6)):
                with self.subTest(profile=profile, success=success, status=status):
                    peer = FrankaPeer(profile)
                    peer.stop_success, peer.stop_status = success, status
                    driver, client = self.server(peer)
                    receipt = client.estop()
                    self.assertFalse(receipt["output"].get("safe_state_achieved", False), receipt)
                    self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
                    self.assertEqual(len(peer.named_goals(STOP_NAME)), 1)
                    self.assertFalse(peer.cancels)

    def test_stock_safe_capability_validates_resolved_output_before_achieved(self):
        for profile in PROFILES:
            for output_type in ("boolean", "string"):
                with self.subTest(profile=profile, output_type=output_type):
                    peer = FrankaPeer(profile)
                    driver, client = self.server(peer, include_safe=True, safe_output_type=output_type)
                    receipt = client.command(SAFE, {})
                    valid = output_type == "boolean"
                    self.assertEqual(receipt["status"], "completed" if valid else "failed", receipt)
                    self.assertEqual(driver.inner.safety_status()["safe_state"]["achieved"], valid)
                    self.assertEqual(len(peer.named_goals(STOP_NAME)), 1)

    def test_exact_goal_result_is_required_and_status_alone_never_finishes(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                peer = FrankaPeer(profile, automatic_stop=False)
                bridge = self.bridge(peer)
                thread, outcome = self.worker(lambda: bridge.safe_state(BridgeContext(deadline_ms=500)))
                goal = peer.wait_goal(STOP_NAME)
                stale = copy.deepcopy(goal)
                if profile == PROFILES[0]:
                    stale["msg"]["goal_id"]["id"] = "old-" + uuid.uuid4().hex
                    peer.transport.feed({"op": "publish", "topic": STOP_NAME + "/status", "msg": {
                        "status_list": [{"goal_id": {"id": goal_id(goal)}, "status": 3}]}})
                else:
                    stale["id"] = "old-" + uuid.uuid4().hex
                peer.complete(stale)
                wrong_endpoint = terminal(profile, goal)
                wrong_endpoint["topic" if profile == PROFILES[0] else "action"] = "/unrelated/result" if profile == PROFILES[0] else "/unrelated"
                # ROS 2 reports a matching-ID endpoint mismatch as uncertainty;
                # only ROS 1's unrelated topic is an ignorable publication.
                if profile == PROFILES[0]:
                    peer.transport.feed(wrong_endpoint)
                self.drain(bridge)
                self.assertTrue(thread.is_alive(), outcome)
                self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
                peer.complete(goal)
                self.joined(thread, outcome)
                self.assertTrue(outcome["result"]["achieved"], outcome)
                self.assertEqual(len(peer.named_goals(STOP_NAME)), 1)

    def test_stock_timeout_does_not_recurse_cancel_or_replay_and_reset_refuses(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                peer = FrankaPeer(profile, automatic_stop=False)
                driver, client = self.server(peer, include_safe=True, stop_timeout_ms=30)
                receipt = client.command(SAFE, {}, deadline_ms=500)
                self.assertEqual(receipt["status"], "unknown", receipt)
                self.assertEqual(len(peer.named_goals(STOP_NAME)), 1)
                self.assertFalse(peer.cancels)
                self.assertTrue(any(item.sent and item.abandoned for item in driver.inner._actions.values()))
                self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
                reset = client.reset()
                self.assertNotEqual(reset.get("result", {}).get("status"), "completed", reset)
                self.assertEqual(len(peer.named_goals(STOP_NAME)), 1)

    def test_stock_disconnect_retains_unknown_stop_and_never_replays(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                peer = FrankaPeer(profile)
                peer.on_stop = lambda message: peer.transport.close()
                driver, client = self.server(peer, include_safe=True)
                receipt = client.command(SAFE, {})
                self.assertEqual(receipt["status"], "unknown", receipt)
                self.assertEqual(len(peer.named_goals(STOP_NAME)), 1)
                self.assertTrue(any(item.abandoned for item in driver.inner._actions.values()))
                self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
                before = len(peer.transport.sent)
                with self.assertRaises(MHSError):
                    driver.inner.reset()
                self.assertEqual(len(peer.transport.sent), before)

    def test_stock_stop_bypasses_active_goal_and_requires_later_fresh_stop(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                peer = FrankaPeer(profile)
                driver, client = self.server(peer)
                running = client.command(MOVE, {}, deadline_ms=10)
                goal = peer.wait_goal(MOVE_NAME)
                receipt = client.estop()
                self.assertFalse(receipt["output"]["safe_state_achieved"], receipt)
                self.assertTrue(peer.named_goals(STOP_NAME))
                self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
                operation = client.server._operations[running["operation_id"]]
                self.assertFalse(operation.done.is_set())
                with peer.condition:
                    self.assertTrue(peer.condition.wait_for(
                        lambda: any(action_name(msg, "cancel") == MOVE_NAME for msg in peer.cancels), timeout=1))
                # Stop acknowledgement does not finish the outstanding Move callback.
                # Franka returns its own terminal separately; cancel itself has no effect.
                peer.complete(goal, success=False, status=4 if profile == PROFILES[0] else 6)
                operation.thread.join(1)
                self.assertFalse(operation.thread.is_alive())
                self.assertNotEqual(client.operation(running["operation_id"])["status"], "completed")
                self.assertTrue(driver.inner.safety_status()["safe_state"]["achieved"])
                self.assertGreaterEqual(len(peer.named_goals(STOP_NAME)), 2)
                frames = peer.transport.sent
                stop_index = next(i for i, msg in enumerate(frames) if action_name(msg) == STOP_NAME)
                cancel_indices = [i for i, msg in enumerate(frames) if action_name(msg, "cancel") == MOVE_NAME]
                if cancel_indices:
                    self.assertLess(stop_index, cancel_indices[0])
                self.assertFalse(any(action_name(msg, "cancel") == STOP_NAME for msg in frames))

    def test_terminal_during_stop_invalidates_attempt_until_fresh_ack(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                peer = FrankaPeer(profile)
                bridge = self.bridge(peer)
                thread, outcome = self.worker(lambda: bridge.call(MOVE, {}, BridgeContext(deadline_ms=500)))
                goal = peer.wait_goal(MOVE_NAME)
                peer.on_stop = lambda stop: [terminal(profile, goal), terminal(profile, stop)]
                self.assertFalse(bridge.safe_state()["achieved"])
                self.joined(thread, outcome)
                self.assertEqual(outcome["result"], {"success": True})
                self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
                peer.on_stop = None
                self.assertTrue(bridge.safe_state()["achieved"])
                self.assertEqual(len(peer.named_goals(STOP_NAME)), 2)

    def test_safety_has_admission_when_ordinary_action_capacity_is_full(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                peer = FrankaPeer(profile)
                bridge = self.bridge(peer)
                with patch("mhs.bridge.ros.MAX_ACTIONS", 1):
                    thread, outcome = self.worker(lambda: bridge.call(MOVE, {}, BridgeContext(deadline_ms=500)))
                    goal = peer.wait_goal(MOVE_NAME)
                    self.assertFalse(bridge.safe_state()["achieved"])
                    self.assertEqual(len(peer.named_goals(STOP_NAME)), 1)
                    peer.complete(goal)
                    self.joined(thread, outcome)
                    self.assertEqual(outcome["result"], {"success": True})

    def test_concurrent_safety_call_cannot_preempt_inflight_stop(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                peer = FrankaPeer(profile, automatic_stop=False)
                bridge = self.bridge(peer)
                first, first_outcome = self.worker(lambda: bridge.safe_state(BridgeContext(deadline_ms=500)))
                goal = peer.wait_goal(STOP_NAME)
                second, second_outcome = self.worker(lambda: bridge.safe_state(BridgeContext(deadline_ms=30)))
                self.joined(second, second_outcome)
                self.assertIn("error", second_outcome)
                self.assertEqual(len(peer.named_goals(STOP_NAME)), 1)
                self.assertFalse(peer.cancels)
                peer.complete(goal)
                self.joined(first, first_outcome)
                self.assertNotIn("error", first_outcome)
                self.assertEqual(len(peer.named_goals(STOP_NAME)), 1)

    def test_late_stop_terminal_needs_fresh_confirmation_and_explicit_reset(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                peer = FrankaPeer(profile, automatic_stop=False)
                bridge = self.bridge(peer)
                with self.assertRaises(signals.OutcomeUnknown):
                    bridge.call(SAFE, {}, BridgeContext(deadline_ms=30))
                goal = peer.wait_goal(STOP_NAME)
                with self.assertRaises(MHSError):
                    bridge.reset()
                peer.complete(goal)
                self.drain(bridge)
                self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
                with self.assertRaises(MHSError):
                    bridge.call(MOVE, {})
                peer.automatic_stop = True
                bridge.reset()
                self.assertFalse(bridge._actions)
                self.assertEqual(len(peer.named_goals(STOP_NAME)), 2)
                self.assertFalse(peer.cancels)
                # Reset clears reconciliation; it does not preserve a cached safe proof.
                self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])

    def test_reset_detects_contradictory_old_result_during_fresh_stop(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                peer = FrankaPeer(profile, automatic_stop=False)
                bridge = self.bridge(peer)
                with self.assertRaises(signals.OutcomeUnknown):
                    bridge.call(SAFE, {}, BridgeContext(deadline_ms=30))
                old = peer.wait_goal(STOP_NAME)
                peer.complete(old)
                self.drain(bridge)
                thread, outcome = self.worker(lambda: bridge.reset(BridgeContext(deadline_ms=500)))
                new = peer.wait_goal(STOP_NAME, 2)
                peer.complete(old, success=False, status=4 if profile == PROFILES[0] else 6)
                self.drain(bridge)
                peer.complete(new)
                self.joined(thread, outcome)
                self.assertIn("error", outcome)
                self.assertIn(goal_id(old), bridge._safety_history)
                self.assertIsNotNone(bridge._safety_history_error)
                self.assertTrue(bridge._safety_reconciliation_needed)
                with self.assertRaises(MHSError):
                    bridge.reset()
                self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])

    def test_close_during_prepare_cannot_send_a_latent_safety_goal(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                entered, release = threading.Event(), threading.Event()
                peer = FrankaPeer(profile)
                class DelayedPrepare(RecordingRosTransport):
                    def prepare(self, *, timeout_s=None):
                        entered.set()
                        if not release.wait(1):
                            raise TimeoutError("test prepare was not released")
                    def close(self):
                        # Observe the bridge guard independently of a transport guard.
                        pass
                peer.transport = DelayedPrepare(peer.handle)
                bridge = self.bridge(peer)
                thread, outcome = self.worker(lambda: bridge.safe_state(BridgeContext(deadline_ms=500)))
                self.addCleanup(release.set)
                self.assertTrue(entered.wait(1))
                bridge.close()
                release.set()
                self.joined(thread, outcome)
                self.assertIn("error", outcome)
                self.assertEqual(peer.transport.sent, [])
                self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])

    def test_close_during_terminal_wait_wakes_owner_without_stop_replay(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                peer = FrankaPeer(profile, automatic_stop=False)
                bridge = self.bridge(peer)
                thread, outcome = self.worker(lambda: bridge.safe_state(BridgeContext(deadline_ms=500)))
                peer.wait_goal(STOP_NAME)
                bridge.close()
                self.joined(thread, outcome)
                self.assertIn("error", outcome)
                self.assertEqual(len(peer.named_goals(STOP_NAME)), 1)
                self.assertFalse(peer.cancels)
                self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])


if __name__ == "__main__":
    unittest.main()
