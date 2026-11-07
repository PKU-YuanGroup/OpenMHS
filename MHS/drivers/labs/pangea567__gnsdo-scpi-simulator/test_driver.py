"""Acceptance run of the GNSDO package: the gate, plus cases for the scalar command map and the four actions.

Add cases, never remove the check_driver call.  The assertions use the fake's placeholder values; they are test data
for this package, not device facts.
"""

import unittest
import time
from pathlib import Path

from mhs.adapter import load_driver
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent

READ_COMMANDS = [
    "*IDN?",
    "SYNC:LOCKED?",
    "SYNC:TINT?",
    "SYNC:HEALTH?",
    "GPS:SAT:TRAC:COUN?",
    "GPS:SAT:VIS:COUN?",
    "MEAS:TEMP?",
    "MEAS:VOLT?",
    "MEAS:POW?",
    "CSAC:TEMP?",
    "CSAC:STATUS?",
    "DIAG:LIFE:COUN?",
    "CSAC:LIFE?",
    "PTIME:LEAP:ACC?",
    "PTIME:OUTPUT?",
    "PTIME:DATE?",
    "PTIME:TIME?",
    "SYNC:HOLD:DUR?",
]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ScalarState(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_reads_use_the_scalar_commands_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written, READ_COMMANDS)
        self.assertEqual(state["identity"], "Jackson Labs, LN Rb GPSDO (PRE), Firmware Rev 1.17")
        self.assertTrue(state["sync_locked"])
        self.assertAlmostEqual(state["tint"], 1.2e-8)
        self.assertEqual(state["health"], "0x0")
        self.assertEqual(state["satellites_tracked"], 8)
        self.assertEqual(state["satellites_visible"], 12)
        self.assertAlmostEqual(state["pcb_temperature"], 42.5)
        self.assertAlmostEqual(state["tcxo_voltage"], 1.66)
        self.assertAlmostEqual(state["power_supply_voltage"], 11.7)
        self.assertAlmostEqual(state["csac_temperature"], 54.0)
        self.assertEqual(state["csac_status"], 0)
        self.assertEqual(state["lifetime"], 871)
        self.assertEqual(state["csac_lifetime"], 11247)
        self.assertEqual(state["leap_seconds"], 18)
        self.assertFalse(state["ptime_output"])
        self.assertEqual(state["holdover_duration"], "0,0")

    def test_no_multiline_composite_report_is_sent(self) -> None:
        driver = self.driver()
        driver.read("main")
        composites = {"SYNC?", "GPS?", "MEAS?", "DIAG?", "CSAC?", "PTIME?", "SYST:STAT?"}
        self.assertTrue(composites.isdisjoint(driver.native.written))

    def test_ambient_time_does_not_change_the_controlled_fake(self) -> None:
        driver = self.driver()
        fields = ["ptime_date", "ptime_time", "holdover_duration"]
        first = driver.read("main", fields)
        time.sleep(1.05)  # Cross an ambient second without advancing fixture time.
        self.assertEqual(driver.read("main", fields), first)
        self.assertEqual(first, {"ptime_date": "2000,1,1", "ptime_time": "12,0,0",
                                 "holdover_duration": "0,0"})

    def test_explicit_clock_advance_preserves_time_and_holdover_behaviour(self) -> None:
        driver = self.driver()
        driver.call("x-cap.pangea567.holdover.v1", {})
        before = driver.read("main", ["holdover_duration", "health"])
        self.assertEqual(before, {"holdover_duration": "0.0,1", "health": "0x4"})
        driver.native.advance_time(61.25)
        after = driver.read("main", ["ptime_time", "holdover_duration", "health"])
        self.assertEqual(after, {"ptime_time": "12,1,1", "holdover_duration": "61.2,1", "health": "0x14"})
        driver.call("x-cap.pangea567.holdover_recovery.v1", {})
        self.assertEqual(driver.read("main", ["holdover_duration", "health"]),
                         {"holdover_duration": "0,0", "health": "0x0"})


class Actions(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_holdover_and_recovery_change_the_lock_state(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.pangea567.holdover.v1", {}), {"initiated": True})
        self.assertEqual(driver.native.written[-1], "SYNC:HOLD:INIT")
        state = driver.read("main", ["sync_locked", "tint", "health", "csac_status"])
        self.assertFalse(state["sync_locked"])
        self.assertAlmostEqual(state["tint"], 8.5e-7)
        self.assertEqual(state["health"], "0x4")
        self.assertEqual(state["csac_status"], 1)
        self.assertEqual(driver.call("x-cap.pangea567.holdover_recovery.v1", {}), {"recovered": True})
        self.assertEqual(driver.native.written[-1], "SYNC:HOLD:REC:INIT")
        state = driver.read("main", ["sync_locked", "tint", "health", "csac_status"])
        self.assertTrue(state["sync_locked"])
        self.assertAlmostEqual(state["tint"], 1.2e-8)
        self.assertEqual(state["health"], "0x0")
        self.assertEqual(state["csac_status"], 0)

    def test_the_source_mode_and_ptime_commands_use_the_clone_syntax(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.pangea567.sync_source.v1", {"mode": "EXTERNAL"}),
                         {"accepted": True})
        self.assertEqual(driver.native.written[-1], "SYNC:SOUR:MODE EXTERNAL")
        self.assertEqual(driver.call("x-cap.pangea567.ptime_output.v1", {"enabled": True}),
                         {"accepted": True})
        self.assertEqual(driver.native.written[-1], "PTIME:OUTPUT ON")
        self.assertTrue(driver.read("main", ["ptime_output"])["ptime_output"])
        self.assertEqual(driver.call("x-cap.pangea567.ptime_output.v1", {"enabled": False}),
                         {"accepted": True})
        self.assertEqual(driver.native.written[-1], "PTIME:OUTPUT OFF")
        self.assertFalse(driver.read("main", ["ptime_output"])["ptime_output"])


if __name__ == "__main__":
    unittest.main()
