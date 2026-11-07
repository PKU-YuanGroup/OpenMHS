"""ROS-free action lifecycle, stock-server receipts, cancellation and stop races."""

from __future__ import annotations

import copy
import itertools
import threading
import time
import unittest
import uuid
from unittest.mock import patch

from mhs import signals
from mhs.bridge.base import BridgeContext
from mhs.bridge.ros import RecordingRosTransport, RosBridge
from mhs.driver import Action, Field, RosDriver, close_server
from mhs.errors import MHSError
from tests.driver import support

CAP = "x-cap.test.goal.v1"
READ = "x-cap.test.observe.v1"
RESUME = "x-cap.test.resume.v1"
PROFILES = ("ros1-actionlib", "ros2-native")


def config(profile="ros2-native"):
    return {"timeout_s": 0.05, "commands": {
        CAP: {"action": "/move", "type": "control_msgs/FollowJointTrajectoryAction" if profile == "ros1-actionlib"
              else "example/action/Move", "profile": profile, "request": {"mode": "test"},
              "args": {"target": {"from": "input.target"}},
              "success": {"path": "error_code", "equals": 0},
              "result": {"map": {"value": "output.value"}}},
        READ: {"service": "/state", "type": "example/srv/State", "operation": "read"},
        RESUME: {"service": "/resume", "type": "std_srvs/srv/Trigger",
                 "success": {"path": "success", "equals": True}},
    }, "reads": {"main": {"fields": {}}}, "writes": {"main": {"params": {
        "setting": {"service": "/set", "type": "example/srv/Set", "args": {"value": {"from": "input.value"}},
                    "success": {"path": "success", "equals": True}}
    }}}, "safety_bindings": {"estop": {"service": "/stop", "type": "std_srvs/srv/Trigger",
             "success": {"path": "success", "equals": True}}}}


def is_goal(message):
    return message["op"] == "send_action_goal" or (message["op"] == "publish" and message.get("topic") == "/move/goal")


def is_cancel(message):
    return message["op"] == "cancel_action_goal" or (message["op"] == "publish" and message.get("topic") == "/move/cancel")


def ident(message):
    return message["msg"]["goal_id"]["id"] if message.get("topic") == "/move/goal" else message["id"]


def result(profile, goal_id, status=None, values=None):
    status = (3 if profile == "ros1-actionlib" else 4) if status is None else status
    values = {"error_code": 0, "value": "done"} if values is None else values
    if profile == "ros1-actionlib":
        return {"op": "publish", "topic": "/move/result",
                "msg": {"status": {"goal_id": {"id": goal_id}, "status": status}, "result": values}}
    return {"op": "action_result", "action": "/move", "id": goal_id,
            "status": status, "result": True, "values": values}


def service_response(message, success=True):
    return {"op": "service_response", "id": message["id"], "service": message["service"],
            "result": True, "values": {"success": success}}


