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
    """The command map, checked on the lines the fake transport receives (the runtime's limits are not involved)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_write_becomes_the_lines_of_the_upstream(self) -> None:
        driver = self.driver()
        driver.write("main", {"time_constant_index": 19, "sensitivity_index": 26, "sync_filter": 0})
        self.assertEqual(driver.native.written[0], "*IDN?")                 # the identity probe on connect
        self.assertEqual(driver.native.written[-3:], ["OFLT 19", "SENS 26", "SYNC 0"])

    def test_the_reads_keep_the_space_before_the_question_mark(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[1:],
                         ["FREQ ?", "OFLT ?", "SENS ?", "SYNC ?", "OUTP? 1", "OUTP? 2", "OUTP? 3", "OUTP? 4"])
        self.assertEqual((state["time_constant_index"], state["sensitivity_index"], state["sync_filter"]),
                         (10, 17, 1))
        self.assertAlmostEqual(state["r"], (state["x"] ** 2 + state["y"] ** 2) ** 0.5, delta=1e-12)

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"time_constant_index": 3, "sensitivity_index": 8, "sync_filter": 0})
        state = driver.read("main", ["time_constant_index", "sensitivity_index", "sync_filter"])
        self.assertEqual(state, {"time_constant_index": 3, "sensitivity_index": 8, "sync_filter": 0})

    def test_the_estop_selects_the_safe_state(self) -> None:
        driver = self.driver()
        driver.write("main", {"sync_filter": 1, "sensitivity_index": 0})
        driver.estop("test")
        self.assertEqual(driver.native.written[-2:], ["SYNC 0", "SENS 26"])
        self.assertEqual(driver.read("main", ["sync_filter", "sensitivity_index"]),
                         {"sync_filter": 0, "sensitivity_index": 26})


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

    def test_the_index_bounds_of_the_upstream_tables(self) -> None:
        client = self.serve()
        for patch in ({"time_constant_index": -1}, {"time_constant_index": 20},
                      {"sensitivity_index": -1}, {"sensitivity_index": 27},
                      {"sync_filter": -1}, {"sync_filter": 2}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"time_constant_index": 0}, {"time_constant_index": 19},
                      {"sensitivity_index": 0}, {"sensitivity_index": 26},
                      {"sync_filter": 0}, {"sync_filter": 1}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
