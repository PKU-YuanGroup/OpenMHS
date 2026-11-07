"""LEAD-SNAPSHOT-SCHEMA: the closed snapshot schema must describe the real wire.

Canonical shape decision (shared with LEAD-FID-004):

* ``state`` is the canonical state document (``{resource_id: state}``) named by
  MHS-002 9.1 and served by ``mhs.resource.read``.
* ``snapshot`` is the retained backward-compatible alias of ``state``; the SDK
  emits both and they must be identical.  A snapshot must carry at least one.
* ``instance_id`` is a ULID (``defs.schema.json#/$defs/ulid``), matching the
  identity the server's restore path compares.

The old schema referenced the non-existent ``#/$defs/instanceId`` (SchemaError
for an ordinary SDK snapshot), required ``snapshot`` while the specification
names ``state``, and did not accept the SDK's ``state`` field at all.  These
tests validate snapshots produced by real reference endpoints -- not a
hand-written fixture -- and walk every local ``$ref`` in ``MHS/schema``.
"""

from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

from mhs import canonical, connect
from mhs.reference import build_endpoint, build_server
from mhs.schema import SchemaStore, resolve_pointer

from . import support
from .support import REPO

SCHEMA_DIR = REPO / "MHS" / "schema"
ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def _iter_refs(node):
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            yield ref
        for key, value in node.items():
            if key == "$ref":
                continue
            yield from _iter_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_refs(item)


class LocalRefResolutionTests(unittest.TestCase):
    """No published schema may reference an undefined local target."""

    @classmethod
    def setUpClass(cls):
        cls.store = SchemaStore(SCHEMA_DIR)
        cls.documents = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(SCHEMA_DIR.glob("*.schema.json"))
        }

    def test_every_local_ref_resolves(self):
        self.assertTrue(self.documents, "no schemas found")
        for name, document in self.documents.items():
            for ref in _iter_refs(document):
                with self.subTest(schema=name, ref=ref):
                    uri, _, fragment = ref.partition("#")
                    base = str(SCHEMA_DIR / name)
                    if uri:
                        # Raises SchemaError when the document or pointer is unknown.
                        self.store.resolve_ref(ref, base=base)
                    else:
                        resolve_pointer(document, fragment)

    def test_snapshot_instance_id_targets_ulid(self):
        snapshot = self.documents["snapshot.schema.json"]
        instance = snapshot["properties"]["instance_id"]
        self.assertEqual(instance["$ref"], "defs.schema.json#/$defs/ulid")
        defs = self.documents["defs.schema.json"]
        self.assertIn("ulid", defs["$defs"])
        self.assertNotIn("instanceId", defs["$defs"])

    def test_no_schema_references_the_removed_instance_id_definition(self):
        offenders = []
        for name, document in self.documents.items():
            for ref in _iter_refs(document):
                if ref.endswith("#/$defs/instanceId"):
                    offenders.append((name, ref))
        self.assertEqual(offenders, [])


