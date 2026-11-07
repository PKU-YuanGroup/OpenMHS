"""Acceptance run of the SPD3303X package: the gate, plus cases for what is specific to this driver.

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
    """The command map, checked on the lines the fake transport receives."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_write_becomes_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage": 5.0, "current": 1.0, "tracking": 1})
        self.assertEqual(driver.native.written[0], "*IDN?")                  # the identity check on connect
        self.assertEqual(driver.native.written[1:], ["CH1:VOLT 5", "CH1:CURR 1", "OUTP:TRACK 1"])
        driver.write("main", {"voltage": 0.0, "current": 3.0, "tracking": 0})
        self.assertEqual(driver.native.written[-3:], ["CH1:VOLT 0", "CH1:CURR 3", "OUTP:TRACK 0"])

    def test_the_reads_use_the_siglent_command_forms(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[1:], [
            "CH1:VOLT?", "CH1:CURR?", "OUTP:TRACK?", "MEASure:VOLTage? CH1",
            "MEASure:CURRent? CH1", "*IDN?", "SYST:ERR?",
        ])
        self.assertEqual(state["identity"], "Siglent Technologies,SPD3303X-E,SPD3XXXXXXXXXXX,V1.01")
        self.assertEqual((state["voltage"], state["current"], state["tracking"]), (0.0, 0.0, 0))
        self.assertEqual(state["last_error"], '+0,"No error"')

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage": 2.5, "current": 0.25, "tracking": 2})
        state = driver.read("main", ["voltage", "current", "tracking"])
        self.assertEqual((state["voltage"], state["current"], state["tracking"]), (2.5, 0.25, 2))

    def test_the_estop_switches_both_outputs_off(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.native.written[-2:], ["OUTPut CH1,OFF", "OUTPut CH2,OFF"])
        self.assertFalse(driver.native.output1_on)
        self.assertFalse(driver.native.output2_on)


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

    def test_the_bounds_of_the_upstream_code(self) -> None:
        client = self.serve()
        for patch in ({"voltage": -0.001}, {"voltage": 30.001}, {"current": -0.001}, {"current": 3.001},
                      {"tracking": 3}, {"tracking": -1}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"voltage": 0}, {"voltage": 30.0}, {"current": 0}, {"current": 3.0},
                      {"tracking": 0}, {"tracking": 1}, {"tracking": 2}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_example_overlay_only_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"voltage": 12.001}, {"current": 1.001}, {"tracking": 2}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"voltage": 12.0}, {"current": 1.0}, {"tracking": 1}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
