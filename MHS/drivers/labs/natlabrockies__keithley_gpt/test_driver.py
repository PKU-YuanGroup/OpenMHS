"""Acceptance run of the Keithley 2400 package: the gate, plus cases for this driver.

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


class WireCommands(unittest.TestCase):
    """The command map, checked on the lines the fake transport receives."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_write_becomes_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {
            "current_compliance": 0.005,
            "measure_current_range": 0.005,
            "measure_voltage_range": 1.0,
            "four_wire": True,
            "nplc_current": 1.0,
            "nplc_voltage": 2.0,
            "source_current_range": 0.005,
            "source_voltage_range": 1.0,
        })
        self.assertEqual(driver.native.written[0], "*IDN?")  # the identity probe on connect
        self.assertEqual(driver.native.written[1:], [
            ":SENS:CURR:PROT 0.005",
            ":SENS:CURR:RANG 0.005",
            ":SENS:VOLT:RANG 1",
            ":SYST:RSEN ON",
            ":SENS:CURR:NPLC 1",
            ":SENS:VOLT:NPLC 2",
            ":SOUR:CURR:RANG 0.005",
            ":SOUR:VOLT:RANG 1",
        ])

    def test_the_reads_use_the_queries_of_the_same_commands(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written, [
            "*IDN?",
            "*IDN?",
            ":SENS:CURR:PROT?",
            ":SENS:CURR:RANG?",
            ":SENS:VOLT:RANG?",
            ":SYST:RSEN?",
            ":SENS:CURR:NPLC?",
            ":SENS:VOLT:NPLC?",
            ":SOUR:CURR:RANG?",
            ":SOUR:VOLT:RANG?",
        ])
        self.assertEqual(state["identity"], "Keithley Instruments,2400,0000000,1.0.0")
        self.assertEqual(state["four_wire"], False)
        self.assertAlmostEqual(state["current_compliance"], 0.002)

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"four_wire": True, "source_voltage_range": 2.0})
        state = driver.read("main", ["four_wire", "source_voltage_range"])
        self.assertEqual(state, {"four_wire": True, "source_voltage_range": 2.0})

    def test_the_estop_turns_the_output_off(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], ":OUTP OFF")


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_operator_bounds_refuse_until_the_operator_fills_them(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, current_compliance=0.005), UNSET)
        self.assertEqual(self.configure(client, source_voltage_range=1.0), UNSET)
        self.assertEqual(self.configure(client, four_wire=True), "completed")

    def test_the_example_overlay_fills_and_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, current_compliance=0.005), "completed")
        self.assertEqual(self.configure(client, current_compliance=0.05), "completed")
        self.assertEqual(self.configure(client, current_compliance=0.1), ENVELOPE)
        self.assertEqual(self.configure(client, nplc_current=20.0), ENVELOPE)


if __name__ == "__main__":
    unittest.main()
