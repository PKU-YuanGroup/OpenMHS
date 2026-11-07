"""Acceptance run of the sdl-simulation package: the gate plus repository cases.

The cases exercise the pinned ROS 1 topic contract through the ROS-free fake:
the four publications and the sent-value receipts, the two status reads (still
answered while the paused flag is set), the operator-required envelope, the
companion world pause and its read-back, the three failure switches, a reset
that leaves the world paused, and that the package offers no unpause.  Add
cases, never remove the ``check_driver`` call.

``run_check`` applies ``MHS_DRIVER_GATE_COMPANIONS`` only on an inner run
(``mhs.driver.check``).  This file forwards the variable so a direct run uses
the same companions root as ``python3 -m mhs.driver check --companions-root``.
Unset, the default ``work/companions`` lock is used.
"""

import json
import os
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
ARM_GOAL = "x-cap.ad-sdl.arm_pose_goal.v1"
BASE_GOAL = "x-cap.ad-sdl.base_pose_goal.v1"
LEFT_GRIPPER = "x-cap.ad-sdl.left_gripper_position.v1"
RIGHT_GRIPPER = "x-cap.ad-sdl.right_gripper_position.v1"
ARM_STATUS = "x-cap.ad-sdl.arm_status.v1"
NAV_STATUS = "x-cap.ad-sdl.nav_status.v1"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"
ARM_POSE = {
    "x": 0.9, "y": -0.05, "z": 0.95,
    "qx": 0.0, "qy": 0.707, "qz": 0.0, "qw": 0.707,
}


def example_overlay():
    return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake",
                              companions_root=os.environ.get("MHS_DRIVER_GATE_COMPANIONS"))
        self.assertEqual(report["failed"], [], report)


class SdlSimulationCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self, *, overlay=True):
        server = load(HERE, backend="fake", site_limits=example_overlay() if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def serve_driver(self, *, overlay=True):
        driver = load_driver(HERE, "fake")
        server = build_server(driver, site_limits=example_overlay() if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    @staticmethod
    def publishes(driver, topic):
        return [message for message in driver.native.sent
                if message.get("op") == "publish" and message.get("topic") == topic]

    @staticmethod
    def services(native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    def test_declaration_is_a_simulated_ros1_mobile_manipulator_with_the_world_pause(self):
        driver = self.driver()
        self.assertEqual(type(driver).ros_version, 1)
        self.assertEqual(type(driver).mode, "simulated")
        self.assertEqual(type(driver).risk, "R2")
        self.assertEqual(type(driver).device_kind, "robot.arm")
        self.assertEqual(type(driver).backends, {"fake": ".fake:FakeSdlSimulation"})
        bindings = dict(type(driver).safety_bindings)
        self.assertEqual(set(bindings), {"estop", "safe_state"})
        self.assertEqual(bindings["estop"]["service"], PAUSE)
        self.assertEqual(bindings["safe_state"]["service"], READBACK)
        self.assertEqual(bindings["safe_state"]["success"], {"path": "pause", "equals": True})
        self.assertIsNone(type(driver).estop_physical_ref)
        self.assertEqual(type(driver).fidelity["fidelity_level"], "F0")
        self.assertEqual(driver.read("main"), {})

    def test_arm_goal_is_one_pose_publication_and_the_receipt_reports_it(self):
        driver = self.driver()
        receipt = driver.call(ARM_GOAL, dict(ARM_POSE))
        self.assertEqual(receipt["published"], True)
        self.assertEqual(receipt["confirmed"], False)
        self.assertEqual(receipt["sent"], ARM_POSE)
        other = driver.call(ARM_GOAL, {**ARM_POSE, "x": 0.4})
        self.assertNotEqual(other["sent"], receipt["sent"])
        self.assertEqual(other["sent"]["x"], 0.4)
        advertised = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(advertised[-1]["topic"], "/ur_arm/moveit/goal_pose")
        self.assertEqual(advertised[-1]["type"], "geometry_msgs/Pose")
        message = self.publishes(driver, "/ur_arm/moveit/goal_pose")[-1]
        self.assertEqual(message["msg"]["position"], {"x": 0.4, "y": -0.05, "z": 0.95})
        self.assertEqual(message["msg"]["orientation"], {"x": 0.0, "y": 0.707, "z": 0.0, "w": 0.707})
        self.assertEqual(driver.native.last_arm_goal["position"]["x"], 0.4)

    def test_base_goal_is_one_pose_stamped_publication(self):
        driver = self.driver()
        payload = {
            "frame_id": "map", "x": -2.6, "y": 0.87, "z": 0.0,
            "qx": 0.0, "qy": 0.0, "qz": 1.0, "qw": -0.00900788442947,
        }
        receipt = driver.call(BASE_GOAL, payload)
        self.assertEqual(receipt["published"], True)
        self.assertEqual(receipt["confirmed"], False)
        self.assertEqual(receipt["sent"]["frame_id"], "map")
        self.assertEqual(receipt["sent"]["x"], -2.6)
        message = self.publishes(driver, "/move_base_simple/goal")[-1]
        self.assertEqual(message["msg"]["header"]["frame_id"], "map")
        self.assertEqual(message["msg"]["pose"]["position"], {"x": -2.6, "y": 0.87, "z": 0.0})
        self.assertEqual(message["msg"]["pose"]["orientation"]["z"], 1.0)

    def test_gripper_commands_are_float64_publications(self):
        driver = self.driver()
        left = driver.call(LEFT_GRIPPER, {"position": 0.0})
        right = driver.call(RIGHT_GRIPPER, {"position": 1.5})
        self.assertEqual(left["sent"], {"position": 0.0})
        self.assertEqual(right["sent"], {"position": 1.5})
        self.assertFalse(left["confirmed"])
        self.assertFalse(right["confirmed"])
        self.assertEqual(driver.native.last_left_gripper, 0.0)
        self.assertEqual(driver.native.last_right_gripper, 1.5)
        self.assertEqual(self.publishes(driver, "/left_gripper_position_controller/command")[-1]["msg"],
                         {"data": 0.0})
        self.assertEqual(self.publishes(driver, "/right_gripper_position_controller/command")[-1]["msg"],
                         {"data": 1.5})

    def test_status_observations_subscribe_to_the_declared_topics(self):
        driver = self.driver()
        arm = driver.call(ARM_STATUS, {})
        nav = driver.call(NAV_STATUS, {})
        self.assertEqual(len(arm["statuses"]), 1)
        self.assertTrue(arm["statuses"][0]["goal_id"]["id"].startswith("placeholder-"))
        self.assertEqual(nav["statuses"][0]["status"], 3)
        subscriptions = {message["topic"] for message in driver.native.sent
                         if message.get("op") == "subscribe"}
        self.assertLessEqual({"/move_group/status", "/move_base/status"}, subscriptions)

    def test_status_reads_still_complete_while_the_world_is_paused(self):
        driver = self.driver()
        driver.native.paused = True
        arm = driver.call(ARM_STATUS, {})
        nav = driver.call(NAV_STATUS, {})
        self.assertEqual(len(arm["statuses"]), 1)
        self.assertEqual(nav["statuses"][0]["status"], 3)
        self.assertTrue(driver.native.paused)

    def test_the_operator_envelope_admits_and_refuses_the_example_bounds(self):
        client = self.serve()
        ok = client.invoke(ARM_GOAL, dict(ARM_POSE), **self.ids)
        self.assertEqual(ok["status"], "completed", ok)
        self.assertEqual(ok["output"]["sent"], ARM_POSE)
        for payload in (
            {"x": 3.0, "y": 0.0, "z": 0.5, "qx": 0.0, "qy": 0.0, "qz": 0.0, "qw": 1.0},
            {"x": 0.5, "y": 0.0, "z": 0.5, "qx": 2.0, "qy": 0.0, "qz": 0.0, "qw": 1.0},
        ):
            denied = client.invoke(ARM_GOAL, payload, **self.ids)
            self.assertEqual(denied["status"], "rejected", (payload, denied))
            self.assertEqual(denied["error"]["mhs_code"], ENVELOPE, (payload, denied))

    def test_operator_required_inputs_are_refused_without_an_overlay(self):
        client = self.serve(overlay=False)
        refused = client.invoke(ARM_GOAL, {
            "x": 0.5, "y": 0.0, "z": 0.5, "qx": 0.0, "qy": 0.0, "qz": 0.0, "qw": 1.0,
        }, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_estop_pauses_the_world_and_confirms_it_by_the_read_back(self):
        driver, client = self.serve_driver()
        self.assertFalse(driver.native.paused)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.services(driver.native), [PAUSE, READBACK])
        self.assertTrue(driver.native.paused)
        refused = client.invoke(ARM_GOAL, dict(ARM_POSE), **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_failed_pause_or_read_back_leaves_the_e_stop_unconfirmed_and_latched(self):
        for switch in ("fail_pause", "fail_readback", "ignore_pause"):
            with self.subTest(switch=switch):
                driver, client = self.serve_driver()
                setattr(driver.native, switch, True)
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
                refused = client.invoke(ARM_GOAL, dict(ARM_POSE), **self.ids)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
                if switch == "fail_pause":
                    self.assertFalse(driver.native.paused)
                else:
                    self.assertTrue(driver.native.paused)

    def test_the_reset_keeps_the_world_paused_and_the_package_offers_no_unpause(self):
        driver, client = self.serve_driver()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        receipt = client.invoke(ARM_GOAL, dict(ARM_POSE), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["sent"], ARM_POSE)
        self.assertTrue(driver.native.paused)
        self.assertNotIn("/gazebo/unpause_physics", self.services(driver.native))
        status = client.invoke(ARM_STATUS, {}, **self.ids)
        self.assertEqual(status["status"], "completed", status)
        self.assertIsNone(driver._model.reenable)
        for spec in type(driver).commands.values():
            self.assertNotIn("unpause", str(spec.get("service", "")))
        self.assertNotIn("unpause", type(driver).safety_bindings)

    def test_a_rejected_publication_is_not_reported_completed(self):
        driver = self.driver()
        driver.native.reject_publish = True
        with self.assertRaises(MHSError):
            driver.call(ARM_GOAL, {
                "x": 0.5, "y": 0.0, "z": 0.5, "qx": 0.0, "qy": 0.0, "qz": 0.0, "qw": 1.0,
            })
        self.assertIsNone(driver.native.last_arm_goal)

    def test_malformed_status_is_not_silently_accepted(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        server.devices[device_id].bridge.native.malformed_status = True
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke(ARM_STATUS, {}, device_id=device_id, session_id=session)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIsNone(receipt.get("output"))


if __name__ == "__main__":
    unittest.main()
