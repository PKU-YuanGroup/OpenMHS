"""Acceptance run of the Astrobee ROS 1 package: the gate plus action-contract cases.

The cases exercise the upstream actionlib wrapper shapes, the application
success predicates, a failed application result, a malformed terminal result
and the independent gnc/control STOP used by the e-stop.  They are fake-only
contract checks; no ROS graph, simulator or hardware is contacted.
"""

import copy
import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import Cancelled, DriverFailed, OutcomeUnknown
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

#: Placeholder PoseStamped input for the fake-backed wire checks.
_STATE = {
    "pose": {
        "position": {"x": 1.0, "y": 2.0, "z": 3.0},
        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
    }
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AstrobeeCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.peer = server.devices[device_id].bridge.native
        return client

    def test_every_position_axis_requires_an_operator_overlay(self):
        client = self.serve()
        before = list(self.peer.goals)
        for value in (1.0, 1e12):
            state = copy.deepcopy(_STATE)
            state["pose"]["position"]["x"] = value
            receipt = client.invoke("x-cap.nasa.astrobee.move.v1", {"states": [state]}, **self.ids)
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(self.peer.goals, before, "no MOVE goal without the installed envelope")

    def test_example_overlay_allows_the_complete_pose_sequence(self):
        client = self.serve(HERE / "site-limits.example.json")
        second = copy.deepcopy(_STATE)
        second["pose"]["position"] = {"x": -1.0, "y": -2.0, "z": -3.0}
        states = [_STATE, second]
        receipt = client.invoke("x-cap.nasa.astrobee.move.v1", {"states": states}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        goals = [g for g in self.peer.goals if g["action"] == "/mob/motion"]
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["goal"]["states"], states)

    def test_each_nested_position_leaf_is_checked_in_later_array_elements(self):
        client = self.serve(HERE / "site-limits.example.json")
        before = list(self.peer.goals)
        for axis in ("x", "y", "z"):
            for value in (-4.01, 4.01, 1e12):
                with self.subTest(axis=axis, value=value):
                    second = copy.deepcopy(_STATE)
                    second["pose"]["position"][axis] = value
                    receipt = client.invoke("x-cap.nasa.astrobee.move.v1",
                                            {"states": [_STATE, second]}, **self.ids)
                    self.assertEqual(receipt["status"], "rejected", receipt)
                    self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
                    self.assertEqual(self.peer.goals, before, "no partial sequence may be sent")

    def test_move_sends_the_motion_action_goal(self) -> None:
        driver = self.driver()
        receipt = driver.call("x-cap.nasa.astrobee.move.v1", {"states": [_STATE]})
        self.assertEqual(receipt, {"response": 1,
                                   "fsm_result": "Motion completed successfully"})
        goal = [message for message in driver.native.sent
                if message.get("op") == "publish" and message.get("topic") == "/mob/motion/goal"][-1]
        self.assertEqual(goal["msg"]["goal"]["command"], 3)
        self.assertEqual(goal["msg"]["goal"]["states"], [_STATE])
        self.assertEqual(goal["msg"]["goal"].get("reference_frame", ""), "")

    def test_the_actionlib_wrappers_are_the_declared_types(self) -> None:
        driver = self.driver()
        driver.call("x-cap.nasa.astrobee.move.v1", {"states": [_STATE]})
        advertised = {message["topic"]: message["type"] for message in driver.native.sent
                      if message.get("op") == "advertise"}
        self.assertEqual(advertised["/mob/motion/goal"], "ff_msgs/MotionActionGoal")
        self.assertEqual(advertised["/mob/motion/cancel"], "actionlib_msgs/GoalID")
        subscribed = {message["topic"]: message["type"] for message in driver.native.sent
                      if message.get("op") == "subscribe"}
        self.assertEqual(subscribed["/mob/motion/result"], "ff_msgs/MotionActionResult")
        self.assertEqual(subscribed["/mob/motion/status"], "actionlib_msgs/GoalStatusArray")

    def test_stop_uses_the_gnc_control_stop_action(self) -> None:
        driver = self.driver()
        receipt = driver.call("x-cap.nasa.astrobee.stop.v1", {})
        self.assertEqual(receipt, {"stopped": True})
        goal = [message for message in driver.native.sent
                if message.get("op") == "publish" and message.get("topic") == "/gnc/control/goal"][-1]
        self.assertEqual(goal["msg"]["goal"], {"command": 0})
        self.assertTrue(driver.native.stopped)

    def test_segment_observation_changes_after_a_move(self) -> None:
        driver = self.driver()
        field = "commanded_segment_stamp_nsecs"
        before = driver.read("main", [field])[field]
        driver.call("x-cap.nasa.astrobee.move.v1", {"states": [_STATE]})
        after = driver.read("main", [field])[field]
        self.assertNotEqual(before, after)

    def test_failed_move_application_is_a_failed_receipt(self) -> None:
        driver = self.driver()
        driver.native.fail_move_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.nasa.astrobee.move.v1", {"states": [_STATE]})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_failed_stop_application_is_a_failed_receipt(self) -> None:
        driver = self.driver()
        driver.native.fail_stop_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.nasa.astrobee.stop.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_malformed_stop_result_is_an_unknown_outcome(self) -> None:
        driver = self.driver()
        driver.native.malformed_stop_result = True
        with self.assertRaises(OutcomeUnknown) as caught:
            driver.call("x-cap.nasa.astrobee.stop.v1", {})
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.UNKNOWN")

    def test_estop_uses_control_stop_and_latches_motion(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        refused = client.invoke("x-cap.nasa.astrobee.move.v1", {"states": [_STATE]}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_estop_failed_stop_application_is_not_reported_safe(self) -> None:
        driver = self.driver()
        driver.native.fail_stop_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.estop("test")
        self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_estop_malformed_stop_result_is_not_reported_safe(self) -> None:
        driver = self.driver()
        driver.native.malformed_stop_result = True
        with self.assertRaises(DriverFailed) as caught:
            driver.estop("test")
        self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_estop_cancels_a_held_move(self) -> None:
        driver = self.driver()
        driver.native.hold_moves = True
        outcome = {}

        def move() -> None:
            try:
                outcome["receipt"] = driver.call(
                    "x-cap.nasa.astrobee.move.v1", {"states": [_STATE]})
            except BaseException as exc:  # reported below
                outcome["error"] = exc

        worker = threading.Thread(target=move, name="astrobee-held-move", daemon=True)
        worker.start()
        deadline = time.monotonic() + 2.0
        while not driver.native.pending_moves and worker.is_alive() and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertTrue(driver.native.pending_moves, "the MOVE goal was not held")
        receipt = driver.estop("test")
        worker.join(2.0)
        self.assertFalse(worker.is_alive())
        self.assertEqual(receipt.get("estop"), "engaged", receipt)
        self.assertIsInstance(outcome.get("error"), Cancelled)

    def test_the_stop_path_is_a_fixed_action_not_a_motion_cancel(self) -> None:
        driver = self.driver()
        binding = type(driver).safety_bindings["estop"]
        self.assertEqual(binding["action"], "/gnc/control")
        self.assertEqual(binding["request"], {"command": 0})
        self.assertEqual(binding["success"], {"path": "response", "equals": 1})
        self.assertIsNone(type(driver).estop_physical_ref)
        self.assertEqual(type(driver).risk, "R2")


if __name__ == "__main__":
    unittest.main()
