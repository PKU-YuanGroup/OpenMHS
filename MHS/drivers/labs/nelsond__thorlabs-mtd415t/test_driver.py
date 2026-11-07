"""Acceptance run of the MTD415T package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent

# The fake's fixed values (test data, not device facts; the placeholders live in fake.py).
TEMPERATURE = 24.5       # placeholder
SETPOINT = 25.0          # placeholder
TEC_CURRENT = 0.35       # placeholder
TEC_VOLTAGE = 1.2        # placeholder
TEC_CURRENT_LIMIT = 1.0  # placeholder
IDN = "MTD415T fake"     # placeholder
UID = "fake-uid"         # placeholder


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Readings(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_state_reads_the_upstream_properties(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state, {
            "temperature": TEMPERATURE,
            "setpoint": SETPOINT,
            "tec_current": TEC_CURRENT,
            "tec_voltage": TEC_VOLTAGE,
            "tec_current_limit": TEC_CURRENT_LIMIT,
            "errors": [],
            "idn": IDN,
            "uid": UID,
            "is_open": True,
        })

    def test_the_temperature_capability_returns_the_measured_temperature(self) -> None:
        driver = self.driver()
        output = driver.call("cap.measure.temperature.v1", {})
        self.assertEqual(output["temperature"], TEMPERATURE)
        self.assertIn("sampled_at", output)

    def test_the_package_stores_no_setpoint_it_did_not_read(self) -> None:
        driver = self.driver()
        first = driver.read("main")
        second = driver.read("main")
        self.assertEqual(first["setpoint"], second["setpoint"])
        self.assertEqual(first["temperature"], second["temperature"])

    def test_close_closes_the_serial_port_and_moves_no_setpoint(self) -> None:
        driver = load_driver(HERE, "fake")
        setpoint = driver.read("main")["setpoint"]
        driver.close()
        self.assertFalse(driver.native.is_open)
        self.assertEqual(driver.native.temp_setpoint, setpoint)
