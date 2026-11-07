"""Acceptance run of the Spot Gazebo ROS 2 simulation package.

The cases exercise the velocity publication and its receipt, the operator-required
envelope, the fresh observations, the companion-cited stop (the Ignition world
pause confirmed by the E2 read-back of WorldStatistics.paused in fresh samples),
its failure paths, the topics a paused world does and does not publish, a reset
that leaves the world paused with the last Twist still stored, the absence of
any unpause, and the operator bridges.

The gate's companion check needs ``MHS_DRIVER_GATE_COMPANIONS`` pointing at the
unit's companions-root (the LOCK.json whose needed_by includes this package).

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
VEL = "x-cap.justyx404.cmd_vel.v1"
ODOM = "x-cap.justyx404.odometry.v1"
JOINTS = "x-cap.justyx404.joint_states.v1"
CLOCK = "x-cap.justyx404.clock.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
CONTROL = "/world/simple_tunnel/control"
STATS = "/world/simple_tunnel/stats"
SLOW = {"linear_velocity": 0.1, "lateral_velocity": 0.0, "angular_velocity": 0.2}
#: The example operator overlay (the CHAMP gait caps copied as an example, not a device fact).
OVERLAY = HERE / "site-limits.example.json"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SpotCases(unittest.TestCase):
    def serve(self, overlay=False):
        server = load(HERE, backend="fake", site_limits=OVERLAY if overlay else None)
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

    def served(self, overlay=False, **switches):
        driver = self.open_driver()
        for name, value in switches.items():
            setattr(driver.native, name, value)
        server = build_server(driver, site_limits=OVERLAY if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def test_velocity_publication_reports_the_three_components_it_sent(self) -> None:
        driver = self.open_driver()
        output = driver.call(VEL, {"linear_velocity": 0.2, "lateral_velocity": -0.1, "angular_velocity": 0.4})
        self.assertEqual(output, {"published": True, "confirmed": False, "sent_linear_velocity": 0.2,
                                  "sent_lateral_velocity": -0.1, "sent_angular_velocity": 0.4})
        self.assertEqual(driver.read("main"), {})  # the device resource reads no topic
        self.assertEqual(len(driver.native.cmd_vel_messages), 1)
        message = driver.native.cmd_vel_messages[0]
        self.assertEqual(message["topic"], "/cmd_vel")
        self.assertEqual(message["msg"]["linear"]["x"], 0.2)
        self.assertEqual(message["msg"]["linear"]["y"], -0.1)
        self.assertEqual(message["msg"]["angular"]["z"], 0.4)
        advertised = [item for item in driver.native.sent
                      if item.get("op") == "advertise" and item.get("topic") == "/cmd_vel"]
        self.assertEqual(advertised[0]["type"], "geometry_msgs/msg/Twist")

    def test_a_velocity_is_refused_until_the_operator_supplies_the_envelope(self) -> None:
        client = self.serve()
        receipt = client.invoke(VEL, SLOW, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET, receipt)

    def test_the_velocity_publication_is_transmission_only(self) -> None:
        client = self.serve(overlay=True)
        receipt = client.invoke(VEL, SLOW, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["published"])
        self.assertFalse(receipt["output"]["confirmed"])
        self.assertEqual(receipt["output"]["sent_linear_velocity"], 0.1)
        self.assertEqual(receipt["output"]["sent_lateral_velocity"], 0.0)
        self.assertEqual(receipt["output"]["sent_angular_velocity"], 0.2)

    def test_out_of_envelope_velocities_are_refused(self) -> None:
        # The bounds are the example overlay's, not sourced device limits.
        client = self.serve(overlay=True)
        for payload in ({"linear_velocity": 1.6, "lateral_velocity": 0.0, "angular_velocity": 0.0},
                        {"linear_velocity": 0.0, "lateral_velocity": -0.3, "angular_velocity": 0.0},
                        {"linear_velocity": 0.0, "lateral_velocity": 0.0, "angular_velocity": 1.1}):
            receipt = client.invoke(VEL, payload, **self.ids)
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, receipt)

    def test_clock_joint_states_and_odometry_are_fresh_observations_while_running(self) -> None:
        driver = self.open_driver()
        clock = driver.call(CLOCK, {})
        self.assertEqual(set(clock["sim_time"]), {"sec", "nanosec"})
        self.assertEqual(clock["sim_time"]["sec"], 12)
        joints = driver.call(JOINTS, {})
        self.assertEqual(len(joints["names"]), 12)
        self.assertEqual(len(joints["positions"]), 12)
        odom = driver.call(ODOM, {})
        self.assertEqual(set(odom), {"position", "orientation", "twist"})
        self.assertEqual(set(odom["position"]), {"x", "y", "z"})

    def test_a_silent_odometry_topic_is_not_invented(self) -> None:
        driver = self.open_driver()
        driver.native.silent_topics.add("/spot/odometry")
        with self.assertRaises(MHSError) as caught:
            driver.call(ODOM, {})
        self.assertIn(caught.exception.code, {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})

    def test_a_rejected_publication_is_not_reported_completed(self) -> None:
        driver = self.open_driver()
        driver.native.reject_publish = True
        with self.assertRaises(MHSError) as caught:
            driver.call(VEL, SLOW)
        self.assertNotEqual(caught.exception.code, "MHS.DEVICE.FAULTED")
        self.assertEqual(driver.native.cmd_vel_messages, [])

    def test_the_e_stop_pauses_the_world_and_confirms_it_from_fresh_statistics(self) -> None:
        driver, client = self.served()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(driver.native.controls, [{"pause": True}])
        self.assertTrue(driver.native.paused)
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

    def test_a_paused_world_keeps_the_stored_twist_and_offers_no_unpause(self) -> None:
        # The stored command is the regression for a delayed /cmd_vel callback and a later controller tick:
        # estop and reset leave the last Twist in place and send no pause-false.
        driver, client = self.served(overlay=True)
        self.assertEqual(client.invoke(VEL, SLOW, **self.ids)["status"], "completed")
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.read("main"), {})
        self.assertEqual((driver.native.last_linear_velocity, driver.native.last_lateral_velocity,
                          driver.native.last_angular_velocity), (0.1, 0.0, 0.2))
        self.assertNotIn({"pause": False}, driver.native.controls)
        self.assertIsNone(driver._model.reenable)
        bindings = list(type(driver).commands.values()) + list(type(driver).safety_bindings.values())
        for binding in bindings:
            world = (binding.get("request") or {}).get("world_control") or {}
            self.assertIsNot(world.get("pause"), False)
        with self.assertRaises(MHSError) as caught:
            driver.call(ODOM, {})
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")
        # /clock and /spot/joint_states keep answering while paused.
        clock = driver.call(CLOCK, {})
        self.assertEqual(clock["sim_time"]["sec"], 12)
        joints = driver.call(JOINTS, {})
        self.assertEqual(len(joints["names"]), 12)
        # A later publication, after the latch is released, is still only a stored Twist.  The world stays paused.
        sent = client.invoke(VEL, {"linear_velocity": 0.0, "lateral_velocity": 0.0, "angular_velocity": 0.0},
                             **self.ids)
        self.assertEqual(sent["status"], "completed", sent)
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.native.controls[-1], {"pause": True})
        self.assertNotIn({"pause": False}, driver.native.controls)

    def test_the_declaration_names_the_operator_run_bridges(self) -> None:
        driver = self.open_driver()
        cls = type(driver)
        self.assertEqual([item["args"].split("@")[0] for item in cls.operator_bridges], [CONTROL, STATS])
        self.assertTrue(cls.operator_bridges[1]["args"].endswith("[ignition.msgs.WorldStatistics"))
        self.assertEqual(cls.estop_latency_ms, 1500)
        self.assertIsNone(driver._model.reenable)
        reference = json.loads((HERE / "reference.json").read_text())
        self.assertEqual(len(reference["safety"]["operator_bridges"]), 2)
        self.assertNotIn("reenable", reference["safety"])
        self.assertIn("## Operator must run", (HERE / "REFERENCE.md").read_text())
        self.assertIn("outside MHS", (HERE / "REFERENCE.md").read_text())


if __name__ == "__main__":
    unittest.main()
