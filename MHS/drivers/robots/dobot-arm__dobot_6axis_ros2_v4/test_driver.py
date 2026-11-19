"""Acceptance run of the Dobot V4 ROS 2 package: the gate plus cases for this driver.

The cases run on the fake backend only; ``driver.native`` is the package's ROS-free recording
transport, so the service calls and subscriptions are exactly those the bridge sent.  Nothing here
contacted a ROS graph or an arm, and no case treats a service acknowledgement as a stopped-state
measurement.  Add cases, never remove the ``check_driver`` call.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import DriverFailed, build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

MOVJ = "/dobot_bringup_ros2/srv/MovJ"
MOVL = "/dobot_bringup_ros2/srv/MovL"
STOP = "/dobot_bringup_ros2/srv/Stop"
ENABLE = "/dobot_bringup_ros2/srv/EnableRobot"

#: Placeholder test inputs (rad, mm).
JOINTS = [0.1, -0.2, 0.3, 0.0, 0.4, -0.1]
POSITION = {"x": 400.0, "y": 0.0, "z": 300.0}
ORIENTATION = {"roll": 0.0, "pitch": math.pi / 2, "yaw": 0.0}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DobotCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, backend="fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self):
        self.served_driver = load_driver(HERE, backend="fake")
        server = build_server(self.served_driver, site_limits=OVERLAY)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    @staticmethod
    def calls(driver, service=None):
        found = [message for message in driver.native.sent
                 if message.get("op") == "call_service" and service in (None, message.get("service"))]
        return found

    # -- reads -------------------------------------------------------------------------------------
    def test_reads_come_from_the_pinned_feedback_topics(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(set(state), {"joint_positions", "tcp_pose", "enabled", "connected"})
        self.assertEqual(len(state["joint_positions"]), 6)
        self.assertEqual(state["enabled"], True)
        subscriptions = [message["topic"] for message in driver.native.sent
                         if message.get("op") == "subscribe"]
        self.assertIn("/joint_states", subscriptions)
        self.assertIn("/dobot_msgs_v4/msg/ToolVectorActual", subscriptions)
        self.assertIn("/dobot_msgs_v4/msg/RobotStatus", subscriptions)

    # -- motion ------------------------------------------------------------------------------------
    def test_move_joint_sends_movj_joint_mode_in_degrees(self) -> None:
        driver = self.driver()
        receipt = driver.call("x-cap.dobot-arm.move_joint.v1", {"joint_positions": JOINTS})
        self.assertIs(receipt["service_returned"], True)
        self.assertRegex(receipt["result_id"], r"^\{\d+\}$")
        call = self.calls(driver, MOVJ)[0]
        self.assertEqual(call["type"], "dobot_msgs_v4/srv/MovJ")
        args = call["args"]
        self.assertIs(args["mode"], True)
        self.assertEqual(args["param_value"], [])
        for got, value in zip((args["a"], args["b"], args["c"], args["d"], args["e"], args["f"]), JOINTS):
            self.assertAlmostEqual(got, math.degrees(value), places=9)

    def test_move_pose_sends_movl_pose_mode_with_radian_to_degree_orientation(self) -> None:
        driver = self.driver()
        receipt = driver.call("x-cap.dobot-arm.move_pose.v1",
                              {"position": POSITION, "orientation": ORIENTATION})
        self.assertIs(receipt["service_returned"], True)
        call = self.calls(driver, MOVL)[0]
        self.assertEqual(call["type"], "dobot_msgs_v4/srv/MovL")
        args = call["args"]
        self.assertIs(args["mode"], False)
        self.assertEqual((args["a"], args["b"], args["c"]), (400.0, 0.0, 300.0))
        self.assertAlmostEqual(args["d"], 0.0)
        self.assertAlmostEqual(args["e"], 90.0)
        self.assertAlmostEqual(args["f"], 0.0)

    # -- safety ------------------------------------------------------------------------------------
    def test_swallowed_dashboard_error_cannot_confirm_the_estop(self) -> None:
        client = self.serve()
        self.served_driver.native.dashboard_failure = True
        stopped = client.estop("upstream TCP error with default res=0", **self.ids)
        self.assertEqual((stopped["status"], stopped["error"]["mhs_code"]),
                         ("failed", "MHS.SAFETY.SAFE_STATE_UNREACHED"), stopped)
        self.assertFalse(self.served_driver.native.stopped)
        refused = client.invoke("x-cap.dobot-arm.move_joint.v1", {"joint_positions": JOINTS}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_stop_service_does_not_certify_an_estop(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.estop("package test"), {})
        self.assertFalse(type(driver).actions["x-cap.dobot-arm.stop.v1"].safe_state)
        self.assertEqual(self.calls(driver, STOP), [])

    def test_an_ordinary_stop_response_cannot_distinguish_a_dashboard_error(self) -> None:
        driver = self.driver()
        driver.native.dashboard_failure = True
        result = driver.call("x-cap.dobot-arm.stop.v1", {})
        self.assertEqual(result, {"service_returned": True})
        self.assertFalse(driver.native.stopped)

    def test_failed_stop_reply_is_not_an_acknowledgement(self) -> None:
        driver = self.driver()
        driver.native.fail_service = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.dobot-arm.stop.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_malformed_stop_reply_is_not_an_acknowledgement(self) -> None:
        driver = self.driver()
        driver.native.malformed_reply = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.dobot-arm.stop.v1", {})

    def test_enable_is_the_declared_re_enable_and_takes_no_input(self) -> None:
        driver = self.driver()
        action = type(driver).actions["x-cap.dobot-arm.enable.v1"]
        self.assertIs(action.reenable, True)
        receipt = driver.call("x-cap.dobot-arm.enable.v1", {})
        self.assertIs(receipt["service_returned"], True)
        call = self.calls(driver, ENABLE)[0]
        self.assertEqual(call["args"], {})

    # -- stock server ------------------------------------------------------------------------------
    def test_move_is_refused_while_latched_and_reset_releases_the_latch(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.dobot-arm.move_joint.v1",
                                {"joint_positions": JOINTS}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        stopped = client.estop("package test", **self.ids)
        self.assertEqual((stopped["status"], stopped["error"]["mhs_code"]),
                         ("failed", "MHS.SAFETY.SAFE_STATE_UNREACHED"), stopped)
        refused = client.invoke("x-cap.dobot-arm.move_joint.v1",
                                {"joint_positions": JOINTS}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        released = client.reset(**self.ids)
        self.assertEqual(released["status"], "completed", released)
        enabled = client.invoke("x-cap.dobot-arm.enable.v1", {}, **self.ids)
        self.assertEqual(enabled["status"], "completed", enabled)

    def test_nonzero_controller_code_is_a_failed_receipt_without_an_effect(self) -> None:
        client = self.serve()
        before = client.read("main", **self.ids)["state"]
        self.served_driver.native.fail_application = True
        refused = client.invoke("x-cap.dobot-arm.move_joint.v1", {"joint_positions": JOINTS}, **self.ids)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(client.read("main", **self.ids)["state"], before)


if __name__ == "__main__":
    unittest.main()
