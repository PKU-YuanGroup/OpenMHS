"""Acceptance run of the SR830 package: the gate, plus cases for what is specific to this driver.

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
    """The command map, checked on the lines the fake transport receives (the runtime's limits are not involved)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_write_becomes_the_lines_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"time_constant_index": 19, "sensitivity_index": 26})
        self.assertEqual(driver.native.written, ["OFLT 19", "SENS 26"])

    def test_the_auxiliary_outputs_are_read(self) -> None:
        driver = self.driver()
        state = driver.read("main", ["aux_output_1", "aux_output_2"])
        self.assertEqual(state, {"aux_output_1": 0.0, "aux_output_2": 0.0})
        self.assertIn("AUXV? 1", driver.native.written)
        self.assertIn("AUXV? 2", driver.native.written)

    def test_the_reads_use_the_data_indexes_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[:4], ["OUTP? 1", "OUTP? 2", "OUTP? 3", "OUTP? 4"])
        self.assertEqual((state["x"], state["y"]), (-1.5e-3, 2.0e-3))
        self.assertEqual((state["r"], state["theta"]), (2.5e-3, 126.86989765))
        self.assertEqual(state["snapshot"], "-0.0015,0.002,0.0025,126.86989765")
        self.assertNotIn("*IDN?", driver.native.written)

    def test_the_estop_sets_the_amplitude_to_zero(self) -> None:
        driver = self.driver()
        driver.write("main", {"amplitude": 0.5})
        self.assertEqual(driver.native.written[-1], "SLVL 0.500000")
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

    def test_the_two_index_tables_are_the_only_sourced_bounds(self) -> None:
        client = self.serve()
        for patch in ({"time_constant_index": 20}, {"time_constant_index": -1},
                      {"sensitivity_index": 27}, {"sensitivity_index": -1}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"time_constant_index": 0}, {"time_constant_index": 19},
                      {"sensitivity_index": 0}, {"sensitivity_index": 26}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_an_unstated_range_needs_the_operator(self) -> None:
        client = self.serve()
        for patch in ({"amplitude": 0.5}, {"frequency": 1000.0}, {"phase": 90.0},
                      {"reference_source": 1}, {"input_source": 1}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_example_overlay_supplies_the_operator_bounds_and_only_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"amplitude": 1.5}, {"frequency": 0.01}, {"phase": 181.0},
                      {"reference_source": 2}, {"input_source": 4}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"amplitude": 0.5}, {"frequency": 1000.0}, {"phase": 90.0},
                      {"reference_source": 1}, {"input_source": 1},
                      {"time_constant_index": 19}, {"sensitivity_index": 26}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
