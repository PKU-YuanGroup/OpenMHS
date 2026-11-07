#!/usr/bin/env python3
"""RREG-001 federation identity-retention tests (MHS-007 REG-034/REG-035).

The static reference registry in this repository has no network federation
client, so this module pins the record-level merge contract that any client must
implement: records published by different registries validate against the same
shared schema, merging retains every originating ``registry_id`` and its own
``trust``, and two different bodies for the same ``id`` remain visible as a
conflict instead of one silently replacing the other.

The merge helper below is a deliberately small reference oracle (deterministic
sorted-key JSON digest, not a full JCS implementation); it exists to make the
identity-retention and conflict requirements executable without inventing a
network federation service.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
WORKSPACE = os.path.abspath(os.path.join(REG, "..", ".."))
SCHEMA_DIR = os.path.join(WORKSPACE, "MHS", "schema")

sys.path.insert(0, REG)
import validate as V  # noqa: E402

#: Fields of the common envelope that identify provenance rather than body.
_PROVENANCE_FIELDS = {"registry_id", "trust", "signatures", "updated_at"}


def base_record(**overrides):
    doc = {
        "record_type": "package",
        "id": "gh.acme/widget",
        "registry_id": "openmhs-registry",
        "package_id": "gh.acme/widget",
        "repo_url": "https://github.com/acme/widget",
        "track": "labs",
        "families": ["python-object"],
        "tier": "B",
        "ring": 2,
        "modes": ["simulated"],
        "capabilities_offered": ["cap.device.describe.v1"],
        "description": "Acme widget adapter",
        "evidence": {"state": "static_scan", "read_by": "static_analysis"},
        "trust": "unsigned",
        "updated_at": "2026-10-20T00:00:00Z",
    }
    doc.update(overrides)
    return doc


def body_digest(record):
    """Deterministic digest of the record body, excluding provenance fields."""
    body = {key: value for key, value in record.items() if key not in _PROVENANCE_FIELDS}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def merge_federated_records(records):
    """REG-035 merge oracle: keep every origin/trust, flag body conflicts.

    Returns one entry per ``id``.  ``origins`` always retains the publishing
    ``registry_id`` and that registry's own ``trust``; ``merged``/``body`` are
    only populated when every copy has the same body digest, and ``conflict``
    is true when they do not.
    """
    grouped = {}
    order = []
    for record in records:
        record_id = record.get("id")
        if record_id not in grouped:
            grouped[record_id] = []
            order.append(record_id)
        grouped[record_id].append(record)
    merged = []
    for record_id in order:
        copies = grouped[record_id]
        origins = [
            {
                "registry_id": item.get("registry_id"),
                "trust": item.get("trust"),
                "body_digest": body_digest(item),
            }
            for item in copies
        ]
        digests = {origin["body_digest"] for origin in origins}
        entry = {
            "id": record_id,
            "origins": origins,
            "conflict": len(digests) > 1,
            "merged": len(digests) == 1,
            "body_digest": next(iter(digests)) if len(digests) == 1 else None,
            "body": None,
        }
        if len(digests) == 1:
            entry["body"] = {
                key: copy.deepcopy(value)
                for key, value in copies[0].items()
                if key not in _PROVENANCE_FIELDS
            }
        merged.append(entry)
    return merged


class FederationIdentityRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = V.SchemaStore(SCHEMA_DIR)
        cls.validator = V.Validator(cls.store)
        cls.schema = cls.store.schemas["registry-record.schema.json"]

    def errors(self, doc):
        return self.validator.validate(doc, self.schema, "registry-record.schema.json")

    def test_same_package_id_from_two_registries_both_validate(self):
        first = base_record()
        second = base_record(
            registry_id="registry.example.org",
            trust="self_signed",
            description="Independent mirror of the Acme widget adapter",
        )
        self.assertEqual(self.errors(first), [])
        self.assertEqual(self.errors(second), [])
        self.assertEqual(first["id"], second["id"])

    def test_merge_retains_origin_registry_and_trust(self):
        first = base_record(trust="registry_verified")
        second = base_record(
            registry_id="registry.example.org",
            trust="self_signed",
        )
        [merged] = merge_federated_records([first, second])
        self.assertEqual(merged["id"], "gh.acme/widget")
        origins = {(item["registry_id"], item["trust"]) for item in merged["origins"]}
        self.assertEqual(
            origins,
            {
                ("openmhs-registry", "registry_verified"),
                ("registry.example.org", "self_signed"),
            },
        )
        # Trust is not upgraded merely because two registries list the record.
        self.assertNotIn("trust", merged["body"])

    def test_same_id_different_body_stays_visible_as_a_conflict(self):
        first = base_record(description="vendor description")
        second = base_record(
            registry_id="registry.example.org",
            description="mirror description with different body",
        )
        [merged] = merge_federated_records([first, second])
        self.assertTrue(merged["conflict"])
        self.assertFalse(merged["merged"])
        self.assertIsNone(merged["body"])
        self.assertEqual(len(merged["origins"]), 2)
        self.assertEqual(len({item["body_digest"] for item in merged["origins"]}), 2)

    def test_identical_bodies_merge_without_losing_either_origin(self):
        first = base_record(trust="registry_verified")
        second = base_record(
            registry_id="registry.example.org",
            trust="self_signed",
            updated_at="2026-10-21T00:00:00Z",  # provenance, not body
        )
        [merged] = merge_federated_records([first, second])
        self.assertFalse(merged["conflict"])
        self.assertTrue(merged["merged"])
        self.assertIsNotNone(merged["body"])
        self.assertEqual(len(merged["origins"]), 2)
        self.assertEqual(
            {item["registry_id"] for item in merged["origins"]},
            {"openmhs-registry", "registry.example.org"},
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
