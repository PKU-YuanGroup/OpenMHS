"""sim.lock.json: the record of a simulator package's passing gate on its real upstream (--backend sim).

The schema, the freshness rule (fake gate digest and upstream pin), the market's ``sim`` field and gate G1's
validation of the file.
"""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from mhs import market
from mhs.driver.check import run_check
from mhs.schema import default_store
from mhs.sim_lock import SIM_LOCK_FILE, market_sim, staleness

REPO = Path(__file__).resolve().parents[4]
EXAMPLE = REPO / "MHS" / "sdk" / "examples" / "thermostat"
COMMIT = "a" * 40
DIGEST = "sha256:" + "b" * 64

RECORD = {
    "openmhs": "0.9",
    "backend": "sim",
    "environment": {"platform": "linux/arm64", "base_image": "python:3.10-slim-bookworm", "python": "3.10",
                    "install": ["pip install ."], "constraints": ["pymunk<7"], "resolved": ["gymnasium==1.4.0"]},
    "upstream": {"commit": COMMIT},
    "gate": {"sdk_version": "0.9.0.dev0", "digest": "sha256:" + "c" * 64, "evidence_state": "contract_checked",
             "warnings": ["G5.BACKEND_SURFACE"]},
    "fake_gate_digest": DIGEST,
    "checked_at": "2026-11-17",
}


def _package(tmp: Path, *, status: str = "pass", digest: str = DIGEST, pin: str = COMMIT) -> Path:
    d = tmp / "pkg"
    d.mkdir()
    (d / "RESULT.json").write_text(json.dumps({"status": status, "gate": {"digest": digest, "failed": []}}))
    (d / "task.json").write_text(json.dumps({"upstream": {"commit": pin}}))
    return d


class SchemaTests(unittest.TestCase):
    def test_the_record_validates(self) -> None:
        self.assertEqual(default_store().validate(RECORD, "sim-lock.schema.json"), [])

    def test_a_record_without_gate_or_with_another_backend_is_invalid(self) -> None:
        for change in ({"gate": None}, {"backend": "fake"}):
            record = {k: v for k, v in copy.deepcopy(RECORD).items() if k not in change or change[k] is not None}
            record.update({k: v for k, v in change.items() if v is not None})
            self.assertNotEqual(default_store().validate(record, "sim-lock.schema.json"), [], change)


class FreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _with_record(self, **package: str) -> Path:
        d = _package(self.root, **package)
        (d / SIM_LOCK_FILE).write_text(json.dumps(RECORD))
        return d

    def test_no_record_is_neither_stale_nor_in_the_market(self) -> None:
        d = _package(self.root)
        self.assertEqual(staleness(d), [])
        self.assertIsNone(market_sim(d))

    def test_a_fresh_record_gives_the_market_field(self) -> None:
        d = self._with_record()
        self.assertEqual(staleness(d), [])
        self.assertEqual(market_sim(d), {"status": "contract_checked", "platform": "linux/arm64", "python": "3.10",
                                         "checked_at": "2026-11-17"})

    def test_a_changed_package_digest_makes_it_stale(self) -> None:
        d = self._with_record(digest="sha256:" + "d" * 64)
        self.assertTrue(any("fake_gate_digest" in r for r in staleness(d)))
        self.assertIsNone(market_sim(d))

    def test_a_moved_pin_makes_it_stale(self) -> None:
        d = self._with_record(pin="e" * 40)
        self.assertTrue(any("upstream.commit" in r for r in staleness(d)))
        self.assertIsNone(market_sim(d))

    def test_a_package_that_no_longer_passes_makes_it_stale(self) -> None:
        d = self._with_record(status="blocked")
        self.assertIn("RESULT.json does not say pass", staleness(d))


class GateAndMarketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.pkg = Path(self.tmp.name) / "thermostat"
        shutil.copytree(EXAMPLE, self.pkg, ignore=shutil.ignore_patterns("__pycache__", "check-report.json"))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _g1_codes(self) -> list[str]:
        report = run_check(self.pkg, "fake", write_report=False)
        g1 = next(g for g in report["gates"] if g["id"] == "G1")
        return [f["code"] for f in g1["findings"]]

    def test_g1_rejects_an_invalid_record(self) -> None:
        (self.pkg / SIM_LOCK_FILE).write_text(json.dumps({"backend": "sim"}))
        self.assertIn("G1.INVALID_FILE", self._g1_codes())

    def test_g1_accepts_a_valid_record(self) -> None:
        (self.pkg / SIM_LOCK_FILE).write_text(json.dumps(RECORD))
        self.assertNotIn("G1.INVALID_FILE", self._g1_codes())

    def test_the_market_entry_carries_sim_only_when_fresh(self) -> None:
        root = Path(self.tmp.name)
        # The tutorial is synthetic (upstream null); give this copy's card a pin so a record can match it.
        task = json.loads((self.pkg / "task.json").read_text())
        task["upstream"] = {**(task.get("upstream") or {}), "commit": COMMIT}
        (self.pkg / "task.json").write_text(json.dumps(task))
        result = json.loads((self.pkg / "RESULT.json").read_text())
        self.assertEqual(result["status"], "pass")
        self.assertNotIn("sim", market.build_entry(self.pkg, root))
        record = copy.deepcopy(RECORD)
        record["fake_gate_digest"] = result["gate"]["digest"]
        (self.pkg / SIM_LOCK_FILE).write_text(json.dumps(record))
        self.assertEqual(staleness(self.pkg), [])
        self.assertEqual(market.build_entry(self.pkg, root)["sim"]["platform"], "linux/arm64")
        record["fake_gate_digest"] = DIGEST   # the driver changed after the run
        (self.pkg / SIM_LOCK_FILE).write_text(json.dumps(record))
        self.assertNotIn("sim", market.build_entry(self.pkg, root))


if __name__ == "__main__":
    unittest.main()
