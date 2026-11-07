"""Repository cases for the CrazyS package, plus the required gate run.

The gate test is kept as generated; the other cases exercise the pinned
Crazyflie command publication and odometry observation, the companion-cited
stop (the Gazebo world pause confirmed by the get_physics_properties
read-back), its failure paths, the latch, a reset that leaves the world paused,
and that the package offers no unpause.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown, build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP_UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
ESTOP_ENGAGED = "MHS.SAFETY.ESTOP_ENGAGED"
COMMAND = "x-cap.gsilano.attitude_thrust.v1"
ODOMETRY = "x-cap.gsilano.odometry.v1"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"
SMALL = {"roll": 0.05, "pitch": 0.0, "yaw_rate": 0.0, "thrust": 100.0}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CrazysCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_odometry_observation_returns_a_sample(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.gsilano.odometry.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(set(output["position"]), {"x", "y", "z"})
        self.assertEqual(set(output["orientation"]), {"x", "y", "z", "w"})
        self.assertIn("frame_id", output)

    def test_command_publication_reaches_the_transport(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call("x-cap.gsilano.attitude_thrust.v1",
                             {"roll": 0.1, "pitch": -0.2, "yaw_rate": 0.3, "thrust": 0.4})
        self.assertEqual(output, {"published": True, "confirmed": False, "sent_roll": 0.1, "sent_pitch": -0.2,
                                  "sent_yaw_rate": 0.3, "sent_thrust": 0.4})
        self.assertEqual(driver.native.command,
                         {"roll": 0.1, "pitch": -0.2, "yaw_rate": 0.3, "thrust": 0.4})
        publishes = [message for message in driver.native.sent if message.get("op") == "publish"]
        self.assertEqual(len(publishes), 1)
        self.assertEqual(publishes[0]["topic"], "/crazyflie2/command/roll_pitch_yawrate_thrust")
        self.assertEqual(publishes[0]["msg"]["roll"], 0.1)
        advertises = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(advertises[0]["type"], "mav_msgs/RollPitchYawrateThrustCrazyflie")

    def test_odometry_subscription_uses_the_declared_topic_and_type(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call("x-cap.gsilano.odometry.v1", {})
        self.assertEqual(output["position"]["z"], 1.0)
        subscriptions = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual(subscriptions[0]["topic"], "/crazyflie2/odometry_sensor1/odometry")
        self.assertEqual(subscriptions[0]["type"], "nav_msgs/Odometry")

    def test_silent_odometry_topic_is_not_a_fresh_sample(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.silent_odometry = True
        with self.assertRaises(MHSError) as caught:
            driver.call("x-cap.gsilano.odometry.v1", {})
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")

    def test_failed_command_transport_is_not_a_success(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_publish = True
        with self.assertRaises((DriverFailed, OutcomeUnknown)) as caught:
            driver.call("x-cap.gsilano.attitude_thrust.v1",
                        {"roll": 0.0, "pitch": 0.0, "yaw_rate": 0.0, "thrust": 0.0})
        self.assertIn(caught.exception.code,
                      {"MHS.OUTCOME.UNKNOWN", "MHS.DEVICE.NOT_READY", "MHS.ADAPTER.SHIM_FAILED"})

    def test_a_command_is_refused_until_an_operator_envelope_exists(self) -> None:
        # Model review 2026-11-05: the clone states no bound, so the inputs are operator_required.
        client = self.serve()
        receipt = client.invoke(COMMAND, {"roll": 0.0, "pitch": 0.0, "yaw_rate": 0.0, "thrust": 0.0},
                                **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")

    def test_the_example_overlay_admits_and_bounds_a_command(self) -> None:
        overlay = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))
        client = self.serve(site_limits=overlay)
        inside = client.invoke(COMMAND, {"roll": 0.05, "pitch": 0.0, "yaw_rate": 0.0, "thrust": 100.0},
                               **self.ids)
        self.assertEqual(inside["status"], "completed", inside)
        outside = client.invoke(COMMAND, {"roll": 0.5, "pitch": 0.0, "yaw_rate": 0.0, "thrust": 100.0},
                                **self.ids)
        self.assertEqual(outside["status"], "rejected", outside)
        self.assertEqual(outside["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")

    def served(self, **switches):
        driver = load_driver(HERE, "fake")
        for name, value in switches.items():
            setattr(driver.native, name, value)
        server = build_server(driver, site_limits=json.loads((HERE / "site-limits.example.json").read_text()))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    @staticmethod
    def services(native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    def test_the_e_stop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        driver, client = self.served()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertTrue(driver.native.paused)
        self.assertEqual(self.services(driver.native)[:2], [PAUSE, READBACK])

    def test_a_failed_pause_or_read_back_leaves_the_e_stop_unconfirmed_and_latched(self) -> None:
        for switch in ("fail_pause", "fail_readback", "ignore_pause"):
            with self.subTest(switch=switch):
                _driver, client = self.served(**{switch: True})
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], ESTOP_UNREACHED)
                refused = client.invoke(COMMAND, SMALL, **self.ids)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP_ENGAGED, refused)

    def test_the_reset_keeps_the_world_paused_and_a_new_command_moves_nothing(self) -> None:
        driver, client = self.served()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.invoke(COMMAND, SMALL, **self.ids)["error"]["mhs_code"], ESTOP_ENGAGED)
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        position = dict(driver.native.odometry["pose"]["pose"]["position"])
        receipt = client.invoke(COMMAND, SMALL, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["sent_thrust"], 100.0)
        self.assertEqual(driver.native.command["thrust"], 100.0)  # stored by the controller, applied on unpause
        self.assertEqual(driver.native.odometry["pose"]["pose"]["position"], position)
        self.assertNotIn("/gazebo/unpause_physics", self.services(driver.native))
        with self.assertRaises(MHSError):
            driver.call(ODOMETRY, {})  # the world is still paused: odometry is silent

    def test_the_package_offers_no_unpause(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(set(type(driver).commands), {COMMAND, ODOMETRY})
        self.assertIsNone(driver._model.reenable)

    def test_the_resource_reads_no_topic(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.paused = True
        self.assertEqual(driver.read("main"), {})


if __name__ == "__main__":
    unittest.main()
