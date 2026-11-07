"""Acceptance run of the keysight33210A package: the gate, plus cases for what is specific to this driver.

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
        driver.write("main", {"frequency": 1000.0, "amplitude": 0.1, "function": "SIN"})
        self.assertEqual(driver.native.written[0], "*IDN?")  # the identity check on connect
        self.assertEqual(driver.native.written[1:], ["FREQ 1.0000e+03", "VOLT 0.1000", "FUNC SIN"])

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 2500.5, "amplitude": 0.25, "offset": 0.5,
                              "function": "SQU", "load": "INF", "output": "ON"})
        state = driver.read("main")
        self.assertEqual(state["frequency"], 2500.5)
        self.assertEqual(state["amplitude"], 0.25)
        self.assertEqual(state["offset"], 0.5)
        self.assertEqual(state["function"], "SQU")
        self.assertEqual(state["load"], "INF")
        self.assertEqual(state["output"], "ON")

    def test_the_estop_disables_the_output(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": "ON"})
        self.assertEqual(driver.read("main", ["output"]), {"output": "ON"})
        driver.estop("test")
        self.assertEqual(driver.native.written[-2:], [":OUTP OFF", ":OUTP OFF"])
        self.assertEqual(driver.read("main", ["output"]), {"output": "OFF"})


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

    def test_operator_required_refuses_until_the_site_supplies_a_bound(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, amplitude=0.05), "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(self.configure(client, offset=0.1), "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(self.configure(client, frequency=1000.0), "completed")

    def test_the_example_overlay_fills_and_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, amplitude=0.05), "completed")
        self.assertEqual(self.configure(client, amplitude=2.0), ENVELOPE)
        self.assertEqual(self.configure(client, frequency=0.5), ENVELOPE)
        self.assertEqual(self.configure(client, frequency=1000.0), "completed")
        self.assertEqual(self.configure(client, function="RAMP"), ENVELOPE)
        self.assertEqual(self.configure(client, function="SQU"), "completed")
        self.assertEqual(self.configure(client, load="INF"), ENVELOPE)
        self.assertEqual(self.configure(client, output="ON"), ENVELOPE)
