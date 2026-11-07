"""JSON Schema tests for ``MHS/schema/bindings.schema.json``."""

from __future__ import annotations

import copy
import json
import os
import unittest
from pathlib import Path

from tests.remediation.bridge import support

from mhs.schema import validate_file

REPO_ROOT = Path(__file__).resolve().parents[5]
SCHEMA_PATH = REPO_ROOT / "MHS" / "schema" / "bindings.schema.json"


class BindingsSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def _errors(self, instance: object) -> list[str]:
        return validate_file(instance, str(SCHEMA_PATH))

    def test_schema_is_2020_12_and_has_expected_identity(self) -> None:
        self.assertEqual(
            self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        self.assertIn("bindings.schema.json", self.schema["$id"])
        self.assertEqual(
            self.schema["required"], ["mhs_bindings", "adapter_id", "bindings"]
        )

    def test_normative_example_is_valid(self) -> None:
        self.assertEqual(self._errors(copy.deepcopy(support.NORMATIVE_EXAMPLE)), [])
        self.assertEqual(self._errors(copy.deepcopy(support.LIFT_BINDINGS)), [])

    def test_missing_native_is_invalid(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        document["bindings"][0]["binding"].pop("native")
        errors = self._errors(document)
        self.assertTrue(errors)
        self.assertTrue(any("native" in error for error in errors), errors)

    def test_unit_missing_to_is_invalid(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        document["bindings"][0]["binding"]["units"]["input.action"] = {
            "from": "1",
            "factor": 1,
        }
        errors = self._errors(document)
        self.assertTrue(errors)
        self.assertTrue(any("to" in error for error in errors), errors)

    def test_unit_missing_from_is_invalid(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        document["bindings"][0]["binding"]["units"]["input.action"] = {
            "to": "1",
            "factor": 1,
        }
        errors = self._errors(document)
        self.assertTrue(errors)
        self.assertTrue(any("from" in error for error in errors), errors)

    def test_errors_object_is_invalid(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        document["bindings"][0]["binding"]["errors"] = {
            "AssertionError": "MHS.DEVICE.PRECONDITION_UNMET"
        }
        errors = self._errors(document)
        self.assertTrue(errors)
        self.assertTrue(any("errors" in error for error in errors), errors)

    def test_missing_concurrency_and_timeout_are_invalid(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        document["bindings"][0]["binding"].pop("concurrency")
        document["bindings"][0]["binding"].pop("timeout_ms")
        errors = self._errors(document)
        self.assertTrue(errors)
        self.assertTrue(any("concurrency" in error for error in errors), errors)
        self.assertTrue(any("timeout_ms" in error for error in errors), errors)

    def test_per_arg_value_constant_and_constants_object_are_both_valid(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        binding = document["bindings"][0]["binding"]
        binding["args"]["expected_revision"] = {"value": "ignore"}
        binding.pop("constants")
        self.assertEqual(self._errors(document), [])

    def test_closed_objects_reject_unknown_keys(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        document["bindings"][0]["binding"]["surprise"] = 1
        self.assertTrue(self._errors(document))
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        document["bindings"][0]["binding"]["args"]["action"]["enum"] = {"left": 0}
        self.assertTrue(self._errors(document))

    def test_enum_map_and_map_alias_are_accepted(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        action = document["bindings"][0]["binding"]["args"]["action"]
        action.pop("enum_map")
        action["map"] = {"left": 0, "right": 1}
        self.assertEqual(self._errors(document), [])

    def test_offset_unit_form_is_valid(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        document["bindings"][0]["binding"]["units"]["input.action"] = {
            "from": "Cel",
            "to": "K",
            "offset": 273.15,
        }
        self.assertEqual(self._errors(document), [])

    def test_arg_units_alias_is_valid(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        binding = document["bindings"][0]["binding"]
        action = binding["args"]["action"]
        action["units"] = binding.pop("units")["input.action"]
        self.assertEqual(self._errors(document), [])

    def test_unsupported_input_requires_a_reason(self) -> None:
        document = copy.deepcopy(support.NORMATIVE_EXAMPLE)
        document["bindings"][0]["binding"]["inputs"] = {"camera": {"unsupported": True}}
        self.assertTrue(self._errors(document))
        document["bindings"][0]["binding"]["inputs"] = {
            "camera": {"unsupported": True, "reason": "not exposed"}
        }
        self.assertEqual(self._errors(document), [])

    def test_schema_path_is_the_documented_one(self) -> None:
        self.assertEqual(
            os.path.normpath(str(SCHEMA_PATH)),
            os.path.normpath(
                str(REPO_ROOT / "MHS" / "schema" / "bindings.schema.json")
            ),
        )


if __name__ == "__main__":
    unittest.main()
