"""Acceptance run of the Stage multi-robot exploration package: the gate plus cases.

The cases exercise the pinned rosbridge contract through the ROS-free fake:
the Clock, LaserScan, Odometry and PointArray observations, the two Twist
publications, the operator-required velocity envelope, the unbound
``reset_positions`` service and the sensed-confirmation stop.  Add cases,
never remove the ``check_driver`` call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
SAFE_UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
RESET_REFUSED = "MHS.SAFETY.RESET_REFUSED"


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StageExplorationCases(unittest.TestCase):
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
        return client

    @staticmethod
    def publishes(driver, topic):
        return [message for message in driver.native.sent
                if message.get("op") == "publish" and message.get("topic") == topic]

    def test_scan_observation_returns_the_declared_shape(self):
        driver = self.driver()
        scan = driver.call("x-cap.larics.scan_robot0.v1", {})
        self.assertEqual(set(scan), {"frame_id", "angle_min", "angle_max", "angle_increment",
                                     "range_min", "range_max", "ranges", "intensities"})
        self.assertEqual(len(scan["ranges"]), 1081)
        self.assertEqual(len(scan["intensities"]), 1081)
        subscriptions = [message["topic"] for message in driver.native.sent
                         if message.get("op") == "subscribe"]
        self.assertIn("/robot_0/base_scan", subscriptions)

    def test_odom_echoes_the_last_cmd_vel_publication(self):
        driver = self.driver()
        receipt = driver.call("x-cap.larics.cmd_vel_robot0.v1",
                              {"linear_velocity": 0.2, "angular_velocity": -0.4})
        self.assertEqual(receipt["published"], True)
        self.assertEqual(receipt["confirmed"], False)
        self.assertEqual(set(receipt), {"published", "confirmed"})
        advertised = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(advertised[-1]["topic"], "/robot_0/cmd_vel")
        self.assertEqual(advertised[-1]["type"], "geometry_msgs/Twist")
        message = self.publishes(driver, "/robot_0/cmd_vel")[-1]
        self.assertEqual(message["msg"]["linear"], {"x": 0.2, "y": 0.0, "z": 0.0})
        self.assertEqual(message["msg"]["angular"], {"x": 0.0, "y": 0.0, "z": -0.4})
        odom = driver.call("x-cap.larics.odom_robot0.v1", {})
        self.assertEqual(odom["linear_x"], 0.2)
        self.assertEqual(odom["angular_z"], -0.4)

    def test_resource_twist_is_the_stored_cmd_vel_echo(self):
        # TCAP-003 hashes resource "main".  The cmd_vel receipt cannot carry the
        # input (the SDK publish result is fixed), so the effect is this echo.
        driver = self.driver()
        before = driver.read("main")
        other = before["robot_1_twist"]
        driver.call("x-cap.larics.cmd_vel_robot0.v1",
                    {"linear_velocity": -0.5, "angular_velocity": 1.0})
        mid = driver.read("main")
        self.assertEqual(mid["robot_0_twist"]["linear"], {"x": -0.5, "y": 0.0, "z": 0.0})
        self.assertEqual(mid["robot_0_twist"]["angular"], {"x": 0.0, "y": 0.0, "z": 1.0})
        self.assertEqual(mid["robot_1_twist"], other)
        self.assertNotEqual(mid["robot_0_twist"], before["robot_0_twist"])
        driver.call("x-cap.larics.cmd_vel_robot0.v1",
                    {"linear_velocity": -0.5, "angular_velocity": 0.0})
        after = driver.read("main")
        self.assertEqual(after["robot_0_twist"]["angular"]["z"], 0.0)
        self.assertNotEqual(after["robot_0_twist"], mid["robot_0_twist"])
        self.assertEqual(after["robot_1_twist"], other)

    def test_clock_and_frontier_reads_use_the_declared_topics(self):
        driver = self.driver()
        clock = driver.call("x-cap.larics.sim_clock.v1", {})
        self.assertEqual(set(clock), {"secs", "nsecs"})
        frontiers = driver.call("x-cap.larics.frontiers.v1", {})
        self.assertTrue(frontiers["points"])
        self.assertEqual(set(frontiers["points"][0]), {"x", "y", "z"})
        subscriptions = {message["topic"] for message in driver.native.sent
                         if message.get("op") == "subscribe"}
        self.assertLessEqual({"/clock", "/filtered_frontiers"}, subscriptions)

    def test_operator_required_velocity_refuses_without_an_overlay(self):
        client = self.serve()
        refused = client.invoke("x-cap.larics.cmd_vel_robot0.v1",
                                {"linear_velocity": 0.2, "angular_velocity": 0.1}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], UNSET)

    def test_example_overlay_admits_an_in_envelope_velocity(self):
        overlay = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))
        client = self.serve(overlay)
        accepted = client.invoke("x-cap.larics.cmd_vel_robot1.v1",
                                 {"linear_velocity": 0.2, "angular_velocity": -0.3}, **self.ids)
        self.assertEqual(accepted["status"], "completed", accepted)
        denied = client.invoke("x-cap.larics.cmd_vel_robot1.v1",
                               {"linear_velocity": 0.6, "angular_velocity": 0.0}, **self.ids)
        self.assertEqual(denied["status"], "rejected", denied)
        self.assertEqual(denied["error"]["mhs_code"], ENVELOPE)

    def test_reset_positions_restores_poses_and_leaves_the_commanded_speed(self):
        driver = self.driver()
        native = driver.native
        native.poses["robot_0"] = [1.0, 2.0, 3.0]
        before = [list(item) for item in native.velocities.values()]
        native.send({"op": "call_service", "service": "/reset_positions", "id": "reset-ok"})
        accepted = native.recv(timeout_s=1.0)
        self.assertEqual(accepted["op"], "service_response")
        self.assertTrue(accepted["result"])
        self.assertEqual(accepted["values"], {})
        self.assertEqual(native.poses["robot_0"], native.initial_poses["robot_0"])
        self.assertEqual([list(item) for item in native.velocities.values()], before)
        self.assertNotEqual(native.velocities["robot_0"], [0.0, 0.0, 0.0])
        native.fail_reset_application = True
        native.send({"op": "call_service", "service": "/reset_positions", "id": "reset-rejected"})
        rejected = native.recv(timeout_s=1.0)
        self.assertEqual(rejected["result"], True)
        self.assertEqual(rejected["values"], {"rejected": True})

    def test_declaration_is_a_simulated_sensed_stop_at_risk_r2(self):
        driver = self.driver()
        cls = type(driver)
        self.assertEqual(cls.ros_version, 1)
        self.assertEqual(cls.mode, "simulated")
        self.assertEqual(cls.risk, "R2")
        self.assertEqual(cls.device_kind, "world.sim")
        self.assertEqual(cls.backends, {"fake": ".fake:FakeDecentralizedMultiRobotExploration"})
        self.assertEqual(cls.fidelity["fidelity_level"], "F0")
        self.assertEqual(cls.fidelity["reset"], "none")
        self.assertEqual(cls.estop_latency_ms, 3500)
        self.assertEqual(set(cls.parameters), {"robot_0_twist", "robot_1_twist"})
        self.assertEqual(set(cls.reads), {"robot_0_twist", "robot_1_twist"})
        self.assertEqual(cls.reads["robot_0_twist"]["path"], "twist.twist")
        self.assertFalse(any(field.writable for field in cls.parameters.values()))
        self.assertEqual(set(cls.safety_bindings), {"sensed_stop"})
        self.assertFalse(any(action.safe_state for action in cls.actions.values()))
        stop = cls.safety_bindings["sensed_stop"]
        self.assertEqual([step["topic"] for step in stop["request"]],
                         ["/robot_0/cmd_vel", "/robot_1/cmd_vel"])
        self.assertEqual(set(stop["sources"]), {"odom_0", "odom_1"})
        self.assertTrue(all("history" not in source for source in stop["sources"].values()))
        self.assertEqual([term["name"] for term in stop["predicate"]], [
            "r0_linear_x", "r0_linear_y", "r0_angular_z", "r0_x", "r0_y",
            "r1_linear_x", "r1_linear_y", "r1_angular_z", "r1_x", "r1_y",
        ])
        topics = [step["topic"] for step in stop["request"]]
        topics += [source["topic"] for source in stop["sources"].values()]
        self.assertFalse(any("robot_2" in topic for topic in topics))
        self.assertIsNone(cls.estop_physical_ref)
        for action in (cls.actions["x-cap.larics.cmd_vel_robot0.v1"],
                       cls.actions["x-cap.larics.cmd_vel_robot1.v1"]):
            self.assertEqual(action.risk, "R2")


class SensedStopCases(unittest.TestCase):
    """SAFE-049: the zero Twists prove nothing; only fresh odometry of both robots at rest achieves the stop."""

    def serve(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return driver, client

    def assert_unreached(self, receipt, reason):
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], SAFE_UNREACHED, receipt)
        self.assertEqual(details(receipt)["reason"], "bridge_reports_unsafe", receipt)
        self.assertEqual(details(receipt)["sensed"]["reason"], reason, receipt)
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertTrue(receipt["output"]["latched"])

    def test_the_estop_is_confirmed_by_fresh_odometry_of_both_robots(self):
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        sensed = receipt["x-vendor"]["sensed_confirmation"]
        self.assertEqual([(step["native"], step["outcome"]) for step in sensed["request"]],
                         [("/robot_0/cmd_vel", "published"), ("/robot_1/cmd_vel", "published")])
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        self.assertEqual(driver.native.velocities["robot_0"], [0.0, 0.0, 0.0])
        self.assertEqual(driver.native.velocities["robot_1"], [0.0, 0.0, 0.0])
        refused = client.invoke("x-cap.larics.cmd_vel_robot0.v1",
                                {"linear_velocity": 0.1, "angular_velocity": 0.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_reset_reconfirms_without_a_request(self):
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        sent = len(driver.native.sent)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertFalse(reset["output"]["resumed"])
        later = driver.native.sent[sent:]
        self.assertFalse([message for message in later if message.get("op") in ("publish", "call_service")])

    def test_a_reset_is_refused_while_another_publisher_commands_cmd_vel(self):
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        driver.native.competing = True
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], RESET_REFUSED, reset)

    def test_a_competing_publisher_keeps_the_stop_unconfirmed(self):
        driver, client = self.serve()
        driver.native.competing = True
        self.assert_unreached(client.estop("test", **self.ids), "not_confirmed")

    def test_one_robot_that_keeps_its_speed_fails_the_stop(self):
        driver, client = self.serve()
        driver.native.ignore_zero.add("robot_0")
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "not_confirmed")
        self.assertEqual(details(receipt)["sensed"]["sources"]["odom_0"].get("last_reset"), "term")
        self.assertEqual(driver.native.velocities["robot_0"], [0.4, 0.0, 0.0])
        self.assertEqual(driver.native.velocities["robot_1"], [0.0, 0.0, 0.0])

    def test_a_nonzero_twist_with_a_still_pose_is_not_at_rest(self):
        driver, client = self.serve()
        driver.native.apply_zero = False
        driver.native.hold_pose = True
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "not_confirmed")
        sources = details(receipt)["sensed"]["sources"]
        self.assertTrue(all(item.get("last_reset") == "term" for item in sources.values()), sources)

    def test_a_drifting_pose_at_zero_speed_is_not_at_rest(self):
        driver, client = self.serve()
        driver.native.drift_at_rest = True
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "not_confirmed")
        sources = details(receipt)["sensed"]["sources"]
        self.assertTrue(all(item.get("samples") == 3 and "last_reset" not in item
                            for item in sources.values()), sources)
        self.assertEqual(driver.native.velocities["robot_0"], [0.0, 0.0, 0.0])

    def test_the_watchdog_can_confirm_without_storing_the_zero_twist(self):
        driver, client = self.serve()
        driver.native.apply_zero = False
        driver.native.watchdog_rest = True
        before = {name: list(value) for name, value in driver.native.velocities.items()}
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual({name: list(value) for name, value in driver.native.velocities.items()}, before)
        self.assertNotEqual(before["robot_0"], [0.0, 0.0, 0.0])
        self.assertEqual(len(driver.native.cmd_vel_messages), 2)

    def test_silent_odometry_is_sensed_missing(self):
        driver, client = self.serve()
        driver.native.silent_odom = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_repeated_producer_stamp_is_stale(self):
        driver, client = self.serve()
        driver.native.frozen_stamps = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_stale")

    def test_a_null_linear_x_is_invalid(self):
        driver, client = self.serve()
        driver.native.null_linear_x = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_invalid")

    def test_a_rejected_publication_is_request_not_sent(self):
        driver, client = self.serve()
        driver.native.reject_publish = True
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "request_not_sent")
        self.assertEqual([step["outcome"] for step in details(receipt)["sensed"]["request"]],
                         ["not_sent", "not_sent"])


if __name__ == "__main__":
    unittest.main()
