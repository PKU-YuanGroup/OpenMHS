"""The error registry (MHS/spec/errors.json) has one record shape and drives mhs.errors."""

from __future__ import annotations

import unittest

from mhs import errors as mhs_errors
from mhs.schema import SchemaStore

from ._support import ERRORS, SCHEMA_DIR, load_json, load_tool

STORE = SchemaStore(root=SCHEMA_DIR)
REGISTRY = load_json(ERRORS)
RECORDS = REGISTRY["errors"]
BY_CODE = {record["code"]: record for record in RECORDS}

DRIVER_SUBSET = {
    "MHS.SAFETY.ENVELOPE_VIOLATION", "MHS.SAFETY.LIMITS_UNSET", "MHS.SAFETY.ESTOP_ENGAGED",
    "MHS.SAFETY.INTERLOCK_OPEN", "MHS.SAFETY.SAFE_STATE_UNREACHED", "MHS.DEVICE.FAULTED",
    "MHS.DEVICE.BUSY", "MHS.DEVICE.PRECONDITION_UNMET", "MHS.CAPABILITY.INPUT_INVALID",
    "MHS.CAPABILITY.OUTPUT_INVALID", "MHS.ADAPTER.SHIM_FAILED", "MHS.OUTCOME.TIMEOUT",
    "MHS.OUTCOME.ABORTED",
}


class RegistryShapeTests(unittest.TestCase):
    def test_registry_validates_against_errors_schema(self):
        self.assertEqual(STORE.validate(REGISTRY, "errors.schema.json"), [])

    def test_one_record_shape(self):
        shapes = {tuple(sorted(set(record) - {"replaced_by"})) for record in RECORDS}
        self.assertEqual(len(shapes), 1, shapes)
        self.assertEqual(REGISTRY["error_count"], len(RECORDS))
        self.assertEqual(len(BY_CODE), len(RECORDS))

    def test_generator_invariants_hold(self):
        tool = load_tool("gen_errors")
        self.assertEqual(tool.registry_problems(REGISTRY), [])

    def test_driver_subset_is_exactly_the_frozen_list(self):
        self.assertEqual({code for code, record in BY_CODE.items() if record["driver_subset"]}, DRIVER_SUBSET)

    def test_new_codes_and_deprecated_alias(self):
        self.assertEqual(BY_CODE["MHS.SAFETY.LIMITS_UNSET"]["jsonrpc_code"], -32010)
        self.assertFalse(BY_CODE["MHS.SAFETY.LIMITS_UNSET"]["retryable"])
        self.assertEqual(BY_CODE["MHS.HOST.ADAPTER_MISSING"]["status"], "stable")
        legacy = BY_CODE["MHS.HOST.OPENAI4S_MISSING"]
        self.assertEqual(legacy["status"], "deprecated")
        self.assertEqual(legacy["replaced_by"], "MHS.HOST.ADAPTER_MISSING")

    def test_safety_and_unknown_outcomes_are_never_retryable(self):
        # ERR-006
        for code, record in BY_CODE.items():
            if code.startswith("MHS.SAFETY.") or code == "MHS.OUTCOME.UNKNOWN":
                self.assertIn(record["retryable"], (False, None), code)

    def test_feature_strings_are_not_errors(self):
        features = {code for code, record in BY_CODE.items() if record["status"] == "feature"}
        self.assertEqual(features, {"MHS.SAFETY.NOT_CERTIFIED", "MHS.CAPABILITY.EXPERIMENTAL_PRESENT"})


class GeneratedModuleTests(unittest.TestCase):
    def test_module_table_matches_registry(self):
        self.assertEqual(list(mhs_errors.MHS_ERROR_CODES), [record["code"] for record in RECORDS])
        for record in RECORDS:
            spec = mhs_errors.MHS_ERROR_CODES[record["code"]]
            self.assertEqual(spec.jsonrpc, record["jsonrpc_code"])
            self.assertEqual(spec.retryable, record["retryable"])
            self.assertEqual(spec.status, record["status"])
            self.assertEqual(spec.driver_subset, record["driver_subset"])
            self.assertEqual(spec.summary, record["meaning"])

    def test_driver_subset_and_deprecations_are_exported(self):
        self.assertEqual(mhs_errors.DRIVER_SUBSET, frozenset(DRIVER_SUBSET))
        self.assertEqual(mhs_errors.DEPRECATED_CODES, {"MHS.HOST.OPENAI4S_MISSING": "MHS.HOST.ADAPTER_MISSING"})
        self.assertTrue(mhs_errors.is_driver_code("MHS.SAFETY.LIMIT_EXCEEDED"))   # legacy alias of ENVELOPE_VIOLATION
        self.assertFalse(mhs_errors.is_driver_code("MHS.AUTH.FORBIDDEN"))

    def test_legacy_aliases_and_normalisation_are_unchanged(self):
        self.assertEqual(len(mhs_errors.LEGACY_ALIASES), 60)
        for legacy, normative in mhs_errors.LEGACY_ALIASES.items():
            self.assertIn(normative, mhs_errors.MHS_ERROR_CODES, legacy)
            self.assertNotIn(legacy, mhs_errors.MHS_ERROR_CODES, legacy)
            self.assertEqual(mhs_errors.normalize_code(legacy), normative)
        self.assertEqual(mhs_errors.normalize_code("MHS.HOST.OPENAI4S_MISSING"), "MHS.HOST.OPENAI4S_MISSING")
        self.assertEqual(mhs_errors.MHSError("MHS.SCHEMA.INVALID_INPUT").code, "MHS.CAPABILITY.INPUT_INVALID")

    def test_new_codes_carry_registry_metadata_on_the_wire(self):
        error = mhs_errors.MHSError("MHS.SAFETY.LIMITS_UNSET", "no limit for setpoint")
        wire = error.to_error_object()
        self.assertEqual(wire["code"], -32010)
        self.assertEqual(wire["data"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertIs(wire["data"]["retryable"], False)
        self.assertIn("site-limits.json", wire["data"]["remediation"])
        self.assertEqual(mhs_errors.ErrorCode.SAFETY_LIMITS_UNSET, "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(mhs_errors.ErrorCode.HOST_ADAPTER_MISSING, "MHS.HOST.ADAPTER_MISSING")


if __name__ == "__main__":
    unittest.main()
