"""Production Franka package tests against a raw, source-shaped ROS 1 peer.

These are F0 software contract tests. The numerical site limits below are
explicit test examples, not manufacturer limits or deployment approval.
The real package and stock MHSClient/Server are used; neither a package fake
factory, a hardware factory, ROS, nor libfranka is started.
"""

from __future__ import annotations

import copy
from pathlib import Path
import threading
import unittest

from mhs.adapter import load_driver
from mhs.bridge.ros_transport import RecordingRosTransport
from mhs.client import MHSClient
from mhs.driver import build_server, close_server
from mhs.errors import MHSError

HERE = Path(__file__).resolve().parent
GRASP = "cap.manipulation.grasp.v1"
MOVE = "x-cap.frankarobotics.move.v1"
HOME = "x-cap.frankarobotics.home.v1"
STOP = "x-cap.frankarobotics.stop.v1"
PREFIX = "/franka_gripper/"


def example_site_limits():
    width = {"min": 0.0, "max": 80.0, "unit": "mm", "source": "operator",
             "reason": "Test fixture example only; not a device specification"}
    return {"openmhs": "0.9", "site": "source-shaped-peer-test",
            "issued_by": {"id": "operator:test-fixture"}, "issued_at": "2026-11-02T00:00:00Z",
            "devices": {"mhs://localhost/franka_gripper": {
                GRASP: {"width": width, "force": {"min": 0.0, "max": 10.0, "unit": "N", "source": "operator"}},
                MOVE: {"width": width, "speed": {"min": 0.0, "max": 0.2, "unit": "m/s", "source": "operator"}},
            }}}


def result_for(goal, *, success=True, error="", status=3, values=None):
    return {"op": "publish", "topic": goal["topic"][:-5] + "/result", "msg": {
        "status": {"goal_id": {"id": goal["msg"]["goal_id"]["id"]}, "status": status},
        "result": {"success": success, "error": error} if values is None else values}}


class RawFrankaPeer:
    """No MHS output shaping; no native terminal result is inferred from cancel."""

    def __init__(self):
        self.hold = set()
        self.replies = {}
        self.goals = []
        self.cancels = []
        self.trace = []
        self.condition = threading.Condition()
        self.native_enabled = False
        self.transport = RecordingRosTransport(self.handle)

    @staticmethod
    def kind(message):
        return message["topic"][len(PREFIX):-5]

    def handle(self, message):
        if message.get("op") == "subscribe" and message.get("topic") == PREFIX + "joint_states":
            return {"op": "publish", "topic": message["topic"], "id": message["id"],
                    "msg": {"position": [0.02, 0.02]}}
        if message.get("op") != "publish":
            return None
        topic = message.get("topic", "")
        if topic.endswith("/cancel"):
            with self.condition:
                self.cancels.append(copy.deepcopy(message))
                self.trace.append("cancel:" + topic[len(PREFIX):-7])
                self.condition.notify_all()
            # The pinned execute callbacks do not implement a preempt handler.
            return None
        if not topic.endswith("/goal"):
            return None
        kind = self.kind(message)
        with self.condition:
            self.goals.append(copy.deepcopy(message))
            self.trace.append("accepted:" + kind)
            if kind == "stop":
                self.native_enabled = False
                self.trace.append("native:stop")
            elif kind not in self.hold:
                self.native_enabled = True
                self.trace.append("native:" + kind)
            self.condition.notify_all()
        if kind in self.hold:
            return None
        return result_for(message, **self.replies.get(kind, {}))

    def goals_of(self, kind):
        with self.condition:
            return [goal for goal in self.goals if self.kind(goal) == kind]

    def wait_goal(self, kind, count=1):
        with self.condition:
            if not self.condition.wait_for(lambda: len(self.goals_of(kind)) >= count, timeout=1):
                raise AssertionError(f"no {kind} goal {count}")
            return copy.deepcopy(self.goals_of(kind)[count - 1])

    def finish(self, goal, **reply):
        kind = self.kind(goal)
        with self.condition:
            if kind != "stop":
                self.native_enabled = True
            self.trace.append("native:" + kind)
            self.trace.append("terminal:" + kind)
        self.transport.feed(result_for(goal, **reply))


