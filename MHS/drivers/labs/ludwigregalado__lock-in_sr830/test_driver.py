"""Acceptance run of the SR830 package: the gate, plus cases for what is specific to this driver.

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
        driver.write("main", {"frequency": 1000.0, "amplitude": 0.1, "input_config": 3})
        self.assertEqual(driver.native.written, ["FREQ 1000", "SLVL 0.1", "ISRC 3"])
        driver.write("main", {"time_constant_index": 19, "reserve": 2, "sync": 1})
        self.assertEqual(driver.native.written[-3:], ["OFLT 19", "RMOD 2", "SYNC 1"])

    def test_the_reads_use_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written, [
            "OUTP? 1", "OUTP? 2", "OUTP? 3", "OUTP? 4", "PHAS?", "FREQ?", "SLVL?",
            "ISRC?", "IGND?", "ICPL?", "ILIN?", "RMOD?", "OFLT?", "OFSL?", "SYNC?", "*IDN?",
        ])
        self.assertAlmostEqual(state["x"], 1.234e-3)
        self.assertAlmostEqual(state["y"], -4.56e-4)
        self.assertAlmostEqual(state["frequency"], 1000.0)
        self.assertEqual(state["identity"], "Stanford_Research_Systems,SR830,fake,1.0")

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 2500.5, "amplitude": 0.25, "line_filter": 2, "slope": 1})
        state = driver.read("main", ["frequency", "amplitude", "line_filter", "slope"])
        self.assertEqual(state, {"frequency": 2500.5, "amplitude": 0.25, "line_filter": 2, "slope": 1})

    def test_the_estop_sets_the_amplitude_to_the_lowest_value(self) -> None:
        driver = self.driver()
        driver.write("main", {"amplitude": 0.5})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], "SLVL 0.004")
        self.assertEqual(driver.read("main", ["amplitude"]), {"amplitude": 0.004})


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

    def test_the_bounds_of_the_upstream_code(self) -> None:
        client = self.serve()
        for patch in ({"frequency": 0.0009}, {"frequency": 102000.1}, {"amplitude": 0.003}, {"amplitude": 5.001},
                      {"input_config": 4}, {"ground": -1}, {"coupling": 2}, {"line_filter": 4},
                      {"reserve": 3}, {"time_constant_index": 20}, {"slope": 3}, {"sync": 2}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"frequency": 0.001}, {"frequency": 102000.0}, {"amplitude": 0.004}, {"amplitude": 5.0},
                      {"input_config": 0}, {"input_config": 3}, {"ground": 1}, {"coupling": 1},
                      {"line_filter": 3}, {"reserve": 2}, {"time_constant_index": 0},
                      {"time_constant_index": 19}, {"slope": 2}, {"sync": 1}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
