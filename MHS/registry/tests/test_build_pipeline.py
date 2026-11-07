#!/usr/bin/env python3
"""The record path of build_registry.py on synthetic inputs (no corpus): triage -> record -> card -> record.

Covers the WP-10 record rules: hardware-first dual-mode devices linked by
``models``, never "no physical effect" on a hardware record, ``source.commit``
from the lock, SPDX licence and class, no Chinese outside ``x-vendor``,
``registry_id`` from ``mhs._ids``, structural simulator families, triaged tier,
blocker codes and the card-derived next action.
"""
from __future__ import annotations

import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
MHS = os.path.abspath(os.path.join(REG, ".."))
sys.path.insert(0, REG)
sys.path.insert(0, os.path.join(MHS, "sdk", "src"))
sys.path.insert(0, HERE)

import build_registry as BR  # noqa: E402
import licenses as L  # noqa: E402
import taskcards as TC  # noqa: E402
import triage as T  # noqa: E402
import validate as V  # noqa: E402
from mhs import _ids  # noqa: E402
from mhs.schema import SchemaStore  # noqa: E402
from test_taskcards import COMMIT, entry, scan  # noqa: E402

STORE = SchemaStore(os.path.join(MHS, "schema"), extra_roots=[os.path.join(REG, "schema")])
OLD_SCAN = {"files": 12, "build_systems": ["python"], "markers": {}, "languages": ["Python"], "readme": "README.md",
            "readme_head": "", "build_files": ["pyproject.toml"], "license_file": "LICENSE", "entry_evidence": [],
            "ext_counts": {".py": 5}}


def catalog_row(**over):
    row = {"_row": 7, "owner": "acme", "repo_name": "bath", "repo_url": "https://github.com/acme/bath",
           "track": "lab_instrument", "category": "设备后端", "adapter_role": "设备SDK", "domain": "",
           "backend_family": "", "description_zh": "恒温槽驱动", "integration_interfaces": "Python SDK; 串口",
           "license": "unknown", "language": "Python", "simulation_available": "partial", "hardware_free": "no",
           "stars": "12", "blockers": "需要真实设备", "master_id": "m1", "minimal_adapter_entry": "unknown",
           "archived": "false", "runtime_requirements": "unknown", "evidence_urls": ""}
    row.update(over)
    return row


def run(track="labs", owner="acme", repo="bath", row=None, source_scan=None, overrides=None, lock_commit=COMMIT,
        overlay=None):
    row = catalog_row() if row is None else row
    base = BR.make_record(track, owner, repo, row, "exact", dict(OLD_SCAN), [], None, None)
    base["registry_id"] = BR.REGISTRY_ID
    lock = {"repo_url": f"https://github.com/{owner}/{repo}", "commit": lock_commit,
            "local_path": f"{track}/{owner}/{repo}", "package_id": base["package_id"]}
    f = T.facts_from_record(base, None, lock, source_scan or scan([entry()]), {}, None)
    decision = T.triage([f], overrides or {})[f.package_id]
    lscan = f.scan["license"]
    lic = L.resolve(base["license"], lscan["spdx"], lscan["file"], f.scan["install"]["declared_license"])
    rec = BR.finalize_record(base, decision, f, lock, lic, overlay, None)
    card = TC.build_card(rec, decision, f, lock, lic, overlay.blocked_on() if overlay else (),
                         row.get("runtime_requirements", ""), overlay.package_status() if overlay else "none")
    TC.assign_waves({f.package_id: card}, {f.package_id: decision}, {f.package_id: f}, {f.package_id: rec["stars"]},
                    pilot_size=0)
    BR.complete_record(rec, card, decision, overlay, row, dict(OLD_SCAN), track, owner, repo)
    return rec, card, decision, lock


