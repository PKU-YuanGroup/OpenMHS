"""Acceptance run of the quadruped_ctrl ROS package: the gate, plus repository cases.

Add cases, never remove the check_driver call.  Neither the zero Twist nor the standing-gait request is a stop by
itself (model review of 2026-11-04).  A ROS 1 producer stamp is not a freshness proof, so the cases below
expect the zero Twist and standing-gait request to be sent and the confirmation refused.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
OVERLAY = HERE / "site-limits.example.json"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], ["G6", "G8"], report)


class QuadrupedCases(unittest.TestCase):
    def serve(self, *, overlay=None):
        server = load(HERE, backend="fake", site_limits=overlay)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_cmd_vel_is_published_with_the_upstream_channels(self) -> None:
        driver = self.driver()
        output = driver.call(
            "x-cap.derek-th-wang.cmd_vel.v1",
            {"linear_x": 0.2, "linear_y": -0.1, "yaw_rate": 0.3},
        )
        self.assertEqual(output, {"published": True, "confirmed": False})
        self.assertEqual(driver.native.last_cmd_vel, [0.2, -0.1, 0.3])
        published = [message for message in driver.native.sent if message.get("op") == "publish"]
        self.assertEqual(len(published), 1)
        twist = published[0]["msg"]
        self.assertEqual(twist["linear"]["x"], 0.2)
        self.assertEqual(twist["linear"]["y"], -0.1)
        self.assertEqual(twist["angular"]["x"], 0.3)

    def test_the_fake_resource_state_echoes_the_last_command_as_a_placeholder(self) -> None:
        driver = self.driver()
        driver.call(
            "x-cap.derek-th-wang.cmd_vel.v1",
            {"linear_x": 0.2, "linear_y": -0.1, "yaw_rate": 0.3},
        )
        state = driver.read("main")
        self.assertEqual(state["odom_x"], 0.2)
        self.assertEqual(state["odom_y"], -0.1)

    def test_gait_type_service_reaches_the_fake_and_returns_success(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.derek-th-wang.gait_type.v1", {"gait_type": 4})
        self.assertEqual(output["result"], 0)
        self.assertIn("gait", output["description"])
        self.assertEqual(driver.native.gait_type, 4)

    def test_robot_mode_service_reaches_the_fake(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.derek-th-wang.robot_mode.v1", {"robot_mode": 1})
        self.assertEqual(output["result"], 0)
        self.assertIn("mode", output["description"])
        self.assertEqual(driver.native.robot_mode, 1)

    def test_a_failed_gait_service_is_reported_as_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_gait_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.derek-th-wang.gait_type.v1", {"gait_type": 1})

    def test_a_rejected_gait_application_is_reported_as_failure(self) -> None:
        driver = self.driver()
        driver.native.reject_gait_application = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.derek-th-wang.gait_type.v1", {"gait_type": 1})

    def test_a_malformed_gait_response_is_an_unknown_outcome(self) -> None:
        driver = self.driver()
        driver.native.malformed_gait_response = True
        with self.assertRaises(OutcomeUnknown):
            driver.call("x-cap.derek-th-wang.gait_type.v1", {"gait_type": 1})

    def test_a_failed_robot_mode_service_is_reported_as_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_robot_mode_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.derek-th-wang.robot_mode.v1", {"robot_mode": 0})

    def test_the_stand_command_sends_the_fixed_standing_gait_request(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.derek-th-wang.stand.v1", {})
        self.assertEqual(output["result"], 0)
        self.assertEqual(driver.native.gait_type, 4)
        call = [message for message in driver.native.sent if message.get("op") == "call_service"][-1]
        self.assertEqual(call["args"], {"cmd": 4})

    def test_odometry_observation_returns_position_and_orientation(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.derek-th-wang.odometry.v1", {})
        self.assertEqual(set(output), {"position", "orientation"})
        self.assertEqual(set(output["position"]), {"x", "y", "z"})
        self.assertEqual(set(output["orientation"]), {"x", "y", "z", "w"})

    def test_imu_observation_returns_acceleration_rate_and_orientation(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.derek-th-wang.imu.v1", {})
        self.assertEqual(set(output), {"linear_acceleration", "angular_velocity", "orientation"})
        self.assertEqual(set(output["linear_acceleration"]), {"x", "y", "z"})
        self.assertEqual(set(output["angular_velocity"]), {"x", "y", "z"})

    def test_yaw_rate_requires_the_operator_overlay(self) -> None:
        client = self.serve()
        receipt = client.invoke(
            "x-cap.derek-th-wang.cmd_vel.v1",
            {"linear_x": 0.1, "linear_y": 0.0, "yaw_rate": 0.1},
            **self.ids,
        )
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_the_example_overlay_admits_a_bounded_yaw_rate(self) -> None:
        client = self.serve(overlay=OVERLAY)
        receipt = client.invoke(
            "x-cap.derek-th-wang.cmd_vel.v1",
            {"linear_x": 0.1, "linear_y": 0.0, "yaw_rate": 0.1},
            **self.ids,
        )
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})

    def test_the_declaration_is_a_sensed_stop_without_an_acknowledged_binding(self) -> None:
        cls = type(self.driver())
        self.assertEqual(set(cls.safety_bindings), {"sensed_stop"})
        self.assertFalse(any(action.safe_state for action in cls.actions.values()))
        terms = cls.safety_bindings["sensed_stop"]["predicate"]
        # The node never fills the odometry twist (walking_simulation.py:414-426): no term reads it.
        self.assertFalse([term for term in terms if "twist" in str(term.get("path", term.get("paths")))])


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


class SensedStopCases(unittest.TestCase):
    """SAFE-049: the requests prove nothing, and a ROS 1 producer stamp does not confirm the stop."""

    def serve(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=str(OVERLAY))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return driver, client

    def assert_unreached(self, receipt, reason):
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        self.assertEqual(details(receipt)["reason"], "bridge_reports_unsafe", receipt)
        self.assertEqual(details(receipt)["sensed"]["reason"], reason, receipt)
        self.assertFalse(receipt["output"]["safe_state_achieved"])

    def test_the_estop_request_is_sent_but_ros1_stamps_do_not_confirm(self) -> None:
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "sensed_missing")
        sensed = details(receipt)["sensed"]
        self.assertEqual([(step["native"], step["outcome"]) for step in sensed["request"]],
                         [("/cmd_vel", "published"), ("/gait_type", "succeeded")])
        self.assertEqual(driver.native.last_cmd_vel, [0.0, 0.0, 0.0])
        self.assertEqual(driver.native.gait_type, 4)
        refused = client.invoke("x-cap.derek-th-wang.gait_type.v1", {"gait_type": 1}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_in_robot_mode_zero_the_standing_gait_request_does_not_confirm(self) -> None:
        driver, client = self.serve()
        driver.native.robot_mode = 0
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")
        self.assertEqual(driver.native.gait_type, 4)

    def test_in_robot_mode_zero_a_refused_gait_request_is_never_confirmed(self) -> None:
        driver, client = self.serve()
        driver.native.robot_mode = 0
        driver.native.reject_gait_application = True
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "sensed_missing")
        self.assertEqual(details(receipt)["sensed"]["request"][1]["outcome"], "refused")

    def test_a_reset_cannot_reconfirm_from_ros1_stamps(self) -> None:
        driver, client = self.serve()
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED", reset)
        refused = client.invoke("x-cap.derek-th-wang.gait_type.v1", {"gait_type": 1}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_reset_is_refused_while_another_publisher_walks_the_robot(self) -> None:
        driver, client = self.serve()
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")
        driver.native.competing_cmd_vel = True
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED", reset)

    def test_a_competing_publisher_keeps_the_stop_unconfirmed(self) -> None:
        driver, client = self.serve()
        driver.native.competing_cmd_vel = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_collapsed_robot_is_not_standing(self) -> None:
        driver, client = self.serve()
        driver.native.collapsed = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_silent_sources_are_sensed_missing(self) -> None:
        driver, client = self.serve()
        driver.native.silent = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_repeated_producer_stamp_is_not_a_freshness_proof(self) -> None:
        driver, client = self.serve()
        driver.native.frozen_stamps = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_null_rate_is_not_counted_on_ros1(self) -> None:
        driver, client = self.serve()
        driver.native.null_rate = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")


if __name__ == "__main__":
    unittest.main()
