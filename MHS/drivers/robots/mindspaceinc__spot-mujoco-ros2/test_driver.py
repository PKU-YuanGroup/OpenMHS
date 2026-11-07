"""Acceptance run of the Spot Mini MuJoCo ROS 2 package: the gate plus package cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ACTUATOR = "x-cap.mindspaceinc.actuator_cmds.v1"
RESET = "x-cap.mindspaceinc.sim_reset.v1"
SAFE_RESET = "x-cap.mindspaceinc.safe_reset.v1"
JOINTS = "x-cap.mindspaceinc.joint_states.v1"

_ZEROS = [0.0] * 12


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SpotMujocoCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_actuator_publication_records_the_fixed_joint_order(self) -> None:
        driver = self.driver()
        receipt = driver.call(ACTUATOR, {
            "kp": [1.0] * 12, "pos": _ZEROS, "kd": [0.5] * 12, "vel": _ZEROS, "torque": _ZEROS,
        })
        self.assertEqual(receipt, {"published": True, "confirmed": False})
        body = driver.native.last_command
        self.assertEqual(body["actuators_name"], [
            "fl.hx", "fl.hy", "fl.kn", "fr.hx", "fr.hy", "fr.kn",
            "hl.hx", "hl.hy", "hl.kn", "hr.hx", "hr.hy", "hr.kn",
        ])
        self.assertEqual(body["kp"], [1.0] * 12)
        self.assertEqual(body["kd"], [0.5] * 12)

    def test_the_actuator_publication_enforces_the_sourced_torque_clamp(self) -> None:
        client = self.serve()
        receipt = client.invoke(ACTUATOR, {
            "kp": _ZEROS, "pos": _ZEROS, "kd": _ZEROS, "vel": _ZEROS,
            "torque": [100.5] + _ZEROS[1:],
        }, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_the_joint_state_observation_returns_one_fresh_sample(self) -> None:
        client = self.serve()
        receipt = client.invoke(JOINTS, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["name"], [
            "fl.hx", "fl.hy", "fl.kn", "fr.hx", "fr.hy", "fr.kn",
            "hl.hx", "hl.hy", "hl.kn", "hr.hx", "hr.hy", "hr.kn",
        ])
        self.assertEqual(len(output["position"]), 12)
        self.assertEqual(len(output["velocity"]), 12)
        self.assertEqual(len(output["effort"]), 12)

    def test_the_reset_service_updates_the_placeholder_base_pose(self) -> None:
        driver = self.driver()
        receipt = driver.call(RESET, {"base_z": 0.9, "joint_positions": [0.1] * 12})
        self.assertEqual(receipt, {"is_success": True})
        self.assertEqual(driver.native.base_position, (0.0, 0.0, 0.9))
        self.assertEqual(driver.native.joint_positions, [0.1] * 12)
        self.assertEqual(driver.native.reset_requests[-1]["header"]["frame_id"], "spot")

    def test_a_rejected_reset_application_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_reset_application = True
        with self.assertRaises(DriverFailed):
            driver.call(RESET, {})
        self.assertEqual(driver.native.base_position, (0.0, 0.0, 0.7))

    def test_a_failed_reset_transport_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_reset_service = True
        with self.assertRaises(DriverFailed):
            driver.call(RESET, {})
        self.assertEqual(driver.native.base_position, (0.0, 0.0, 0.7))

    def test_a_malformed_joint_state_is_not_a_sample(self) -> None:
        driver = self.driver()
        driver.native.malformed_joint_state = True
        with self.assertRaises(Exception) as caught:
            driver.call(JOINTS, {})
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.DEVICE.NOT_READY")

    def test_a_failed_reset_application_fails_the_native_estop_path(self) -> None:
        driver = self.driver()
        driver.native.fail_reset_application = True
        with self.assertRaises(Exception) as caught:
            driver.estop("test")
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_a_failed_reset_transport_fails_the_native_estop_path(self) -> None:
        driver = self.driver()
        driver.native.fail_reset_service = True
        with self.assertRaises(Exception) as caught:
            driver.estop("test")
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_a_malformed_reset_reply_fails_the_native_estop_path(self) -> None:
        driver = self.driver()
        driver.native.malformed_reset = True
        with self.assertRaises(Exception) as caught:
            driver.estop("test")
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_the_simulated_stop_resets_and_latches(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        refused = client.invoke(ACTUATOR, {
            "kp": _ZEROS, "pos": _ZEROS, "kd": _ZEROS, "vel": _ZEROS, "torque": _ZEROS,
        }, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_safe_state_action_is_input_free_and_does_not_latch(self) -> None:
        client = self.serve()
        receipt = client.invoke(SAFE_RESET, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"is_success": True})
        after = client.invoke(ACTUATOR, {
            "kp": _ZEROS, "pos": _ZEROS, "kd": _ZEROS, "vel": _ZEROS, "torque": _ZEROS,
        }, **self.ids)
        self.assertEqual(after["status"], "completed", after)

    def test_the_extension_observation_is_latched_but_resource_read_is_not(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        refused = client.invoke(JOINTS, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        state = client.read("main", device_id=self.ids["device_id"], session_id=self.ids["session_id"])
        self.assertIn("joint_positions", state["state"])


if __name__ == "__main__":
    unittest.main()
