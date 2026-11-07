"""Acceptance run of the ros2-amr-simulation ROS 2 package: the gate plus cases.

The cases exercise the pinned Gazebo topic contract through the ROS-free fake:
the subscriptions and their shapes, the /cmd_vel publication, the
operator-required velocity envelope (both signs, and the refusal without an
overlay), the sensed-confirmation stop (SAFE-049, simulated devices only: the
zero Twist proves nothing; only fresh stamped /odom poses that stay still
within the bound achieve the e-stop) and the declaration itself.
Add cases, never remove the ``check_driver`` call.
"""

import json
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
CMD_VEL = "x-cap.karthik0497.cmd_vel.v1"


def example_overlay():
    return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Ros2AmrSimulationCases(unittest.TestCase):
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

    @staticmethod
    def publishes(driver, topic):
        return [message for message in driver.native.sent
                if message.get("op") == "publish" and message.get("topic") == topic]

    def test_reads_subscribe_to_odom_and_return_their_shapes(self):
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["pose"]["position"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(state["pose"]["orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        # The fake starts driving at a placeholder 0.3 m/s (nothing is at rest before a stop request).
        self.assertEqual(state["twist"]["linear"], {"x": 0.3, "y": 0.0, "z": 0.0})
        subscriptions = [message["topic"] for message in driver.native.sent
                         if message.get("op") == "subscribe"]
        self.assertIn("/odom", subscriptions)
        self.assertNotIn("/cmd_vel", subscriptions)

    def test_cmd_vel_publication_maps_only_the_two_twist_axes(self):
        driver = self.driver()
        receipt = driver.call("x-cap.karthik0497.cmd_vel.v1",
                              {"linear_velocity": 0.2, "angular_velocity": -0.4})
        self.assertEqual(receipt, {"published": True, "confirmed": False})
        advertised = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(advertised[-1]["topic"], "/cmd_vel")
        self.assertEqual(advertised[-1]["type"], "geometry_msgs/msg/Twist")
        message = self.publishes(driver, "/cmd_vel")[-1]
        self.assertEqual(message["msg"]["linear"], {"x": 0.2, "y": 0.0, "z": 0.0})
        self.assertEqual(message["msg"]["angular"], {"x": 0.0, "y": 0.0, "z": -0.4})
        # The fake echoes the last publication as placeholder odometry, not physics.
        self.assertEqual(driver.read("main", ["twist"])["twist"]["linear"]["x"], 0.2)
        self.assertEqual(driver.read("main", ["twist"])["twist"]["angular"]["z"], -0.4)

    def test_clock_and_joint_state_reads_use_the_declared_topics(self):
        driver = self.driver()
        clock = driver.call("x-cap.karthik0497.clock.v1", {})
        self.assertEqual(set(clock["sim_time"]), {"sec", "nanosec"})
        joints = driver.call("x-cap.karthik0497.joint_states.v1", {})
        self.assertEqual(set(joints), {"frame_id", "names", "positions", "velocities"})
        self.assertEqual(len(joints["names"]), len(joints["positions"]))
        subscriptions = {message["topic"] for message in driver.native.sent
                         if message.get("op") == "subscribe"}
        self.assertLessEqual({"/clock", "/joint_states"}, subscriptions)

    def test_the_operator_envelope_admits_and_refuses_both_signs(self):
        # The example overlay (-0.5..0.5 m/s, -1.0..1.0 rad/s) is operator data, not a source; the
        # point is that reverse and negative commands are bounded too (the former one-sided Limit was not).
        client = self.serve()
        ok = client.invoke(CMD_VEL, {"linear_velocity": 0.2, "angular_velocity": -0.4}, **self.ids)
        self.assertEqual(ok["status"], "completed", ok)
        for linear, angular in ((0.6, 0.0), (-0.6, 0.0), (0.0, -1.1), (-1000.0, 0.0)):
            denied = client.invoke(CMD_VEL, {"linear_velocity": linear, "angular_velocity": angular},
                                   **self.ids)
            self.assertEqual(denied["status"], "rejected", (linear, angular, denied))
            self.assertEqual(denied["error"]["mhs_code"], ENVELOPE, (linear, angular))

    def test_the_publication_is_refused_without_the_operator_overlay(self):
        client = self.serve(overlay=False)
        refused = client.invoke(CMD_VEL, {"linear_velocity": 0.1, "angular_velocity": 0.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_stop_is_a_sensed_confirmation_without_an_acknowledged_binding(self):
        driver = self.driver()
        self.assertEqual(set(type(driver).safety_bindings), {"sensed_stop"})
        self.assertIsNone(type(driver).estop_physical_ref)
        sources = type(driver).safety_bindings["sensed_stop"]["sources"]
        # /joint_states is never a source: display.launch.py also starts joint_state_publisher_gui on it.
        self.assertEqual({source["topic"] for source in sources.values()}, {"/odom"})

    def test_malformed_odometry_is_not_silently_accepted(self):
        driver = self.driver()
        driver.native.malformed_odom = True
        with self.assertRaises(MHSError) as caught:
            driver.read("main")
        self.assertIn(caught.exception.code,
                      {"MHS.DEVICE.NOT_READY", "MHS.RESOURCE.STATE_INVALID"})

    def test_declaration_is_a_simulated_ros2_mobile_base(self):
        driver = self.driver()
        self.assertEqual(type(driver).ros_version, 2)
        self.assertEqual(type(driver).mode, "simulated")
        self.assertEqual(type(driver).risk, "R2")
        self.assertEqual(type(driver).device_kind, "robot.mobile_base")
        self.assertEqual(type(driver).backends, {"fake": ".fake:FakeRos2AmrSimulation"})
        self.assertEqual(type(driver).fidelity["fidelity_level"], "F0")


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


class SensedStopCases(unittest.TestCase):
    """SAFE-049: the zero Twist proves nothing; only fresh stamped /odom poses that stay still achieve the stop."""

    def serve(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=example_overlay())
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

    def test_the_estop_publishes_a_zero_twist_and_is_confirmed_by_fresh_odometry(self):
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        sensed = receipt["x-vendor"]["sensed_confirmation"]
        self.assertEqual(sensed["request"], [{"native": "/cmd_vel", "kind": "topic", "outcome": "published"}])
        zero = [message for message in driver.native.sent
                if message.get("op") == "publish" and message.get("topic") == "/cmd_vel"][-1]
        self.assertEqual(zero["msg"], {"linear": {"x": 0.0, "y": 0.0, "z": 0.0},
                                       "angular": {"x": 0.0, "y": 0.0, "z": 0.0}})
        self.assertEqual(driver.native.linear, 0.0)
        refused = client.invoke(CMD_VEL, {"linear_velocity": 0.1, "angular_velocity": 0.2}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_reset_reconfirms_without_a_request_and_resumes_nothing(self):
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        published = len([message for message in driver.native.sent if message.get("op") == "publish"])
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertFalse(reset["output"]["resumed"])
        self.assertEqual(len([message for message in driver.native.sent if message.get("op") == "publish"]),
                         published)
        self.assertEqual(driver.native.linear, 0.0)

    def test_a_reset_is_refused_while_another_publisher_moves_the_base(self):
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        driver.native.competing_publisher = True        # amr_menu.py publishes its speed again
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED", reset)

    def test_a_competing_publisher_keeps_the_stop_unconfirmed(self):
        driver, client = self.serve()
        driver.native.competing_publisher = True
        self.assert_unreached(client.estop("test", **self.ids), "not_confirmed")

    def test_silent_odometry_is_sensed_missing(self):
        driver, client = self.serve()
        driver.native.silent_odom = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_repeated_producer_stamp_is_stale(self):
        driver, client = self.serve()
        driver.native.frozen_stamps = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_stale")

    def test_a_null_pose_field_is_invalid(self):
        driver, client = self.serve()
        driver.native.null_pose = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_invalid")


if __name__ == "__main__":
    unittest.main()
