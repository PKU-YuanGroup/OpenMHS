#!/usr/bin/env python3
"""Driver-package overlays, the aggregates builder and the validator's semantic checks (no corpus)."""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
MHS = os.path.abspath(os.path.join(REG, ".."))
sys.path.insert(0, REG)
sys.path.insert(0, os.path.join(MHS, "sdk", "src"))
sys.path.insert(0, HERE)

import build_index as BI  # noqa: E402
import overlays as OV  # noqa: E402
import validate as V  # noqa: E402
from mhs.schema import SchemaStore  # noqa: E402
from test_build_pipeline import run  # noqa: E402
from test_taskcards import COMMIT, entry, scan  # noqa: E402

STORE = SchemaStore(os.path.join(MHS, "schema"), extra_roots=[os.path.join(REG, "schema")])
DIGEST = "sha256:" + "ab" * 32


def write(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)


def lock_doc(commit=COMMIT, reviewed=None):
    return {"package_id": "gh.acme/bath", "upstream": {"repo_url": "https://github.com/acme/bath", "commit": commit,
                                                        "license_spdx": "MIT"},
            "backends": {"fake": ".fake:FakeBath"}, "sdk_version": "0.9.0.dev0",
            "authored_by": {"kind": "model", "model_id": "deepseek"}, "reviewed_by": reviewed}


GATE_IDS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9")


