#!/usr/bin/env python3
"""Regression tests for the MHS registry remediation (RREG-001, REG-003, REG-004).

Stdlib only. Run from the workspace root:

    python3 -m unittest discover -s MHS/registry/tests -v

The tests exercise the same embedded schema validator and semantic checks used by
``MHS/registry/validate.py``; they do not modify the registry.  RREG-001 keeps the
shared schema publisher-neutral while the reference corpus keeps its expected
publisher as deployment-local policy.
"""
from __future__ import annotations

import copy
import glob
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
WORKSPACE = os.path.abspath(os.path.join(REG, "..", ".."))
SCHEMA_DIR = os.path.join(WORKSPACE, "MHS", "schema")

sys.path.insert(0, REG)
sys.path.insert(0, os.path.join(WORKSPACE, "MHS", "sdk", "src"))
import family_data as FD  # noqa: E402
import validate as V  # noqa: E402
from mhs import _ids  # noqa: E402

REGISTRY_ID = _ids.REGISTRY_ID
ARCHIVED_MANIFESTS = os.path.join(WORKSPACE, "_archive", "registry", "manifests-skeleton-2026-10")


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def base_record(**overrides):
    doc = {
        "record_type": "package",
        "id": "gh.acme/widget",
        "registry_id": REGISTRY_ID,
        "package_id": "gh.acme/widget",
        "repo_url": "https://github.com/acme/widget",
        "track": "labs",
        "families": ["python-object"],
        "tier": "B",
        "ring": 2,
        "modes": ["simulated"],
        "capabilities_offered": ["cap.device.describe.v1"],
        "evidence": {"state": "static_scan", "read_by": "static_analysis"},
        "trust": "unsigned",
        "updated_at": "2026-10-20T00:00:00Z",
    }
    doc.update(overrides)
    return doc


class SchemaEnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = V.SchemaStore(SCHEMA_DIR)
        cls.validator = V.Validator(cls.store)
        cls.schema = cls.store.schemas["registry-record.schema.json"]

    def errors(self, doc):
        return self.validator.validate(doc, self.schema, "registry-record.schema.json")

    def test_positive_fixture_with_envelope_validates(self):
        self.assertEqual(self.errors(base_record()), [])

    def test_missing_id_fails(self):
        doc = base_record()
        del doc["id"]
        errs = self.errors(doc)
        self.assertTrue(any("id" in e and "required" in e for e in errs), errs)

    def test_missing_registry_id_fails(self):
        doc = base_record()
        del doc["registry_id"]
        errs = self.errors(doc)
        self.assertTrue(any("registry_id" in e and "required" in e for e in errs), errs)

    def test_second_publisher_is_valid_in_the_shared_schema(self):
        # RREG-001: the normative schema is not a publisher allow-list.  A
        # truthful independent registry DNS name must validate.
        doc = base_record(registry_id="registry.example.org")
        self.assertEqual(self.errors(doc), [])

    def test_second_publisher_is_rejected_by_deployment_local_policy(self):
        # The reference corpus is published by the reference registry; that
        # deployment expectation lives in validate.py, not in the schema.
        doc = base_record(registry_id="registry.example.org")
        errs, _ = V.check_record_semantics(doc, {"cap.device.describe.v1": {}})
        self.assertTrue(any("deployment-local publisher policy" in e for e in errs), errs)
        # A mirror can validate the same truthful record against its own policy.
        errs, _ = V.check_record_semantics(
            doc, {"cap.device.describe.v1": {}}, "registry.example.org")
        self.assertFalse(any("registry_id" in e for e in errs), errs)

    def test_invalid_registry_identifiers_are_rejected(self):
        for value in (
            "",
            "registry",                       # not a DNS name
            "-bad.example",                   # label starts with '-'
            "bad-.example",                   # label ends with '-'
            "bad_name.example",               # underscore
            "Registry.Example.Org",           # uppercase is not the canonical form
            "registry..org",                  # empty label
            "registry.example.org.",          # trailing root dot
            "registry.example.org/path",      # path, not a DNS name
            "https://registry.example.org",   # scheme, not a DNS name
            "a" * 64 + ".example",            # label over 63 octets
        ):
            with self.subTest(registry_id=value):
                self.assertTrue(
                    any("registry_id" in e for e in self.errors(
                        base_record(registry_id=value))),
                    value,
                )

    def test_id_pattern_must_match_package_shape(self):
        doc = base_record(id="not-a-package-id")
        errs = self.errors(doc)
        self.assertTrue(any("$.id" in e for e in errs), errs)

    def test_id_must_equal_package_id_semantically(self):
        doc = base_record(id="gh.other/widget")
        errs, _ = V.check_record_semantics(doc, {"cap.device.describe.v1": {}})
        self.assertTrue(any("!= package_id" in e for e in errs), errs)


class CapabilityReferentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = V.load_core_capabilities()

    def test_core_capability_resolves(self):
        errs, ext = V.check_record_semantics(base_record(), self.core)
        self.assertEqual(errs, [])
        self.assertEqual(ext, [])

    def test_unknown_core_capability_rejected(self):
        doc = base_record(capabilities_offered=["cap.optics.illumination.v1"])
        errs, _ = V.check_record_semantics(doc, self.core)
        self.assertTrue(any("unknown core capability" in e for e in errs), errs)

    def test_micromanager_template_uses_imaging_illumination(self):
        caps = FD.FAMILY_CAPS["micromanager"]
        self.assertIn("cap.imaging.illumination.v1", caps)
        self.assertNotIn("cap.optics.illumination.v1", caps)
        self.assertEqual([c for c in caps if c not in self.core], [])

    def test_undeclared_extension_rejected(self):
        doc = base_record(capabilities_offered=["x-cap.acme.vision.v1"])
        errs, _ = V.check_record_semantics(doc, self.core)
        self.assertTrue(any("not explicitly declared" in e for e in errs), errs)

    def test_declared_extension_accepted_and_reported(self):
        doc = base_record(
            capabilities_offered=["x-cap.acme.vision.v1"],
            **{"x-vendor": {"capability_extensions": {
                "x-cap.acme.vision.v1": {"declared_by": "gh.acme.widget",
                                         "evidence": "adapter manifest"}}}},
        )
        errs, ext = V.check_record_semantics(doc, self.core)
        self.assertEqual(errs, [])
        self.assertEqual(ext, ["x-cap.acme.vision.v1"])

    def test_manifest_core_capability_resolves(self):
        doc = {"devices": [{"capabilities": [
            {"capability_id": "cap.device.describe.v1", "resource": "device"}]}]}
        errs, ext = V.check_manifest_semantics(doc, self.core)
        self.assertEqual(errs, [])
        self.assertEqual(ext, [])

    def test_manifest_unknown_core_capability_rejected(self):
        doc = {"devices": [{"capabilities": [
            {"capability_id": "cap.measure.temperature_ccd.v1", "resource": "device"}]}]}
        errs, _ = V.check_manifest_semantics(doc, self.core)
        self.assertTrue(any("unknown core capability" in e for e in errs), errs)

    def test_manifest_extension_is_declared_and_reported(self):
        doc = {"devices": [{"capabilities": [
            {"capability_id": "x-cap.acme.vision.v1", "resource": "device"}]}]}
        errs, ext = V.check_manifest_semantics(doc, self.core)
        self.assertEqual(errs, [])
        self.assertEqual(ext, ["x-cap.acme.vision.v1"])

    def test_recipe_unknown_capability_rejected(self):
        errs, _ = V.check_recipe_semantics("| call | `cap.optics.illumination.v1` | x |",
                                           self.core)
        self.assertTrue(any("unknown core capability" in e for e in errs), errs)


class PureSimulatorModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = V.load_core_capabilities()

    def test_pyvisa_sim_hardware_mode_is_an_error(self):
        doc = base_record(package_id="gh.pyvisa/pyvisa-sim", id="gh.pyvisa/pyvisa-sim",
                          families=["scpi-visa"], modes=["hardware", "simulated"])
        errs, _ = V.check_record_semantics(doc, self.core)
        self.assertTrue(any("must not advertise hardware" in e for e in errs), errs)

    def test_pyvisa_sim_source_backed_modes_pass(self):
        doc = base_record(package_id="gh.pyvisa/pyvisa-sim", id="gh.pyvisa/pyvisa-sim",
                          families=["scpi-visa"], modes=["simulated", "replay"])
        errs, _ = V.check_record_semantics(doc, self.core)
        self.assertEqual(errs, [])

    def test_shipped_pyvisa_sim_record_is_simulated_replay(self):
        path = os.path.join(REG, "repos", "labs", "pyvisa__pyvisa-sim.json")
        doc = load_json(path)
        self.assertEqual(doc["modes"], ["simulated", "replay"])
        self.assertNotIn("hardware", doc["modes"])
        self.assertEqual(doc["x-vendor"]["classification"]["mode_override"]["rule"],
                         "package-specific-pure-simulator")


class CorpusRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = V.load_core_capabilities()

    def test_every_shipped_record_has_envelope_and_valid_referents(self):
        paths = sorted(glob.glob(os.path.join(REG, "repos", "*", "*.json")))
        self.assertEqual(len(paths), 2967)
        bad = []
        for path in paths:
            doc = load_json(path)
            if doc.get("id") != doc.get("package_id"):
                bad.append((path, "id != package_id"))
            if doc.get("registry_id") != REGISTRY_ID:
                bad.append((path, "registry_id"))
            errs, _ = V.check_record_semantics(doc, self.core)
            bad.extend((path, e) for e in errs)
        self.assertEqual(bad[:5], [])

    def test_registry_id_comes_from_the_identifier_module(self):
        self.assertEqual(V.REGISTRY_ID, _ids.REGISTRY_ID)
        self.assertNotIn("modelhardwarestandard", V.REGISTRY_ID)

    def test_skeleton_manifests_are_archived_not_generated(self):
        # the 1,967 skeleton manifests were moved to _archive/registry/ (WP-10); records no longer point at them
        self.assertFalse(os.path.exists(os.path.join(REG, "manifests")))
        if os.path.isdir(ARCHIVED_MANIFESTS):   # absent in a copy of MHS/ alone
            self.assertEqual(len(glob.glob(os.path.join(ARCHIVED_MANIFESTS, "*", "*.json"))), 1967)
        for path in sorted(glob.glob(os.path.join(REG, "repos", "*", "*.json")))[:200]:
            self.assertIsNone(load_json(path)["adapter"]["manifest_ref"], path)

    def test_every_family_recipe_resolves_its_capabilities(self):
        paths = sorted(glob.glob(os.path.join(REG, "families", "*.md")))
        families = {load_json(p)["families"][0] for p in glob.glob(os.path.join(REG, "repos", "*", "*.json"))}
        self.assertEqual({os.path.basename(p)[:-3] for p in paths}, families)
        bad = []
        for path in paths:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            errs, _ = V.check_recipe_semantics(text, self.core)
            bad.extend((path, e) for e in errs + V.check_recipe_layout(text))
        self.assertEqual(bad[:5], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
