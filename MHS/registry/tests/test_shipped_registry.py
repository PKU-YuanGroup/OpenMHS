#!/usr/bin/env python3
"""Invariants of the committed registry: records, task cards, pilot pool, recipes, spot check.

Reads only files under MHS/ (works in a copy of MHS/ without the corpus).
"""
from __future__ import annotations

import contextlib
import glob
import io
import json
import os
import re
import sys
import unittest
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
MHS = os.path.abspath(os.path.join(REG, ".."))
sys.path.insert(0, REG)
sys.path.insert(0, os.path.join(MHS, "sdk", "src"))

import catalog_view as CV  # noqa: E402
import taskcards as TC  # noqa: E402
import validate as V  # noqa: E402
from mhs import _ids  # noqa: E402
from mhs.schema import SchemaStore  # noqa: E402

STORE = SchemaStore(os.path.join(MHS, "schema"), extra_roots=[os.path.join(REG, "schema")])
EXEMPLARS = ("gh.tiagocoutinho/julabo", "gh.thinksrs/srsinst.sr860", "gh.xarm-developer/xarm-python-sdk",
             "gh.farama-foundation/gymnasium")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class ShippedRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = {r["package_id"]: r for r in (load(p) for p in glob.glob(os.path.join(REG, "repos", "*", "*.json")))}
        cls.cards = TC.load_cards()

    def test_one_valid_card_per_record(self):
        self.assertEqual(len(self.records), 2967)
        self.assertEqual(set(self.cards), set(self.records))
        bad = [(pid, STORE.validate(c, "taskcard.schema.json")[:2]) for pid, c in self.cards.items()
               if STORE.validate(c, "taskcard.schema.json")]
        self.assertEqual(bad[:3], [])

    def test_dispatch_rule_and_blocked_helpers(self):
        for pid, card in self.cards.items():
            if card["decision"] in ("direct-driver", "family-config") and card["helper_status"] == "blocked":
                self.assertTrue(card["blocked_on"], pid)
            if card["quarantine"]:
                self.assertEqual(card["decision"], "skip", pid)
                self.assertIn("QUARANTINE", card["blocked_on"], pid)
        dispatchable = [c for c in self.cards.values() if TC.dispatchable_now(c)]
        # A card leaves the dispatchable set when its package records a result, so the cards with a result count too.
        finished = [c for c in self.cards.values() if c.get("package_status") in ("pass", "blocked", "skip-proposed")]
        self.assertGreater(len(dispatchable) + len(finished), 300)
        self.assertTrue(all(c["helper"] in ("PythonObjectDriver", "SerialDriver", "ScpiDriver", "GymnasiumDriver",
                                            "MujocoDriver", "RosDriver", "QcodesDriver", "OphydDriver",
                                            "McpClientDriver", "PyLabRobotDriver", "TagDriver", "Sila2Driver")
                            for c in dispatchable))

    # --- w1-waiting-routing (2026-11-05): Sila2Driver proves one source profile ---
    def test_only_the_pinned_phenix_exemplar_is_a_sila2_task(self):
        # triage rule 9 tags every repository that imports a SiLA library as family sila2, and G7 proves one
        # PhenixImager feature at one commit (mhs/driver/sila2_check.py): every other SiLA card needs a reviewed override
        from mhs.driver.sila2_check import SOURCE_COMMIT
        import triage as T
        sila = {pid: card for pid, card in self.cards.items()
                if card["family"] == "sila2" and card["decision"] in ("direct-driver", "family-config")}
        self.assertEqual(set(sila), {"gh.anguyen-23/sila-testing"})
        card = sila["gh.anguyen-23/sila-testing"]
        self.assertEqual((card["driver_dir"], card["upstream"]["commit"], card["helper"]),
                         (T.FAMILIES["sila2"].exemplar, SOURCE_COMMIT, "Sila2Driver"))
        record = self.records["gh.anguyen-23/sila-testing"]
        rule = "family sila2 is dispatchable only"
        self.assertFalse([e for e in V.check_card(card, record) if rule in e])
        moved = dict(card, upstream=dict(card["upstream"], commit="0" * 40))
        self.assertTrue([e for e in V.check_card(moved, record) if rule in e])
    # --- end w1-waiting-routing ---

    def test_no_device_below_its_class_risk_floor(self):
        violations = []
        for pid, rec in self.records.items():
            violations += [(pid, e) for e in V.check_device_plan(rec) if "CAP-017" in e or "KIND_MISMATCH" in e]
            card = self.cards[pid]
            if card["safety"]["risk_floor"] != CV.risk_floor(card["hints"]["candidate_classes"]):
                violations.append((pid, "card risk floor"))
        self.assertEqual(violations[:5], [])

    def test_hardware_first_and_no_physical_effect_text(self):
        dual = 0
        for pid, rec in self.records.items():
            modes = rec["modes"]
            if "hardware" in modes:
                self.assertEqual(modes[0], "hardware", pid)
                self.assertNotIn("no physical effect", json.dumps(rec).lower(), pid)
            if {"hardware", "simulated"} <= set(modes):
                dual += 1
                plan = rec["x-vendor"]["device_plan"]
                self.assertEqual(plan[1]["models"], [plan[0]["device_id"]], pid)
        self.assertGreater(dual, 100)

    def test_waves_and_ranks(self):
        by_wave = {}
        for card in self.cards.values():
            by_wave.setdefault(card["wave"], []).append(card["rank"])
        self.assertTrue(set(by_wave) <= set(TC.WAVES))
        for wave, ranks in by_wave.items():
            self.assertEqual(sorted(ranks), list(range(1, len(ranks) + 1)), wave)
        for pid in EXEMPLARS:
            self.assertEqual(self.cards[pid]["wave"], 0, pid)

    def test_pilot_candidates(self):
        doc = load(TC.PILOT_PATH)
        self.assertEqual(doc["count"], 40)
        ids = [c["package_id"] for c in doc["candidates"]]
        self.assertEqual(len(set(ids)), 40)
        for pid in EXEMPLARS:
            self.assertIn(pid, ids)
        buckets = Counter(c["bucket"] for c in doc["candidates"])
        self.assertEqual(set(buckets), set(TC.PILOT_BUCKETS))
        self.assertGreaterEqual(min(buckets.values()), 5)
        for item in doc["candidates"]:
            card = self.cards[item["package_id"]]
            self.assertEqual(item["task"], card)
            self.assertEqual(card["helper_status"], "available")
            self.assertEqual(card["blocked_on"], [])
            self.assertIn(card["wave"], (0, 1))

    def test_entry_symbols_are_typed_ast_symbols(self):
        for pid, card in self.cards.items():
            for sym in card["entry_symbols"]:
                # ast: the class is defined at file:line (validate.py checks the line with the corpus);
                # recon: a gym registration whose class is not defined in the clone;
                # override: named by an override entry (a recon proposal a maintainer accepted)
                self.assertIn(sym["confidence"], ("ast", "recon", "override"), pid)
                self.assertFalse(sym["file"].lower().startswith("readme"), pid)
                self.assertFalse(sym["file"].endswith("__init__.py") and sym["line"] == 1, pid)
            for cmd in card["install"]["commands"]:
                self.assertIn(cmd, ("pip install .", "pip install -r requirements.txt", "colcon build", "catkin_make"), pid)

    def test_validator_passes_without_the_corpus(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = V.main(["--no-corpus", "--quiet"])
        self.assertEqual(code, 0, out.getvalue()[-3000:])
        self.assertIn("RESULT: PASS", out.getvalue())

    def test_spotcheck_verdicts_are_recorded(self):
        path = os.path.join(REG, "tasks", "SPOTCHECK.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertTrue(text.startswith("# Task-card spot check"))
        rounds = re.split(r"^## (Round (\d+) \(seed \d+, [a-z ]+\))$", text, flags=re.MULTILINE)
        total = 0
        second = []     # the second verification's dispatchable rounds (5 to 9)
        for title, number, body in zip(rounds[1::3], rounds[2::3], rounds[3::3]):
            body = body.split("\n## ", 1)[0]
            rows = re.findall(r"^\| *\d+ *\| *`(gh\.[^`]+)` *\|.*\| *(correct|debatable|\*\*wrong\*\*) *\|", body,
                              re.MULTILINE)
            self.assertIn(len(rows), (20, 30), title)
            for pid, _verdict in rows:
                self.assertIn(pid, self.cards, title)
            acceptable = sum(1 for _p, v in rows if v in ("correct", "debatable"))
            if int(number) != 5:
                # round 5 measured the registry the second verification failed, before its fixes
                self.assertGreaterEqual(acceptable / len(rows), 0.9, title)
            if int(number) >= 5 and "dispatchable" in title:
                second.extend(rows)
            total += len(rows)
        self.assertEqual(total, 290)
        self.assertEqual(len(second), 120)
        self.assertGreaterEqual(sum(1 for _p, v in second if v != "**wrong**") / len(second), 0.9)


if __name__ == "__main__":
    unittest.main()
