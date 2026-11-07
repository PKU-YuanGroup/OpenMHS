"""Acceptance run of the SR860 package: the gate, plus cases for what is specific to this driver.

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

    def test_a_write_becomes_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 1000.0, "amplitude": 0.1, "time_constant": 0.001})
        self.assertEqual(driver.native.written[0], "*IDN?")                      # the identity check on connect
        self.assertEqual(driver.native.written[1:], ["FREQ 1000", "SLVL 0.1", "OFLT 6"])
        driver.write("main", {"time_constant": 30000.0, "frequency": 0.001})
        self.assertEqual(driver.native.written[-2:], ["OFLT 21", "FREQ 0.001"])

    def test_the_reads_use_the_data_indexes_of_the_readme(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[1:], ["FREQ?", "SLVL?", "OUTP? 0", "OUTP? 1", "OUTP? 2", "OUTP? 3"])
        self.assertEqual((state["frequency"], state["amplitude"]), (99999.5, 0.0))
        self.assertEqual((state["r"], state["theta"]), (1.717368435e-11, 115.52829742))
        self.assertAlmostEqual((state["x"] ** 2 + state["y"] ** 2) ** 0.5, state["r"], delta=1e-18)

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 2500.5, "amplitude": 0.25})
        state = driver.read("main", ["frequency", "amplitude"])
        self.assertEqual((state["frequency"], state["amplitude"]), (2500.5, 0.25))

    def test_the_estop_sets_the_amplitude_to_zero(self) -> None:
        driver = self.driver()
        driver.write("main", {"amplitude": 0.5})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], "SLVL 0")
        self.assertEqual(driver.read("main", ["amplitude"]), {"amplitude": 0.0})


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
        for patch in ({"frequency": 0.0009}, {"frequency": 500000.1}, {"amplitude": -0.001}, {"amplitude": 2.001},
                      {"time_constant": 2e-6}, {"time_constant": 1e-7}, {"time_constant": 30001.0}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"frequency": 0.001}, {"frequency": 500000.0}, {"amplitude": 0}, {"amplitude": 2.0},
                      {"time_constant": 1e-6}, {"time_constant": 30000.0}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_example_overlay_only_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"frequency": 0.5}, {"frequency": 100001.0}, {"amplitude": 0.11}, {"time_constant": 1e-6},
                      {"time_constant": 10.0}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"frequency": 1000.0}, {"amplitude": 0.1}, {"time_constant": 0.001}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
