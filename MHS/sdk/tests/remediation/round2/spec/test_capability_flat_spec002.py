"""SPEC-002 regression tests: chapter 03 must describe the flat capability contract.

The capability schema is flat: ``summary``, ``tags``, ``units``, ``effects``,
``hazards``, ``preconditions``, ``postconditions``, ``determinism`` and the other
members live on the class document.  A nested ``semantics`` object is forbidden.
These tests parse the prose examples, validate the whole capability catalogue, and
assert that chapter 03 contains no normative nested path.
"""

from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

from mhs.client import MHSClient
from mhs.reference import build_endpoint, build_server
from mhs.schema import SchemaStore

ROOT = Path(__file__).resolve().parents[6]
SPEC = ROOT / "MHS/spec"
SCHEMA = "capability.schema.json"
FLAT_FIELDS = (
    "summary",
    "tags",
    "units",
    "effects",
    "hazards",
    "preconditions",
    "postconditions",
    "determinism",
    "typical_duration_ms",
    "notes",
)


def _json_blocks(text: str) -> list[dict]:
    documents = []
    for match in re.finditer(r"```json\n(.*?)\n```", text, re.S):
        documents.append(json.loads(match.group(1)))
    return documents


class CapabilityFlatContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.store = SchemaStore()
        cls.chapter = (SPEC / "03-capability-registry.md").read_text(encoding="utf-8")
        cls.architecture = (SPEC / "00-architecture.md").read_text(encoding="utf-8")

    def assert_valid(self, document: dict, label: str) -> None:
        errors = [str(item) for item in self.store.validate(document, SCHEMA)]
        self.assertEqual(errors, [], f"{label}: {errors}")

    def test_every_chapter03_json_example_validates(self) -> None:
        documents = _json_blocks(self.chapter)
        self.assertTrue(documents, "chapter 03 must carry at least one parseable flat example")
        for index, document in enumerate(documents):
            self.assert_valid(document, f"chapter03 example {index}")

    def test_architecture_shape_example_validates(self) -> None:
        shape = self.architecture.split("### 4.1 Shape", 1)[1].split("### 4.2 Verbs", 1)[0]
        documents = _json_blocks(shape)
        self.assertEqual(len(documents), 1)
        self.assert_valid(documents[0], "architecture §4.1")
        self.assertNotIn("semantics", documents[0])
        for field in ("summary", "tags", "units", "effects", "hazards", "preconditions", "postconditions", "determinism"):
            self.assertIn(field, documents[0], field)

    def test_all_catalogue_classes_validate(self) -> None:
        catalogue = json.loads((SPEC / "capabilities.json").read_text(encoding="utf-8"))
        classes = catalogue["capabilities"]
        self.assertEqual(len(classes), catalogue["capability_count"])
        for capability_class in classes:
            self.assertNotIn("semantics", capability_class, capability_class.get("capability_id"))
            self.assert_valid(capability_class, str(capability_class.get("capability_id")))

    def test_nested_semantics_class_is_rejected(self) -> None:
        catalogue = json.loads((SPEC / "capabilities.json").read_text(encoding="utf-8"))
        nested = copy.deepcopy(catalogue["capabilities"][0])
        semantics = {}
        for field in FLAT_FIELDS:
            if field in nested:
                semantics[field] = nested.pop(field)
        nested["semantics"] = semantics
        errors = [str(item) for item in self.store.validate(nested, SCHEMA)]
        self.assertTrue(errors)
        joined = "\n".join(errors)
        self.assertIn("missing required property 'summary'", joined)
        self.assertIn("missing required property 'tags'", joined)
        self.assertIn("additional property 'semantics' is not allowed", joined)

    def test_chapter03_has_no_nested_semantics_paths(self) -> None:
        self.assertIsNone(re.search(r"semantics\.[a-z_]", self.chapter), "chapter 03 still contains a semantics.* path")
        self.assertNotRegex(self.chapter, r"\|\s*`semantics`\s*\|", "chapter 03 still documents a semantics table row")

    def test_cap009_010_011_are_flat(self) -> None:
        for requirement in ("CAP-009", "CAP-010", "CAP-011"):
            match = re.search(rf"\*\*{requirement}\.\*\*(.*?)(?=\n\n\*\*|\n\n---)", self.chapter, re.S)
            self.assertIsNotNone(match, requirement)
            text = match.group(1)
            self.assertNotIn("semantics.", text, requirement)
        self.assertIn("`summary` MUST", self.chapter)
        self.assertIn("`tags` MUST", self.chapter)
        self.assertIn("`effects` MUST", self.chapter)
        self.assertIn("`hazards` MUST", self.chapter)

    def test_runtime_schema_get_serves_flat_classes(self) -> None:
        class Loopback:
            def __init__(self, server):
                self.server = server

            def request(self, message, timeout=None):
                response = self.server.handle(message)
                return response.to_dict() if hasattr(response, "to_dict") else response

            def close(self):
                pass

        spec = build_endpoint("conveyor", test_profile=True)
        server = build_server(spec, log_ready=False)
        client = MHSClient(Loopback(server))
        try:
            hello = client.hello()
            self.assertEqual(hello.get("mhs_version"), "1.0")
            checked = 0
            for manifest in client.devices():
                for binding in manifest.get("capabilities") or []:
                    result = client.get_schema(binding["capability_id"])
                    document = result["schema"]
                    self.assertNotIn("semantics", document, binding["capability_id"])
                    self.assert_valid(document, binding["capability_id"])
                    checked += 1
            self.assertGreater(checked, 0)
        finally:
            client.close()
            spec.close()

    def test_flat_fixture_derived_from_chapter_table_validates(self) -> None:
        # Build a minimal class from the chapter's documented flat fields; this
        # is the positive control for the old nested fixture.
        catalogue = json.loads((SPEC / "capabilities.json").read_text(encoding="utf-8"))
        document = copy.deepcopy(catalogue["capabilities"][0])
        document["capability_id"] = "cap.x.mhs-conformance.flat-fixture.v1"
        document["title"] = "Flat fixture"
        for field in FLAT_FIELDS:
            if field in document:
                continue
            if field in ("tags", "effects", "hazards", "preconditions", "postconditions"):
                document[field] = []
            elif field == "units":
                document[field] = {}
            elif field == "determinism":
                document[field] = "exact"
            elif field == "typical_duration_ms":
                document[field] = 0
            else:
                document[field] = ""
        self.assert_valid(document, "flat fixture")


if __name__ == "__main__":
    unittest.main()