class RealSnapshotContractTests(unittest.TestCase):
    """A real SDK snapshot validates against the published closed schema."""

    @classmethod
    def setUpClass(cls):
        cls.store = SchemaStore(SCHEMA_DIR)
        # Wire path: reference arm endpoint -> HTTP -> SDK client -> snapshot.
        cls.arm_spec = build_endpoint(
            "arm", endpoint_id="mhs://snapshot-contract.local:7400", noise=True
        )
        cls.arm_server = build_server(cls.arm_spec, log_ready=False)
        cls.arm_handle = cls.arm_server.start_http("127.0.0.1", 0)
        cls.arm_client = connect(cls.arm_handle.url)
        cls.arm_device_id = cls.arm_spec.devices[0]["device_id"]
        cls.arm_client.open_session([cls.arm_device_id], capabilities=None,
                                    mode="simulated", ttl_s=300)
        cls.arm_snapshot = cls.arm_client.snapshot(cls.arm_device_id)

    @classmethod
    def tearDownClass(cls):
        cls.arm_client.close()
        cls.arm_handle.shutdown()
        cls.arm_spec.close()

    def _in_process_snapshot(self, endpoint_name: str):
        spec = build_endpoint(endpoint_name, endpoint_id="mhs://snapshot-contract.local:7401")
        server = build_server(spec, log_ready=False)
        try:
            device_id = spec.devices[0]["device_id"]
            session_id = support.hello_and_session(server, device_id, "simulated")
            snapshot = support.snapshot(server, session_id, device_id)
            return snapshot, copy.deepcopy(spec.devices[0])
        finally:
            spec.close()

    def test_real_arm_snapshot_validates(self):
        snapshot = copy.deepcopy(self.arm_snapshot)
        errors = self.store.validate(snapshot, "snapshot.schema.json")
        self.assertEqual(errors, [], f"real SDK snapshot does not validate: {errors}")

    def test_real_conveyor_snapshot_validates(self):
        snapshot, manifest = self._in_process_snapshot("conveyor")
        self.assertEqual(self.store.validate(snapshot, "snapshot.schema.json"), [])
        resource = manifest["resources"][0]
        self.assertEqual(
            snapshot["state_hash"],
            canonical.state_hash(snapshot["state"][resource["resource_id"]],
                                 resource.get("hash_exclusions") or []),
        )

    def test_real_arm_snapshot_is_self_consistent(self):
        snapshot = self.arm_snapshot
        manifest = self.arm_spec.devices[0]
        resource = manifest["resources"][0]
        self.assertEqual(snapshot["state"], snapshot["snapshot"],
                         "state and the snapshot alias must be identical")
        self.assertEqual(snapshot["snapshot_digest"], canonical.digest(snapshot["snapshot"]))
        self.assertEqual(
            snapshot["state_hash"],
            canonical.state_hash(snapshot["state"][resource["resource_id"]],
                                 resource.get("hash_exclusions") or []),
        )
        self.assertEqual(snapshot["device_id"], manifest["device_id"])
        self.assertEqual(snapshot["instance_id"], manifest["instance_id"])
        self.assertRegex(snapshot["instance_id"], ULID_RE)
        self.assertEqual(snapshot["mode"], manifest["mode"])
        self.assertEqual(snapshot["fidelity_digest"], canonical.digest(manifest["fidelity"]))
        self.assertEqual(
            set(snapshot),
            {
                "device_id", "instance_id", "mode", "revision", "state_hash",
                "state", "snapshot", "snapshot_digest", "fidelity_digest", "created_at",
            },
        )

    def test_schema_accepts_each_alias_alone(self):
        only_state = copy.deepcopy(self.arm_snapshot)
        only_state.pop("snapshot")
        self.assertEqual(self.store.validate(only_state, "snapshot.schema.json"), [])
        only_alias = copy.deepcopy(self.arm_snapshot)
        only_alias.pop("state")
        self.assertEqual(self.store.validate(only_alias, "snapshot.schema.json"), [])

    def test_schema_rejects_snapshot_without_any_state_document(self):
        candidate = copy.deepcopy(self.arm_snapshot)
        candidate.pop("state")
        candidate.pop("snapshot")
        self.assertTrue(self.store.validate(candidate, "snapshot.schema.json"))

    def test_schema_is_still_closed(self):
        candidate = copy.deepcopy(self.arm_snapshot)
        candidate["unexpected"] = True
        self.assertTrue(self.store.validate(candidate, "snapshot.schema.json"))

    def test_identity_metadata_is_mandatory_and_typed(self):
        for field in ("device_id", "instance_id", "mode", "revision", "state_hash",
                      "snapshot_digest", "fidelity_digest"):
            with self.subTest(field=field):
                candidate = copy.deepcopy(self.arm_snapshot)
                candidate.pop(field)
                self.assertTrue(
                    self.store.validate(candidate, "snapshot.schema.json"),
                    f"missing {field} must not validate",
                )
        for field, value in (
            ("instance_id", "not-a-ulid"),
            ("state_hash", "sha256:nothex"),
            ("fidelity_digest", []),
            ("mode", "turbo"),
        ):
            with self.subTest(field=field, value=repr(value)):
                candidate = copy.deepcopy(self.arm_snapshot)
                candidate[field] = value
                self.assertTrue(self.store.validate(candidate, "snapshot.schema.json"))

    def test_schema_error_no_longer_escapes_as_exception(self):
        """The old $ref raised SchemaError instead of returning errors."""

        try:
            errors = self.store.validate(copy.deepcopy(self.arm_snapshot),
                                         "snapshot.schema.json")
        except Exception as exc:  # noqa: BLE001 - the defect under test
            self.fail(f"snapshot validation raised {type(exc).__name__}: {exc}")
        self.assertIsInstance(errors, list)


if __name__ == "__main__":
    unittest.main()
