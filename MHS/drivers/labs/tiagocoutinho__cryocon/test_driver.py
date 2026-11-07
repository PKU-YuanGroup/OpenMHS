"""Acceptance run of the CryoCon package: the gate, plus cases for what is specific to this driver.

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
IDN = "Cryo-con,24C,000000,1.00A"    # placeholder
NAME = "Cryocon fake"                # placeholder
TEMPERATURE = 300.0                  # placeholder
TEMPERATURE_CELSIUS = 26.85          # placeholder
CHANNEL_B = 24.5                     # placeholder
LOOP_SETPOINT = 25.0                 # placeholder


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Readings(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_state_reads_the_upstream_members(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state, {
            "idn": IDN,
            "name": NAME,
            "hw_revision": "FAKE-HW",
            "fw_revision": "FAKE-FW",
            "lockout": False,
            "led": False,
            "display_filter_time": 1.0,
            "date": "2026-01-02",
            "time": "03:04:05",
            "control": False,
            "channel": "A",
            "channel_name": "A",
            "temperature": TEMPERATURE,
            "temperature_unit": "K",
            "minimum": 3.4,
            "maximum": 304.12,
            "alarm": "--",
            "loop": 1,
            "loop_setpoint": LOOP_SETPOINT,
            "loop_source": "A",
            "loop_type": "MAN",
            "loop_output_power": 40.3,
            "loop_range": "MID",
        })

    def test_the_reads_do_not_move_the_device(self) -> None:
        driver = self.driver()
        first = driver.read("main")
        second = driver.read("main")
        self.assertEqual(first, second)

    def test_the_measurement_converts_the_selected_channel_to_celsius(self) -> None:
        driver = self.driver()
        output = driver.call("cap.measure.temperature.v1", {})
        self.assertAlmostEqual(output["temperature"], TEMPERATURE_CELSIUS)
        self.assertIn("sampled_at", output)

    def test_the_probe_selects_another_channel(self) -> None:
        driver = self.driver()
        output = driver.call("cap.measure.temperature.v1", {"probe": "B"})
        self.assertEqual(output["temperature"], CHANNEL_B)

    def test_a_sensor_unit_channel_is_not_reported_as_celsius(self) -> None:
        driver = self.driver()
        with self.assertRaises(DriverFailed) as caught:
            driver.call("cap.measure.temperature.v1", {"probe": "D"})
        self.assertEqual(caught.exception.code, "MHS.DEVICE.PRECONDITION_UNMET")

    def test_the_package_declares_no_writable_parameter(self) -> None:
        driver = self.driver()
        with self.assertRaises(MHSError) as caught:
            driver.write("main", {"temperature": 1.0})
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.NOT_WRITABLE")


if __name__ == "__main__":
    unittest.main()
