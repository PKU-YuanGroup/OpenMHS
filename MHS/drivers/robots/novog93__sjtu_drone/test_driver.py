"""Acceptance and package-specific cases for the sjtu_drone ROS 2 simulation package.

The other cases exercise the declared topic contract, the operator-required
cmd_vel envelope, the world reset that is not a stop (/reset_world leaves the
plugin's flight state and stored command in place), the companion-cited stop
(the Gazebo world pause confirmed by the E1 stall read-back of get_model_list),
its failure paths, a reset that leaves the world paused and that the package
offers no unpause.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown, build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
TAKEOFF = "x-cap.novog93.takeoff.v1"
LAND = "x-cap.novog93.land.v1"
RESET = "x-cap.novog93.reset.v1"
CMD_VEL = "x-cap.novog93.cmd_vel.v1"
POSCTRL = "x-cap.novog93.posctrl.v1"
VEL_MODE = "x-cap.novog93.vel_mode.v1"
STATE = "x-cap.novog93.state.v1"
POSE = "x-cap.novog93.pose.v1"
MODE = "x-cap.novog93.mode.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SjtuDroneCases(unittest.TestCase):
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

    def test_command_publications_reach_the_declared_topics(self) -> None:
        driver = self.driver()
        takeoff = driver.call(TAKEOFF, {})
        self.assertTrue(takeoff["published"])
        self.assertFalse(takeoff["confirmed"])
        self.assertTrue(driver.call(LAND, {})["published"])
        self.assertTrue(driver.call(POSCTRL, {"enabled": True})["published"])
        self.assertTrue(driver.call(VEL_MODE, {"enabled": True})["published"])
        self.assertTrue(driver.call(RESET, {})["published"])
        sent = [message.get("topic") for message in driver.native.sent
                if message.get("op") == "publish"]
        self.assertEqual(sent, [
            "/simple_drone/takeoff",
            "/simple_drone/land",
            "/simple_drone/posctrl",
            "/simple_drone/dronevel_mode",
            "/simple_drone/reset",
        ])

    def test_cmd_vel_is_refused_until_the_operator_supplies_bounds(self) -> None:
        client = self.serve()
        receipt = client.invoke(
            CMD_VEL,
            {"linear_x": 0.0, "linear_y": 0.0, "linear_z": 0.0,
             "angular_x": 0.0, "angular_y": 0.0, "angular_z": 0.0},
            **self.ids,
        )
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")

    def test_the_state_and_pose_observations_return_their_samples(self) -> None:
        driver = self.driver()
        self.assertIsInstance(driver.call(STATE, {})["state"], int)
        pose = driver.call(POSE, {})
        self.assertEqual(set(pose), {"x", "y", "z", "orientation_w", "orientation_x",
                                     "orientation_y", "orientation_z"})
        # The plugin publishes cmd_mode only from SwitchModeCallback: select the mode first.
        driver.call(VEL_MODE, {"enabled": False})
        self.assertEqual(driver.call(MODE, {})["mode"], "position")

    def test_a_malformed_state_message_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.malformed_state = True
        with self.assertRaises(MHSError) as caught:
            driver.call(STATE, {})
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")

    def test_a_rejected_publication_does_not_complete(self) -> None:
        driver = self.driver()
        driver.native.reject_publish = True
        with self.assertRaises(OutcomeUnknown):
            driver.call(TAKEOFF, {})

    def test_the_simulated_state_label_follows_the_recorded_publications(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.native.state_value, 0)   # placeholder LANDED_MODEL
        driver.call(TAKEOFF, {})
        self.assertEqual(driver.native.state_value, 2)   # placeholder TAKINGOFF_MODEL
        driver.call(LAND, {})
        self.assertEqual(driver.native.state_value, 3)   # placeholder LANDING_MODEL
        driver.call(RESET, {})
        # Reset() does not assign navi_state (plugin_drone_private.cpp:36-56).
        self.assertEqual(driver.native.state_value, 3)   # placeholder LANDING_MODEL

    def test_the_world_reset_is_acknowledged_but_keeps_the_flight_state(self) -> None:
        driver = self.driver()
        driver.call(TAKEOFF, {})
        command = {"linear": {"x": 0.5, "y": 0.0, "z": 0.0},      # placeholder Twist
                   "angular": {"x": 0.0, "y": 0.0, "z": 0.0}}
        driver.native.last_cmd_vel = command
        receipt = driver.call("x-cap.novog93.reset_world.v1", {})
        self.assertTrue(receipt["reset"])
        services = [message.get("service") for message in driver.native.sent
                    if message.get("op") == "call_service"]
        self.assertEqual(services, ["/reset_world"])
        self.assertEqual(driver.native.state_value, 2)   # placeholder TAKINGOFF_MODEL, unchanged
        self.assertEqual(driver.native.last_cmd_vel, command)

    def test_a_failed_world_reset_does_not_report_success(self) -> None:
        driver = self.driver()
        driver.native.fail_reset_world = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.novog93.reset_world.v1", {})

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

    def test_the_e_stop_pauses_and_confirms_a_frozen_sim_time(self) -> None:
        driver, client = self.served()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.services(driver.native), ["/pause_physics", "/get_model_list", "/get_model_list"])
        self.assertNotIn("/reset_world", self.services(driver.native))  # a world reset is not the stop
        refused = client.invoke(TAKEOFF, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_running_world_or_a_failed_call_leaves_the_e_stop_unconfirmed(self) -> None:
        for switch in ("ignore_pause", "fail_pause", "fail_model_list"):
            with self.subTest(switch=switch):
                _driver, client = self.served(**{switch: True})
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
                self.assertTrue(receipt["output"]["latched"], receipt)

    def test_the_reset_keeps_the_world_paused_and_offers_no_unpause(self) -> None:
        driver, client = self.served()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        self.assertEqual(client.invoke(LAND, {}, **self.ids)["status"], "completed")  # stored for the next unpause
        self.assertNotIn("/unpause_physics", self.services(driver.native))
        self.assertIsNone(driver._model.reenable)
        with self.assertRaises(MHSError):
            driver.call(STATE, {})  # the plugin publishes no state while the world is paused
        self.assertEqual(driver.read("main"), {})  # the resource reads no topic

    def test_the_cmd_vel_receipt_reports_what_it_sent(self) -> None:
        driver = self.driver()
        values = {"linear_x": 0.1, "linear_y": 0.0, "linear_z": 0.2, "angular_x": 0.0, "angular_y": 0.0,
                  "angular_z": -0.3}
        output = driver.call(CMD_VEL, values)
        self.assertEqual(output, {"published": True, "confirmed": False,
                                  **{"sent_" + key: value for key, value in values.items()}})
        echoed = driver.call("x-cap.novog93.last_cmd_vel.v1", {})
        self.assertEqual(echoed["linear"], {"x": 0.1, "y": 0.0, "z": 0.2})


if __name__ == "__main__":
    unittest.main()
