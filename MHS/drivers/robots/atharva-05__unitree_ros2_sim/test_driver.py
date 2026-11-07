"""Acceptance run of the Unitree GO1 simulation package: the gate plus cases.

The cases exercise the pinned ROS 2 topic contract through the ROS-free fake:
the subscriptions and their shapes, the /cmd_vel publication, the sourced
model velocity envelope, the companion-cited stop (the Gazebo world pause
confirmed by the E1 stall read-back of get_model_list), its failure paths,
a reset that leaves the world paused, that the package offers no unpause, and
the declaration itself.  Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
ODOMETRY = "x-cap.atharva-05.odometry.v1"
CMD_VEL = "x-cap.atharva-05.cmd_vel.v1"
SLOW = {"linear_x": 0.1, "linear_y": 0.0, "angular_z": 0.2}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UnitreeRos2SimCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self):
        server = load(HERE, backend="fake")
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
        state = driver.call(ODOMETRY, {})
        self.assertEqual(state["pose"]["position"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(state["pose"]["orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        self.assertEqual(state["twist"]["linear"], {"x": 0.0, "y": 0.0, "z": 0.0})
        subscriptions = [message["topic"] for message in driver.native.sent
                         if message.get("op") == "subscribe"]
        self.assertIn("/odom", subscriptions)

    def test_cmd_vel_publication_maps_the_three_axes(self):
        driver = self.driver()
        receipt = driver.call("x-cap.atharva-05.cmd_vel.v1",
                              {"linear_x": 0.2, "linear_y": -0.1, "angular_z": -0.4})
        self.assertEqual(receipt, {"published": True, "confirmed": False, "sent_linear_x": 0.2,
                                   "sent_linear_y": -0.1, "sent_angular_z": -0.4})
        advertised = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(advertised[-1]["topic"], "/cmd_vel")
        self.assertEqual(advertised[-1]["type"], "geometry_msgs/msg/Twist")
        message = self.publishes(driver, "/cmd_vel")[-1]
        self.assertEqual(message["msg"]["linear"], {"x": 0.2, "y": -0.1, "z": 0.0})
        self.assertEqual(message["msg"]["angular"], {"x": 0.0, "y": 0.0, "z": -0.4})
        # The fake echoes the last publication as placeholder odometry, not physics.
        twist = driver.call(ODOMETRY, {})["twist"]
        self.assertEqual((twist["linear"]["x"], twist["linear"]["y"], twist["angular"]["z"]), (0.2, -0.1, -0.4))

    def test_scan_read_uses_the_declared_topic_and_shape(self):
        driver = self.driver()
        scan = driver.call("x-cap.atharva-05.scan.v1", {})
        self.assertEqual(set(scan), {"frame_id", "angle_min", "angle_max", "angle_increment",
                                     "time_increment", "scan_time", "range_min", "range_max",
                                     "ranges", "intensities"})
        self.assertEqual(len(scan["ranges"]), 3)  # placeholder array size, not the 450-sample device output
        subscriptions = {message["topic"] for message in driver.native.sent
                         if message.get("op") == "subscribe"}
        self.assertIn("/scan", subscriptions)

    def test_sourced_model_limits_admit_and_refuse_the_envelope(self):
        client = self.serve()
        ok = client.invoke("x-cap.atharva-05.cmd_vel.v1",
                           {"linear_x": 0.2, "linear_y": 0.1, "angular_z": 0.4}, **self.ids)
        self.assertEqual(ok["status"], "completed", ok)
        denied = client.invoke("x-cap.atharva-05.cmd_vel.v1",
                               {"linear_x": 0.41, "linear_y": 0.0, "angular_z": 0.0}, **self.ids)
        self.assertEqual(denied["status"], "rejected", denied)
        self.assertEqual(denied["error"]["mhs_code"], ENVELOPE)

    def served(self, **switches):
        driver = self.driver()
        for name, value in switches.items():
            setattr(driver.native, name, value)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    @staticmethod
    def services(native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    def test_the_e_stop_pauses_and_confirms_a_frozen_sim_time(self):
        driver, client = self.served()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.services(driver.native), ["/pause_physics", "/get_model_list", "/get_model_list"])
        refused = client.invoke(CMD_VEL, SLOW, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_running_world_or_a_failed_call_leaves_the_e_stop_unconfirmed_and_latched(self):
        for switch in ("ignore_pause", "fail_pause", "fail_model_list"):
            with self.subTest(switch=switch):
                _driver, client = self.served(**{switch: True})
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
                self.assertTrue(receipt["output"]["latched"], receipt)

    def test_the_sim_time_advances_while_the_world_runs(self):
        driver = self.driver()
        first = driver.native._service({"service": "/get_model_list", "id": "a"})["values"]["header"]["stamp"]
        second = driver.native._service({"service": "/get_model_list", "id": "b"})["values"]["header"]["stamp"]
        self.assertNotEqual(first, second)

    def test_the_reset_keeps_the_world_paused_and_offers_no_unpause(self):
        driver, client = self.served()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        receipt = client.invoke(CMD_VEL, SLOW, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)  # stored by move_base; acts after an unpause
        self.assertNotIn("/unpause_physics", self.services(driver.native))
        self.assertIsNone(driver._model.reenable)
        with self.assertRaises(MHSError):
            driver.call(ODOMETRY, {})  # the p3d plugin is silent while paused
        self.assertEqual(driver.read("main"), {})  # the resource reads no topic

    def test_malformed_odometry_is_not_silently_accepted(self):
        driver = self.driver()
        driver.native.malformed_odom = True
        with self.assertRaises(MHSError) as caught:
            driver.call(ODOMETRY, {})
        self.assertIn(caught.exception.code,
                      {"MHS.DEVICE.NOT_READY", "MHS.RESOURCE.STATE_INVALID", "MHS.CAPABILITY.OUTPUT_INVALID"})

    def test_malformed_scan_is_not_silently_accepted(self):
        driver = self.driver()
        driver.native.malformed_scan = True
        with self.assertRaises(Exception) as caught:  # noqa: BLE001 - the receipt must not be completed
            driver.call("x-cap.atharva-05.scan.v1", {})
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_a_nonfinite_scan_range_is_not_served_as_a_number(self):
        # Model review (2026-11-05): the bridge refuses non-finite numbers, so a scan with an inf or NaN
        # range yields no output rather than a fabricated finite range.
        for value in (float("inf"), float("nan")):
            driver = self.driver()
            driver.native.scan_ranges = [value, 2.0, 3.0]  # placeholder
            with self.assertRaises(MHSError) as caught:
                driver.call("x-cap.atharva-05.scan.v1", {})
            self.assertIn(caught.exception.code, {"MHS.OUTCOME.UNKNOWN", "MHS.CAPABILITY.OUTPUT_INVALID",
                                                  "MHS.DEVICE.NOT_READY"})

    def test_rejected_publication_is_not_reported_as_published(self):
        driver = self.driver()
        driver.native.reject_publish = True
        with self.assertRaises(Exception) as caught:  # noqa: BLE001 - the publication must not be completed
            driver.call("x-cap.atharva-05.cmd_vel.v1",
                        {"linear_x": 0.0, "linear_y": 0.0, "angular_z": 0.0})
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.OUTCOME.UNKNOWN")

    def test_declaration_is_a_simulated_ros2_mobile_base(self):
        driver = self.driver()
        self.assertEqual(type(driver).ros_version, 2)
        self.assertEqual(type(driver).mode, "simulated")
        self.assertEqual(type(driver).risk, "R2")
        self.assertEqual(type(driver).device_kind, "robot.mobile_base")
        self.assertEqual(type(driver).backends, {"fake": ".fake:FakeUnitreeRos2Sim"})
        self.assertEqual(type(driver).fidelity["fidelity_level"], "F0")


if __name__ == "__main__":
    unittest.main()
