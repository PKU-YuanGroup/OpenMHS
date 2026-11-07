"""The published schemas must validate the published examples.

Examples are named ``<schema stem>.<slug>.json``; the stem selects the schema.
``examples/*.json`` and ``examples/valid/*.json`` must validate; the invalid
examples and the semantic rules are covered by ``tests/catalog_data``.
"""

from __future__ import annotations

import glob
import json
import os
import unittest

from mhs.schema import validate, validate_file

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
SCHEMA_DIR = os.path.join(ROOT, "MHS", "schema")


def _schema_for(path: str) -> str:
    return os.path.basename(path).split(".", 1)[0] + ".schema.json"


def _load(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class ExampleValidationTest(unittest.TestCase):
    def test_examples_validate(self):
        examples = sorted(glob.glob(os.path.join(SCHEMA_DIR, "examples", "*.json")))
        examples += sorted(glob.glob(os.path.join(SCHEMA_DIR, "examples", "valid", "*.json")))
        self.assertGreaterEqual(len(examples), 12)
        for path in examples:
            with self.subTest(example=os.path.basename(path)):
                instance = _load(path)
                errors = validate_file(instance, os.path.join(SCHEMA_DIR, _schema_for(path)))
                self.assertEqual(errors, [], f"{os.path.basename(path)}: {errors}")

    def test_capability_catalogue_validates(self):
        catalogue = _load(os.path.join(ROOT, "MHS", "spec", "capabilities.json"))
        schema_path = os.path.join(SCHEMA_DIR, "capability.schema.json")
        failures = []
        for entry in catalogue["capabilities"]:
            errors = validate_file(entry, schema_path)
            if errors:
                failures.append((entry["capability_id"], errors[:3]))
        self.assertEqual(failures, [])

    def test_error_registry_validates(self):
        registry = _load(os.path.join(ROOT, "MHS", "spec", "errors.json"))
        self.assertEqual(validate_file(registry, os.path.join(SCHEMA_DIR, "errors.schema.json")), [])

    def test_inline_schema_validation_still_works(self):
        self.assertEqual(validate({"a": 1}, {"type": "object", "properties": {"a": {"type": "integer"}}}), [])


if __name__ == "__main__":
    unittest.main()
