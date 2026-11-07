"""Acceptance run of the tutorial package: add cases, never remove the harness call."""

import unittest
from pathlib import Path

from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


if __name__ == "__main__":
    unittest.main()
