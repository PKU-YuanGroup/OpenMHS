"""Traversal-safe public schema lookup and the developer-only path loader."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mhs._ids import LEGACY_SCHEMA_PREFIX, SCHEMA_BASE
from mhs.schema import (
    KNOWN_SCHEMA_PREFIXES,
    SchemaError,
    SchemaStore,
    Validator,
    public_schema_name,
    validate,
    validate_file,
)

from ._paths import EXAMPLE_DEVICE, SCHEMA_DIR

REJECTED_REFS = [
    "../x",
    "../device.schema.json",
    "..",
    "/etc/passwd",
    "/etc/passwd.json",
    "~/.docker/config.json",
    "~root/x.json",
    "C:\\Windows\\win.ini",
    "C:/x.json",
    "c:x.json",
    "D:device.schema.json",
    "\\\\server\\share\\x.json",
    "..\\device.schema.json",
    "a/b.json",
    "examples/device.conveyor-workcell.json",
    "Device.schema.json",
    "device.schema.json\x00",
    "device.schema.json#/$defs/x",
    "%2e%2e%2fsecret.json",
    "-x.json",
    "device.schema.yaml",
    "device",
    "",
    "https://evil.example/schema/device.schema.json",
    "file:///etc/passwd",
    SCHEMA_BASE + "../device.schema.json",
    SCHEMA_BASE + "sub/device.schema.json",
    LEGACY_SCHEMA_PREFIX + "../../etc/passwd",
    "x" * 600 + ".json",
]


class PublicNameTests(unittest.TestCase):
    def test_accepts_bare_names_and_known_ids(self) -> None:
        self.assertEqual(public_schema_name("device.schema.json"), "device.schema.json")
        self.assertEqual(public_schema_name("endpoint-descriptor.schema.json"),
                         "endpoint-descriptor.schema.json")
        self.assertEqual(public_schema_name("capabilities.json"), "capabilities.json")
        for prefix in KNOWN_SCHEMA_PREFIXES:
            self.assertEqual(public_schema_name(prefix + "receipt.schema.json"), "receipt.schema.json")

    def test_rejects_paths_and_foreign_ids(self) -> None:
        for ref in REJECTED_REFS + [None, 7, b"device.schema.json"]:
            with self.subTest(ref=ref):
                with self.assertRaises(SchemaError):
                    public_schema_name(ref)


class ResolvePublicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SchemaStore(SCHEMA_DIR)
        self.tmp = tempfile.TemporaryDirectory(prefix="openmhs-store-")
        self.addCleanup(self.tmp.cleanup)

    def test_resolves_shipped_schema_by_name_and_both_prefixes(self) -> None:
        document, base = self.store.resolve_public("device.schema.json")
        self.assertEqual(Path(base), (SCHEMA_DIR / "device.schema.json").resolve())
        for prefix in (SCHEMA_BASE, LEGACY_SCHEMA_PREFIX):
            other, other_base = self.store.resolve_public(prefix + "device.schema.json")
            self.assertIs(other, document)
            self.assertEqual(other_base, base)

    def test_rejects_traversal_absolute_home_and_drive_refs(self) -> None:
        for ref in REJECTED_REFS:
            with self.subTest(ref=ref):
                with self.assertRaises(SchemaError):
                    self.store.resolve_public(ref)

    def test_unknown_well_formed_name_is_not_found(self) -> None:
        with self.assertRaises(SchemaError):
            self.store.resolve_public("no-such.schema.json")

    def test_never_serves_a_developer_loaded_file(self) -> None:
        secret = Path(self.tmp.name) / "secret.json"
        secret.write_text(json.dumps({"api_token": "DUMMY"}), encoding="utf-8")
        document, _ = self.store.load_path(secret)
        self.assertEqual(document["api_token"], "DUMMY")
        with self.assertRaises(SchemaError):
            self.store.resolve_public("secret.json")

    def test_load_does_not_follow_paths_outside_the_roots(self) -> None:
        secret = Path(self.tmp.name) / "outside.schema.json"
        secret.write_text(json.dumps({"type": "object"}), encoding="utf-8")
        for key in (str(secret), "../" * 12 + str(secret).lstrip("/"), "~/.docker/config.json"):
            with self.subTest(key=key):
                with self.assertRaises(SchemaError):
                    self.store.load(key)
        # Inside the root a plain file name still works.
        document, base = self.store.load("receipt.schema.json")
        self.assertEqual(Path(base).name, "receipt.schema.json")

    def test_both_prefixes_resolve_in_load_and_refs(self) -> None:
        legacy, _ = self.store.load(LEGACY_SCHEMA_PREFIX + "defs.schema.json")
        current, _ = self.store.load(SCHEMA_BASE + "defs.schema.json")
        self.assertIs(legacy, current)
        for prefix in (SCHEMA_BASE, LEGACY_SCHEMA_PREFIX):
            schema = {"$ref": prefix + "defs.schema.json#/$defs/ulid"}
            validator = Validator(resolver=self.store)
            self.assertEqual(validator.validate("01J8ZQ3V6Y7M2N4P6R8S0T2V4W", schema), [])
            self.assertTrue(validator.validate("not a ulid", schema))


class ValidatorSemanticsTests(unittest.TestCase):
    """Local validation by path keeps working through the developer loader."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="openmhs-validator-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "item.schema.json").write_text(json.dumps({
            "type": "object",
            "properties": {"n": {"$ref": "num.schema.json"}},
            "required": ["n"],
        }), encoding="utf-8")
        (root / "num.schema.json").write_text(json.dumps({"type": "integer"}), encoding="utf-8")
        self.schema_path = root / "item.schema.json"

    def test_validate_with_a_schema_path(self) -> None:
        self.assertEqual(validate({"n": 1}, str(self.schema_path)), [])
        self.assertTrue(validate({"n": "x"}, str(self.schema_path)))
        self.assertEqual(validate_file({"n": 2}, self.schema_path), [])
        store = SchemaStore(SCHEMA_DIR)
        self.assertEqual(store.validate({"n": 3}, str(self.schema_path)), [])
        self.assertTrue(store.validate({}, str(self.schema_path)))

    def test_shipped_example_still_validates_by_name(self) -> None:
        store = SchemaStore(SCHEMA_DIR)
        example = json.loads(EXAMPLE_DEVICE.read_text(encoding="utf-8"))
        self.assertEqual(store.validate(example, "device.schema.json"), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
