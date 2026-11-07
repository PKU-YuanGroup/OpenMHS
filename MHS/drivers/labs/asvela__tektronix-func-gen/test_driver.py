"""Acceptance run of the Tektronix AFG package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TektronixAfgCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_initial_state_comes_from_the_fake(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["output_ch1"], state["output_ch2"]), ("ON", "OFF"))
        self.assertEqual((state["function_ch1"], state["function_ch2"]), ("SIN", "RAMP"))
        self.assertEqual((state["amplitude_ch1"], state["amplitude_ch2"]), (0.5, 1.0))
        self.assertEqual((state["frequency_ch1"], state["frequency_ch2"]), (1000.0, 1000.0))
        self.assertFalse(state["frequency_lock"])
        self.assertIn("USER5", state["waveform_catalogue"])
        self.assertIn("No error", state["error_queue"])

    def test_a_numeric_write_needs_the_site_overlay(self) -> None:
        client = self.serve()
        for patch in ({"amplitude_ch1": 0.5}, {"offset_ch2": 0.0}, {"frequency_ch1": 1000.0}):
            receipt = self.configure(client, **patch)
            self.assertEqual(receipt["status"], "rejected", patch)
            self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET, patch)

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = self.configure(client, amplitude_ch1=0.25, offset_ch2=-0.5, frequency_ch1=2500.0)
        self.assertEqual(receipt["status"], "completed", receipt)
        state = self.state(client)
        self.assertEqual(state["amplitude_ch1"], 0.25)
        self.assertEqual(state["offset_ch2"], -0.5)
        self.assertEqual(state["frequency_ch1"], 2500.0)
        for patch in ({"amplitude_ch1": 0.01}, {"offset_ch2": 6.0}, {"frequency_ch1": 0.5}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_the_string_settings_and_the_estop(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = self.configure(client, function_ch1="SQUare", output_ch1="OFF", output_ch2="ON",
                                 frequency_lock=True)
        self.assertEqual(receipt["status"], "completed", receipt)
        state = self.state(client)
        self.assertEqual((state["function_ch1"], state["output_ch1"]), ("SQUare", "OFF"))
        self.assertEqual((state["output_ch2"], state["frequency_lock"]), ("ON", True))
        refused = self.configure(client, function_ch1="USER5")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertEqual((state["output_ch1"], state["output_ch2"]), ("OFF", "OFF"))
        latched = self.configure(client, frequency_lock=False)
        self.assertEqual(latched["error"]["mhs_code"], ESTOP)

    def test_the_estop_sends_the_two_output_off_commands(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.set_frequency_ch1(2500.0)
        self.assertEqual(driver.frequency_ch1(), 2500.0)
        driver.stop()
        self.assertEqual(driver.native.written, ["OUTPut1:STATe OFF", "OUTPut2:STATe OFF"])
        self.assertEqual((driver.output_ch1(), driver.output_ch2()), ("OFF", "OFF"))


if __name__ == "__main__":
    unittest.main()
