"""Acceptance run of the PN300 package: the gate, plus cases for what is specific to this driver.

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
        driver.write("main", {"output": "ON", "source": "B", "operating_mode": "TRAC",
                              "source_type": "CC", "voltage": 0.5, "current": 0.05})
        self.assertEqual(driver.native.written[0], "*IDN?")  # the identity query on connect
        self.assertEqual(driver.native.written[1:],
                         ["OUT_ON", "SEL_B", "OPER_TRAC", "CONT_CC", "VSET 0.5", "ISET 0.05"])

    def test_the_reads_return_the_fake_state(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": "ON", "voltage": 0.5, "current": 0.05})
        state = driver.read("main", ["output", "source", "operating_mode", "source_type", "protection",
                                     "voltage", "current", "measured_voltage", "measured_current"])
        self.assertEqual(state["output"], "ON")
        self.assertEqual(state["source"], "A")
        self.assertEqual(state["operating_mode"], "IND")
        self.assertEqual(state["source_type"], "CV")
        self.assertEqual(state["protection"], "LIM")
        self.assertEqual((state["voltage"], state["current"]), (0.5, 0.05))
        self.assertEqual((state["measured_voltage"], state["measured_current"]), (0.5, 0.05))

    def test_the_estop_disables_the_output(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": "ON", "voltage": 0.5})
        driver.estop("test")
        self.assertIn("OUT_OFF", driver.native.written)
        state = driver.read("main", ["output", "measured_voltage"])
        self.assertEqual(state, {"output": "OFF", "measured_voltage": 0.0})


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
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_operator_bounds_of_the_example_overlay(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"voltage": -0.1}, {"voltage": 1.1}, {"current": 0.0005}, {"current": 0.2}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"voltage": 0.0}, {"voltage": 1.0}, {"current": 0.001}, {"current": 0.1}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_discrete_state_sets(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"output": "UP"}, {"source": "C"}, {"operating_mode": "SERIES"},
                      {"source_type": "XX"}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"output": "ON"}, {"source": "B"}, {"operating_mode": "PAR"},
                      {"source_type": "CC"}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_an_unfilled_operator_bound_is_refused(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, voltage=0.5), UNSET)
        self.assertEqual(self.configure(client, current=0.05), UNSET)


if __name__ == "__main__":
    unittest.main()
