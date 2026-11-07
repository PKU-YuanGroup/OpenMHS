"""Acceptance run of the comunication-instrument package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent

# The fake's canned replies (test data, not device facts).
STATUS = 305419896       # placeholder test data
TYPE = "abc"             # placeholder test data
VOLTAGE = 12             # placeholder test data
TEMPERATURE = 24         # placeholder test data
CURRENT = 100            # placeholder test data


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Readings(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_state_uses_the_five_upstream_requests(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.commands, ["STA", "TYP", "VOL", "TMP", "CUR"])
        self.assertEqual(state, {"status": STATUS, "type": TYPE, "voltage": VOLTAGE,
                                 "temperature": TEMPERATURE, "current": CURRENT})

    def test_the_sensing_action_returns_every_channel(self) -> None:
        driver = self.driver()
        output = driver.call("cap.sensing.read.v1", {})
        self.assertEqual(output["values"], {"status": STATUS, "type": TYPE, "voltage": VOLTAGE,
                                            "temperature": TEMPERATURE, "current": CURRENT})
        self.assertIn("sampled_at", output)

    def test_the_sensing_action_filters_the_declared_fields(self) -> None:
        driver = self.driver()
        output = driver.call("cap.sensing.read.v1", {"fields": ["temperature", "type"]})
        self.assertEqual(output["values"], {"type": TYPE, "temperature": TEMPERATURE})

    def test_the_estop_closes_and_detaches_the_serial_port(self) -> None:
        driver = self.driver()
        port = driver.native.ser
        self.assertFalse(port.closed)
        receipt = driver.estop("test")
        self.assertEqual(receipt["estop"], "engaged")
        self.assertEqual(receipt["native"], "ser.close")
        self.assertTrue(port.closed)
        self.assertIsNone(driver.native.ser)


if __name__ == "__main__":
    unittest.main()
