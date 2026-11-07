"""Acceptance run of the TurtleBot3 fake-node package: the gate plus repository cases.

The cases exercise the declared topic contract through the ROS-free fake: the
subscriptions and their shapes, the /cmd_vel publication, the operator-required
velocity envelope, and the sensed-confirmation stop (SAFE-049, simulated only).
The zero Twist proves nothing; only fresh stamped /odom poses that stay still
within the bound achieve the e-stop.  A rosbridge publication is transmission
evidence only, never a motion or stop measurement.  Add cases, never remove the
``check_driver`` call.
"""

import json
import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CMD_VEL = "x-cap.robotis-git.turtlebot3_sim_cmd_vel.v1"
ODOMETRY = "x-cap.robotis-git.turtlebot3_sim_odometry.v1"
JOINT_STATES = "x-cap.robotis-git.turtlebot3_sim_joint_states.v1"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
_ODOM_QOS_REF = "turtlebot3_fake_node/src/turtlebot3_fake_node.cpp:40-43"
# Placeholder wheel geometry, the same constants fake.py uses to fill joint velocities.
_RADIUS = 0.033
_SEPARATION = 0.160


def example_overlay():
    return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


def _wheels(linear, angular=0.0):
    half = _SEPARATION / 2.0
    return [round((linear - angular * half) / _RADIUS, 9),
            round((linear + angular * half) / _RADIUS, 9)]


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


def _c_div(left, right):
    """C++ floating division: 0/0 and NaN are NaN, and a non-zero divided by 0 is signed inf."""
    if math.isnan(left) or math.isnan(right):
        return float("nan")
    if right == 0.0:
        if left == 0.0:
            return float("nan")
        return math.copysign(float("inf"), left)
    return left / right


