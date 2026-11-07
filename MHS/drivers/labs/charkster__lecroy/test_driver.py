"""Acceptance run of the LeCroy package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NativeCalls(unittest.TestCase):
    """The setter paths, checked on the calls the fake backend receives."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_sourced_trigger_write_reaches_trigger_setup(self) -> None:
        driver = self.driver()
        driver.write("main", {"trigger_slope": "Negative", "trigger_mode": "Normal"})
        setup_calls = [call for call in driver.native.calls if call[0] == "trigger_setup"]
        self.assertTrue(setup_calls)
        self.assertEqual(setup_calls[-1][4:6], ("Negative", "Normal"))
        state = driver.read("main", ["trigger_slope", "trigger_mode"])
        self.assertEqual((state["trigger_slope"], state["trigger_mode"]), ("Negative", "Normal"))

    def test_the_estop_resets_the_instrument(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.native.reset_count, 1)


class Actions(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake", site_limits=str(HERE / "site-limits.example.json"))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client, ids

    def test_the_measure_action_returns_a_number(self) -> None:
        client, ids = self.serve()
        receipt = client.invoke("x-cap.charkster.measure.v1",
                                {"assigned_channel": "P1", "stat_type": "value"}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"assigned_channel": "P1", "stat_type": "value", "value": 1.0})

    def test_the_trigger_action_uses_the_operator_overlay(self) -> None:
        client, ids = self.serve()
        receipt = client.invoke("x-cap.charkster.trigger.v1",
                                {"trigger_level": 0.5, "trigger_horizontal_offset": 0.0,
                                 "trigger_slope": "Positive", "trigger_mode": "Normal"}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["trigger_level"], 0.5)
        self.assertEqual(receipt["output"]["trigger_slope"], "Positive")


if __name__ == "__main__":
    unittest.main()
