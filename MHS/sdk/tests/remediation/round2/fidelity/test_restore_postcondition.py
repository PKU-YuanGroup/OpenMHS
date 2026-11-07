"""LEAD-FID-004: restore must not report ``completed`` unless it restored.

Independent oracle for the server-owned restore postcondition (server.py is
Lead's single-writer file; this module never imports server internals beyond the
public JSON-RPC surface).

The review counterexample is a *schema-valid* snapshot that retains the target
``fidelity_digest`` but asks the seeded arm for ``noise_enabled = false``.  Its
``state_hash`` correctly recomputes from the declared state, yet the seeded
bridge keeps its own ``noise_enabled`` flag, so the post-restore state hash
differs.  The server used to return ``completed`` with a different
``state_hash_after``.  Whatever the server chooses (reject before the effect,
roll back and fail, or report UNKNOWN), it must be truthful: ``completed`` only
when the actual post-state hash equals the declared hash, and otherwise the
receipt must match the state a fresh read observes.
"""

from __future__ import annotations

import copy
import unittest

from mhs import canonical
from mhs.reference import build_endpoint, build_server
from mhs.schema import SchemaStore

from . import support
from .support import REPO, SNAPSHOT_SCHEMA

RESOURCE_ID = "arm"
SCHEMA_STORE = SchemaStore(REPO / "MHS" / "schema")


class RestoreOracleMixin:
    """Shared endpoint/session plumbing and the postcondition assertion."""

    def _endpoint(self, *, noise: bool, endpoint_id: str):
        spec = build_endpoint("arm", endpoint_id=endpoint_id, noise=noise)
        server = build_server(spec, log_ready=False)
        device_id = spec.devices[0]["device_id"]
        session_id = support.hello_and_session(server, device_id, "simulated")
        return spec, server, device_id, session_id

    def _read_hash(self, server, session_id, device_id) -> str:
        read = support.read_state(server, session_id, device_id, RESOURCE_ID)
        return str(read["state_hash"])

    def _move(self, server, session_id, device_id, joints):
        return support.rpc(
            server,
            "mhs.command",
            {
                "session_id": session_id,
                "device_id": device_id,
                "capability_id": "cap.motion.joint_position.v1",
                "input": {"joint_positions_deg": joints},
            },
        )

    def _assert_truthful_restore(self, server, session_id, device_id, receipt,
                                 declared_hash: str, before_hash: str) -> None:
        status = receipt.get("status")
        after_hash = self._read_hash(server, session_id, device_id)
        self.assertIn(
            status,
            {"completed", "failed", "unknown", "rejected"},
            f"unexpected restore status {status!r}",
        )
        if status == "completed":
            self.assertEqual(
                after_hash, declared_hash,
                "completed restore did not reproduce the declared state_hash",
            )
            self.assertEqual(receipt.get("state_hash_after"), declared_hash)
            self.assertNotIn("error", receipt)
        elif status == "rejected":
            # A rejection is a claim of no effect; the state must not have moved.
            self.assertEqual(
                after_hash, before_hash,
                "restore was rejected as no-effect but the state changed",
            )
            self.assertEqual(receipt.get("state_hash_after"), before_hash)
        else:
            # failed/unknown may follow a partial effect: the receipt must carry
            # the *actual* post-state hash, never the declared one as a cover.
            self.assertNotEqual(
                after_hash, declared_hash,
                f"{status} receipt claims the declared state was reached",
            )
            self.assertEqual(
                receipt.get("state_hash_after"), after_hash,
                f"{status} receipt state_hash_after is not the observed post-state",
            )
            self.assertIn("error", receipt)
            self.assertTrue(receipt["error"].get("mhs_code"))

    def _assert_receipt_in_evidence(self, server, session_id, device_id, receipt):
        exported = support.rpc(
            server,
            "mhs.evidence.export",
            {"session_id": session_id, "device_id": device_id},
        )
        receipts = exported.get("receipts") or []
        self.assertIn(receipt["receipt_id"], [item.get("receipt_id") for item in receipts])
        verification = support.rpc(
            server,
            "mhs.evidence.verify",
            {"session_id": session_id, "device_id": device_id},
        )
        self.assertTrue(verification["valid"], verification["errors"])
        return exported


