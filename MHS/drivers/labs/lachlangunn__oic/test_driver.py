"""Acceptance run of the OIC Arduino DAQ package: the gate, plus cases for this driver's wire commands.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


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

    def test_the_identity_is_checked_before_the_first_command(self) -> None:
        driver = self.driver()
        driver.read("main", ["voltage0"])
        self.assertEqual(driver.native.written[0], "*IDN?")

    def test_the_reads_use_the_three_measurement_commands(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[1:], [":MEASURE:VOLTAGE?", ":MEASURE:VOLTAGE1?",
                                                     ":MEASURE:VOLTAGE2?"])
        self.assertEqual(state, {"voltage0": 0.0, "voltage1": 0.0, "voltage2": 0.0})

    def test_a_write_becomes_the_source_command_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage0": 2.5, "voltage1": 1.25})
        self.assertEqual(driver.native.written[1:], [":SOURCE:VOLTAGE 2.5V", ":SOURCE:VOLTAGE1 1.25V"])
        state = driver.read("main", ["voltage0", "voltage1"])
        self.assertEqual(state, {"voltage0": 2.5, "voltage1": 1.25})

    def test_the_estop_writes_zero_to_both_source_channels(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage0": 5.0, "voltage1": 5.0})
        driver.estop("test")
        self.assertEqual(driver.native.written[-2:], [":SOURCE:VOLTAGE 0V", ":SOURCE:VOLTAGE1 0V"])
        self.assertEqual(driver.read("main", ["voltage0", "voltage1"]), {"voltage0": 0.0, "voltage1": 0.0})


class Limits(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_full_scale_of_the_firmware(self) -> None:
        client = self.serve()
        for patch in ({"voltage0": -0.001}, {"voltage0": 5.001}, {"voltage1": -1.0}, {"voltage1": 5.5},
                      {"voltage0": 0.0, "voltage1": -0.1}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"voltage0": 0.0}, {"voltage0": 5.0}, {"voltage1": 0.0}, {"voltage1": 5.0},
                      {"voltage0": 2.5, "voltage1": 4.75}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_state_reflects_a_write(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, voltage0=3.25), "completed")
        state = client.read("main", device_id=self.ids["device_id"], session_id=self.ids["session_id"])["state"]
        self.assertEqual(state["voltage0"], 3.25)


if __name__ == "__main__":
    unittest.main()
