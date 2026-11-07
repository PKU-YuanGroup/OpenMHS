"""Acceptance run of the SR865 package: the gate, plus cases for what is specific to this driver.

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
        driver.write("main", {"time_constant": 1e-3, "sensitivity": 0.5, "phase": 45.0})
        self.assertEqual(driver.native.written, ["OFLT 6", "SCAL 1", "PHAS 45.000000"])
        driver.write("main", {"time_constant": 30e-3, "sensitivity": 0.2, "phase": -12.5})
        self.assertEqual(driver.native.written[-3:], ["OFLT 9", "SCAL 2", "PHAS -12.500000"])

    def test_the_reads_use_the_worker_query_strings(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written, ["OFLT?", "SCAL?", "PHAS?"])
        self.assertEqual((state["tau_index"], state["sens_index"], state["phase"]), (0, 0, 0.0))

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"time_constant": 100e-6, "sensitivity": 0.05, "phase": 33.25})
        state = driver.read("main")
        self.assertEqual((state["tau_index"], state["sens_index"], state["phase"]), (4, 4, 33.25))

    def test_the_estop_clears_the_status_and_leaves_the_settings_alone(self) -> None:
        driver = self.driver()
        driver.write("main", {"time_constant": 1e-3})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], "*CLS")
        self.assertEqual(driver.native.tau_index, 6)


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

    def test_the_values_of_the_upstream_arrays(self) -> None:
        client = self.serve()
        for patch in ({"phase": -180.1}, {"phase": 180.1}, {"time_constant": 2e-6},
                      {"time_constant": 1e-9}, {"sensitivity": 0.3}, {"sensitivity": 2}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"phase": -180}, {"phase": 180}, {"time_constant": 1e-6},
                      {"time_constant": 30e3}, {"sensitivity": 1}, {"sensitivity": 1e-9}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_example_overlay_only_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"phase": -91}, {"phase": 91}, {"time_constant": 1e-6},
                      {"sensitivity": 1e-9}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"phase": 45}, {"time_constant": 0.01}, {"sensitivity": 0.5}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
