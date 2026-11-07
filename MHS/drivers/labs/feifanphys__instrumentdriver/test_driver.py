"""Acceptance run of the Keysight N5182B package: the gate, plus cases for what is specific to this driver.

The command cases check the lines the fake transport receives; the limit cases go through a served endpoint, where the
runtime (not the driver) enforces the envelope.  Add cases, never remove the check_driver call.
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

    @staticmethod
    def lines(driver):
        return [command for _kind, command in driver.native.command_log]

    def test_a_write_becomes_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 2.4e9, "power": -10.0, "output": True})
        self.assertEqual(self.lines(driver)[0], "*IDN?")  # the identity check on connect
        self.assertEqual(self.lines(driver)[1:], ["FREQ 2400000000.0", "POW -10.0DBM", "OUTP ON"])

    def test_the_reads_use_the_queries_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 1000.5, "power": -3.25, "output": False})
        state = driver.read("main")
        self.assertEqual(state, {"frequency": 1000.5, "power": -3.25, "output": False})
        queries = [command for kind, command in driver.native.command_log if kind == "query"]
        self.assertEqual(queries[-3:], ["FREQ?", "POW?", "OUTP?"])

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 2.5e9, "power": -20.0, "output": True})
        state = driver.read("main")
        self.assertEqual((state["frequency"], state["power"], state["output"]), (2.5e9, -20.0, True))

    def test_the_estop_switches_the_output_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": True})
        driver.estop("test")
        self.assertEqual(self.lines(driver)[-1], "OUTP OFF")
        self.assertFalse(driver.read("main", ["output"])["output"])

    def test_reset_sends_rst_and_restores_the_mock_state(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 2.4e9, "power": -10.0, "output": True})
        self.assertEqual(driver.call("x-cap.feifanphys.reset.v1", {}), {})
        self.assertEqual(self.lines(driver)[-1], "*RST")
        state = driver.read("main")
        self.assertEqual((state["frequency"], state["power"], state["output"]), (1.0e9, 0.0, False))


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

    def test_numeric_writes_need_an_operator_bound(self) -> None:
        client = self.serve()
        for patch in ({"frequency": 1.0e9}, {"power": -10.0}, {"frequency": 1.0e9, "power": -10.0}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)
        self.assertEqual(self.configure(client, output=True), "completed")

    def test_the_example_overlay_bounds_the_numeric_writes(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"frequency": 999999.0}, {"frequency": 3000000001.0}, {"power": -31.0}, {"power": 0.1}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"frequency": 1000000.0}, {"frequency": 3000000000.0}, {"power": -30.0}, {"power": 0.0}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_reset_action_is_served(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.feifanphys.reset.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")


if __name__ == "__main__":
    unittest.main()
