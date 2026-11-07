"""Acceptance run of the pyinstrument PSupply package: the gate, plus cases for what is specific to this driver.

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


class NativeCalls(unittest.TestCase):
    """The decorated methods on the fake backend object (the runtime's limits are not involved)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_writes_reach_the_three_psupply_methods(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage_setpoint": 12.5, "current_setpoint": 1.5, "output_enabled": False})
        self.assertEqual(driver.native.voltage_writes[-1], 12.5)
        self.assertEqual(driver.native.current_writes[-1], 1.5)
        self.assertEqual(driver.native.off_calls, 1)
        self.assertEqual(driver.read("main", ["voltage", "current"]), {"voltage": 0.0, "current": 0.0})

    def test_the_measurements_follow_the_setpoints_while_the_output_is_on(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage_setpoint": 5.0, "current_setpoint": 0.5, "output_enabled": True})
        state = driver.read("main")
        self.assertEqual((state["voltage"], state["current"]), (5.0, 0.5))

    def test_the_estop_calls_off_and_zeroes_the_readings(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertGreaterEqual(driver.native.off_calls, 1)
        self.assertEqual(driver.read("main", ["voltage"]), {"voltage": 0.0})


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_without_an_overlay_every_setpoint_is_operator_required(self) -> None:
        client = self.serve()
        for patch in ({"voltage_setpoint": 1.0}, {"current_setpoint": 0.5}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_example_overlay_bounds_the_setpoints(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"voltage_setpoint": -1.0}, {"voltage_setpoint": 30.001},
                      {"current_setpoint": -0.001}, {"current_setpoint": 5.001}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"voltage_setpoint": 0.0}, {"voltage_setpoint": 30.0},
                      {"current_setpoint": 0.0}, {"current_setpoint": 5.0}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


class MeasureCapabilities(unittest.TestCase):
    def test_both_measure_actions_return_a_stamped_reading(self) -> None:
        server = load(HERE, backend="fake", site_limits=str(HERE / "site-limits.example.json"))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        ids = {"device_id": device_id, "session_id": session}
        client.invoke("cap.device.configure.v1", {"voltage_setpoint": 4.0, "current_setpoint": 0.25}, **ids)
        voltage = client.invoke("cap.measure.voltage.v1", {}, **ids)
        current = client.invoke("cap.measure.current.v1", {}, **ids)
        self.assertEqual(voltage["status"], "completed")
        self.assertEqual(current["status"], "completed")
        self.assertEqual(voltage["output"]["voltage"], 4.0)
        self.assertEqual(current["output"]["current"], 0.25)
        self.assertIsInstance(voltage["output"]["sampled_at"], str)


if __name__ == "__main__":
    unittest.main()
