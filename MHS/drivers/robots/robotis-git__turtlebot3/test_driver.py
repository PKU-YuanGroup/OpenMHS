"""Acceptance run of the TurtleBot3 ROS 2 package: the gate plus repository-specific cases.

The cases exercise the pinned wire shapes: one ``TwistStamped`` publication on
``/cmd_vel``, the ``std_srvs/SetBool`` ``motor_power`` service, the read-only
observations, and the failure and latch paths through the actual native stop
(fake) transport.  A publication acknowledgement is not a motion or stop
measurement.  Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
MOTOR_POWER = "/motor_power"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Turtlebot3Cases(unittest.TestCase):
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
    def calls(driver):
        return [message for message in driver.native.sent if message.get("op") == "call_service"]

    def test_reads_expose_the_pinned_observation_topics(self):
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["battery_voltage"], 11.1)
        self.assertEqual(state["battery_percentage"], 0.75)
        self.assertIs(state["battery_present"], True)
        self.assertEqual(state["odom_pose"], {
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        })
        self.assertEqual(state["wheel_velocity"], [0.0, 0.0])
        self.assertIs(state["torque_enabled"], True)
        topics = [message["topic"] for message in driver.native.sent if message.get("op") == "subscribe"]
        for topic in ("/battery_state", "/odom", "/joint_states", "/sensor_state"):
            self.assertIn(topic, topics)

    def test_cmd_vel_publishes_one_explicit_twist_stamped(self):
        driver = self.driver()
        receipt = driver.call("x-cap.robotis-git.cmd_vel.v1",
                              {"linear_velocity": 0.2, "angular_velocity": 1.0})
        self.assertEqual(receipt, {"published": True, "confirmed": False})
        sends = driver.native.sent
        advertised = [message for message in sends if message.get("op") == "advertise"]
        published = [message for message in sends if message.get("op") == "publish"]
        self.assertEqual(advertised[-1]["topic"], "/cmd_vel")
        self.assertEqual(advertised[-1]["type"], "geometry_msgs/msg/TwistStamped")
        self.assertEqual(published[-1]["topic"], "/cmd_vel")
        self.assertEqual(published[-1]["msg"]["twist"]["linear"]["x"], 0.2)
        self.assertEqual(published[-1]["msg"]["twist"]["angular"]["z"], 1.0)
        self.assertEqual(driver.native.last_linear_x, 0.2)
        self.assertEqual(driver.native.last_angular_z, 1.0)

    def test_motor_power_service_maps_the_boolean_and_changes_the_torque_observation(self):
        driver = self.driver()
        receipt = driver.call("x-cap.robotis-git.motor_power.v1", {"enabled": False})
        self.assertEqual(receipt, {"success": True, "message": "ok"})
        self.assertEqual(self.calls(driver)[-1]["service"], MOTOR_POWER)
        self.assertEqual(self.calls(driver)[-1]["type"], "std_srvs/srv/SetBool")
        self.assertEqual(self.calls(driver)[-1]["args"], {"data": False})
        self.assertEqual(driver.read("main", ["torque_enabled"]), {"torque_enabled": False})
        driver.call("x-cap.robotis-git.motor_power.v1", {"enabled": True})
        self.assertEqual(driver.read("main", ["torque_enabled"]), {"torque_enabled": True})

    def test_disable_torque_is_a_fixed_input_free_request(self):
        driver = self.driver()
        receipt = driver.call("x-cap.robotis-git.disable_torque.v1", {})
        self.assertEqual(receipt, {"success": True, "message": "ok"})
        self.assertEqual(self.calls(driver)[-1]["args"], {"data": False})
        self.assertEqual(driver.read("main", ["torque_enabled"]), {"torque_enabled": False})

    def test_failed_service_result_is_not_success(self):
        driver = self.driver()
        driver.native.fail_motor_service = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.robotis-git.motor_power.v1", {"enabled": False})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_rejected_application_result_is_not_success(self):
        driver = self.driver()
        driver.native.reject_motor_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.robotis-git.disable_torque.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_malformed_service_reply_is_an_unknown_outcome(self):
        driver = self.driver()
        driver.native.malformed_motor_response = True
        with self.assertRaises(OutcomeUnknown) as caught:
            driver.call("x-cap.robotis-git.motor_power.v1", {"enabled": False})
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.UNKNOWN")

    def test_native_estop_reaches_motor_power_and_reports_the_torque_disable(self):
        driver = self.driver()
        receipt = driver.estop("test")
        self.assertEqual(receipt["estop"], "engaged")
        self.assertEqual(receipt["performed"], [MOTOR_POWER])
        self.assertEqual([call["args"] for call in self.calls(driver)], [{"data": False}])
        self.assertIs(driver.native.torque_enabled, False)

    def test_native_estop_refuses_failed_refused_and_malformed_replies(self):
        for failure in ("fail_motor_service", "reject_motor_application", "malformed_motor_response"):
            with self.subTest(failure=failure):
                driver = self.driver()
                setattr(driver.native, failure, True)
                with self.assertRaises(DriverFailed) as caught:
                    driver.estop("negative-path test")
                self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_server_estop_latches_motor_power_but_allows_the_safe_state_action(self):
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        refused = client.invoke("x-cap.robotis-git.motor_power.v1", {"enabled": True}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        allowed = client.invoke("x-cap.robotis-git.disable_torque.v1", {}, **self.ids)
        self.assertEqual(allowed["status"], "completed", allowed)
        self.assertEqual(allowed["output"], {"success": True, "message": "ok"})

    def test_declaration_keeps_reset_unexposed_and_claims_no_physical_stop(self):
        driver = self.driver()
        self.assertIsNone(type(driver).estop_physical_ref)
        self.assertEqual(set(type(driver).safety_bindings), {"estop"})
        self.assertNotIn("x-cap.robotis-git.reset.v1", type(driver).commands)
        self.assertNotIn("/reset", repr(type(driver).commands))
        self.assertEqual(type(driver).ros_version, 2)
        self.assertEqual(type(driver).mode, "hardware")
        self.assertEqual(type(driver).risk, "R2")
        self.assertEqual(type(driver).backends, {"fake": ".fake:FakeTurtlebot3"})

    def test_velocity_requires_operator_limits_and_example_is_enforced(self):
        client = self.serve()
        cap = "x-cap.robotis-git.cmd_vel.v1"
        payload = {"linear_velocity": 0.05, "angular_velocity": 0.25}
        refused = client.invoke(cap, payload, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        client = self.serve(HERE / "site-limits.example.json")
        self.assertEqual(client.invoke(cap, payload, **self.ids)["status"], "completed")
        for value in (-0.2, 0.2):
            denied = client.invoke(cap, dict(payload, linear_velocity=value), **self.ids)
            self.assertEqual(denied["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        for value in (-1.0, 1.0):
            denied = client.invoke(cap, dict(payload, angular_velocity=value), **self.ids)
            self.assertEqual(denied["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")


if __name__ == "__main__":
    unittest.main()