class RosActionTests(unittest.TestCase):
    def bridge(self, profile="ros2-native", handler=None, cfg=None, transport=None, capability_schemas=None):
        transport = transport or RecordingRosTransport(handler)
        bridge = RosBridge(cfg or config(profile), transport=transport, capability_schemas=capability_schemas)
        self.addCleanup(bridge.close)
        return bridge, transport

    def server(self, profile, handler, max_duration_ms=1000):
        cfg = config(profile)
        transport = RecordingRosTransport(handler)
        cls = type("ActionDriver", (RosDriver,), {
            "device_id": "ros-action-test", "device_kind": "instrument", "risk": "R0",
            "ros_version": 1 if profile == "ros1-actionlib" else 2, "timeout_s": cfg["timeout_s"],
            "commands": {CAP: cfg["commands"][CAP]}, "safety_bindings": cfg["safety_bindings"],
            "backends": {"fake": lambda: transport},
            "actions": {CAP: Action(name="run_goal", input={"target": Field("string")},
                                    output={"value": Field("string")}, long_running=True,
                                    cancellable=True, max_duration_ms=max_duration_ms)},
        })
        driver = cls(backend="fake")
        server, client = support.serve(driver)
        self.addCleanup(close_server, server)
        return driver, client, transport

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

    def wait_for(self, predicate, timeout=1):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if predicate():
                return
            time.sleep(0.002)
        self.fail("condition did not become true")

    def test_strict_action_binding_grammar_and_zero_construction_traffic(self):
        for profile in PROFILES:
            base = config(profile)
            bad_specs = [dict(base["commands"][CAP], profile="automatic"),
                         dict(base["commands"][CAP], type="example/srv/Move"),
                         dict(base["commands"][CAP], feedback=1),
                         dict(base["commands"][CAP], operation="read"),
                         dict(base["commands"][CAP], safe_state=True),
                         dict(base["commands"][CAP], topic="/move")]
            for missing in ("profile", "type", "success"):
                bad = copy.deepcopy(base["commands"][CAP])
                del bad[missing]
                bad_specs.append(bad)
            for spec in bad_specs:
                with self.subTest(profile=profile, spec=spec):
                    transport = RecordingRosTransport()
                    with self.assertRaises(MHSError):
                        RosBridge({"commands": {CAP: spec}}, transport=transport)
                    self.assertEqual(transport.sent, [])
        for field in ("reads", "writes", "safety_bindings"):
            cfg = ({field: {"main": {"fields" if field == "reads" else "params": {"value": config()["commands"][CAP]}}}}
                   if field != "safety_bindings" else {field: {"estop": config()["commands"][CAP]}})
            with self.subTest(field=field), self.assertRaises(MHSError):
                RosBridge(cfg, transport=RecordingRosTransport())

    def test_stock_server_success_requires_both_terminal_and_application_success(self):
        cases = [("success", None, None, "completed"), ("app_failure", None, {"error_code": 1, "value": "bad"}, "failed"),
                 ("missing_success", None, {"value": "missing"}, "failed")]
        for profile in PROFILES:
            cases_for_profile = cases + [("abort", 4 if profile == "ros1-actionlib" else 6, None, "failed")]
            if profile == "ros1-actionlib":
                cases_for_profile.append(("reject", 5, None, "failed"))
            for name, status, values, expected in cases_for_profile:
                with self.subTest(profile=profile, case=name):
                    def handler(message):
                        if is_goal(message):
                            return result(profile, ident(message), status, values)
                        if message["op"] == "call_service":
                            return service_response(message)
                    _, client, transport = self.server(profile, handler)
                    receipt = client.command(CAP, {"target": "home"})
                    self.assertEqual(receipt["status"], expected, receipt)
                    self.assertEqual(len([m for m in transport.sent if is_goal(m)]), 1)
                    if expected == "completed":
                        self.assertEqual(receipt["output"], {"value": "done"})

    def test_ros2_false_wrapper_or_bad_terminal_is_unknown_in_stock_server(self):
        mutations = [{"result": False, "status": 0, "values": "Action goal was rejected"},
                     {"status": 3}, {"status": True}, {"status": None}, {"values": []},
                     {"action": "/different"}]
        for change in mutations:
            with self.subTest(change=change):
                def handler(message):
                    return {**result("ros2-native", ident(message)), **change} if is_goal(message) else None
                driver, client, transport = self.server("ros2-native", handler)
                receipt = client.command(CAP, {"target": "home"})
                self.assertEqual(receipt["status"], "unknown", receipt)
                self.assertEqual(len(driver.inner._actions), 1)
                self.assertEqual(len(transport.sent), 1)

    def test_ros1_generated_types_and_goal_envelope_are_explicit(self):
        bridge, transport = self.bridge("ros1-actionlib", lambda msg: result("ros1-actionlib", ident(msg)) if is_goal(msg) else None)
        self.assertEqual(bridge.call(CAP, {"target": "home"}), {"value": "done"})
        types = {m["topic"]: m["type"] for m in transport.sent if "type" in m}
        self.assertEqual(types, {"/move/goal": "control_msgs/FollowJointTrajectoryActionGoal",
            "/move/result": "control_msgs/FollowJointTrajectoryActionResult", "/move/status": "actionlib_msgs/GoalStatusArray",
            "/move/cancel": "actionlib_msgs/GoalID"})
        goal = next(m for m in transport.sent if is_goal(m))
        self.assertEqual(goal["msg"]["goal"], {"mode": "test", "target": "home"})
        self.assertTrue(goal["msg"]["goal_id"]["id"])
        self.assertTrue(all(m["op"] == "subscribe" for m in transport.sent[:2]))
        self.assertEqual(len([m for m in transport.sent if m["op"] == "unsubscribe"]), 2)

    def test_ros2_wire_uses_action_type_and_stale_ids_cannot_finish_new_goal(self):
        old = "previous-goal"
        def handler(message):
            if is_goal(message):
                self.assertEqual(message["action_type"], "example/action/Move")
                self.assertNotIn("type", message)
                return [result("ros2-native", old, values={"error_code": 0, "value": "stale"}),
                        result("ros2-native", ident(message))]
        bridge, transport = self.bridge(handler=handler)
        self.assertEqual(bridge.call(CAP, {"target": "home"}), {"value": "done"})
        old = ident(transport.sent[0])
        self.assertEqual(bridge.call(CAP, {"target": "again"}), {"value": "done"})
        self.assertNotEqual(ident(transport.sent[0]), ident(transport.sent[1]))

    def test_goal_ids_remain_fresh_when_process_session_counter_restarts(self):
        goals = []
        # Fixed distinct UUIDs make the oracle deterministic while exercising
        # the same session counter reset that two fresh processes would have.
        for value in (1, 2):
            with patch("mhs.bridge.ros._SESSIONS", itertools.count(1)):
                bridge, transport = self.bridge("ros1-actionlib", lambda msg: result("ros1-actionlib", ident(msg))
                                                if is_goal(msg) else None)
                self.assertEqual(bridge._prefix, "mhs-1-")
                # Fix only the ordinary goal UUID; construction also allocates
                # an independent nonce for bounded safety-goal history.
                with patch("mhs.bridge.ros.uuid.uuid4", return_value=uuid.UUID(int=value)):
                    bridge.call(CAP, {"target": "home"})
                goals.append(ident(next(msg for msg in transport.sent if is_goal(msg))))
        self.assertNotEqual(goals[0], goals[1])
        self.assertEqual(goals, ["mhs-action-" + uuid.UUID(int=value).hex for value in (1, 2)])

    def test_stock_server_ignores_stale_and_unrelated_goal_ids(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                def handler(message):
                    if is_goal(message):
                        return [result(profile, "stale-id", values={"error_code": 0, "value": "wrong"}),
                                result(profile, ident(message))]
                _, client, _ = self.server(profile, handler)
                receipt = client.command(CAP, {"target": "home"})
                self.assertEqual(receipt["status"], "completed", receipt)
                self.assertEqual(receipt["output"], {"value": "done"})

    def test_ros1_status_or_unrelated_goal_result_is_not_completion(self):
        sent = threading.Event()
        goal_id = []
        def handler(message):
            if is_goal(message):
                goal_id.append(ident(message))
                sent.set()
                return [{"op": "publish", "topic": "/move/status", "msg": {"status_list": [
                    {"goal_id": {"id": goal_id[0]}, "status": 3}]}}, result("ros1-actionlib", "another-goal")]
        bridge, transport = self.bridge("ros1-actionlib", handler)
        thread, outcome = self.worker(lambda: bridge.call(CAP, {"target": "home"}))
        self.assertTrue(sent.wait(1))
        time.sleep(0.025)
        self.assertTrue(thread.is_alive())
        transport.feed(result("ros1-actionlib", goal_id[0]))
        thread.join(1)
        self.assertEqual(outcome, {"result": {"value": "done"}})

    def test_stock_operation_outlives_reply_deadline_and_wire_timeout(self):
        goal = []
        def handler(message):
            if is_goal(message):
                goal.append(message)
        driver, client, transport = self.server("ros2-native", handler)
        receipt = client.command(CAP, {"target": "home"}, deadline_ms=15)
        self.assertIn(receipt["status"], ("accepted", "running"), receipt)
        self.assertTrue(goal)
        time.sleep(0.075)  # exceeds timeout_s=50 ms; execution budget is still one second
        self.assertEqual(driver.inner._actions[ident(goal[0])].response, None)
        transport.feed(result("ros2-native", ident(goal[0])))
        self.wait_for(lambda: client.operation(receipt["operation_id"])["status"] == "completed")
        operation = client.operation(receipt["operation_id"])
        self.assertEqual(operation["status"], "completed", operation)
        self.assertEqual(len([m for m in transport.sent if is_goal(m)]), 1)

    def test_stock_cancellation_waits_for_exact_goal_terminal_and_independent_stop(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                goals = []
                def handler(message):
                    if is_goal(message):
                        goals.append(ident(message))
                    elif message["op"] == "call_service":
                        return service_response(message)
                    elif is_cancel(message):
                        self.assertEqual(message["id"], goals[0])
                        if profile == "ros1-actionlib":
                            self.assertEqual(message["msg"], {"id": goals[0], "stamp": {"secs": 0, "nsecs": 0}})
                        return result(profile, goals[0], 2 if profile == "ros1-actionlib" else 5)
                driver, client, transport = self.server(profile, handler)
                receipt = client.command(CAP, {"target": "home"}, deadline_ms=10)
                cancelled = client.rpc("mhs.operations.cancel", {"session_id": client.session_id,
                    "operation_id": receipt["operation_id"], "deadline_ms": 1000})
                self.assertEqual(cancelled["status"], "cancelled", cancelled)
                frames = transport.sent
                self.assertLess(next(i for i, m in enumerate(frames) if m.get("service") == "/stop"),
                                next(i for i, m in enumerate(frames) if is_cancel(m)))
                self.assertEqual(driver.inner._actions, {})

    def test_cancel_terminal_without_stop_confirmation_remains_unknown(self):
        cancelled = threading.Event()
        goal_id = []
        def handler(message):
            if is_goal(message):
                goal_id.append(ident(message))
                cancelled.set()
            if message["op"] == "call_service":
                return service_response(message, success=False)
            if is_cancel(message):
                return result("ros2-native", goal_id[0], 5)
        bridge, _ = self.bridge(handler=handler)
        with self.assertRaises(signals.OutcomeUnknown):
            bridge.call(CAP, {"target": "home"}, BridgeContext(cancel_event=cancelled))
        self.assertTrue(next(iter(bridge._actions.values())).abandoned)

    def test_completion_racing_cancel_retains_actual_success(self):
        cancelled = threading.Event()
        def handler(message):
            if is_goal(message):
                cancelled.set()
                return result("ros2-native", ident(message))
            if message["op"] == "call_service":
                return service_response(message)
        bridge, _ = self.bridge(handler=handler)
        self.assertEqual(bridge.call(CAP, {"target": "home"}, BridgeContext(cancel_event=cancelled)), {"value": "done"})

    def test_unknown_blocks_actuation_until_late_terminal_and_explicit_confirmed_reset(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                def handler(message):
                    if message["op"] == "call_service":
                        return service_response(message)
                bridge, transport = self.bridge(profile, handler)
                with self.assertRaises(signals.OutcomeUnknown):
                    bridge.call(CAP, {"target": "home"}, {"deadline_ms": 20})
                goal = next(m for m in transport.sent if is_goal(m))
                count = len(transport.sent)
                for fn in (lambda: bridge.call(CAP, {"target": "again"}), lambda: bridge.call(RESUME),
                           lambda: bridge.write("main", {"setting": 1}), bridge.reset):
                    with self.assertRaises(MHSError):
                        fn()
                self.assertEqual(len(transport.sent), count)
                self.assertEqual(bridge.call(READ), {})
                transport.feed(result(profile, ident(goal)))
                self.wait_for(lambda: next(iter(bridge._actions.values())).response is not None)
                with self.assertRaises(MHSError):
                    bridge.call(RESUME)  # late result alone does not release the block
                bridge.reset()
                self.assertEqual(bridge._actions, {})
                self.assertEqual(bridge.call(RESUME), {})
                self.assertEqual(len([m for m in transport.sent if is_goal(m)]), 1)

    def test_write_waiting_for_action_is_refused_when_action_becomes_unknown(self):
        goal_sent, write_waiting = threading.Event(), threading.Event()
        def handler(message):
            if is_goal(message):
                goal_sent.set()
            elif message["op"] == "call_service":
                return service_response(message)
        bridge, transport = self.bridge(handler=handler)
        action_thread, action_outcome = self.worker(lambda: bridge.call(CAP, {"target": "home"}))
        self.assertTrue(goal_sent.wait(1))
        acquire = bridge._acquire_transaction
        def observed_acquire(context, deadline, epoch):
            if context.command_id == "queued-write":
                write_waiting.set()
            return acquire(context, deadline, epoch)
        with patch.object(bridge, "_acquire_transaction", side_effect=observed_acquire):
            write_thread, write_outcome = self.worker(lambda: bridge.write("main", {"setting": 3},
                                                     BridgeContext(command_id="queued-write")))
            self.assertTrue(write_waiting.wait(1))
            goal = next(msg for msg in transport.sent if is_goal(msg))
            transport.feed({**result("ros2-native", ident(goal)), "status": 0})
            action_thread.join(1)
            write_thread.join(1)
        self.assertIsInstance(action_outcome.get("error"), signals.OutcomeUnknown)
        self.assertEqual(write_outcome["error"].code, "MHS.DEVICE.NOT_READY")
        self.assertFalse(any(msg.get("service") == "/set" for msg in transport.sent))

    def test_reset_rechecks_reconciliation_after_stop_or_reset_service_wait(self):
        for blocked_service in ("/stop", "/reset"):
            with self.subTest(service=blocked_service):
                cfg = config()
                cfg["timeout_s"] = 2
                cfg["safety_bindings"]["reset"] = {"service": "/reset", "type": "std_srvs/srv/Trigger",
                    "success": {"path": "success", "equals": True}}
                cancelled, waiting = threading.Event(), threading.Event()
                state = {"stopped": False, "hold": False}
                def handler(message):
                    if is_goal(message):
                        state["goal"] = ident(message)
                        cancelled.set()
                    elif is_cancel(message):
                        return result("ros2-native", state["goal"], 5)
                    elif message["op"] == "call_service":
                        if state["hold"] and message["service"] == blocked_service:
                            state["held"] = message
                            waiting.set()
                            return None
                        return service_response(message, state["stopped"] if message["service"] == "/stop" else True)
                bridge, transport = self.bridge(cfg=cfg, handler=handler)
                with self.assertRaises(signals.OutcomeUnknown):
                    bridge.call(CAP, {"target": "home"}, BridgeContext(cancel_event=cancelled))
                state.update(stopped=True, hold=True)
                thread, outcome = self.worker(bridge.reset)
                self.assertTrue(waiting.wait(1))
                transport.feed(result("ros2-native", state["goal"], 6))
                with bridge._condition:
                    self.assertTrue(bridge._condition.wait_for(
                        lambda: bridge._actions[state["goal"]].error is not None, timeout=1))
                transport.feed(service_response(state["held"]))
                thread.join(1)
                self.assertEqual(outcome["error"].code, "MHS.SAFETY.SAFE_STATE_UNREACHED")
                self.assertIn(state["goal"], bridge._actions)
                with self.assertRaises(MHSError):
                    bridge.call(RESUME)
                self.assertFalse(any(msg.get("service") == "/resume" for msg in transport.sent))

    def test_disconnect_after_goal_is_unknown_and_never_replayed(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                driver, client, _ = self.server(profile, lambda msg: None)
                # Use the server's own transport for the controlled disconnect.
                driver.native.handler = lambda msg: driver.native.close() if is_goal(msg) else None
                receipt = client.command(CAP, {"target": "home"})
                self.assertEqual(receipt["status"], "unknown", receipt)
                before = len(driver.native.sent)
                with self.assertRaises(MHSError):
                    driver.inner.reset()
                self.assertEqual(len(driver.native.sent), before)

    def test_stock_execution_budget_expiry_remains_unknown_without_cancel_confirmation(self):
        driver, client, transport = self.server("ros2-native", lambda msg: service_response(msg)
                                               if msg["op"] == "call_service" else None, max_duration_ms=30)
        receipt = client.command(CAP, {"target": "home"}, deadline_ms=1000)
        self.assertEqual(receipt["status"], "unknown", receipt)
        self.assertEqual(len([m for m in transport.sent if is_goal(m)]), 1)
        self.assertEqual(len([m for m in transport.sent if is_cancel(m)]), 1)
        self.assertTrue(next(iter(driver.inner._actions.values())).abandoned)

    def test_late_success_during_cancellation_grace_cannot_complete_expired_goal(self):
        goals = []
        def handler(message):
            if is_goal(message):
                goals.append(ident(message))
            elif message["op"] == "call_service":
                return service_response(message)
            elif is_cancel(message):
                return result("ros2-native", goals[0])  # success arrives only after the deadline
        bridge, _ = self.bridge(handler=handler)
        with self.assertRaises(signals.OutcomeUnknown):
            bridge.call(CAP, {"target": "home"}, {"deadline_ms": 15})
        self.assertTrue(next(iter(bridge._actions.values())).abandoned)

    def test_slow_goal_send_is_unknown_even_if_it_queues_a_success(self):
        def handler(message):
            if is_goal(message):
                time.sleep(0.06)  # exceeds the wire timeout, not the execution budget
                return result("ros2-native", ident(message))
        bridge, _ = self.bridge(handler=handler)
        with self.assertRaises(signals.OutcomeUnknown):
            bridge.call(CAP, {"target": "home"}, {"deadline_ms": 500})

    def test_estop_during_initial_prepare_prevents_goal_transmission(self):
        preparing, release = threading.Event(), threading.Event()
        class Delayed(RecordingRosTransport):
            def prepare(self, *, timeout_s):
                if threading.current_thread().name == "delayed-goal":
                    preparing.set()
                    release.wait(1)
        transport = Delayed(lambda msg: service_response(msg) if msg["op"] == "call_service" else None)
        bridge, _ = self.bridge(transport=transport)
        outcome = []
        def call():
            try:
                bridge.call(CAP, {"target": "home"})
            except BaseException as exc:
                outcome.append(exc)
        thread = threading.Thread(target=call, name="delayed-goal", daemon=True)
        thread.start()
        self.addCleanup(thread.join, 1)
        self.addCleanup(release.set)
        self.assertTrue(preparing.wait(1))
        self.assertFalse(bridge.estop()["safe_state_achieved"])
        release.set()
        thread.join(1)
        self.assertEqual(outcome[0].code, "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertFalse(any(is_goal(message) for message in transport.sent))
        self.assertTrue(bridge.safe_state()["achieved"])

    def test_empty_application_result_requires_explicit_empty_predicate(self):
        cfg = config()
        cfg["commands"][CAP]["success"] = {"path": "$", "equals": {}}
        cfg["commands"][CAP].pop("result")
        bridge, _ = self.bridge(cfg=cfg, handler=lambda msg: result("ros2-native", ident(msg), values={}) if is_goal(msg) else None)
        self.assertEqual(bridge.call(CAP, {"target": "home"}), {})

    def test_matching_wrong_profile_terminal_status_is_unknown(self):
        # ROS 2 CANCELING=3 is not ROS 1 SUCCEEDED=3. ROS 1 LOST is never terminal success.
        for profile, status in (("ros2-native", 3), ("ros1-actionlib", 9), ("ros1-actionlib", 6)):
            with self.subTest(profile=profile, status=status):
                bridge, _ = self.bridge(profile, lambda msg: result(profile, ident(msg), status) if is_goal(msg) else None)
                with self.assertRaises(signals.OutcomeUnknown):
                    bridge.call(CAP, {"target": "home"})

    def test_feedback_is_bounded_and_does_not_complete_or_extend_deadline(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                cfg = config(profile)
                cfg["commands"][CAP]["feedback"] = True
                bridge, transport = self.bridge(profile, cfg=cfg)
                thread, outcome = self.worker(lambda: bridge.call(CAP, {"target": "home"}, {"deadline_ms": 1000}))
                self.wait_for(lambda: any(is_goal(m) for m in transport.sent))
                goal_id = ident(next(m for m in transport.sent if is_goal(m)))
                for index in range(300):
                    feedback = ({"op": "action_feedback", "action": "/move", "id": goal_id, "values": {"count": index}}
                                if profile == "ros2-native" else {"op": "publish", "topic": "/move/feedback",
                                    "msg": {"status": {"goal_id": {"id": goal_id}, "status": 1}, "feedback": {"count": index}}})
                    transport.feed(feedback)
                self.wait_for(lambda: bridge._actions[goal_id].feedback_count == 300)
                self.assertEqual(bridge._actions[goal_id].feedback, {"count": 299})
                self.assertTrue(thread.is_alive())
                transport.feed(result(profile, goal_id))
                thread.join(1)
                self.assertEqual(outcome, {"result": {"value": "done"}})

    def test_estop_preempts_action_and_fences_queued_goal(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                sent = threading.Event()
                goal_ids = []
                def handler(message):
                    if is_goal(message):
                        goal_ids.append(ident(message))
                        sent.set()
                    elif message["op"] == "call_service":
                        return service_response(message)
                    elif is_cancel(message):
                        return result(profile, goal_ids[0], 2 if profile == "ros1-actionlib" else 5)
                bridge, transport = self.bridge(profile, handler)
                running, first = self.worker(lambda: bridge.call(CAP, {"target": "first"}))
                self.assertTrue(sent.wait(1))
                queued, second = self.worker(lambda: bridge.call(CAP, {"target": "queued"}))
                time.sleep(0.01)
                self.assertFalse(bridge.estop()["safe_state_achieved"])
                running.join(1)
                queued.join(1)
                self.assertIsInstance(first.get("error"), signals.Cancelled, first)
                self.assertEqual(second["error"].code, "MHS.SAFETY.ESTOP_ENGAGED")
                self.assertEqual(len(goal_ids), 1)
                self.assertTrue(bridge.safety_status()["safe_state"]["achieved"])
                self.assertLess(next(i for i, m in enumerate(transport.sent) if m.get("service") == "/stop"),
                                next(i for i, m in enumerate(transport.sent) if is_cancel(m)))

    def test_stock_estop_latches_while_action_is_running(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                goals = []
                def handler(message):
                    if is_goal(message):
                        goals.append(ident(message))
                    elif message["op"] == "call_service":
                        return service_response(message)
                    elif is_cancel(message):
                        return result(profile, goals[0], 2 if profile == "ros1-actionlib" else 5)
                _, client, transport = self.server(profile, handler)
                running = client.command(CAP, {"target": "home"}, deadline_ms=10)
                stopped = client.estop()
                self.assertEqual(stopped["output"]["estop"], "engaged", stopped)
                self.wait_for(lambda: client.operation(running["operation_id"])["status"] == "cancelled")
                refused = client.command(CAP, {"target": "again"})
                self.assertEqual(support.code(refused), "MHS.SAFETY.ESTOP_ENGAGED", refused)
                self.assertEqual(len([m for m in transport.sent if is_goal(m)]), 1)

    def test_cancelled_before_send_never_publishes_a_goal(self):
        cancelled = threading.Event()
        cancelled.set()
        bridge, transport = self.bridge()
        with self.assertRaises(signals.Cancelled):
            bridge.call(CAP, {"target": "home"}, BridgeContext(cancel_event=cancelled))
        self.assertEqual(transport.sent, [])


if __name__ == "__main__":
    unittest.main()