def _fake_node_odom_step(pose, wheel_left, wheel_right, radius, separation, step_time):
    """Restate turtlebot3_fake_node.cpp:193-221. Not a device fact and not executed upstream."""
    w_left = _c_div(wheel_left, radius)     # cpp:194
    w_right = _c_div(wheel_right, radius)   # cpp:196
    inc_left = w_left * step_time           # cpp:201
    inc_right = w_right * step_time         # cpp:202
    if math.isnan(inc_left):                # cpp:204-206
        inc_left = 0.0
    if math.isnan(inc_right):               # cpp:208-210
        inc_right = 0.0
    delta_s = radius * (inc_right + inc_left) / 2.0                  # cpp:215
    delta_theta = _c_div(radius * (inc_right - inc_left), separation)  # cpp:216
    x, y, yaw = pose
    x = x + delta_s * math.cos(yaw + (delta_theta / 2.0))            # cpp:219
    y = y + delta_s * math.sin(yaw + (delta_theta / 2.0))            # cpp:220
    yaw = yaw + delta_theta                                           # cpp:221
    return (x, y, yaw), (w_left, w_right), (delta_s, delta_theta)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Turtlebot3SimulationCases(unittest.TestCase):
    def serve(self, *, overlay=True):
        server = load(HERE, backend="fake", site_limits=example_overlay() if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def direct(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver, driver.native

    def test_reads_expose_odometry_and_wheel_velocity(self) -> None:
        driver, fake = self.direct()
        state = driver.read("main")
        again = driver.read("main")
        pose = {
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        }
        twist = {
            "linear": {"x": 0.2, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
        }
        self.assertEqual(state["odom_pose"], pose)
        self.assertEqual(state["odom_twist"], twist)
        self.assertEqual(state["wheel_velocity"], _wheels(0.2))
        # A non-zero command is not stored, so a second read agrees with the first.
        self.assertEqual(again["odom_pose"], state["odom_pose"])
        self.assertEqual(again["odom_twist"], state["odom_twist"])
        self.assertEqual(again["wheel_velocity"], state["wheel_velocity"])
        topics = [message.get("topic") for message in fake.sent if message.get("op") == "subscribe"]
        self.assertIn("/odom", topics)
        self.assertIn("/joint_states", topics)

    def test_a_moving_burst_is_not_stored(self) -> None:
        _driver, fake = self.direct()
        samples = fake._respond({"op": "subscribe", "topic": "/odom", "id": "burst", "throttle_rate": 50})
        xs = [sample["msg"]["pose"]["pose"]["position"]["x"] for sample in samples]
        self.assertGreater(xs[-1] - xs[0], 0.01)
        self.assertEqual(fake.stored_x, 0.0)
        self.assertEqual(fake.stored_linear, 0.2)
        self.assertEqual(samples[0]["msg"]["twist"]["twist"]["linear"]["x"], 0.2)

    def test_odometry_observation_returns_pose_and_twist(self) -> None:
        driver, _fake = self.direct()
        receipt = driver.call(ODOMETRY, {})
        self.assertIn("position", receipt["pose"])
        self.assertIn("orientation", receipt["pose"])
        self.assertIn("linear", receipt["twist"])
        self.assertIn("angular", receipt["twist"])

    def test_joint_state_observation_returns_two_wheels(self) -> None:
        driver, _fake = self.direct()
        receipt = driver.call(JOINT_STATES, {})
        self.assertEqual(receipt["names"], ["wheel_left_joint", "wheel_right_joint"])
        self.assertEqual(len(receipt["positions"]), 2)
        self.assertEqual(len(receipt["velocities"]), 2)

    def test_cmd_vel_publication_reaches_the_topic_and_is_not_confirmed(self) -> None:
        driver, fake = self.direct()
        result = driver.call(CMD_VEL, {"linear_velocity": 0.2, "angular_velocity": 1.0})
        self.assertTrue(result["published"])
        self.assertFalse(result["confirmed"])
        self.assertEqual(fake.last_cmd_vel["linear"]["x"], 0.2)
        self.assertEqual(fake.last_cmd_vel["angular"]["z"], 1.0)
        self.assertIn({"op": "publish", "topic": "/cmd_vel"},
                      [{key: message.get(key) for key in ("op", "topic")} for message in fake.sent])
        # The non-zero command is recorded and does not replace the stored odom sample.
        state = driver.read("main")
        self.assertEqual(state["odom_pose"]["position"]["x"], 0.0)
        self.assertEqual(state["odom_twist"]["linear"]["x"], 0.2)
        self.assertEqual(state["wheel_velocity"], _wheels(0.2, 1.0))

    def test_cmd_vel_without_the_operator_overlay_is_refused(self) -> None:
        client = self.serve(overlay=False)
        receipt = client.invoke(CMD_VEL, {"linear_velocity": 0.0, "angular_velocity": 0.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_cmd_vel_with_the_example_overlay_is_enforced(self) -> None:
        client = self.serve()
        payload = {"linear_velocity": 0.05, "angular_velocity": 0.25}
        self.assertEqual(client.invoke(CMD_VEL, payload, **self.ids)["status"], "completed")
        for field, value in (("linear_velocity", 0.21), ("angular_velocity", 1.01)):
            denied = client.invoke(CMD_VEL, dict(payload, **{field: value}), **self.ids)
            self.assertEqual(denied["status"], "rejected", denied)
            self.assertEqual(denied["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_a_missing_odometry_field_is_reported_as_a_failure(self) -> None:
        driver, fake = self.direct()
        fake.omit_odom_twist = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(ODOMETRY, {})
        self.assertIn(caught.exception.code,
                      {"MHS.RESOURCE.STATE_INVALID", "MHS.CAPABILITY.OUTPUT_INVALID",
                       "MHS.DEVICE.NOT_READY"})

    def test_a_wrong_pose_shape_is_reported_as_a_failure(self) -> None:
        driver, fake = self.direct()
        fake.bad_pose_type = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(ODOMETRY, {})
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_the_observations_do_not_publish(self) -> None:
        driver, fake = self.direct()
        driver.call(ODOMETRY, {})
        driver.call(JOINT_STATES, {})
        self.assertFalse([message for message in fake.sent if message.get("op") == "publish"])

    def test_the_declaration_is_a_sensed_stop_at_r2(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        cls = type(driver)
        self.assertEqual(cls.ros_version, 2)
        self.assertEqual(cls.mode, "simulated")
        self.assertEqual(cls.device_kind, "world.sim")
        self.assertEqual(cls.risk, "R2")
        self.assertEqual(cls.estop_latency_ms, 3500)
        self.assertIsNone(cls.estop_physical_ref)
        self.assertEqual(set(cls.safety_bindings), {"sensed_stop"})
        stop = cls.safety_bindings["sensed_stop"]
        self.assertEqual(stop["request"][0]["topic"], "/cmd_vel")
        self.assertEqual(stop["request"][0]["source_name"], "cmd_vel")
        self.assertEqual(stop["request"][0]["message"]["linear"]["x"], 0.0)
        source = stop["sources"]["odom"]
        self.assertEqual(source["topic"], "/odom")
        self.assertEqual(source["throttle_ms"], 50)
        self.assertEqual(source["history"], {"durability": "volatile", "ref": _ODOM_QOS_REF})
        self.assertEqual({term["path"] for term in stop["predicate"]}, {
            "pose.pose.position.x", "pose.pose.position.y",
            "pose.pose.orientation.z", "pose.pose.orientation.w"})
        self.assertTrue(all("span_max" in term for term in stop["predicate"]))
        self.assertEqual(stop["consecutive"], 5)
        self.assertEqual(stop["min_span_ms"], 200)
        self.assertEqual(cls.actions[CMD_VEL].risk, "R2")
        self.assertNotIn("/reset", repr(cls.commands))
        self.assertEqual(cls.backends, {"fake": ".fake:FakeTurtlebot3Simulations"})


class SensedStopCases(unittest.TestCase):
    """SAFE-049: the zero Twist proves nothing; only a fresh still /odom pose achieves the stop."""

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
        self.assertTrue(details(receipt)["latched"], receipt)
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertTrue(receipt["output"]["latched"])

    def test_the_estop_publishes_a_zero_twist_and_is_confirmed_by_fresh_odometry(self) -> None:
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        self.assertTrue(receipt["output"]["latched"])
        sensed = receipt["x-vendor"]["sensed_confirmation"]
        self.assertEqual(sensed["request"], [{"native": "/cmd_vel", "kind": "topic", "outcome": "published"}])
        self.assertEqual(sensed["sources"]["odom"]["samples"], 5)
        zero = [message for message in driver.native.sent
                if message.get("op") == "publish" and message.get("topic") == "/cmd_vel"][-1]
        self.assertEqual(zero["msg"], {"linear": {"x": 0.0, "y": 0.0, "z": 0.0},
                                       "angular": {"x": 0.0, "y": 0.0, "z": 0.0}})
        throttled = [message for message in driver.native.sent
                     if message.get("op") == "subscribe" and message.get("topic") == "/odom"
                     and message.get("throttle_rate") == 50]
        self.assertEqual(len(throttled), 1)
        self.assertEqual(driver.native.stored_linear, 0.0)
        self.assertEqual(driver.native.goal_linear, 0.0)
        refused = client.invoke(CMD_VEL, {"linear_velocity": 0.1, "angular_velocity": 0.2}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_reset_reconfirms_without_a_request_and_resumes_nothing(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        published = len([message for message in driver.native.sent if message.get("op") == "publish"])
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertFalse(reset["output"]["resumed"])
        self.assertEqual(len([message for message in driver.native.sent if message.get("op") == "publish"]),
                         published)
        self.assertEqual(driver.native.stored_linear, 0.0)
        self.assertEqual(driver.native.goal_linear, 0.0)

    def test_a_reset_is_refused_while_another_publisher_moves_the_base(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        published = len([message for message in driver.native.sent if message.get("op") == "publish"])
        driver.native.competing_publisher = True
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED", reset)
        self.assertEqual(len([message for message in driver.native.sent if message.get("op") == "publish"]),
                         published)

    def test_a_competing_publisher_keeps_the_stop_unconfirmed(self) -> None:
        driver, client = self.serve()
        driver.native.competing_publisher = True
        self.assert_unreached(client.estop("test", **self.ids), "not_confirmed")

    def test_an_ignored_zero_twist_is_not_confirmed(self) -> None:
        driver, client = self.serve()
        driver.native.ignore_zero = True
        self.assert_unreached(client.estop("test", **self.ids), "not_confirmed")
        zero = [message for message in driver.native.sent
                if message.get("op") == "publish" and message.get("topic") == "/cmd_vel"][-1]
        self.assertEqual(zero["msg"]["linear"]["x"], 0.0)
        self.assertEqual(zero["msg"]["angular"]["z"], 0.0)
        self.assertEqual(driver.native.goal_linear, 0.2)

    def test_silent_odometry_is_sensed_missing(self) -> None:
        driver, client = self.serve()
        driver.native.silent_odom = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_repeated_producer_stamp_is_stale(self) -> None:
        driver, client = self.serve()
        driver.native.frozen_stamps = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_stale")

    def test_a_null_pose_field_is_invalid(self) -> None:
        driver, client = self.serve()
        driver.native.null_pose = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_invalid")

    def test_zero_radius_with_a_nonzero_separation_stays_finite_and_still_confirms(self) -> None:
        # cpp:142-145 with a zero Twist stores wheel speeds of 0. A 10 ms step is the node's timer.
        rested, wheels, delta = _fake_node_odom_step((0.0, 0.0, 0.0), 0.0, 0.0, 0.0, 0.160, 0.01)
        self.assertEqual(delta, (0.0, 0.0))
        self.assertTrue(all(math.isfinite(value) for value in rested))
        self.assertEqual(rested, (0.0, 0.0, 0.0))
        self.assertTrue(all(math.isnan(value) for value in wheels))
        both_defaults, _, both_delta = _fake_node_odom_step((0.0, 0.0, 0.0), 0.0, 0.0, 0.0, 0.0, 0.01)
        self.assertTrue(math.isnan(both_delta[1]))
        self.assertTrue(any(not math.isfinite(value) for value in both_defaults))
        driving, _, drive_delta = _fake_node_odom_step((0.0, 0.0, 0.0), 0.2, 0.2, 0.0, 0.160, 0.01)
        self.assertTrue(math.isnan(drive_delta[0]))
        self.assertTrue(any(not math.isfinite(value) for value in driving))
        driver, client = self.serve()
        driver.native.nan_wheel_velocity = True
        sample = driver.native._joint_message("probe")
        self.assertTrue(all(math.isnan(value) for value in sample["msg"]["velocity"]))
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(receipt["x-vendor"]["sensed_confirmation"]["sources"]["odom"]["samples"], 5)


if __name__ == "__main__":
    unittest.main()
