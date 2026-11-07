"""Acceptance run of the SMC100 package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases use the package's fake backend only; no hardware is
attached.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FakeMotion(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_reads_use_the_status_and_position_methods(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["position"], 5.0)  # placeholder
        self.assertEqual(state["error_code"], 0)  # placeholder
        self.assertEqual(state["state"], "33")  # placeholder

    def test_the_moves_reach_the_fake_and_change_the_position(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.freespace.home.v1"), {"homed": True, "position": 0.0})
        self.assertEqual(driver.call("x-cap.freespace.move_absolute.v1", {"position": 5.0}),
                         {"position": 5.0})
        self.assertEqual(driver.call("x-cap.freespace.move_relative.v1", {"distance": 2.5}),
                         {"position": 7.5})
        self.assertEqual(driver.read("main", ["position"])["position"], 7.5)

    def test_the_estop_calls_the_upstream_stop(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertTrue(driver.native.stopped)
        self.assertGreaterEqual(driver.native.stop_calls, 1)
        self.assertEqual(driver.native.state, "3C")  # placeholder: DISABLE from READY


if __name__ == "__main__":
    unittest.main()