class RecordPathTests(unittest.TestCase):
    def assert_valid(self, rec, lock):
        self.assertEqual(STORE.validate(rec, "registry-record.schema.json"), [])
        errs, _ = V.check_record_semantics(rec, V.load_core_capabilities(), None, lock)
        self.assertEqual(errs, [])

    def test_direct_driver_record(self):
        mock = {"kind": "class", "file": "bath/sim.py", "line": 3, "symbol": "bath.sim:SimBath"}
        rec, card, decision, lock = run(source_scan=scan([entry()], mocks=[mock]))
        self.assert_valid(rec, lock)
        self.assertEqual(decision.strategy, "direct-driver")
        self.assertEqual(rec["registry_id"], _ids.REGISTRY_ID)
        self.assertEqual(rec["integration"]["strategy"], "direct-driver")
        self.assertEqual(rec["modes"], ["hardware", "simulated"])         # an upstream simulator: dual mode
        plan = rec["x-vendor"]["device_plan"]
        self.assertEqual([d["mode"] for d in plan], ["hardware", "simulated"])
        self.assertEqual(plan[1]["models"], [plan[0]["device_id"]])
        self.assertTrue(plan[0]["device_id"].startswith(f"mhs://{_ids.REGISTRY_ID}/labs/acme__bath/"))
        self.assertTrue(plan[0]["estop_required"])
        self.assertEqual(plan[0]["risk_floor"], "R2")                      # thermal.setpoint in the catalogue
        self.assertEqual(rec["source"], {"repo_url": "https://github.com/acme/bath", "commit": COMMIT})
        self.assertEqual((rec["license"], rec["license_spdx"], rec["license_class"]), ("MIT", "MIT", "permissive"))
        self.assertEqual(rec["x-vendor"]["license"]["source"], "license-file")
        self.assertEqual(rec["x-vendor"]["catalog"]["license_raw"], "unknown")
        self.assertEqual(rec["adapter"]["manifest_ref"], None)
        self.assertEqual(rec["capabilities_offered"], card["hints"]["candidate_classes"])
        self.assertEqual((rec["wave"], rec["rank"], rec["blocked_on"]), (card["wave"], card["rank"], []))
        self.assertIn(card["acceptance"], rec["integration"]["next_action"])
        self.assertNotIn("no physical effect", str(rec).lower())
        self.assertEqual(rec["ring"], 2)

    def test_chinese_catalogue_text_stays_in_x_vendor(self):
        rec, _card, _d, lock = run()
        self.assertEqual(V.check_english(rec), [])
        self.assertEqual(rec["x-vendor"]["catalog"]["blockers_raw"], "需要真实设备")
        self.assertEqual(rec["x-vendor"]["catalog"]["description_zh"], "恒温槽驱动")
        self.assertNotIn("串口", " ".join(rec["interfaces"]))

    def test_simulator_family_needs_a_structural_marker(self):
        row = catalog_row(backend_family="Isaac Sim", category="完整环境", adapter_role="任务环境")
        rec, _c, decision, lock = run(row=row, source_scan=scan([], imports=("numpy",)))
        self.assertEqual(rec["x-vendor"]["classification"]["catalog_family"], "isaac-sim")
        self.assertEqual(rec["families"], ["other"])
        self.assertIn("no structural marker", rec["x-vendor"]["classification"]["family_note"])
        rec2, _c, _d, _l = run(row=row, source_scan=scan([], imports=("isaacgym",)))
        self.assertEqual(rec2["families"], ["isaac-gym"])           # the family the code shows

    def test_triage_family_wins_and_tier_follows_the_decision(self):
        gym = [{"id": "Toy-v1", "entry_point": "toy.env:ToyEnv", "file": "toy/__init__.py", "line": 3}]
        rec, card, decision, lock = run(repo="toy", source_scan=scan([], gym=gym, imports=("gymnasium",)))
        self.assertEqual((decision.strategy, decision.family), ("family-config", "gymnasium"))
        self.assertEqual(rec["families"], ["gymnasium"])
        self.assertEqual(rec["modes"], ["simulated"])
        self.assert_valid(rec, lock)
        skip = catalog_row(category="辅助工具", adapter_role="外围工具")      # auxiliary tool, peripheral tool
        rec2, card2, d2, lock2 = run(row=skip, source_scan=scan([entry()]))
        self.assertEqual(d2.strategy, "skip")
        self.assertEqual((rec2["tier"], rec2["modes"], rec2["capabilities_offered"]), ("D", [], []))
        self.assertNotIn("recipe", rec2["integration"])
        self.assertTrue(rec2["integration"]["next_action"].startswith("Not integrated:"))
        self.assertTrue(any(b.startswith("NOT_A_DEVICE") for b in rec2["integration"]["blockers"]))
        self.assert_valid(rec2, lock2)

    def test_blocked_helper_codes(self):
        # tag-bridge has a helper since 2026-11-04; pin a missing helper so the blocker path stays covered.
        missing = T.Family("tag-bridge", None, "helper:tag-bridge", None)
        f_scan = scan([entry()], imports=("pymodbus",))
        with unittest.mock.patch.dict(T.FAMILIES, {"tag-bridge": missing}):
            rec, card, decision, lock = run(source_scan=f_scan)
        self.assertEqual(decision.family, "tag-bridge")
        self.assertEqual(rec["blocked_on"], ["helper:tag-bridge"])
        self.assertIn("HELPER_MISSING: helper:tag-bridge", rec["integration"]["blockers"])
        self.assertTrue(rec["integration"]["next_action"].startswith("Wait for helper:tag-bridge"))
        self.assertEqual(rec["families"], ["tag-bridge"])
        self.assertEqual(rec["wave"], TC.WAVE_HELPER)
        self.assert_valid(rec, lock)

    def test_final_modes_put_hardware_first(self):
        d = T.Decision(package_id="gh.a/b", strategy="untriaged", role="framework", reason_code="untriaged:x", rule=11)
        f = T.RepoFacts(package_id="gh.a/b", local_path="labs/a/b", track="labs", owner="a", repo="b",
                        scan=scan([]))
        self.assertEqual(BR.final_modes({"tier": "B", "modes": ["simulated", "hardware"]}, d, f, None),
                         ["hardware", "simulated"])
        self.assertEqual(BR.final_modes({"tier": "D", "modes": ["simulated"]}, d, f, None), [])
        twin = T.Decision(package_id="gh.a/b", strategy="family-config", role="twin-candidate", reason_code="family:mujoco",
                          rule=9, family="mujoco")
        self.assertEqual(BR.final_modes({"tier": "B", "modes": ["hardware", "simulated"]}, twin, f, None), ["simulated"])

    def test_simulation_catalogue_rows_get_no_hardware_mode_without_a_hardware_transport(self):
        model = catalog_row(category="设备后端", adapter_role="测量模型")   # device backend / measurement model
        d = T.Decision(package_id="gh.acme/bath", strategy="untriaged", role="device-driver",
                       reason_code="untriaged:weak_entry", rule=11)
        f = T.RepoFacts(package_id="gh.acme/bath", local_path="labs/acme/bath", track="labs", owner="acme", repo="bath",
                        catalog={"category": model["category"], "adapter_role": model["adapter_role"]},
                        scan=scan([dict(entry(), transport=["socket"])]))
        self.assertEqual(BR.final_modes({"tier": "B", "modes": ["hardware", "simulated"]}, d, f, None), ["simulated"])
        f.scan = scan([dict(entry(), transport=["pyvisa"])])
        self.assertEqual(BR.final_modes({"tier": "B", "modes": ["hardware"]}, d, f, None), ["hardware"])

    def test_overlay_status_drives_next_action_and_dispatch(self):
        import overlays as OV
        passed = OV.Overlay(key="labs/acme__bath", path="MHS/drivers/labs/acme__bath",
                            docs={"RESULT.json": {"status": "pass", "gate": {"digest": "sha256:" + "ab" * 32,
                                                                              "failed": []}}})
        rec, card, _d, lock = run(overlay=passed)
        self.assertEqual(card["package_status"], "pass")
        self.assertFalse(TC.dispatchable_now(card))
        self.assertTrue(rec["integration"]["next_action"].startswith("Maintain MHS/drivers/labs/acme__bath"))
        self.assertNotIn("Write the", rec["integration"]["next_action"])
        self.assertEqual((rec["ring"], rec["adapter"]["state"], rec["evidence"]["state"]),
                         (1, "runnable", "contract_checked"))
        import build_index as BI
        self.assertFalse(BI.dispatchable_now(rec))
        self.assert_valid(rec, lock)
        blocked = OV.Overlay(key="labs/acme__bath", path="MHS/drivers/labs/acme__bath",
                             docs={"RESULT.json": {"status": "blocked", "blocked_on": ["INSTALL_FAILED"]}})
        rec2, card2, _d2, _l2 = run(overlay=blocked)
        self.assertEqual((card2["package_status"], card2["blocked_on"]), ("blocked", ["INSTALL_FAILED"]))
        self.assertIn("is blocked on INSTALL_FAILED", rec2["integration"]["next_action"])
        self.assertIn("INSTALL_FAILED", rec2["integration"]["blockers"])

    def test_near_empty_card_is_routed_to_recon(self):
        rec, card, _d, lock = run(source_scan=scan([entry(methods=("run",), score=14)], root_files=()))
        self.assertEqual(card["blocked_on"], [])                         # an entry symbol exists: still dispatchable
        rec2, card2, _d2, lock2 = run(row=catalog_row(), source_scan=scan([], root_files=()),
                                      overrides={"gh.acme/bath": {"package_id": "gh.acme/bath", "strategy": "direct-driver",
                                                                  "role": "device-driver", "family": "python-object",
                                                                  "justification": "a flagship SDK the scan cannot read"}})
        self.assertEqual(card2["blocked_on"], [TC.RECON_BLOCK])
        self.assertEqual(card2["wave"], TC.WAVE_RECON)
        self.assertTrue(rec2["integration"]["next_action"].startswith("Recon first"))
        self.assertTrue(any(b.startswith("NEEDS_RECON") for b in rec2["integration"]["blockers"]))

    def test_build_date_ignores_source_date_epoch(self):
        saved = {k: os.environ.get(k) for k in ("SOURCE_DATE_EPOCH", "MHS_REGISTRY_DATE")}
        try:
            os.environ["SOURCE_DATE_EPOCH"] = "1700000000"
            os.environ.pop("MHS_REGISTRY_DATE", None)
            self.assertEqual(BR.build_date(), BR.DEFAULT_DATE)
            os.environ["MHS_REGISTRY_DATE"] = "2027-01-01T00:00:00Z"
            self.assertEqual(BR.build_date(), "2027-01-01T00:00:00Z")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_uncloned_rows_are_english_with_originals_in_x_vendor(self):
        row = catalog_row(category="完整环境", adapter_role="任务环境", priority="参考")
        by_key = {("acme", "bath"): row}
        notes = {"https://github.com/acme/bath": {"status": "unavailable", "note": "原地址返回 404"}}
        rows = BR.build_uncloned(by_key, [], notes)
        self.assertEqual(len(rows), 1)
        u = rows[0]
        self.assertEqual(V.check_english({k: v for k, v in u.items() if k != "x-vendor"}), [])
        self.assertEqual(u["priority"], "reference")
        self.assertEqual(u["x-vendor"]["analyst_note_zh"], "原地址返回 404")
        self.assertIn("unavailable", u["analyst_note"])

    def test_registry_identifiers(self):
        self.assertEqual(BR.REGISTRY_ID, _ids.REGISTRY_ID)
        self.assertEqual(TC.CARD_SCHEMA, _ids.SCHEMA_BASE + "taskcard.schema.json")
        self.assertNotIn("modelhardwarestandard", BR.REGISTRY_ID + TC.CARD_SCHEMA + V.REGISTRY_ID)


if __name__ == "__main__":
    unittest.main()
