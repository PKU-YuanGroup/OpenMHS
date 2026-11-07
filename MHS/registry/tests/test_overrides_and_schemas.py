#!/usr/bin/env python3
"""Curated overrides, the task-card and override schemas, and catalogue-derived risk.

Reads only files under MHS/ (works in a copy of MHS/ without the corpus).
Schemas are checked with the SDK validator (mhs.schema), which resolves the
relative ``defs.schema.json`` references against MHS/schema.
"""
from __future__ import annotations

import copy
import glob
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
MHS = os.path.abspath(os.path.join(REG, ".."))
sys.path.insert(0, REG)
sys.path.insert(0, os.path.join(MHS, "sdk", "src"))

import catalog_view as CV  # noqa: E402
import family_data as FD  # noqa: E402
import triage as T  # noqa: E402
from mhs import _ids  # noqa: E402
from mhs.schema import SchemaStore  # noqa: E402

CARD_EXAMPLE = os.path.join(REG, "schema", "examples", "taskcard.thermal-bath.json")
APPENDIX_D = os.path.join(MHS, "spec", "appendix-d-anthropic-mhs.md")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


STORE = SchemaStore(os.path.join(MHS, "schema"), extra_roots=[os.path.join(REG, "schema")])


class OverrideFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = sorted(glob.glob(os.path.join(T.OVERRIDES_DIR, "*.json")))
        cls.overrides = T.load_overrides()
        cls.package_ids = set()
        for path in glob.glob(os.path.join(REG, "repos", "*", "*.json")):
            cls.package_ids.add(load(path)["package_id"])

    def test_every_file_validates_against_the_override_schema(self):
        self.assertTrue(self.files)
        for path in self.files:
            with self.subTest(file=os.path.basename(path)):
                self.assertEqual(STORE.validate(load(path), "overrides.schema.json"), [])

    def test_the_curated_repos_are_not_lost(self):
        # About one hundred curated entries, and more as reviews correct card shapes and recon results arrive
        # (MHS/handoff/PLAYBOOK.md sections 3 and 7), so only the floor is fixed.
        self.assertGreaterEqual(len(self.overrides), 90)

    def test_every_override_targets_a_registry_record(self):
        self.assertEqual(T.unknown_overrides(self.overrides, self.package_ids), [])

    def test_entries_are_sorted_and_justified_in_one_line(self):
        for path in self.files:
            ids = [o["package_id"] for o in load(path)["overrides"]]
            self.assertEqual(ids, sorted(ids), os.path.basename(path))
        for pid, item in self.overrides.items():
            self.assertRegex(item["justification"], r"^[^\n]{10,240}$", pid)
            self.assertIsNone(re.search(r"[一-鿿]", item["justification"]), pid)

    def test_exemplars_are_wave_zero_and_dispatchable(self):
        want = {
            "gh.tiagocoutinho/julabo": ("direct-driver", "python-object"),
            "gh.thinksrs/srsinst.sr860": ("family-config", "scpi"),
            "gh.xarm-developer/xarm-python-sdk": ("direct-driver", "python-object"),
            "gh.farama-foundation/gymnasium": ("family-config", "gymnasium"),
        }
        for pid, (strategy, family) in want.items():
            item = self.overrides[pid]
            self.assertEqual((item["strategy"], item["family"], item.get("wave")), (strategy, family, 0), pid)
            self.assertIsNotNone(T.FAMILIES[family].helper, pid)

    def test_the_schema_admits_reviewed_classes_and_a_publication_review_only_as_designed(self):
        def doc(**extra):
            item = {"package_id": "gh.acme/gizmo", "strategy": "family-config", "role": "device-driver",
                    "family": "ros", "justification": "Model review: the node only publishes camera frames."}
            item.update(extra)
            return {"overrides_version": "0.9", "title": "t", "overrides": [item]}
        ok = doc(capability_classes=["cap.sensing.image.v1"], publish_review="required", omit_sim_contract=True)
        self.assertEqual(STORE.validate(ok, "overrides.schema.json"), [])
        for bad in (doc(capability_classes=[]), doc(capability_classes=["cap.sensing.image"]),
                    doc(capability_classes=["cap.sensing.image.v1"] * 2), doc(publish_review="not_required"),
                    doc(omit_sim_contract=False),
                    doc(strategy="skip", family=None, capability_classes=["cap.sensing.image.v1"]),
                    doc(strategy="skip", family=None, omit_sim_contract=True)):
            if bad["overrides"][0].get("family") is None:
                bad["overrides"][0].pop("family", None)
            with self.subTest(bad=bad["overrides"][0]):
                self.assertTrue(STORE.validate(bad, "overrides.schema.json"))
        # every reviewed class in the shipped overrides is a stable catalogue class (build_registry.py refuses others)
        for pid, item in self.overrides.items():
            for cap in item.get("capability_classes", []):
                self.assertIn((CV.catalog().get(cap) or {}).get("status"), ("stable", "active"), (pid, cap))

    def test_partner_names_come_from_appendix_d(self):
        with open(APPENDIX_D, encoding="utf-8") as fh:
            table = fh.read()
        partners = {item["partner"] for item in self.overrides.values() if item.get("partner")}
        self.assertTrue(partners)
        for name in partners:
            key = re.split(r"[ (/]", name)[0]
            self.assertIn(key, table, name)


class TaskCardSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.card = load(CARD_EXAMPLE)

    def errors(self, card):
        return STORE.validate(card, "taskcard.schema.json")

    def mutate(self, **changes):
        card = copy.deepcopy(self.card)
        for key, value in changes.items():
            if "." in key:
                outer, inner = key.split(".", 1)
                card[outer][inner] = value
            else:
                card[key] = value
        return card

    def test_schema_ids_use_the_project_namespace(self):
        for name in ("taskcard.schema.json", "overrides.schema.json"):
            doc = load(os.path.join(REG, "schema", name))
            self.assertEqual(doc["$id"], _ids.SCHEMA_BASE + name)

    def test_example_card_validates(self):
        self.assertEqual(self.errors(self.card), [])

    def test_card_fields_follow_the_handoff_format(self):
        schema = load(os.path.join(REG, "schema", "taskcard.schema.json"))
        expected = {"card_version", "package_id", "track", "local_path", "driver_dir", "upstream", "decision",
                    "reason_code", "role", "family", "helper", "helper_status", "blocked_on", "quarantine",
                    "variant_of", "wave", "rank", "exemplar", "entry_symbols", "install", "mock_strategy", "hints",
                    "safety", "needs_recon", "timebox_min", "acceptance", "skip_reason", "publish_review"}
        self.assertEqual(set(schema["required"]), expected)
        # package_status and models are generated on every card but optional, so a package's task.json from an
        # earlier card stays valid; companions (user decision 2026-11-05) appears only on a card whose reviewed
        # override declares companion sources
        self.assertEqual(set(schema["properties"]) - {"$schema"}, expected | {"package_status", "models", "companions"})

    def test_blocked_helper_needs_blocked_on(self):
        self.assertTrue(self.errors(self.mutate(helper_status="blocked", helper=None)))
        self.assertEqual(self.errors(self.mutate(helper_status="blocked", helper=None, blocked_on=["helper:ros"])), [])

    def test_quarantine_only_on_skip_cards(self):
        self.assertTrue(self.errors(self.mutate(quarantine=True, blocked_on=["QUARANTINE"])))
        ok = self.mutate(decision="skip", reason_code="skip:quarantine", quarantine=True, blocked_on=["QUARANTINE"],
                         skip_reason="download lure", family=None, helper=None, helper_status=None)
        self.assertEqual(self.errors(ok), [])
        ok["blocked_on"] = []
        self.assertTrue(self.errors(ok))

    def test_publish_review_follows_the_licence_class(self):
        for cls in ("network-copyleft", "source-available", "proprietary", "unknown"):
            card = self.mutate(**{"upstream.license_class": cls})
            self.assertTrue(self.errors(card), cls)
            card["publish_review"] = "required"
            self.assertEqual(self.errors(card), [], cls)
        self.assertEqual(self.errors(self.mutate(**{"upstream.license_class": "copyleft"})), [])

    def test_other_constraints(self):
        bad = [
            self.mutate(decision="skip"),                                   # skip without skip_reason
            self.mutate(variant_of="gh.example/upstream"),                  # variant on a dispatched card
            self.mutate(**{"upstream.commit": None}),                       # dispatched card without a pin
            self.mutate(acceptance="python3 -m mhs.driver check elsewhere"),
            self.mutate(helper="BridgeDriver"),
            self.mutate(entry_symbols=[{"symbol": "pkg/mod.py", "file": "pkg/mod.py", "line": 1, "confidence": "ast"}]),
            self.mutate(hints={"reads": [], "writes": [], "actions": [], "candidate_classes": ["thermal"]}),
            self.mutate(extra_field=True),
        ]
        for card in bad:
            with self.subTest(card={k: card[k] for k in card if card[k] != self.card.get(k)}):
                self.assertTrue(self.errors(card))


class CatalogueRiskTests(unittest.TestCase):
    def test_private_risk_and_hint_tables_are_gone(self):
        self.assertFalse(hasattr(FD, "CAP_RISK"))
        self.assertFalse(hasattr(FD, "CAP_HINT_RULES"))
        with open(os.path.join(REG, "family_data.py"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("CAP_RISK", text)
        self.assertNotIn("CAP_HINT_RULES", text)

    def test_risk_floor_and_verb_come_from_the_catalogue(self):
        doc = load(os.path.join(MHS, "spec", "capabilities.json"))
        for entry in doc["capabilities"]:
            cid = entry["capability_id"]
            self.assertEqual(CV.risk_floor([cid]), entry["risk_class"], cid)
            self.assertEqual(CV.verb(cid), entry["verb"], cid)
        self.assertEqual(CV.risk_floor([]), "R0")
        self.assertEqual(CV.risk_floor(["x-cap.acme.thing.v1"]), "R0")
        highest = max((e["risk_class"] for e in doc["capabilities"]), key=CV.RISK_ORDER.index)
        self.assertEqual(CV.risk_floor([e["capability_id"] for e in doc["capabilities"]]), highest)


if __name__ == "__main__":
    unittest.main()
