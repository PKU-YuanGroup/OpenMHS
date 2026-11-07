"""Acceptance run of the New Era NE-500 package: the gate, plus cases for this driver.

Add cases, never remove the ``check_driver`` call.
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
    """The command bytes this driver sends to the fake serial handle of new_era3.py."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    @staticmethod
    def link(driver):
        return driver.native.ser()

    def test_a_rate_write_uses_the_direction_and_unit_commands_of_the_clone(self) -> None:
        driver = self.driver()
        applied = driver.write("main", {"flow_rate": 1000.0})
        link = self.link(driver)
        self.assertEqual(link.written[:2], ["0DIRINF", "0RAT1000.UH"])
        self.assertEqual(applied["applied"]["flow_rate"], 1000.0)
        driver.write("main", {"flow_rate": -12345.0})
        self.assertEqual(link.written[-4:-2], ["0DIRWDR", "0RAT12.34MH"])
        self.assertEqual(link.direction, "WDR")

    def test_a_large_rate_is_written_in_mh(self) -> None:
        driver = self.driver()
        driver.write("main", {"flow_rate": 10000.0})
        self.assertEqual(self.link(driver).written[:2], ["0DIRINF", "0RAT10.0MH"])

    def test_a_diameter_write_is_a_dia_command(self) -> None:
        driver = self.driver()
        driver.write("main", {"diameter": 4.699})
        link = self.link(driver)
        self.assertEqual(link.written[:1], ["0DIA4.699"])
        self.assertAlmostEqual(self.link(driver).diameter, 4.699)

    def test_the_reads_use_two_rate_queries_and_one_diameter_query(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(self.link(driver).written, ["0RAT", "0RAT", "0DIA"])
        self.assertEqual(state["flow_rate"], 0.0)
        self.assertAlmostEqual(state["diameter"], 4.699)

    def test_start_and_stop_actions_reach_the_fake(self) -> None:
        driver = self.driver()
        driver.write("main", {"flow_rate": 1000.0})
        started = driver.call("x-cap.clarklabucb.start_pump.v1", {})
        link = self.link(driver)
        self.assertTrue(link.running)
        self.assertIn("0RUN", link.written)
        self.assertEqual(started["flow_rate"], 1000.0)
        stopped = driver.call("x-cap.clarklabucb.stop_pump.v1", {})
        self.assertEqual(stopped, {"stopped": True})
        self.assertFalse(link.running)
        self.assertEqual(link.written[-2:], ["0STP", "0RAT0UH"])

    def test_the_estop_sends_the_broadcast_stop(self) -> None:
        driver = self.driver()
        driver.call("x-cap.clarklabucb.start_pump.v1", {})
        driver.estop("test")
        link = self.link(driver)
        self.assertEqual(link.written[-1], "*STP")
        self.assertFalse(link.running)


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

    def test_the_writes_need_the_operator_ranges(self) -> None:
        client = self.serve()
        for patch in ({"flow_rate": 1.0}, {"flow_rate": 0.0}, {"diameter": 4.699}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_example_overlay_narrows_both_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"flow_rate": -1.0}, {"flow_rate": 10001.0}, {"diameter": 0.0}, {"diameter": 50.1}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"flow_rate": 0.0}, {"flow_rate": 10000.0}, {"diameter": 0.1}, {"diameter": 50.0}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