def report_doc(generated_at="2026-10-27T10:00:00.000Z", duration=1500.0, status="pass", digest=DIGEST):
    """A schema-valid passing check report (a gate run); ``generated_at`` and the durations differ per run."""
    return {"openmhs": "0.9", "package_id": "gh.acme/bath", "driver_dir": "MHS/drivers/labs/acme__bath",
            "backend": "fake", "sdk_version": "0.9.0.dev0", "generated_at": generated_at, "duration_ms": duration,
            "passed": True, "failed": [], "evidence_state": "contract_checked", "report_digest": digest,
            "gates": [{"id": gate, "name": gate, "status": status if gate == "G2" else "pass", "required": True,
                       "duration_ms": duration / 10, "findings": []} for gate in GATE_IDS]}


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "drivers")
        self.pkg = os.path.join(self.root, "labs", "acme__bath")

    def tearDown(self):
        self.tmp.cleanup()

    def test_pass_gives_contract_checked_only(self):
        write(os.path.join(self.pkg, "driver.lock.json"), lock_doc())
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "pass", "gate": {"digest": DIGEST, "failed": []}})
        before = OV.tree_digests(self.root)
        overlay = OV.load(self.root)["labs/acme__bath"]
        self.assertEqual(OV.tree_digests(self.root), before)        # reading never writes
        self.assertEqual(overlay.evidence_state(), "contract_checked")
        self.assertEqual(overlay.adapter_state(), "runnable")
        self.assertEqual(overlay.blocked_on(), [])
        self.assertEqual(OV.key_for("labs/acme/bath"), "labs/acme__bath")

    def test_hardware_checked_needs_a_reviewed_hardware_report(self):
        write(os.path.join(self.pkg, "driver.lock.json"), lock_doc())
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "pass", "gate": {"digest": DIGEST, "failed": []}})
        write(os.path.join(self.pkg, "check-report.json"), {"backend": "hardware", "passed": True,
                                                            "evidence_state": "hardware_checked", "report_digest": DIGEST})
        self.assertEqual(OV.load(self.root)["labs/acme__bath"].evidence_state(), "contract_checked")
        write(os.path.join(self.pkg, "driver.lock.json"),
              lock_doc(reviewed={"reviewer": "operator", "date": "2026-10-21", "scope": "hardware"}))
        self.assertEqual(OV.load(self.root)["labs/acme__bath"].evidence_state(), "hardware_checked")

    def test_a_record_does_not_depend_on_the_generated_gate_report(self):
        write(os.path.join(self.pkg, "driver.lock.json"), lock_doc())
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "pass", "gate": {"digest": DIGEST, "failed": []}})
        without = OV.load(self.root)["labs/acme__bath"]
        write(os.path.join(self.pkg, "check-report.json"), report_doc())          # a gate run wrote it
        with_report = OV.load(self.root)["labs/acme__bath"]
        self.assertIn("check-report.json", with_report.docs)                       # the validator still reads it
        self.assertEqual(with_report.to_vendor(), without.to_vendor())
        self.assertEqual(without.to_vendor()["files"], ["RESULT.json", "driver.lock.json"])
        rec_without, card_without, _d, _l = run(overlay=without)
        rec_with, card_with, _d2, _l2 = run(overlay=with_report)
        self.assertEqual(rec_with, rec_without)
        self.assertEqual(card_with, card_without)
        self.assertEqual([ref.rsplit("/", 1)[1] for ref in rec_with["evidence"]["provenance_refs"]], ["RESULT.json"])

    def test_a_hardware_report_is_named_as_the_evidence_it_is(self):
        write(os.path.join(self.pkg, "driver.lock.json"),
              lock_doc(reviewed={"reviewer": "operator", "date": "2026-10-21", "scope": "hardware"}))
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "pass", "gate": {"digest": DIGEST, "failed": []}})
        write(os.path.join(self.pkg, "check-report.json"), {"backend": "hardware", "passed": True,
                                                            "evidence_state": "hardware_checked", "report_digest": DIGEST})
        overlay = OV.load(self.root)["labs/acme__bath"]
        self.assertEqual(overlay.evidence_state(), "hardware_checked")
        self.assertIn("check-report.json", overlay.to_vendor()["files"])
        rec, _card, _d, _l = run(overlay=overlay)
        self.assertEqual([ref.rsplit("/", 1)[1] for ref in rec["evidence"]["provenance_refs"]],
                         ["RESULT.json", "check-report.json"])

    def test_blocked_result_feeds_blocked_on(self):
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "blocked", "blocked_on": ["INSTALL_FAILED"]})
        overlay = OV.load(self.root)["labs/acme__bath"]
        self.assertEqual(overlay.blocked_on(), ["INSTALL_FAILED"])
        self.assertIsNone(overlay.evidence_state())
        self.assertEqual(overlay.package_status(), "blocked")

    def test_package_status(self):
        write(os.path.join(self.pkg, "driver.lock.json"), lock_doc())
        self.assertEqual(OV.load(self.root)["labs/acme__bath"].package_status(), "in_progress")
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "pass", "gate": {"digest": DIGEST, "failed": []}})
        self.assertEqual(OV.load(self.root)["labs/acme__bath"].package_status(), "pass")
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "pass", "gate": {"failed": []}})   # no digest
        self.assertEqual(OV.load(self.root)["labs/acme__bath"].package_status(), "in_progress")
        # the validator compares the card's package_status with the overlay
        rec, card, _d, _lock = run()
        errors = V.check_overlays(OV.load(self.root), {card["package_id"]: card}, {"labs/acme__bath": rec}, STORE)
        self.assertIn("card package_status 'none' != overlay 'in_progress'", "\n".join(errors))

    def test_a_card_that_lags_a_package_is_a_warning_only_when_allowed(self):
        """A driver pull request cannot rebuild the registry: CI allows exactly the two lagging comparisons."""
        rec, card, _d, _lock = run()
        write(os.path.join(self.pkg, "driver.lock.json"), lock_doc())
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "pass", "gate": {"digest": DIGEST, "failed": []}})
        overlays = OV.load(self.root)
        strict = V.check_overlays(overlays, {card["package_id"]: card}, {"labs/acme__bath": rec}, STORE)
        self.assertTrue(any("card package_status 'none' != overlay 'pass'" in e for e in strict))
        self.assertTrue(any("record evidence" in e for e in strict))
        lagging = []
        tolerant = V.check_overlays(overlays, {card["package_id"]: card}, {"labs/acme__bath": rec}, STORE, stale=lagging)
        self.assertEqual(tolerant, [])
        self.assertEqual(len(lagging), 2)
        # what is wrong with the package itself stays an error
        write(os.path.join(self.pkg, "driver.lock.json"), lock_doc(commit="f" * 40))
        lagging = []
        errors = V.check_overlays(OV.load(self.root), {card["package_id"]: card}, {"labs/acme__bath": rec}, STORE, stale=lagging)
        self.assertTrue(any("commit != card upstream.commit" in e for e in errors))

    def test_validator_checks_overlay_integrity(self):
        rec, card, _d, _lock = run()
        write(os.path.join(self.pkg, "driver.lock.json"), lock_doc(commit="f" * 40))
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "pass", "gate": {"digest": DIGEST, "failed": []}})
        write(os.path.join(self.pkg, "task.json"), dict(card, decision="skip"))
        overlays = OV.load(self.root)
        errors = V.check_overlays(overlays, {card["package_id"]: card}, {"labs/acme__bath": rec}, STORE)
        text = "\n".join(errors)
        self.assertIn("driver.lock.json: commit != card upstream.commit", text)
        self.assertIn("task.json: decision", text)
        self.assertIn("record evidence 'static_scan' != overlay 'contract_checked'", text)
        orphan = OV.load(self.root)
        self.assertTrue(V.check_overlays(orphan, {}, {}, STORE)[0].endswith("no registry record (no task card)"))


