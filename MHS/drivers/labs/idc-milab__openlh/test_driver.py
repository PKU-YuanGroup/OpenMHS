"""Acceptance run of the OpenLH package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ReadsAndWrites(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_reads_come_from_the_native_object(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual((state["position_x"], state["position_y"], state["position_z"]), (150.0, 0.0, 150.0))
        self.assertEqual((state["polar_rotation"], state["polar_stretch"], state["polar_height"]),
                         (0.0, 150.0, 150.0))
        self.assertEqual([state[name] for name in ("base_angle", "left_angle", "right_angle", "hand_angle")],
                         [90.0, 90.0, 90.0, 90.0])
        self.assertEqual(state["ultrasonic_distance"], 30)
        self.assertFalse(state["limit_switch"])
        self.assertFalse(state["is_moving"])
        self.assertFalse(state["pump_on"])
        self.assertFalse(state["gripper_closed"])
        self.assertIn(("get_position", (), {}), driver.native._calls)
        self.assertIn(("get_ultrasonic", (), {}), driver.native._calls)

    def test_a_servo_write_reaches_set_servo_angle_and_reads_back(self) -> None:
        driver = self.driver()
        driver.write("main", {"base_angle": 45.0, "hand_angle": 135.0})
        state = driver.read("main", ["base_angle", "hand_angle"])
        self.assertEqual(state, {"base_angle": 45.0, "hand_angle": 135.0})
        self.assertIn(("set_servo_angle", (0, 45.0), {"wait": True, "timeout": 10}), driver.native._calls)
        self.assertIn(("set_servo_angle", (3, 135.0), {"wait": True, "timeout": 10}), driver.native._calls)

    def test_the_pump_and_gripper_writes_are_observable(self) -> None:
        driver = self.driver()
        driver.write("main", {"pump_on": True, "gripper_closed": True})
        state = driver.read("main", ["pump_on", "gripper_closed"])
        self.assertEqual(state, {"pump_on": True, "gripper_closed": True})
        driver.write("main", {"pump_on": False, "gripper_closed": False})
        self.assertEqual(driver.read("main", ["pump_on", "gripper_closed"]),
                         {"pump_on": False, "gripper_closed": False})

    def test_the_estop_turns_the_tool_outputs_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"pump_on": True, "gripper_closed": True})
        driver.estop("test")
        self.assertEqual(driver.read("main", ["pump_on", "gripper_closed"]),
                         {"pump_on": False, "gripper_closed": False})
        self.assertIn(("set_pump", (False,), {"timeout": None}), driver.native._calls)
        self.assertIn(("set_gripper", (False,), {"timeout": None}), driver.native._calls)


class ServedCapabilities(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_servo_bounds_are_enforced(self) -> None:
        client = self.serve()
        for patch in ({"base_angle": -0.1}, {"base_angle": 180.1}, {"hand_angle": 200}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"base_angle": 0}, {"base_angle": 180}, {"hand_angle": 90}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_cartesian_move_needs_an_operator_envelope(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.motion.cartesian_pose.v1", {"position": {"x": 5, "y": 5, "z": 5}},
                                **self.ids)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_the_example_overlay_admits_an_in_range_cartesian_move(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke("cap.motion.cartesian_pose.v1", {"position": {"x": 5, "y": 5, "z": 5}},
                                **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["reached"])
        self.assertEqual(receipt["output"]["position"], {"x": 5.0, "y": 5.0, "z": 5.0})
        receipt = client.invoke("cap.motion.cartesian_pose.v1", {"position": {"x": 10.5, "y": 5, "z": 5}},
                                **self.ids)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_the_safe_state_action_turns_the_tool_outputs_off(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, pump_on=True, gripper_closed=True), "completed")
        receipt = client.invoke("x-cap.idc-milab.tool_off.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["tool_off"])
        state = client.read("main", **self.ids)["state"]
        self.assertFalse(state["pump_on"])
        self.assertFalse(state["gripper_closed"])


if __name__ == "__main__":
    unittest.main()
