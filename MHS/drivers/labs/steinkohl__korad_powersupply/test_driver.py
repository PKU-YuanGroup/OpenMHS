"""Acceptance run of the Korad KC3405P package: the gate, plus cases for what is specific to this driver.

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

    def driver(self, **options):
        driver = load_driver(HERE, "fake", options=options or None)
        self.addCleanup(driver.close)
        return driver

    def test_every_write_reaches_the_fake_and_is_read_back(self) -> None:
        driver = self.driver()
        driver.write("main", {
            "voltage_setpoint": 12.5,
            "current_setpoint": 1.25,
            "overvoltage_protection_setpoint": 20.0,
            "overcurrent_protection_setpoint": 2.5,
            "output_enabled": True,
            "overvoltage_protection_enabled": False,
            "overcurrent_protection_enabled": False,
        })
        state = driver.read("main")
        self.assertEqual(state["voltage_setpoint"], 12.5)
        self.assertEqual(state["current_setpoint"], 1.25)
        self.assertEqual(state["overvoltage_protection_setpoint"], 20.0)
        self.assertEqual(state["overcurrent_protection_setpoint"], 2.5)
        self.assertTrue(state["output_enabled"])
        self.assertEqual(state["voltage"], 12.5)
        self.assertEqual(state["current"], 1.25)
        self.assertFalse(state["overvoltage_protection_enabled"])
        self.assertFalse(state["overcurrent_protection_enabled"])

    def test_the_channel_option_selects_the_controlled_output(self) -> None:
        driver = self.driver(channel=2)
        driver.write("main", {"output_enabled": True})
        state = driver.read("main", ["channel", "output_enabled"])
        self.assertEqual(state, {"channel": 2, "output_enabled": True})
        status = driver.native.get_status()
        self.assertEqual(status["ch2_output"], "on")
        self.assertEqual(status["ch1_output"], "off")

    def test_the_estop_turns_all_four_outputs_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"output_enabled": True})
        driver.estop("test")
        self.assertFalse(driver.read("main", ["output_enabled"])["output_enabled"])
        status = driver.native.get_status()
        for channel in (1, 2, 3, 4):
            self.assertEqual(status[f"ch{channel}_output"], "off", channel)


class RuntimeLimits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        return client, {"device_id": device_id, "session_id": session_id}

    @staticmethod
    def configure(client, ids, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_without_an_overlay_every_numeric_write_is_operator_required(self) -> None:
        client, ids = self.serve()
        for patch in ({"voltage_setpoint": 1.0}, {"current_setpoint": 0.5},
                      {"overvoltage_protection_setpoint": 2.0},
                      {"overcurrent_protection_setpoint": 0.2}):
            self.assertEqual(self.configure(client, ids, **patch), UNSET, patch)

    def test_the_example_overlay_bounds_the_four_numeric_writes(self) -> None:
        client, ids = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"voltage_setpoint": -1.0}, {"voltage_setpoint": 30.001},
                      {"current_setpoint": -0.001}, {"current_setpoint": 5.001},
                      {"overvoltage_protection_setpoint": -1.0},
                      {"overvoltage_protection_setpoint": 30.001},
                      {"overcurrent_protection_setpoint": -0.001},
                      {"overcurrent_protection_setpoint": 5.001}):
            self.assertEqual(self.configure(client, ids, **patch), ENVELOPE, patch)
        for patch in ({"voltage_setpoint": 0.0}, {"voltage_setpoint": 30.0},
                      {"current_setpoint": 0.0}, {"current_setpoint": 5.0},
                      {"overvoltage_protection_setpoint": 0.0},
                      {"overvoltage_protection_setpoint": 30.0},
                      {"overcurrent_protection_setpoint": 0.0},
                      {"overcurrent_protection_setpoint": 5.0}):
            self.assertEqual(self.configure(client, ids, **patch), "completed", patch)


class Capabilities(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake", site_limits=str(HERE / "site-limits.example.json"))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        return client, {"device_id": device_id, "session_id": session_id}

    def test_both_measure_actions_return_a_stamped_reading(self) -> None:
        client, ids = self.serve()
        client.invoke("cap.device.configure.v1",
                      {"voltage_setpoint": 4.0, "current_setpoint": 0.25, "output_enabled": True}, **ids)
        voltage = client.invoke("cap.measure.voltage.v1", {"dc": True}, **ids)
        current = client.invoke("cap.measure.current.v1", {}, **ids)
        self.assertEqual(voltage["status"], "completed")
        self.assertEqual(current["status"], "completed")
        self.assertEqual(voltage["output"]["voltage"], 4.0)
        self.assertEqual(current["output"]["current"], 0.25)
        self.assertIsInstance(voltage["output"]["sampled_at"], str)
        self.assertIsInstance(current["output"]["sampled_at"], str)

    def test_the_safe_state_action_disables_all_outputs(self) -> None:
        client, ids = self.serve()
        client.invoke("cap.device.configure.v1", {"output_enabled": True}, **ids)
        receipt = client.invoke("x-cap.steinkohl.output_off.v1", {}, **ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertFalse(receipt["output"]["output_enabled"])
        state = client.read(device_id=ids["device_id"], resource_id="main", session_id=ids["session_id"])
        self.assertFalse(state["state"]["output_enabled"])


if __name__ == "__main__":
    unittest.main()
