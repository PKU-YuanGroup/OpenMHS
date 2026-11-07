"""Synthetic tag-bridge fixture: the stock acceptance oracle."""
import unittest
from pathlib import Path

from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent


class FixtureGate(unittest.TestCase):
    def test_stock_gate(self):
        self.assertEqual(check_driver(HERE, backend="fake")["failed"], [])
