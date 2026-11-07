"""Acceptance run of the sqlim/sr860-python package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import math
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
        driver.write("main", {
            "frequency": 1000.0, "amplitude": 0.1, "phase": 45.0, "dc_offset": -1.5, "harmonic": 3,
            "time_constant": 0.001, "sync_filter_enable": False, "adv_filter_enable": True,
            "x_offset": 10.0, "y_offset": -10.0, "r_offset": 0.0,
            "x_offset_enable": True, "y_offset_enable": False, "r_offset_enable": True,
        })
        self.assertEqual(driver.native.written[0], "*IDN?")  # the identity check on connect
        self.assertEqual(driver.native.written[1:], [
            "FREQ 1000.000", "SLVL 0.100000000", "PHAS 45.0000000", "SOFF -1.5000", "HARM 3",
            "OFLT 6", "SYNC 0", "ADVFILT 1", "COFP 0, 10.00", "COFP 1, -10.00", "COFP 2, 0.00",
            "COFA 0, 1", "COFA 1, 0", "COFA 2, 1",
        ])
        driver.write("main", {"time_constant": 30000.0, "frequency": 0.001})
        self.assertEqual(driver.native.written[-2:], ["OFLT 21", "FREQ 0.001"])

    def test_the_reads_use_the_query_forms_of_the_api_table(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[1:], [
            "FREQ?", "SLVL?", "PHAS?", "SOFF?", "HARM?", "OFLT?", "SYNC?", "ADVFILT?",
            "COFP? 0", "COFP? 1", "COFP? 2", "COFA? 0", "COFA? 1", "COFA? 2",
            "OUTP? 0", "OUTP? 1", "OUTP? 2", "OUTP? 3",
        ])
        self.assertEqual((state["frequency"], state["amplitude"], state["phase"]), (1000.0, 1.0, 0.0))
        self.assertEqual(state["time_constant_index"], 10)
        self.assertIs(state["sync_filter_enable"], True)
        self.assertIs(state["adv_filter_enable"], False)
        self.assertIs(state["x_offset_enable"], False)
        self.assertAlmostEqual(state["r"], math.hypot(1.5e-3, -2.5e-4), places=15)
        self.assertAlmostEqual(state["theta"], math.degrees(math.atan2(-2.5e-4, 1.5e-3)), places=12)

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 2500.5, "amplitude": 0.25, "sync_filter_enable": False,
                              "x_offset_enable": True, "time_constant": 3.0})
        state = driver.read("main", ["frequency", "amplitude", "sync_filter_enable", "x_offset_enable",
                                     "time_constant_index"])
        self.assertEqual(state, {"frequency": 2500.5, "amplitude": 0.25, "sync_filter_enable": False,
                                 "x_offset_enable": True, "time_constant_index": 13})

    def test_the_estop_lowers_the_sine_output(self) -> None:
        driver = self.driver()
        driver.write("main", {"amplitude": 0.5})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], "SLVL 0.000000001")
        self.assertEqual(driver.read("main", ["amplitude"]), {"amplitude": 1e-9})


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
        refused = [
            {"frequency": 0.0009}, {"frequency": 500000.1},
            {"amplitude": 0.0}, {"amplitude": 2.001},
            {"phase": -360000.1}, {"phase": 360000.1},
            {"dc_offset": -5.1}, {"dc_offset": 5.1},
            {"harmonic": 0}, {"harmonic": 100},
            {"time_constant": 2e-6}, {"time_constant": 30001.0},
            {"x_offset": -1000.0}, {"x_offset": 1000.0},
            {"y_offset": -1000.0}, {"r_offset": 1000.0},
        ]
        for patch in refused:
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        accepted = [
            {"frequency": 0.001}, {"frequency": 500000.0},
            {"amplitude": 1e-9}, {"amplitude": 2.0},
            {"phase": -360000.0}, {"phase": 360000.0},
            {"dc_offset": -5.0}, {"dc_offset": 5.0},
            {"harmonic": 1}, {"harmonic": 99},
            {"time_constant": 1e-6}, {"time_constant": 30000.0},
            {"x_offset": -999.99}, {"x_offset": 999.99},
            {"y_offset": -999.99}, {"r_offset": 999.99},
        ]
        for patch in accepted:
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_booleans_have_no_numeric_envelope(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.device.configure.v1", {
            "sync_filter_enable": False, "adv_filter_enable": True,
            "x_offset_enable": True, "y_offset_enable": False, "r_offset_enable": True,
        }, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_the_example_overlay_only_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"frequency": 0.5}, {"frequency": 100001.0}, {"amplitude": 0.11},
                      {"time_constant": 1e-6}, {"time_constant": 10.0}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"frequency": 1000.0}, {"amplitude": 0.1}, {"time_constant": 0.001}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
