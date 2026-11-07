"""Acceptance run of the Benning MM12 package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent

# The fake's canned replies (placeholder test data, not device facts).
DEVICE_MODEL = "MM12"             # placeholder test data
DEVICE_SERIAL = "00000000"        # placeholder test data
MODEL_ID = 0                      # placeholder test data
FIRMWARE_VERSION = 1.00           # placeholder test data
FUNCTION = "DC V"                 # placeholder test data
VALUE_BASE = 1.2345               # placeholder test data
BASE_UNIT = "V"                   # placeholder test data
VALUE_DISPLAY = 1234.5            # placeholder test data
DISPLAY_UNIT = "mV"               # placeholder test data

STATE = {
    "device_model": DEVICE_MODEL,
    "device_serial": DEVICE_SERIAL,
    "model_id": MODEL_ID,
    "firmware_version": FIRMWARE_VERSION,
    "function": FUNCTION,
    "value_base": VALUE_BASE,
    "base_unit": BASE_UNIT,
    "value_display": VALUE_DISPLAY,
    "display_unit": DISPLAY_UNIT,
}

VALUES = {
    "function": FUNCTION,
    "value_base": VALUE_BASE,
    "base_unit": BASE_UNIT,
    "value_display": VALUE_DISPLAY,
    "display_unit": DISPLAY_UNIT,
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Readings(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_state_uses_the_three_upstream_queries(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state, STATE)
        self.assertIn("getDeviceInfos", driver.native.calls)
        self.assertIn("getMeasurement_baseUnits", driver.native.calls)
        self.assertIn("getMeasurement_humanUnits", driver.native.calls)

    def test_the_sensing_action_returns_every_display_channel(self) -> None:
        driver = self.driver()
        output = driver.call("cap.sensing.read.v1", {})
        self.assertEqual(output["values"], VALUES)
        self.assertIn("sampled_at", output)

    def test_the_sensing_action_filters_the_declared_fields(self) -> None:
        driver = self.driver()
        output = driver.call("cap.sensing.read.v1", {"fields": ["function", "value_base"]})
        self.assertEqual(output["values"], {"function": FUNCTION, "value_base": VALUE_BASE})

    def test_an_empty_native_reply_is_a_device_fault(self) -> None:
        # The upstream returns {} when a frame does not validate (Benning_MM12_class.py:299-301, 357-359, 482-484);
        # the driver must not carry on with an empty reading.
        for method in ("getDeviceInfos", "getMeasurement_baseUnits", "getMeasurement_humanUnits"):
            with self.subTest(method=method):
                driver = self.driver()
                setattr(driver.native, method, lambda: {})
                with self.assertRaises(DriverFailed) as raised:
                    driver.read("main")
                self.assertEqual(raised.exception.code, "MHS.DEVICE.FAULTED")

    def test_the_teardown_closes_the_upstream_connection(self) -> None:
        driver = self.driver()
        self.assertFalse(driver.native.closed)
        driver.close()
        self.assertTrue(driver.native.closed)
        self.assertIn("closeConnection", driver.native.calls)


if __name__ == "__main__":
    unittest.main()