class RestorePostconditionTests(RestoreOracleMixin, unittest.TestCase):
    def test_state_hash_must_recompute_from_the_submitted_state(self):
        """A snapshot whose hash only matches the *current* device is invalid.

        PROTO-035 rejects a snapshot "whose state_hash does not recompute".  The
        candidate below is schema-valid and keeps a digest that equals the
        current device hash even though it does not recompute from its own
        declared state (``noise_enabled`` was flipped).  Accepting it as
        ``completed`` would let a contradictory snapshot pass because the
        seeded bridge happens to keep its own flag.
        """

        spec, server, device_id, session_id = self._endpoint(
            noise=True, endpoint_id="mhs://restore-oracle.local:7407"
        )
        try:
            self._move(server, session_id, device_id, [5, 6])
            current = support.snapshot(server, session_id, device_id)
            candidate = copy.deepcopy(current)
            for envelope in ("state", "snapshot"):
                if isinstance(candidate.get(envelope), dict):
                    candidate[envelope][RESOURCE_ID]["noise_enabled"] = False
            candidate["snapshot_digest"] = canonical.digest(candidate["state"])
            # The declared state_hash is a valid digest but does not recompute
            # from the declared state; it only equals the current device hash.
            self.assertNotEqual(
                canonical.state_hash(candidate["state"][RESOURCE_ID], []),
                candidate["state_hash"],
            )
            self.assertEqual(candidate["state_hash"], current["state_hash"])
            self.assertEqual(SCHEMA_STORE.validate(candidate, SNAPSHOT_SCHEMA), [])

            before_hash = self._read_hash(server, session_id, device_id)
            revision_before = support.read_state(
                server, session_id, device_id, RESOURCE_ID
            )["revision"]
            receipt = support.restore(server, session_id, device_id, candidate)
            self.assertEqual(
                receipt["status"], "rejected",
                "a snapshot whose state_hash does not recompute from its state "
                "must be rejected before any effect",
            )
            self.assertEqual(receipt["error"]["mhs_code"], "MHS.CONFLICT.STATE_HASH")
            self.assertEqual(self._read_hash(server, session_id, device_id), before_hash)
            self.assertEqual(
                support.read_state(server, session_id, device_id, RESOURCE_ID)["revision"],
                revision_before,
                "a rejected snapshot must not advance the revision",
            )
        finally:
            spec.close()

    def test_schema_valid_seeded_flag_mismatch_is_never_completed(self):
        spec, server, device_id, session_id = self._endpoint(
            noise=True, endpoint_id="mhs://restore-oracle.local:7400"
        )
        try:
            self._move(server, session_id, device_id, [30, -20])
            original = support.snapshot(server, session_id, device_id)
            candidate = copy.deepcopy(original)
            for envelope in ("state", "snapshot"):
                if isinstance(candidate.get(envelope), dict):
                    candidate[envelope][RESOURCE_ID]["noise_enabled"] = False
            candidate["snapshot_digest"] = canonical.digest(candidate["state"])
            candidate["state_hash"] = canonical.state_hash(
                candidate["state"][RESOURCE_ID], []
            )
            # It is a valid snapshot under the published closed schema and it
            # keeps the target fidelity digest.
            self.assertEqual(SCHEMA_STORE.validate(candidate, SNAPSHOT_SCHEMA), [])
            self.assertEqual(candidate["fidelity_digest"], original["fidelity_digest"])
            self.assertEqual(candidate["state"], candidate["snapshot"])

            before_hash = self._read_hash(server, session_id, device_id)
            receipt = support.restore(server, session_id, device_id, candidate)
            self.assertNotEqual(
                receipt.get("status"), "completed",
                "restore reported completed even though the seeded arm cannot "
                "reproduce the declared state",
            )
            self._assert_truthful_restore(
                server, session_id, device_id, receipt,
                declared_hash=candidate["state_hash"], before_hash=before_hash,
            )
            self._assert_receipt_in_evidence(server, session_id, device_id, receipt)
        finally:
            spec.close()

    def test_stripped_metadata_is_not_accepted_into_another_configuration(self):
        seeded_spec, seeded_server, seeded_device, seeded_session = self._endpoint(
            noise=True, endpoint_id="mhs://restore-oracle.local:7400"
        )
        exact_spec, exact_server, exact_device, exact_session = self._endpoint(
            noise=False, endpoint_id="mhs://restore-oracle.local:7401"
        )
        try:
            self._move(seeded_server, seeded_session, seeded_device, [12, 34])
            snapshot = support.snapshot(seeded_server, seeded_session, seeded_device)
            stripped = copy.deepcopy(snapshot)
            stripped.pop("instance_id")
            stripped.pop("fidelity_digest")
            before_hash = self._read_hash(exact_server, exact_session, exact_device)
            receipt = support.restore(exact_server, exact_session, exact_device, stripped)
            self.assertNotEqual(receipt.get("status"), "completed")
            self._assert_truthful_restore(
                exact_server, exact_session, exact_device, receipt,
                declared_hash=stripped["state_hash"], before_hash=before_hash,
            )
            self.assertEqual(receipt["error"]["mhs_code"], "MHS.CONFLICT.SNAPSHOT_MISMATCH")
        finally:
            seeded_spec.close()
            exact_spec.close()

    def test_exact_round_trip_reproduces_declared_hash(self):
        spec, server, device_id, session_id = self._endpoint(
            noise=False, endpoint_id="mhs://restore-oracle.local:7402"
        )
        try:
            self._move(server, session_id, device_id, [10, 20])
            checkpoint = support.snapshot(server, session_id, device_id)
            self._move(server, session_id, device_id, [40, -15])
            self.assertNotEqual(
                self._read_hash(server, session_id, device_id), checkpoint["state_hash"]
            )
            revision_before_restore = support.read_state(
                server, session_id, device_id, RESOURCE_ID
            )["revision"]
            receipt = support.restore(server, session_id, device_id, checkpoint)
            self.assertEqual(receipt["status"], "completed", receipt.get("error"))
            self.assertEqual(receipt["state_hash_after"], checkpoint["state_hash"])
            self.assertEqual(
                self._read_hash(server, session_id, device_id), checkpoint["state_hash"]
            )
            self.assertEqual(
                receipt["state_revision_after"], revision_before_restore + 1
            )
            self.assertEqual(receipt["state_revision_before"], revision_before_restore)
            self.assertEqual(
                receipt["output"]["state_hash"], checkpoint["state_hash"]
            )
            self._assert_receipt_in_evidence(server, session_id, device_id, receipt)
        finally:
            spec.close()

    def test_seeded_round_trip_reproduces_declared_hash(self):
        spec, server, device_id, session_id = self._endpoint(
            noise=True, endpoint_id="mhs://restore-oracle.local:7403"
        )
        try:
            self._move(server, session_id, device_id, [25, -35])
            checkpoint = support.snapshot(server, session_id, device_id)
            self.assertTrue(checkpoint["state"][RESOURCE_ID]["noise_enabled"])
            self._move(server, session_id, device_id, [55, 10])
            self._move(server, session_id, device_id, [-20, 5])
            receipt = support.restore(server, session_id, device_id, checkpoint)
            self.assertEqual(receipt["status"], "completed", receipt.get("error"))
            self.assertEqual(receipt["state_hash_after"], checkpoint["state_hash"])
            self.assertEqual(
                self._read_hash(server, session_id, device_id), checkpoint["state_hash"]
            )
        finally:
            spec.close()

    def test_cross_configuration_snapshots_are_rejected(self):
        seeded_spec, seeded_server, seeded_device, seeded_session = self._endpoint(
            noise=True, endpoint_id="mhs://restore-oracle.local:7404"
        )
        exact_spec, exact_server, exact_device, exact_session = self._endpoint(
            noise=False, endpoint_id="mhs://restore-oracle.local:7405"
        )
        try:
            self._move(seeded_server, seeded_session, seeded_device, [18, -12])
            seeded_snapshot = support.snapshot(
                seeded_server, seeded_session, seeded_device
            )
            self._move(exact_server, exact_session, exact_device, [7, 9])
            exact_snapshot = support.snapshot(exact_server, exact_session, exact_device)
            self.assertNotEqual(seeded_snapshot["instance_id"], exact_snapshot["instance_id"])
            self.assertNotEqual(
                seeded_snapshot["fidelity_digest"], exact_snapshot["fidelity_digest"]
            )

            before = self._read_hash(exact_server, exact_session, exact_device)
            receipt = support.restore(
                exact_server, exact_session, exact_device, seeded_snapshot
            )
            self.assertEqual(receipt["status"], "rejected")
            self.assertEqual(
                receipt["error"]["mhs_code"], "MHS.CONFLICT.SNAPSHOT_MISMATCH"
            )
            self._assert_truthful_restore(
                exact_server, exact_session, exact_device, receipt,
                declared_hash=seeded_snapshot["state_hash"], before_hash=before,
            )

            before = self._read_hash(seeded_server, seeded_session, seeded_device)
            receipt = support.restore(
                seeded_server, seeded_session, seeded_device, exact_snapshot
            )
            self.assertEqual(receipt["status"], "rejected")
            self.assertEqual(
                receipt["error"]["mhs_code"], "MHS.CONFLICT.SNAPSHOT_MISMATCH"
            )
            self._assert_truthful_restore(
                seeded_server, seeded_session, seeded_device, receipt,
                declared_hash=exact_snapshot["state_hash"], before_hash=before,
            )
        finally:
            seeded_spec.close()
            exact_spec.close()

    def test_repeated_completed_restore_is_idempotent(self):
        spec, server, device_id, session_id = self._endpoint(
            noise=True, endpoint_id="mhs://restore-oracle.local:7406"
        )
        try:
            self._move(server, session_id, device_id, [15, 25])
            checkpoint = support.snapshot(server, session_id, device_id)
            command_id = canonical.ulid()
            first = support.restore(server, session_id, device_id, checkpoint,
                                    command_id=command_id)
            second = support.restore(server, session_id, device_id, checkpoint,
                                     command_id=command_id)
            self.assertEqual(first["status"], "completed", first.get("error"))
            self.assertEqual(second["status"], "completed")
            self.assertTrue(second.get("replayed"), second)
            self.assertEqual(first["receipt_id"], second["receipt_id"])
            self.assertEqual(first["state_revision_after"], second["state_revision_after"])
            self.assertEqual(
                self._read_hash(server, session_id, device_id), checkpoint["state_hash"]
            )
        finally:
            spec.close()


if __name__ == "__main__":
    unittest.main()
