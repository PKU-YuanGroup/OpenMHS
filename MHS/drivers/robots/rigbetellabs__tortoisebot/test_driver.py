"""Acceptance run of the TortoiseBot ROS 2 simulation package.

The cases exercise the velocity publication and its receipt, the sourced velocity caps, the fresh observations, the
companion-cited stop (the Ignition world pause confirmed by the E2 read-back of WorldStatistics.paused in fresh
samples), its failure paths, the topics a paused world does not publish, a reset that leaves the world paused, the
declared resume (a zero Twist, then the unpause) and the operator bridges.

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
VEL = "x-cap.rigbetellabs.vel.v1"
ODOM = "x-cap.rigbetellabs.odom.v1"
CLOCK = "x-cap.rigbetellabs.clock.v1"
SCAN = "x-cap.rigbetellabs.scan.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
RESUME = "x-cap.rigbetellabs.resume.v1"
CONTROL = "/world/default/control"
STATS = "/world/default/stats"
SLOW = {"linear_velocity": 0.1, "angular_velocity": 0.0}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TortoisebotCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def open_driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_velocity_publication_reaches_the_cmd_vel_topic(self) -> None:
        driver = self.open_driver()
        output = driver.call(VEL, {"linear_velocity": 0.2, "angular_velocity": -0.5})
        self.assertEqual(output, {"published": True, "confirmed": False, "sent_linear_velocity": 0.2,
                                  "sent_angular_velocity": -0.5})
        self.assertEqual(driver.read("main"), {})  # the device resource reads no topic
        self.assertEqual(len(driver.native.cmd_vel_messages), 1)
        message = driver.native.cmd_vel_messages[0]
        self.assertEqual(message["topic"], "/cmd_vel")
        self.assertEqual(message["msg"]["linear"]["x"], 0.2)
        self.assertEqual(message["msg"]["angular"]["z"], -0.5)
        advertised = [item for item in driver.native.sent
                      if item.get("op") == "advertise" and item.get("topic") == "/cmd_vel"]
        self.assertEqual(advertised[0]["type"], "geometry_msgs/msg/Twist")

    def test_velocity_outside_the_upstream_cap_is_refused_before_publication(self) -> None:
        client = self.serve()
        receipt = client.invoke(VEL, {"linear_velocity": 0.24, "angular_velocity": 0.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_clock_odometry_and_scan_are_fresh_observations(self) -> None:
        driver = self.open_driver()
        clock = driver.call(CLOCK, {})
        self.assertEqual(clock["sim_time"]["sec"], 12)
        first = driver.call(CLOCK, {})
        self.assertEqual(first["sim_time"]["sec"], 12)
        subscriptions = [item for item in driver.native.sent
                         if item.get("op") == "subscribe" and item.get("topic") == "/clock"]
        self.assertEqual(len(subscriptions), 2)
        odom = driver.call(ODOM, {})
        self.assertEqual(set(odom), {"x", "y", "linear_velocity", "angular_velocity"})
        scan = driver.call(SCAN, {})
        self.assertEqual(scan["frame_id"], "lidar")
        self.assertEqual(len(scan["ranges"]), 8)

    def test_a_silent_odometry_topic_is_not_invented(self) -> None:
        driver = self.open_driver()
        driver.native.silent_topics.add("/odom")
        with self.assertRaises(MHSError) as caught:
            driver.call(ODOM, {})
        self.assertIn(caught.exception.code, {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})

    def test_malformed_odometry_is_refused(self) -> None:
        driver = self.open_driver()
        driver.native.malformed_odom = True
        with self.assertRaises(MHSError) as caught:
            driver.call(ODOM, {})
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_a_rejected_publication_is_not_reported_completed(self) -> None:
        driver = self.open_driver()
        driver.native.reject_publish = True
        with self.assertRaises(MHSError) as caught:
            driver.call(VEL, {"linear_velocity": 0.1, "angular_velocity": 0.0})
        self.assertNotEqual(caught.exception.code, "MHS.DEVICE.FAULTED")
        self.assertEqual(driver.native.cmd_vel_messages, [])

    def test_a_nonfinite_scan_range_is_not_served_as_a_number(self) -> None:
        # Model review (2026-11-05): the bridge refuses non-finite numbers, so a scan with an inf or NaN
        # range yields no output rather than a fabricated finite range.
        for value in (float("inf"), float("nan")):
            driver = self.open_driver()
            driver.native.scan_ranges = [value] + list(driver.native.scan_ranges[1:])  # placeholder
            with self.assertRaises(MHSError) as caught:
                driver.call(SCAN, {})
            self.assertIn(caught.exception.code, {"MHS.OUTCOME.UNKNOWN", "MHS.CAPABILITY.OUTPUT_INVALID",
                                                  "MHS.DEVICE.NOT_READY"})

    def served(self, **switches):
        driver = self.open_driver()
        for name, value in switches.items():
            setattr(driver.native, name, value)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def test_the_e_stop_pauses_the_world_and_confirms_it_from_fresh_statistics(self) -> None:
        driver, client = self.served()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(driver.native.controls, [{"pause": True}])
        wire = [(item.get("op"), item.get("service") or item.get("topic")) for item in driver.native.sent
                if item.get("op") in ("call_service", "subscribe", "unsubscribe")]
        self.assertEqual(wire, [("call_service", CONTROL), ("subscribe", STATS), ("unsubscribe", STATS)])
        refused = client.invoke(VEL, SLOW, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_an_unanswered_or_failed_pause_a_running_world_or_no_statistics_leave_the_e_stop_unconfirmed(self):
        for switch in ("fail_control", "reject_control", "ignore_pause", "silent_stats"):
            with self.subTest(switch=switch):
                _driver, client = self.served(**{switch: True})
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
                self.assertTrue(receipt["output"]["latched"], receipt)

    def test_a_paused_world_publishes_no_odometry_and_the_resume_clears_the_stored_twist(self) -> None:
        driver, client = self.served()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = client.invoke(RESUME, {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.read("main"), {})
        with self.assertRaises(MHSError) as caught:
            driver.call(ODOM, {})
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")
        self.assertEqual(client.invoke(VEL, SLOW, **self.ids)["status"], "completed")  # stored for an unpause
        mark = len(driver.native.sent)
        resumed = client.invoke(RESUME, {}, **self.ids)
        self.assertEqual(resumed["status"], "completed", resumed)
        self.assertEqual(resumed["output"], {"acknowledged": True, "zero_command_published": True})
        tail = [item for item in driver.native.sent[mark:] if item.get("op") in ("publish", "call_service")]
        self.assertEqual([(item["op"], item.get("topic") or item.get("service")) for item in tail],
                         [("publish", "/cmd_vel"), ("call_service", CONTROL)])
        self.assertEqual((tail[0]["msg"]["linear"]["x"], tail[0]["msg"]["angular"]["z"]), (0.0, 0.0))
        self.assertEqual(driver.native.controls[-1], {"pause": False})

    def test_the_declaration_names_the_operator_run_bridges(self) -> None:
        driver = self.open_driver()
        cls = type(driver)
        self.assertEqual([item["args"].split("@")[0] for item in cls.operator_bridges], [CONTROL, STATS])
        self.assertTrue(cls.operator_bridges[1]["args"].endswith("[ignition.msgs.WorldStatistics"))
        self.assertEqual((cls.estop_latency_ms, driver._model.reenable), (1500, RESUME))
        reference = json.loads((HERE / "reference.json").read_text())
        self.assertEqual(len(reference["safety"]["operator_bridges"]), 2)
        self.assertIn("## Operator must run", (HERE / "REFERENCE.md").read_text())


if __name__ == "__main__":
    unittest.main()