class ProductionSafetyTests(unittest.TestCase):
    def endpoint(self, peer, *, limits=True):
        driver = load_driver(HERE, "fake", native=peer.transport)
        server = build_server(driver, site_limits=example_site_limits() if limits else None)
        self.addCleanup(close_server, server)
        client = MHSClient(server)
        client.hello()
        device_id = next(iter(server.devices))
        client.open_session([device_id], mode="simulated",
                            principal={"id": "agent:production-test", "kind": "agent"})
        self.assertIs(driver.native, peer.transport)
        self.assertIs(driver.inner._transport, peer.transport)
        self.assertEqual(server.devices[device_id].mode, "simulated")
        self.assertEqual(server.devices[device_id].safety.risk_class, "R2")
        return driver, server, client, device_id

    def invoke(self, client, device_id, capability, payload=None, *, deadline_ms=1000):
        payload = copy.deepcopy(payload or {})
        permit_id = None
        if capability != STOP:
            permit = client.permit(capability, payload, device_id=device_id, resource="main")
            self.assertEqual(permit["capability_id"], capability)
            self.assertEqual(permit["resource"], "main")
            permit_id = permit["permit_id"]
        return client.invoke(capability, payload, device_id=device_id, resource="main",
                             permit_id=permit_id, deadline_ms=deadline_ms)

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
        self.assertNotIn("error", outcome)
        return outcome["result"]

    def reset_refused(self, client, device_id):
        try:
            receipt = client.reset(device_id)
        except MHSError:
            return
        self.assertNotEqual(receipt["status"], "completed", receipt)

    def test_move_uses_production_receipt_with_submitted_speed_after_native_success(self):
        peer = RawFrankaPeer()
        _, _, client, did = self.endpoint(peer)
        receipt = self.invoke(client, did, MOVE, {"width": 40.0, "speed": 0.125})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"success": True, "error": "", "requested_speed_m_s": 0.125})
        goal = peer.wait_goal("move")
        self.assertEqual(goal["msg"]["goal"], {"width": 0.04, "speed": 0.125})
        self.assertNotIn("requested_speed_m_s", result_for(goal)["msg"]["result"])
        self.assertFalse(peer.goals_of("homing"))

    def test_grasp_wire_units_and_false_native_success_are_preserved(self):
        for grasped in (True, False):
            with self.subTest(grasped=grasped):
                peer = RawFrankaPeer()
                peer.replies["grasp"] = {"status": 3, "success": grasped, "error": ""}
                _, _, client, did = self.endpoint(peer)
                receipt = self.invoke(client, did, GRASP, {"width": 30.0, "force": 5.0})
                self.assertEqual(receipt["status"], "completed", receipt)
                self.assertEqual(receipt["output"], {"grasped": grasped})
                self.assertEqual(peer.wait_goal("grasp")["msg"]["goal"], {
                    "width": 0.03, "force": 5.0, "speed": 0.1,
                    "epsilon": {"inner": 0.005, "outer": 0.005}})

    def test_homing_and_stop_use_distinct_fixed_goals(self):
        peer = RawFrankaPeer()
        driver, _, client, did = self.endpoint(peer)
        home = self.invoke(client, did, HOME)
        stop = self.invoke(client, did, STOP)
        self.assertEqual(home["status"], "completed", home)
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(home["output"], {"success": True, "error": ""})
        self.assertEqual(stop["output"], {"success": True, "error": ""})
        self.assertEqual([peer.kind(goal) for goal in peer.goals], ["homing", "stop"])
        self.assertTrue(all(goal["msg"]["goal"] == {} for goal in peer.goals))
        self.assertTrue(driver.inner.safety_status()["safe_state"]["achieved"])
        self.assertFalse(peer.native_enabled)

    def test_unsupported_approach_is_rejected_before_any_native_goal(self):
        peer = RawFrankaPeer()
        _, _, client, did = self.endpoint(peer)
        receipt = self.invoke(client, did, GRASP, {
            "width": 30.0, "force": 5.0, "approach": {"distance": 10.0}})
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        self.assertFalse(peer.goals)

    def test_example_site_envelope_is_required_and_enforced_pre_send(self):
        for limits, payload, code in (
            (False, {"width": 40.0, "speed": 0.1}, "MHS.SAFETY.LIMITS_UNSET"),
            (True, {"width": 40.0, "speed": 0.25}, "MHS.SAFETY.ENVELOPE_VIOLATION"),
        ):
            with self.subTest(limits=limits):
                peer = RawFrankaPeer()
                _, _, client, did = self.endpoint(peer, limits=limits)
                receipt = self.invoke(client, did, MOVE, payload)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], code)
                self.assertFalse(peer.goals)

    def test_failed_or_unknown_move_does_not_report_requested_speed_as_completion(self):
        for reply, expected in (({"success": False, "error": "native failed"}, "failed"),
                                ({"status": 9}, "unknown")):
            with self.subTest(reply=reply):
                peer = RawFrankaPeer()
                peer.replies["move"] = reply
                _, _, client, did = self.endpoint(peer)
                receipt = self.invoke(client, did, MOVE, {"width": 40.0, "speed": 0.075})
                self.assertEqual(receipt["status"], expected, receipt)
                self.assertNotIn("requested_speed_m_s", receipt.get("output") or {})
                self.assertEqual(peer.wait_goal("move")["msg"]["goal"]["speed"], 0.075)
                self.assertEqual(len(peer.goals_of("move")), 1)

    def test_independent_stop_dispatches_during_each_pending_native_action(self):
        for capability, kind, payload in ((MOVE, "move", {"width": 40.0, "speed": 0.1}),
                                         (GRASP, "grasp", {"width": 30.0, "force": 5.0}),
                                         (HOME, "homing", {})):
            with self.subTest(kind=kind):
                peer = RawFrankaPeer()
                peer.hold.add(kind)
                driver, _, client, did = self.endpoint(peer)
                thread, outcome = self.worker(lambda: self.invoke(client, did, capability, payload))
                goal = peer.wait_goal(kind)
                stopped = self.invoke(client, did, STOP)
                self.assertEqual(stopped["status"], "failed", stopped)
                self.assertEqual(len(peer.goals_of("stop")), 1)
                self.assertTrue(thread.is_alive(), outcome)
                self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
                peer.finish(goal)
                self.assertEqual(self.joined(thread, outcome)["status"], "completed")
                self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
                fresh = self.invoke(client, did, STOP)
                self.assertEqual(fresh["status"], "completed", fresh)
                self.assertTrue(driver.inner.safety_status()["safe_state"]["achieved"])
                self.assertEqual(len(peer.goals_of(kind)), 1)

    def test_stop_before_queued_native_move_stays_unknown_until_fresh_stop_and_reset(self):
        peer = RawFrankaPeer()
        peer.hold.add("move")
        driver, _, client, did = self.endpoint(peer)
        thread, outcome = self.worker(lambda: self.invoke(
            client, did, MOVE, {"width": 40.0, "speed": 0.1}, deadline_ms=1000))
        goal = peer.wait_goal("move")
        stopped = client.estop("source-shaped stop-before-native-start race", did, deadline_ms=500)
        self.assertFalse(stopped["output"]["safe_state_achieved"], stopped)
        self.assertFalse(peer.native_enabled)
        with peer.condition:
            self.assertTrue(peer.condition.wait_for(lambda: bool(peer.cancels), timeout=1))
        unknown = self.joined(thread, outcome)
        self.assertEqual(unknown["status"], "unknown", unknown)
        self.assertNotIn("requested_speed_m_s", unknown.get("output") or {})
        self.assertEqual(len(peer.goals_of("move")), 1)
        self.reset_refused(client, did)
        self.assertFalse(peer.goals_of("homing"))
        self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
        # The callback was queued before stop; it starts after stop and its
        # terminal arrives after the caller already received unknown.
        peer.finish(goal)
        with driver.inner._condition:
            self.assertTrue(driver.inner._condition.wait_for(
                lambda: driver.inner._actions[goal["msg"]["goal_id"]["id"]].response is not None, timeout=1))
        self.assertTrue(peer.native_enabled)
        self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
        refused = self.invoke(client, did, HOME)
        self.assertNotEqual(refused["status"], "completed", refused)
        self.assertFalse(peer.goals_of("homing"))
        count_before_fresh = len(peer.goals_of("stop"))
        fresh = self.invoke(client, did, STOP)
        self.assertEqual(fresh["status"], "completed", fresh)
        self.assertEqual(len(peer.goals_of("stop")), count_before_fresh + 1)
        self.assertFalse(peer.native_enabled)
        reset = client.reset(did)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertFalse(reset["output"]["resumed"])
        self.assertFalse(peer.native_enabled)
        self.assertFalse(peer.goals_of("homing"))
        self.assertEqual(len(peer.goals_of("move")), 1)
        self.assertTrue(all(frame["msg"]["id"] == goal["msg"]["goal_id"]["id"]
                            for frame in peer.cancels))
        self.assertLess(peer.trace.index("native:stop"), peer.trace.index("native:move"))
        self.assertIn("native:stop", peer.trace[peer.trace.index("terminal:move") + 1:])

    def test_stop_bad_terminal_status_and_malformed_output_fail_closed(self):
        cases = ({"status": 4}, {"status": 9}, {"success": False},
                 {"values": {"success": True}}, {"values": {"success": True, "error": 17}})
        for reply in cases:
            with self.subTest(reply=reply):
                peer = RawFrankaPeer()
                peer.replies["stop"] = reply
                driver, _, client, did = self.endpoint(peer)
                receipt = self.invoke(client, did, STOP)
                self.assertIn(receipt["status"], ("failed", "unknown"), receipt)
                self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
                self.assertEqual(len(peer.goals_of("stop")), 1)
                self.assertFalse(peer.cancels)
                self.assertFalse(peer.goals_of("homing"))


if __name__ == "__main__":
    unittest.main()
