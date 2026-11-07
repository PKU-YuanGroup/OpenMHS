"""Acceptance run of the Tecan Genesis package: the gate, plus cases for the frame and the command stack.

Keep the ``check_driver`` call.  The gate is expected to fail at G3 while the package is blocked on the missing
native stop (RESULT.json); the other cases exercise the fake transport without involving hardware.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
STX, ETX = 0x02, 0x03


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FrameAndStack(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_initialize_builds_the_group_feed_frames(self) -> None:
        driver = self.driver()
        result = driver.run_initialize()
        self.assertTrue(result["started"])
        self.assertEqual(result["commands"], ["M1:PIS", "R1:PIA"])
        frames = driver.native.written
        self.assertEqual(len(frames), 4)
        for frame in frames:
            self.assertEqual(frame[0], STX)
            self.assertEqual(frame[-1], 0x0A)
            self.assertEqual(frame[-3], ETX)
            checksum = 0
            for byte in frame[:-2]:
                checksum ^= byte
            self.assertEqual(checksum, frame[-2])
        self.assertEqual(driver.commands_added(), 2)
        self.assertEqual(driver.queued_commands(), 2)

    def test_move_uses_the_z_ticks_conversion(self) -> None:
        driver = self.driver()
        result = driver.move_liha_z(12.3)
        self.assertEqual(result["command"], "PAZ" + ",".join(["123"] * 8))
        self.assertTrue(result["started"])
        self.assertEqual(driver.queued_commands(), 1)


if __name__ == "__main__":
    unittest.main()
