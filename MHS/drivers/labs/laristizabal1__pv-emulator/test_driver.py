"""Acceptance run of the pv-emulator driver package; add cases, never remove the harness call."""

import json
import unittest
from pathlib import Path

from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PackageMetadata(unittest.TestCase):
    """Repository-specific checks that do not import the package or the clone."""

    def test_declares_the_upstream_source_and_risk(self) -> None:
        source = (HERE / "driver.py").read_text(encoding="utf-8")
        self.assertIn('native = "comm.bridge:EAPowerSupply"', source)
        self.assertIn('risk = "R2"', source)
        self.assertIn("safe_state=True", source)

    def test_lock_matches_the_card(self) -> None:
        card = json.loads((HERE / "task.json").read_text(encoding="utf-8"))
        lock = json.loads((HERE / "driver.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["package_id"], card["package_id"])
        self.assertEqual(lock["upstream"]["commit"], card["upstream"]["commit"])
        self.assertEqual(set(lock["backends"]), {"hardware", "fake"})


if __name__ == "__main__":
    unittest.main()
