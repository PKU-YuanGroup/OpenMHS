"""Valid examples validate; every invalid example fails at its expected JSON pointer."""

from __future__ import annotations

import unittest

from mhs._ids import SCHEMA_BASE
from mhs.schema import SchemaStore

from . import _semantics
from ._support import (
    CAPABILITIES,
    EXAMPLES,
    INVALID,
    SCHEMA_DIR,
    VALID,
    error_tokens,
    load_json,
    pointer_tokens,
    schema_for,
)

STORE = SchemaStore(root=SCHEMA_DIR)
CLASSES = {entry["capability_id"]: entry for entry in load_json(CAPABILITIES)["capabilities"]}
CASES = load_json(INVALID / "expected-failures.json")["cases"]


def _valid_manifests() -> dict[str, dict]:
    manifests = {}
    for path in sorted(VALID.glob("device.*.json")):
        document = load_json(path)
        manifests[document["device_id"]] = document
    return manifests


def semantic_problems(path, document) -> list[tuple[str, str, str]]:
    """Run the load-time rules that apply to ``document``'s schema."""
    schema = schema_for(path)
    if schema == "device.schema.json":
        return _semantics.check_manifest(document, CLASSES)
    if schema == "site-limits.schema.json":
        return _semantics.check_overlay(document, _valid_manifests(), CLASSES)
    return []


class ValidExampleTests(unittest.TestCase):
    def test_every_new_schema_has_a_valid_example(self):
        covered = {schema_for(path) for path in VALID.glob("*.json")}
        for name in ("reference.schema.json", "site-limits.schema.json", "driver-lock.schema.json",
                     "driver-result.schema.json", "check-report.schema.json", "endpoints.schema.json",
                     "device.schema.json", "registry-record.schema.json", "conformance-report.schema.json",
                     "permit.schema.json"):
            self.assertIn(name, covered)

    def test_valid_examples_validate(self):
        paths = sorted(VALID.glob("*.json"))
        self.assertGreaterEqual(len(paths), 10)
        for path in paths:
            with self.subTest(example=path.name):
                document = load_json(path)
                self.assertEqual(STORE.validate(document, schema_for(path)), [])
                self.assertEqual(semantic_problems(path, document), [])

    def test_declared_schema_matches_file_name(self):
        for path in sorted(VALID.glob("*.json")) + sorted(INVALID.glob("*.*.json")):
            declared = load_json(path).get("$schema")
            if declared is None:      # schemas without a $schema member (permit, records)
                continue
            with self.subTest(example=path.name):
                self.assertEqual(declared, SCHEMA_BASE + schema_for(path))

    def test_extension_bindings_pin_their_schema_digest(self):
        from mhs import canonical

        pinned = 0
        for path in sorted(VALID.glob("device.*.json")):
            for binding in load_json(path)["capabilities"]:
                if "x-mhs-schema-digest" in binding:
                    pinned += 1
                    expected = canonical.digest({"input_schema": binding["input_schema"],
                                                 "output_schema": binding["output_schema"]})
                    self.assertEqual(binding["x-mhs-schema-digest"], expected, binding["capability_id"])
        self.assertGreaterEqual(pinned, 1)

    def test_top_level_examples_still_validate(self):
        # Pre-0.9 examples (and the manifests derived from them) stay valid:
        # every device.schema change in 0.9 is additive.
        for path in sorted(EXAMPLES.glob("*.json")):
            with self.subTest(example=path.name):
                self.assertEqual(STORE.validate(load_json(path), schema_for(path)), [])
                self.assertEqual(semantic_problems(path, load_json(path)), [])


class InvalidExampleTests(unittest.TestCase):
    def test_index_covers_every_invalid_file(self):
        indexed = {case["file"] for case in CASES}
        on_disk = {path.name for path in INVALID.glob("*.json")} - {"expected-failures.json"}
        self.assertEqual(indexed, on_disk)
        self.assertEqual(len(indexed), len(CASES), "duplicate index entries")

    def test_required_failure_kinds_are_present(self):
        files = {case["file"] for case in CASES}
        rules = {case.get("rule") for case in CASES}
        self.assertIn("device.limit-key-typo.json", files)          # 'maxx'
        self.assertIn("device.unknown-rule-member.json", files)
        self.assertIn("device.interlock-empty-required-for.json", files)
        self.assertIn("array-bound-length", rules)
        self.assertIn("overlay-narrows", rules)                      # widening overlay
        self.assertIn("verb-matches-class", rules)                   # verb mismatch

    def test_invalid_examples_fail_at_expected_pointer(self):
        for case in CASES:
            with self.subTest(example=case["file"]):
                path = INVALID / case["file"]
                document = load_json(path)
                self.assertEqual(case["schema"], schema_for(path))
                expected = pointer_tokens(case["pointer"])
                errors = STORE.validate(document, case["schema"])
                if case["check"] == "schema":
                    self.assertTrue(errors, "expected a schema error")
                    hits = [e for e in errors if error_tokens(e) == expected
                            and case.get("contains", "") in e]
                    self.assertTrue(hits, f"no error at {case['pointer']!r}: {errors}")
                else:
                    self.assertEqual(case["check"], "semantic")
                    self.assertEqual(errors, [], "a semantic example must be schema-valid")
                    problems = semantic_problems(path, document)
                    hits = [p for p in problems if pointer_tokens(p[0]) == expected and p[1] == case["rule"]]
                    self.assertTrue(hits, f"no {case['rule']} problem at {case['pointer']!r}: {problems}")


if __name__ == "__main__":
    unittest.main()
