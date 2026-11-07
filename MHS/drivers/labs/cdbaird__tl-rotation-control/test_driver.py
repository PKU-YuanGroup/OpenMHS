"""Acceptance run of the Elliptec rotation stage package: the gate, plus cases for this driver.

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
    """The upstream command letters, checked on the fake, not on a stage."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_reads_use_the_query_letters_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main", ["position", "step_size", "status_code", "serial_number"])
        self.assertEqual(driver.native.commands, ["0gp", "0gj", "0gs"])
        self.assertEqual(state["position"], 90.0)
        self.assertEqual(state["step_size"], 45.0)
        self.assertEqual(state["status_code"], 0)
        self.assertEqual(state["serial_number"], "00000000")

    def test_a_position_write_is_the_absolute_move_of_the_clone(self) -> None:
        driver = self.driver()
        applied = driver.write("main", {"position": 90.0})
        self.assertEqual(driver.native.commands, ["0ma0000FFF0", "0gp"])
        self.assertEqual(applied["applied"]["position"], 90.0)
        self.assertEqual(driver.read("main", ["position"]), {"position": 90.0})

    def test_a_step_size_write_is_the_stepsize_setting_of_the_clone(self) -> None:
        driver = self.driver()
        applied = driver.write("main", {"step_size": 30.0})
        self.assertEqual(driver.native.commands, ["0sj00005550", "0gj"])
        self.assertEqual(applied["applied"]["step_size"], 30.0)
        self.assertEqual(driver.read("main", ["step_size"]), {"step_size": 30.0})

    def test_home_sends_the_home_move(self) -> None:
        driver = self.driver()
        driver.write("main", {"position": 90.0})
        result = driver.call("x-cap.cdbaird.home.v1", {})
        self.assertTrue(result["homed"])
        self.assertEqual(driver.native.commands, ["0ma0000FFF0", "0gp", "0ho0", "0gp"])
        self.assertEqual(driver.read("main", ["position"]), {"position": 0.0})

    def test_the_estop_isolates_the_module(self) -> None:
        driver = self.driver()
        driver.write("main", {"position": 90.0})
        driver.estop("test")
        self.assertEqual(driver.native.commands[-1], "0is01")
        self.assertEqual(driver.read("main", ["status_code"]), {"status_code": 5})


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

    def test_the_position_needs_the_operator_overlay(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, position=10.0), UNSET)

    def test_the_step_size_bounds_of_the_gui(self) -> None:
        client = self.serve()
        for value in (0.9, 359.1):
            self.assertEqual(self.configure(client, step_size=value), ENVELOPE, value)
        for value in (1.0, 359.0):
            self.assertEqual(self.configure(client, step_size=value), "completed", value)

    def test_the_example_overlay_bounds_the_position(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for value in (-0.1, 360.1):
            self.assertEqual(self.configure(client, position=value), ENVELOPE, value)
        for value in (0.0, 360.0):
            self.assertEqual(self.configure(client, position=value), "completed", value)


if __name__ == "__main__":
    unittest.main()
