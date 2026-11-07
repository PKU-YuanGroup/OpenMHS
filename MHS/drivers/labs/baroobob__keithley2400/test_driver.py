"""Acceptance run of the Keithley 2400 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
SAFE_COMMAND = "OUTP OFF;SOUR:VOLT 0;SOUR:CURR 0"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WireCommands(unittest.TestCase):
    """The command map, checked on the lines the fake transport receives (the runtime's limits are not involved)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_identity_check_is_the_one_of_the_clone(self) -> None:
        driver = self.driver()
        driver.read("main", ["output"])  # opens the transport and probes *IDN?
        self.assertEqual(driver.native.written[0], "*IDN?")
        self.assertEqual(driver.inner.idn, "KEITHLEY INSTRUMENTS INC.,MODEL 2400,0000000,1.0")

    def test_a_voltage_write_is_the_command_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage": 0.5})
        self.assertEqual(driver.native.written[-1], "SOUR:VOLT 0.5")

    def test_the_output_uses_on_and_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": True})
        driver.write("main", {"output": False})
        self.assertEqual(driver.native.written[-2:], ["OUTP ON", "OUTP OFF"])

    def test_a_measurement_is_the_read_sequence_of_the_clone(self) -> None:
        driver = self.driver()
        reading = driver.call("x-cap.baroobob.measure_current.v1", {"interval": 10})
        self.assertEqual(driver.native.written[-1],
                         "SOUR:FUNC VOLT;CONF:CURR;FORM:ELEM CURR;ARM:COUN 1;TRIG:COUN 1;TRIG:DEL 10.000000;READ?")
        self.assertIsInstance(reading["current"], float)
        self.assertEqual(driver.read("main", ["trigger_delay"]), {"trigger_delay": 10.0})

    def test_the_estop_writes_the_safe_command(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], SAFE_COMMAND)


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    @staticmethod
    def code(receipt):
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_source_voltage_needs_an_operator_bound(self) -> None:
        client = self.serve()
        self.assertEqual(self.code(client.invoke("cap.device.configure.v1", {"voltage": 0.5}, **self.ids)), UNSET)

    def test_the_example_overlay_fills_and_only_narrows_the_voltage(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.code(client.invoke("cap.device.configure.v1", {"voltage": 0.5}, **self.ids)),
                         "completed")
        for patch in ({"voltage": 2.0}, {"voltage": -2.0}):
            self.assertEqual(self.code(client.invoke("cap.device.configure.v1", patch, **self.ids)), ENVELOPE, patch)
        self.assertEqual(self.code(client.invoke("cap.device.configure.v1", {"output": True}, **self.ids)),
                         "completed")

    def test_the_measurement_interval_is_bounded(self) -> None:
        client = self.serve()
        for interval in (-1, 100):
            self.assertEqual(self.code(client.invoke("x-cap.baroobob.measure_current.v1", {"interval": interval},
                                                     **self.ids)), ENVELOPE, interval)
        self.assertEqual(self.code(client.invoke("x-cap.baroobob.measure_current.v1", {"interval": 0}, **self.ids)),
                         "completed")


if __name__ == "__main__":
    unittest.main()
