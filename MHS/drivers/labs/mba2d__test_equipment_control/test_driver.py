"""Acceptance run of the A2D Eload package: the gate, plus cases for what is specific to this driver.

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

    def test_the_reads_query_the_channels_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written, ["*IDN?", "MEAS:VOLT 1?", "MEAS:VOLT:ADC 1?", "CURR 1?",
                                                 "MEAS:TEMP 1?", "INSTR:RELAY 1?", "INSTR:LED 1?",
                                                 "INSTR:FAN 1?"])
        self.assertEqual((state["voltage"], state["adc_voltage"]), (12.0, 11.9))
        self.assertEqual(state["current_reported"], 0.0)
        self.assertEqual((state["output"], state["led"], state["fan"]), (False, False, False))

    def test_a_write_becomes_the_command_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"current": 2.5, "output": True, "led": True, "fan": True})
        self.assertEqual(driver.native.written[1:], ["CURR 1,2.5", "INSTR:RELAY 1,1", "INSTR:LED 1,1",
                                                     "INSTR:FAN 1,1"])

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": True, "led": True, "fan": True})
        state = driver.read("main", ["output", "led", "fan"])
        self.assertEqual((state["output"], state["led"], state["fan"]), (True, True, True))

    def test_a_current_write_moves_the_reported_target_current(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.read("main", ["current_reported"]), {"current_reported": 0.0})
        driver.write("main", {"current": 2.0})
        self.assertEqual(driver.read("main", ["current_reported"]), {"current_reported": -2.0})

    def test_the_estop_opens_the_output_relay(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": True})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], "INSTR:RELAY 1,0")
        self.assertEqual(driver.read("main", ["output"]), {"output": False})


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

    def test_the_maximum_current_of_the_upstream_code(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, current=10.001), ENVELOPE)
        self.assertEqual(self.configure(client, current=10.0), "completed")
        self.assertEqual(self.configure(client, current=0.0), "completed")

    def test_the_example_overlay_only_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, current=5.001), ENVELOPE)
        self.assertEqual(self.configure(client, current=5.0), "completed")


if __name__ == "__main__":
    unittest.main()