class GateDigestTests(unittest.TestCase):
    """RESULT.json's gate digest survives re-running the gate: it is the digest of the report without its clock."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "drivers")
        self.pkg = os.path.join(self.root, "labs", "acme__bath")
        write(os.path.join(self.pkg, "driver.lock.json"), lock_doc())

    def tearDown(self):
        self.tmp.cleanup()

    def digest_errors(self):
        rec, card, _d, _lock = run()
        errors = V.check_overlays(OV.load(self.root), {card["package_id"]: card}, {"labs/acme__bath": rec}, STORE)
        return [e for e in errors if "gate digest" in e or "check-report" in e]

    def test_stable_digest_ignores_only_the_clock(self):
        from mhs.driver.check import stable_digest
        first, second = report_doc(), report_doc("2026-10-28T11:30:00.000Z", 987.6, digest="sha256:" + "cd" * 32)
        self.assertEqual(stable_digest(first), stable_digest(second))
        before = json.dumps(first, sort_keys=True)
        stable_digest(first)
        self.assertEqual(json.dumps(first, sort_keys=True), before)             # the report is not changed
        self.assertNotEqual(stable_digest(first), stable_digest(report_doc(status="warn")))
        changed = report_doc()
        changed["gates"][5]["findings"] = [{"code": "G6.NO_INPUT", "message": "no input", "severity": "warning"}]
        self.assertNotEqual(stable_digest(first), stable_digest(changed))
        self.assertTrue(stable_digest(first).startswith("sha256:"))

    def test_a_rerun_with_new_timestamps_keeps_result_json_valid(self):
        from mhs.driver.check import stable_digest
        recorded = report_doc()
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "pass", "gate": {"digest": stable_digest(recorded),
                                                                                "failed": []}})
        write(os.path.join(self.pkg, "check-report.json"), recorded)
        self.assertEqual(self.digest_errors(), [])
        # the gate runs again: a new generated_at, new durations and so a new report_digest
        write(os.path.join(self.pkg, "check-report.json"),
              report_doc("2026-10-29T08:00:00.000Z", 2222.2, digest="sha256:" + "ef" * 32))
        self.assertEqual(self.digest_errors(), [])

    def test_the_reports_own_digest_is_still_accepted(self):
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "pass", "gate": {"digest": DIGEST, "failed": []}})
        write(os.path.join(self.pkg, "check-report.json"), report_doc(digest=DIGEST))
        self.assertEqual(self.digest_errors(), [])

    def test_a_missing_report_is_not_an_error(self):
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "pass", "gate": {"digest": DIGEST, "failed": []}})
        self.assertFalse(os.path.exists(os.path.join(self.pkg, "check-report.json")))
        self.assertEqual(self.digest_errors(), [])

    def test_a_changed_gate_result_makes_result_json_stale(self):
        from mhs.driver.check import stable_digest
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "pass",
                                                      "gate": {"digest": stable_digest(report_doc()), "failed": []}})
        write(os.path.join(self.pkg, "check-report.json"), report_doc(status="warn"))      # G2 now warns
        errors = self.digest_errors()
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("RESULT.json gate digest", errors[0])
        self.assertIn("re-run the gate", errors[0])


class IndexTests(unittest.TestCase):
    def test_render_is_deterministic_and_uses_records_only(self):
        rec, _card, _d, _l = run()
        other, _c, _d2, _l2 = run(repo="toy")
        texts = BI.render([other, rec])
        self.assertEqual(texts, BI.render([rec, other]))
        index = json.loads(texts[BI.INDEX_JSON])
        self.assertEqual(index["generated_at"], rec["updated_at"])
        self.assertEqual([r["package_id"] for r in index["records"]], ["gh.acme/bath", "gh.acme/toy"])
        first = index["records"][0]
        self.assertEqual((first["strategy"], first["commit"], first["task_card"]),
                         ("direct-driver", COMMIT, "tasks/labs/acme__bath.json"))
        self.assertEqual(index["stats"]["total"], 2)
        self.assertEqual(len(texts[BI.INDEX_JSONL].splitlines()), 2)
        self.assertTrue(texts[BI.RECORDS_CSV].startswith("id,registry_id,package_id,"))


class ValidatorSemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = V.load_core_capabilities()
        cls.rec, cls.card, _d, cls.lock = run()

    def errs(self, rec):
        return V.check_record_semantics(rec, self.core, None, self.lock)[0]

    def test_clean_record_passes(self):
        self.assertEqual(self.errs(self.rec), [])
        self.assertEqual(V.check_card(self.card, self.rec), [])

    def test_chinese_outside_x_vendor_is_an_error(self):
        rec = copy.deepcopy(self.rec)
        rec["interfaces"].append("串口")
        self.assertTrue(any("non-English" in e for e in self.errs(rec)))
        rec = copy.deepcopy(self.rec)
        rec["domains"] = ["chemistry [zh]"]
        self.assertTrue(any("non-English" in e for e in self.errs(rec)))

    def test_hardware_rules(self):
        rec = copy.deepcopy(self.rec)
        rec["modes"] = list(reversed(rec["modes"]))
        self.assertTrue(any("hardware must come first" in e for e in self.errs(rec)))
        rec = copy.deepcopy(self.rec)
        rec["description"] += " Pause the simulation; no physical effect."
        self.assertTrue(any("no physical effect" in e for e in self.errs(rec)))

    def test_quarantine_commit_and_device_plan(self):
        rec = copy.deepcopy(self.rec)
        rec["quarantine"] = True
        self.assertTrue(any(e.startswith("quarantine:") for e in self.errs(rec)))
        rec = copy.deepcopy(self.rec)
        rec["source"]["commit"] = "e" * 40
        self.assertTrue(any("corpus lock" in e for e in self.errs(rec)))
        rec = copy.deepcopy(self.rec)
        rec["x-vendor"]["device_plan"][0]["resources"] = [{"kind": "robot.arm", "capabilities": ["cap.thermal.setpoint.v1"]}]
        self.assertTrue(any("KIND_MISMATCH" in e for e in self.errs(rec)))
        rec = copy.deepcopy(self.rec)
        rec["x-vendor"]["device_plan"][0]["risk_floor"] = "R0"
        errs = self.errs(rec)
        self.assertTrue(any("CAP-017" in e for e in errs), errs)
        rec = copy.deepcopy(self.rec)
        rec["x-vendor"]["device_plan"][1]["models"] = []
        self.assertTrue(any("models" in e for e in self.errs(rec)))

    def test_card_checks(self):
        card = copy.deepcopy(self.card)
        card["safety"]["risk_floor"] = "R0"
        self.assertTrue(any("catalogue floor" in e for e in V.check_card(card, self.rec)))
        card = copy.deepcopy(self.card)
        card["wave"] = 7
        self.assertTrue(any("wave" in e for e in V.check_card(card, self.rec)))
        card = copy.deepcopy(self.card)
        card["hints"]["candidate_classes"] = ["cap.world.state.v1"]
        card["safety"]["risk_floor"] = "R0"
        self.assertTrue(any("deprecated" in e for e in V.check_card(card, self.rec)))

    def test_recipe_layout(self):
        good = "- bridge_status: `available`\n\n```\nmhs serve <driver-dir>\n```\n"
        self.assertEqual(V.check_recipe_layout(good), [])
        bad = good + "```\npython -m mhs.bridge.gymnasium --adapter mhs/mhs-adapter.json\n```\n"
        self.assertTrue(V.check_recipe_layout(bad))
        self.assertTrue(V.check_recipe_layout("mhs serve <driver-dir>\n"))   # no bridge_status line


if __name__ == "__main__":
    unittest.main()
