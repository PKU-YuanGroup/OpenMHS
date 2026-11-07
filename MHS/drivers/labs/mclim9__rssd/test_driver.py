"""Acceptance run of the FSWP package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
UNSET = "MHS.SAFETY.LIMITS_UNSET"
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

    def test_the_connect_probes_the_identity(self) -> None:
        driver = self.driver()
        driver.read("main")
        self.assertEqual(driver.native.written[0], "*IDN?")

    def test_a_write_becomes_the_command_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"attenuation_db": 20, "center_freq_hz": 2.0e9, "sweep_points": 501})
        self.assertEqual(driver.native.written[1:], ["INP:ATT 20", ":SENS:FREQ:CENT 2000000000 HZ",
                                                     ":SENS:SWE:POIN 501.000000"])

    def test_the_reads_use_the_queries_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[1:], ["INP:ATT?", "INST:LIST?", ":SENS:FREQ:CENT?",
                                                     ":SENS:SWE:POIN?", "SENS:SWE:TIME?", ":SENS:SWE:TYPE?",
                                                     "DISP:TRAC:Y:RLEV?"])
        self.assertEqual(state["attenuation_db"], 0)
        self.assertEqual(state["center_freq_hz"], 1.0e9)
        self.assertEqual(state["sweep_points"], 1001)
        self.assertEqual(state["sweep_type"], "SWE")

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"attenuation_db": 25, "center_freq_hz": 3.0e9, "sweep_points": 2001})
        state = driver.read("main", ["attenuation_db", "center_freq_hz", "sweep_points"])
        self.assertEqual(state, {"attenuation_db": 25, "center_freq_hz": 3.0e9, "sweep_points": 2001})

    def test_the_estop_writes_the_safe_state_commands(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.native.written[-2:], ["INIT:CONT OFF", ":INP:ATT:AUTO ON"])
        self.assertFalse(driver.native.continuous)
        self.assertTrue(driver.native.attenuation_auto)


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

    def test_every_write_needs_the_operator_overlay(self) -> None:
        client = self.serve()
        for patch in ({"attenuation_db": 10}, {"center_freq_hz": 1.0e9}, {"sweep_points": 1001}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_example_overlay_bounds_every_write(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"attenuation_db": -1}, {"attenuation_db": 31}, {"center_freq_hz": 9.0e6},
                      {"center_freq_hz": 41.0e9}, {"sweep_points": 200}, {"sweep_points": 20002}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"attenuation_db": 0}, {"attenuation_db": 30}, {"center_freq_hz": 1.0e7},
                      {"center_freq_hz": 40.0e9}, {"sweep_points": 201}, {"sweep_points": 20001}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
