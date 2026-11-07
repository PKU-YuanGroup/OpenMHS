"""Acceptance run of the Keithley 2000 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import DriverFailed
from mhs.errors import MHSError
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent

# The fake's fixed values (test data, not device facts; the placeholders live in fake.py).
IDENTIFICATION = "Keithley Instruments,2000,000000,FAKE"    # placeholder
VOLTAGE_DC = 1.25                                           # placeholder
CURRENT_DC = 0.0025                                         # placeholder
RESISTANCE = 1000.0                                         # placeholder
VOLTAGE_RANGE = 10.0                                        # placeholder
CURRENT_RANGE = 0.1                                         # placeholder
UNMET = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Readings(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_state_reads_the_upstream_channels(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.read("main"), {
            "identification": IDENTIFICATION,
            "voltage_dc": VOLTAGE_DC,
            "current_dc": CURRENT_DC,
            "resistance": RESISTANCE,
            "voltage_range": VOLTAGE_RANGE,
        })

    def test_the_reads_do_not_move_the_device(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.read("main"), driver.read("main"))

    def test_each_catalogue_action_returns_its_channel_value(self) -> None:
        driver = self.driver()
        voltage = driver.call("cap.measure.voltage.v1", {})
        current = driver.call("cap.measure.current.v1", {})
        resistance = driver.call("cap.measure.resistance.v1", {})
        self.assertEqual(voltage["voltage"], VOLTAGE_DC)
        self.assertEqual(current["current"], CURRENT_DC)
        self.assertEqual(resistance["resistance"], RESISTANCE)
        for output in (voltage, current, resistance):
            self.assertIn("sampled_at", output)

    def test_the_action_inputs_reach_the_channel_range(self) -> None:
        driver = self.driver()
        voltage = driver.call("cap.measure.voltage.v1",
                              {"channel": "voltage_dc", "range_v": 100.0, "dc": True})
        current = driver.call("cap.measure.current.v1", {"channel": "current_dc", "range_a": 1.0})
        self.assertEqual(voltage["range_v"], 100.0)
        self.assertEqual(current["range_a"], 1.0)
        self.assertEqual(voltage["voltage"], VOLTAGE_DC)
        self.assertEqual(current["current"], CURRENT_DC)

    def test_the_voltage_range_write_is_read_back(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage_range": 100.0})
        self.assertEqual(driver.read("main", ["voltage_range"]), {"voltage_range": 100.0})
        driver.write("main", {"voltage_range": 0.0})
        self.assertEqual(driver.read("main", ["voltage_range"]), {"voltage_range": 0.0})

    def test_the_unsupported_modes_are_refused(self) -> None:
        driver = self.driver()
        for capability_id, payload in (
            ("cap.measure.voltage.v1", {"dc": False}),
            ("cap.measure.resistance.v1", {"four_wire": True}),
            ("cap.measure.voltage.v1", {"channel": "current_dc"}),
        ):
            with self.assertRaises(DriverFailed) as caught:
                driver.call(capability_id, payload)
            self.assertEqual(caught.exception.code, UNMET)

    def test_the_package_declares_no_writable_parameter(self) -> None:
        driver = self.driver()
        with self.assertRaises(MHSError) as caught:
            driver.write("main", {"voltage_dc": 2.0})
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.NOT_WRITABLE")

    def test_the_operator_reset_reaches_the_fake(self) -> None:
        driver = self.driver()
        driver.reset()
        self.assertEqual(driver.native._reset_count, 1)


if __name__ == "__main__":
    unittest.main()
