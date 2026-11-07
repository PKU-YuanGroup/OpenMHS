"""Acceptance run of the linorobot2 ROS 2 package: the gate plus specific cases.

The cases exercise the pinned Gazebo topic contract through the ROS-free fake: the read capabilities and their
shapes, the /cmd_vel publication and its receipt, the operator-required envelope, the companion-cited stop (the
gz-sim world pause confirmed by the E2 read-back of WorldStatistics.paused in fresh samples), its failure paths, the
topics a paused world does not publish, a reset that leaves the world paused, the declared resume (a zero Twist, then
the unpause), the operator bridges and the declaration itself. Add cases, never remove the ``check_driver`` call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
CMD_VEL = "x-cap.linorobot.cmd_vel.v1"
ODOMETRY = "x-cap.linorobot.odometry.v1"
RESUME = "x-cap.linorobot.resume.v1"
CONTROL = "/world/turtlebot3_world/control"
STATS = "/world/turtlebot3_world/stats"
SLOW = {"linear_velocity": 0.1, "angular_velocity": 0.2}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Linorobot2Cases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def served(self, site_limits=HERE / "site-limits.example.json", **switches):
        driver = self.driver()
        for name, value in switches.items():
            setattr(driver.native, name, value)
        server = build_server(driver, site_limits=site_limits)
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
    def wire(driver):
        return [(message.get("op"), message.get("service") or message.get("topic")) for message in driver.native.sent
                if message.get("op") in ("call_service", "subscribe", "unsubscribe", "publish")]

    def test_the_odometry_read_subscribes_and_returns_its_shape(self):
        driver = self.driver()
        state = driver.call(ODOMETRY, {})
        self.assertEqual(state["pose"]["position"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(state["pose"]["orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        self.assertEqual(state["twist"]["linear"], {"x": 0.0, "y": 0.0, "z": 0.0})
        subscriptions = [message["topic"] for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertIn("/odom/unfiltered", subscriptions)
        self.assertNotIn("/cmd_vel", subscriptions)
        self.assertEqual(driver.read("main"), {})  # the device resource reads no topic

    def test_cmd_vel_publication_maps_the_two_axes_and_reports_them(self):
        driver = self.driver()
        receipt = driver.call(CMD_VEL, {"linear_velocity": 0.2, "angular_velocity": -0.4})
        self.assertEqual(receipt, {"published": True, "confirmed": False, "sent_linear_velocity": 0.2,
                                   "sent_angular_velocity": -0.4})
        advertised = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual((advertised[-1]["topic"], advertised[-1]["type"]), ("/cmd_vel", "geometry_msgs/msg/Twist"))
        message = self.publishes(driver, "/cmd_vel")[-1]
        self.assertEqual(message["msg"]["linear"], {"x": 0.2, "y": 0.0, "z": 0.0})
        self.assertEqual(message["msg"]["angular"], {"x": 0.0, "y": 0.0, "z": -0.4})
        # The fake echoes the last publication as placeholder odometry, not physics.
        twist = driver.call(ODOMETRY, {})["twist"]
        self.assertEqual((twist["linear"]["x"], twist["angular"]["z"]), (0.2, -0.4))

    def test_clock_imu_and_scan_reads_use_the_declared_topics(self):
        driver = self.driver()
        clock = driver.call("x-cap.linorobot.clock.v1", {})
        self.assertEqual(set(clock["sim_time"]), {"sec", "nanosec"})
        imu = driver.call("x-cap.linorobot.imu.v1", {})
        self.assertEqual(set(imu), {"orientation", "angular_velocity", "linear_acceleration"})
        scan = driver.call("x-cap.linorobot.scan.v1", {})
        self.assertEqual(scan["frame_id"], "laser")
        self.assertLess(len(scan["ranges"]), 360)  # reduced placeholder array, not the 360-ray sensor
        subscriptions = {message["topic"] for message in driver.native.sent if message.get("op") == "subscribe"}
        self.assertLessEqual({"/clock", "/imu/data", "/scan"}, subscriptions)

    def test_operator_required_inputs_refuse_without_an_overlay(self):
        _driver, client = self.served(site_limits=None)
        receipt = client.invoke(CMD_VEL, SLOW, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_example_overlay_admits_and_narrows_the_envelope(self):
        _driver, client = self.served()
        ok = client.invoke(CMD_VEL, SLOW, **self.ids)
        self.assertEqual(ok["status"], "completed", ok)
        denied = client.invoke(CMD_VEL, {"linear_velocity": 1.0, "angular_velocity": 0.2}, **self.ids)
        self.assertEqual(denied["status"], "rejected", denied)
        self.assertEqual(denied["error"]["mhs_code"], ENVELOPE)

    def test_the_e_stop_pauses_the_world_and_confirms_it_from_fresh_statistics(self):
        driver, client = self.served()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(driver.native.controls, [{"pause": True}])
        self.assertTrue(driver.native.paused)
        self.assertEqual(self.wire(driver), [("call_service", CONTROL), ("subscribe", STATS), ("unsubscribe", STATS)])
        refused = client.invoke(CMD_VEL, SLOW, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_an_unanswered_or_failed_pause_a_running_world_or_no_statistics_leave_the_e_stop_unconfirmed(self):
        for switch in ("fail_control", "reject_control", "ignore_pause", "silent_stats"):
            with self.subTest(switch=switch):
                _driver, client = self.served(**{switch: True})
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
                self.assertFalse(receipt["output"]["safe_state_achieved"], receipt)
                self.assertTrue(receipt["output"]["latched"], receipt)

    def test_a_paused_world_publishes_no_odometry_and_the_device_stays_readable(self):
        driver, client = self.served()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.read("main"), {})
        with self.assertRaises(MHSError) as caught:
            driver.call(ODOMETRY, {})
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")
        self.assertEqual(set(driver.call("x-cap.linorobot.clock.v1", {})["sim_time"]), {"sec", "nanosec"})

    def test_the_resume_is_refused_while_latched_and_clears_the_stored_twist_after_the_reset(self):
        driver, client = self.served()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = client.invoke(RESUME, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)  # the reset releases the latch only; the world stays paused
        stored = client.invoke(CMD_VEL, SLOW, **self.ids)
        self.assertEqual(stored["status"], "completed", stored)  # stored by DiffDrive; acts after an unpause
        mark = len(driver.native.sent)
        resumed = client.invoke(RESUME, {}, **self.ids)
        self.assertEqual(resumed["status"], "completed", resumed)
        self.assertEqual(resumed["output"], {"acknowledged": True, "zero_command_published": True})
        tail = [message for message in driver.native.sent[mark:] if message.get("op") in ("publish", "call_service")]
        self.assertEqual([(message["op"], message.get("topic") or message.get("service")) for message in tail],
                         [("publish", "/cmd_vel"), ("call_service", CONTROL)])
        self.assertEqual(tail[0]["msg"]["linear"]["x"], 0.0)
        self.assertEqual(tail[0]["msg"]["angular"]["z"], 0.0)
        self.assertEqual(driver.native.controls[-1], {"pause": False})
        self.assertEqual(driver.native.pending_pause, False)  # applied at the next world step

    def test_malformed_odometry_is_not_silently_accepted(self):
        driver = self.driver()
        driver.native.malformed_odom = True
        with self.assertRaises(MHSError) as caught:
            driver.call(ODOMETRY, {})
        self.assertIn(caught.exception.code, {"MHS.DEVICE.NOT_READY", "MHS.CAPABILITY.OUTPUT_INVALID"})

    def test_declaration_is_a_simulated_ros2_mobile_base_with_operator_run_bridges(self):
        driver = self.driver()
        cls = type(driver)
        self.assertEqual((cls.ros_version, cls.mode, cls.risk, cls.device_kind), (2, "simulated", "R2",
                                                                                  "robot.mobile_base"))
        self.assertEqual(cls.backends, {"fake": ".fake:FakeLinorobot2"})
        self.assertEqual(cls.fidelity["fidelity_level"], "F0")
        self.assertEqual(cls.estop_latency_ms, 1500)
        self.assertEqual(driver._model.reenable, RESUME)
        self.assertEqual([item["args"].split("@")[0] for item in cls.operator_bridges], [CONTROL, STATS])
        reference = json.loads((HERE / "reference.json").read_text())
        self.assertEqual(len(reference["safety"]["operator_bridges"]), 2)
        self.assertIn("## Operator must run", (HERE / "REFERENCE.md").read_text())


if __name__ == "__main__":
    unittest.main()
