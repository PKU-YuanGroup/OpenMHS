"""Acceptance run of the ASI MS-2000-500-CP package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = HERE / "site-limits.example.json"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
MOVE = "x-cap.amsikking.move_stage.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ReadsAndWrites(unittest.TestCase):
    """The served state and the two PWM writes, checked on the fake backend object."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_reads_and_the_fake_start_state(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual((state["position_x"], state["position_y"], state["position_z"]), (0.0, 0.0, 0.0))
        self.assertFalse(state["motor_moving"])
        self.assertEqual(state["pwm_intensity"], 10)
        self.assertEqual(state["pwm_state"], "off")

    def test_a_write_changes_the_state_it_reads_back(self) -> None:
        driver = self.driver()
        driver.write("main", {"pwm_intensity": 40})
        self.assertEqual(driver.read("main", ["pwm_intensity"]), {"pwm_intensity": 40})
        for state in ("on", "pwm", "external", "off"):
            driver.write("main", {"pwm_state": state})
            self.assertEqual(driver.read("main", ["pwm_state"]), {"pwm_state": state})
            self.assertEqual(driver.native.state, state)

    def test_the_estop_switches_the_pwm_output_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"pwm_state": "pwm"})
        self.assertEqual(driver.native.state, "pwm")
        driver.estop("test")
        self.assertEqual(driver.native.state, "off")
        self.assertEqual(driver.read("main", ["pwm_state"]), {"pwm_state": "off"})


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def outcome(self, client, capability_id, payload):
        """``completed``, or the MHS code the call was refused with."""
        receipt = client.invoke(capability_id, payload, **self.ids)
        if receipt["status"] == "rejected":
            return receipt["error"]["mhs_code"]
        return receipt["status"]

    def test_the_pwm_bounds_of_the_upstream_code(self) -> None:
        client = self.serve()
        for patch in ({"pwm_intensity": 0}, {"pwm_intensity": 100}, {"pwm_state": "invalid"}):
            self.assertEqual(self.outcome(client, "cap.device.configure.v1", patch), ENVELOPE, patch)
        for patch in ({"pwm_intensity": 1}, {"pwm_intensity": 99}, {"pwm_state": "off"}, {"pwm_state": "on"},
                      {"pwm_state": "pwm"}, {"pwm_state": "external"}):
            self.assertEqual(self.outcome(client, "cap.device.configure.v1", patch), "completed", patch)

    def test_a_move_needs_the_operator_travel(self) -> None:
        client = self.serve()
        payload = {"x_um": 1000.0, "y_um": 2000.0, "z_um": -500.0}
        self.assertEqual(self.outcome(client, MOVE, payload), UNSET)

    def test_the_example_overlay_fills_the_travel_and_narrows_it(self) -> None:
        client = self.serve(str(OVERLAY))
        self.assertEqual(self.outcome(client, MOVE, {"x_um": 1000.0, "y_um": 2000.0, "z_um": -500.0}),
                         "completed")
        for payload in ({"x_um": 50001.0, "y_um": 0.0, "z_um": 0.0},
                        {"x_um": 0.0, "y_um": -25001.0, "z_um": 0.0},
                        {"x_um": 0.0, "y_um": 0.0, "z_um": 10001.0}):
            self.assertEqual(self.outcome(client, MOVE, payload), ENVELOPE, payload)

    def test_a_completed_move_reports_the_positions_it_applied(self) -> None:
        client = self.serve(str(OVERLAY))
        payload = {"x_um": 1234.0, "y_um": -2345.0, "z_um": 345.0}
        receipt = client.invoke(MOVE, payload, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["x_um"], output["y_um"], output["z_um"]), (1234.0, -2345.0, 345.0))
        self.assertTrue(output["reached"])


if __name__ == "__main__":
    unittest.main()
