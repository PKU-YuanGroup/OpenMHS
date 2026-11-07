"""Acceptance run of the agilent33600 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"


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

    def test_a_write_becomes_the_scalar_commands_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 1000000.0, "amplitude": 0.2, "offset": 0.0,
                              "function": "SIN", "waveform": "ATLASCALIB_B", "sample_rate": 1000000000.0})
        sent = [line for line in driver.native.written if line != "SYST:ERR?"]
        self.assertEqual(sent[0], "*IDN?")
        self.assertEqual(sent[1:], [
            "SOURCE1:FREQUENCY 1000000",
            "SOURCE1:VOLTAGE 0.2",
            "SOUR1:VOLT:OFFS 0",
            "SOURCE1:FUNC SIN",
            "SOUR1:FUNC:ARB ATLASCALIB_B",
            "SOUR1:FUNC:ARB:SRAT 1000000000",
        ])

    def test_the_reads_use_the_query_form_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        queries = driver.native.written[1:]  # written[0] is the identity probe on connect
        self.assertEqual(queries, [
            "*IDN?",
            "SOURCE1:FREQUENCY?",
            "SOURCE1:VOLTAGE?",
            "SOUR1:VOLT:OFFS?",
            "SOURCE1:FUNC?",
            "SOUR1:FUNC:ARB?",
            "SOUR1:FUNC:ARB:SRAT?",
        ])
        self.assertEqual(state["function"], "SIN")
        self.assertEqual(state["waveform"], "ATLASCALIB_B")
        self.assertIsInstance(state["frequency"], float)

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 2500000.5, "amplitude": 0.25, "function": "ARB"})
        state = driver.read("main", ["frequency", "amplitude", "function"])
        self.assertEqual((state["frequency"], state["amplitude"], state["function"]),
                         (2500000.5, 0.25, "ARB"))

    def test_the_estop_switches_the_output_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"amplitude": 0.5})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], "OUTPUT1 OFF")
        self.assertFalse(driver.native.output_on)
        self.assertEqual(driver.read("main", ["amplitude"]), {"amplitude": 0.5})  # the setting stays


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

    def test_operator_required_bounds_refuse_until_the_overlay_fills_them(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, frequency=1000000.0), LIMITS_UNSET)
        self.assertEqual(self.configure(client, amplitude=0.1), LIMITS_UNSET)
        self.assertEqual(self.configure(client, offset=0.0), LIMITS_UNSET)
        self.assertEqual(self.configure(client, sample_rate=1000000.0), LIMITS_UNSET)
        # A string setting carries no numeric bound, so it is usable without an overlay.
        self.assertEqual(self.configure(client, function="SIN"), "completed")

    def test_the_example_overlay_supplies_and_narrows_the_bounds(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"frequency": 10.0}, {"frequency": 100000001.0}, {"amplitude": -1.0},
                      {"amplitude": 4.0}, {"offset": -6.0}, {"offset": 6.0},
                      {"sample_rate": 10.0}, {"sample_rate": 1000000001.0}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"frequency": 1000.0}, {"frequency": 100000000.0}, {"amplitude": 0.0},
                      {"amplitude": 3.5}, {"offset": -5.0}, {"offset": 5.0},
                      {"sample_rate": 1000.0}, {"sample_rate": 1000000000.0}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_enum_and_the_name_length_are_refused(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, function="NOISE"), "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(self.configure(client, waveform="ABCDEFGHIJKLM"), "MHS.CAPABILITY.INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
