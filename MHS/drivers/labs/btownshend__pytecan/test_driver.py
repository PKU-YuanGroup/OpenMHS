"""Acceptance run of the pytecan package: the gate, plus cases for the Gemini command surface.

The stock gate assertion stays failing while the native stop is missing. The other cases exercise only the fake.
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


class GeminiCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_reads_and_start_pipetting(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.status(), "IDLE")                   # placeholder reply
        self.assertEqual(driver.version(), "fake-gemini-0")         # placeholder reply
        self.assertEqual(driver.variable(), 4.5)                    # placeholder starting value
        started = driver.start_pipetting()
        self.assertEqual(started, {"started": True, "status": "RUNNING"})   # placeholder status
        self.assertEqual(driver.status(), "RUNNING")                # placeholder reply

    def test_set_variable_keeps_the_upstream_two_decimals(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.set_variable(12.3456), 12.35)       # SET_VARIABLE uses %.2f
        self.assertEqual(driver.variable(), 12.35)

    def test_close_does_not_stop_or_disconnect_the_fake(self):
        driver = self.driver()
        driver.start_pipetting()
        driver.native.close()
        self.assertEqual(driver.status(), "RUNNING")  # placeholder: upstream close() is a pass


if __name__ == "__main__":
    unittest.main()
