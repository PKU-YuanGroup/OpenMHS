"""Acceptance run of the GP350 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
TORR_TO_PA = 133.32236842105263


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Commands(unittest.TestCase):
    """The lines and the replies this driver uses, checked on the fake transport."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_reads_use_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native._commands, ["DS IG", "IGB", "IGB", "DGS"])
        self.assertAlmostEqual(state["pressure"], 1.20e-07 * TORR_TO_PA, delta=1e-20)
        self.assertEqual((state["filament_1"], state["filament_2"], state["degas"]), (True, False, False))

    def test_a_write_sends_the_switch_command_and_verifies_the_readback(self) -> None:
        driver = self.driver()
        driver.write("main", {"filament_1": False, "degas": True})
        self.assertEqual(driver.native._commands[0], "IG1 OFF")
        self.assertEqual(driver.native._commands[1], "IGB")
        self.assertIn("DG ON", driver.native._commands)
        self.assertIn("DGS", driver.native._commands)
        state = driver.read("main", ["filament_1", "degas"])
        self.assertEqual(state, {"filament_1": False, "degas": True})

    def test_an_invalid_reply_is_accepted_only_when_the_state_already_matches(self) -> None:
        driver = self.driver()
        # filament 1 starts on; IG1 ON therefore answers INVALID (upstream simulator), and IGB confirms it is on.
        driver.write("main", {"filament_1": True})
        self.assertEqual(driver.native._commands[:2], ["IG1 ON", "IGB"])
        self.assertEqual(driver.read("main", ["filament_1"]), {"filament_1": True})

    def test_the_no_reading_sentinel_is_an_error(self) -> None:
        driver = self.driver()
        driver.native._pressure_reply = "9.90E+09"          # placeholder: the documented no-reading reply
        with self.assertRaises(DriverFailed):
            driver.read("main")

    def test_the_estop_switches_every_heater_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"filament_2": True, "degas": True})
        driver.estop("test")
        self.assertEqual(driver.native._commands[-3:], ["IG1 OFF", "IG2 OFF", "DG OFF"])
        state = driver.read("main", ["filament_1", "filament_2", "degas"])
        self.assertEqual(state, {"filament_1": False, "filament_2": False, "degas": False})


if __name__ == "__main__":
    unittest.main()
