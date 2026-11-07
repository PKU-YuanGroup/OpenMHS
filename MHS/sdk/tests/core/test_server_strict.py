"""Strict contract tests for MHSServer + MHSClient over stdio (T1).

These cases map one-to-one to the wire requirements exercised by a host:
discovery, sessions, receipts for every negative outcome, revisions, permits,
interlocks, e-stop/reset, deadlines/cancellation, snapshots and evidence.
"""

from __future__ import annotations

import sys
import time
import unittest

from mhs import canonical, connect
from mhs.errors import MHSError
from mhs.schema import SchemaStore


def _conveyor():
    return connect([sys.executable, "-m", "mhs.reference", "conveyor", "--stdio", "--test-profile"])


class StdioContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _conveyor()
        cls.store = SchemaStore()
        cls.hello = cls.client.hello()
        cls.devices = cls.client.devices()
        cls.device_id = cls.devices[0]["device_id"]
        cls.session = cls.client.open_session(
            [cls.device_id], capabilities=None, mode="simulated", ttl_s=600
        )
        cls.session_id = cls.session["session_id"]

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.close()
        except Exception:  # noqa: BLE001
            pass

    # -- helpers -----------------------------------------------------
    def _code(self, receipt):
        return (receipt.get("error") or {}).get("mhs_code") if isinstance(receipt, dict) else None

    def _step(self, ticks=1, **kwargs):
        return self.client.invoke(
            "cap.world.step.v1", {"ticks": ticks}, device_id=self.device_id, **kwargs
        )

    def _revision(self):
        return self.client.read("workcell", device_id=self.device_id)["revision"]

    # -- discovery ---------------------------------------------------
    def test_hello_discovery(self):
        self.assertEqual(self.hello["mhs_version"], "1.0")
        self.assertIn("MHS.SAFETY.NOT_CERTIFIED", self.hello["features"])
        self.assertIsInstance(self.hello["conformance"], list)
        limits = self.hello["limits"]
        for key in ("max_request_bytes", "max_batch", "max_subscriptions",
                    "session_max_ttl_s", "receipt_retention_days"):
            self.assertIn(key, limits)

    def test_manifests_validate_and_include_fidelity(self):
        self.assertTrue(self.devices)
        for manifest in self.devices:
            errors = self.store.validate(manifest, "device.schema.json")
            self.assertEqual(errors, [], errors[:5])
            if manifest["mode"] in ("simulated", "hybrid"):
                self.assertIn("fidelity", manifest)
                self.assertIn("gaps", manifest["fidelity"])
                self.assertTrue(manifest["fidelity"]["snapshot_restore"])
        inspected = self.client.inspect(self.device_id)
        self.assertEqual(inspected["device_id"], self.device_id)
        self.assertTrue(inspected["capabilities"])

    def test_schema_get_serves_schema_and_digest(self):
        result = self.client.get_schema("device.schema.json")
        self.assertIn("schema", result)
        self.assertEqual(result["digest"], canonical.digest(result["schema"]))
        capability = self.client.get_schema("cap.world.step.v1")
        self.assertEqual(capability["schema"]["capability_id"], "cap.world.step.v1")
        self.assertEqual(capability["digest"], canonical.digest(capability["schema"]))

    # -- sessions ----------------------------------------------------
    def test_least_privilege_and_forbidden_capability(self):
        narrow = self.client.open_session(
            [self.device_id], capabilities=["cap.world.step.v1"], mode="simulated", ttl_s=60
        )
        self.assertEqual(len(narrow["granted"]), 1)
        with self.assertRaises(MHSError) as ctx:
            self.client.invoke(
                "cap.actuation.valve.v1", {"gate": "main"},
                device_id=self.device_id, session_id=narrow["session_id"],
            )
        self.assertEqual(ctx.exception.code, "MHS.SESSION.CAPABILITY_NOT_GRANTED")
        # Close it so the shared default session stays untouched.
        self.client.close_session(narrow["session_id"])
        self.client.session_id = self.session_id

    def test_heartbeat_and_session_mode_mismatch(self):
        beat = self.client.heartbeat(self.session_id)
        self.assertIn("expires_at", beat)
        with self.assertRaises(MHSError) as ctx:
            self.client.open_session([self.device_id], capabilities=None, mode="hardware", ttl_s=10)
        self.assertEqual(ctx.exception.code, "MHS.SESSION.MODE_MISMATCH")

    def test_expired_session_is_a_session_error(self):
        short = self.client.open_session(
            [self.device_id], capabilities=None, mode="simulated", ttl_s=1
        )
        time.sleep(1.2)
        with self.assertRaises(MHSError) as ctx:
            self.client.read("workcell", device_id=self.device_id,
                             session_id=short["session_id"])
        self.assertEqual(ctx.exception.code, "MHS.SESSION.EXPIRED")
        self.client.session_id = self.session_id

    # -- reads / negative receipts ----------------------------------
    def test_read_state_hash_recomputes(self):
        result = self.client.read("workcell", device_id=self.device_id)
        resource = next(r for r in self.client.inspect(self.device_id)["resources"]
                        if r["resource_id"] == "workcell")
        self.assertEqual(
            result["state_hash"],
            canonical.state_hash(result["state"], resource.get("hash_exclusions") or []),
        )
        self.assertIsInstance(result["revision"], int)

    def test_invalid_input_is_a_rejected_receipt_without_effect(self):
        revision = self._revision()
        receipt = self._step("five")
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(self._code(receipt), "MHS.CAPABILITY.INPUT_INVALID")
        # WP-04 4c: a limited field out of range is a safety refusal.
        receipt = self._step(-5)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(self._code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(self._revision(), revision)

    def test_revision_conflict_is_a_rejected_receipt(self):
        revision = self._revision()
        receipt = self._step(1, expected_revision=revision + 7)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(self._code(receipt), "MHS.CONFLICT.REVISION")
        self.assertEqual((receipt.get("error") or {}).get("current_revision"), revision)
        self.assertEqual(self._revision(), revision)

    def test_unknown_capability_is_a_rejected_receipt(self):
        receipt = self.client.invoke("cap.mhs.nope.v1", {}, device_id=self.device_id)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(self._code(receipt), "MHS.CAPABILITY.UNKNOWN")

    def test_duplicate_command_id_replay_and_conflict(self):
        first = self._step(2)
        self.assertEqual(first["status"], "completed")
        revision = first["state_revision_after"]
        replay = self._step(2, command_id=first["command_id"])
        self.assertEqual(replay["status"], "completed")
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["receipt_id"], first["receipt_id"])
        self.assertEqual(self._revision(), revision)
        conflict = self._step(3, command_id=first["command_id"])
        self.assertEqual(conflict["status"], "rejected")
        self.assertEqual(self._code(conflict), "MHS.CONFLICT.COMMAND_ID_REUSE")
        self.assertEqual(self._revision(), revision)
        # The retained receipt is not overwritten.
        replay_again = self._step(2, command_id=first["command_id"])
        self.assertTrue(replay_again["replayed"])
        self.assertEqual(replay_again["receipt_id"], first["receipt_id"])

    def test_rejection_is_not_retained_as_the_command_outcome(self):
        revision = self._revision()
        command_id = canonical.ulid()
        rejected = self._step(1, command_id=command_id, expected_revision=revision + 5)
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(self._code(rejected), "MHS.CONFLICT.REVISION")
        # A retry of the same command_id after fixing the revision must execute.
        accepted = self._step(1, command_id=command_id, expected_revision=revision)
        self.assertEqual(accepted["status"], "completed")
        self.assertFalse(accepted.get("replayed"))
        self.assertNotEqual(accepted["receipt_id"], rejected["receipt_id"])

    # -- safety ------------------------------------------------------
    def test_open_interlock_blocks_actuation(self):
        opened = self.client.invoke(
            "x-cap.mhs-test.set_door.v1", {"state": "open"}, device_id=self.device_id
        )
        self.assertEqual(opened["status"], "completed")
        try:
            # Plan 3.6: the permit (step 10) is checked before the interlocks
            # (step 11), so the valve's permit is issued first.
            permit = self.client.permit(
                "cap.actuation.valve.v1", {"gate": "main"}, device_id=self.device_id,
                resource=self.client.capability_resource("cap.actuation.valve.v1", device_id=self.device_id),
            )
            receipt = self.client.invoke(
                "cap.actuation.valve.v1", {"gate": "main"}, device_id=self.device_id,
                permit_id=permit["permit_id"],
            )
            self.assertEqual(receipt["status"], "rejected")
            self.assertEqual(self._code(receipt), "MHS.SAFETY.INTERLOCK_OPEN")
            self.assertEqual((receipt.get("error") or {}).get("interlocks")[0]["state"], "open")
        finally:
            self.client.invoke(
                "x-cap.mhs-test.set_door.v1", {"state": "closed"}, device_id=self.device_id
            )
            self.client.reset(self.device_id)

    def test_envelope_violation_blocks_effects(self):
        revision = self._revision()
        receipt = self._step(10_001)
        self.assertEqual(receipt["status"], "rejected")
        self.assertIn(self._code(receipt),
                      ("MHS.SAFETY.ENVELOPE_VIOLATION", "MHS.CAPABILITY.INPUT_INVALID"))
        self.assertEqual(self._revision(), revision)

    def test_permit_required_valid_and_single_use(self):
        payload = {"gate": "divert"}
        missing = self.client.invoke("cap.actuation.valve.v1", payload, device_id=self.device_id)
        self.assertEqual(missing["status"], "rejected")
        self.assertIn(self._code(missing),
                      ("MHS.SAFETY.PERMIT_INVALID", "MHS.SAFETY.APPROVAL_REQUIRED"))
        permit = self.client.permit(
            "cap.actuation.valve.v1", payload, ttl_s=60,
            resource=self.client.capability_resource(
                "cap.actuation.valve.v1", device_id=self.device_id
            ),
        )
        self.assertIn("permit_id", permit)
        granted = self.client.invoke(
            "cap.actuation.valve.v1", payload, device_id=self.device_id,
            permit_id=permit["permit_id"],
        )
        self.assertEqual(granted["status"], "completed")
        # A single-use permit cannot be presented again, even with the same input.
        reused = self.client.invoke(
            "cap.actuation.valve.v1", payload, device_id=self.device_id,
            permit_id=permit["permit_id"],
        )
        self.assertEqual(reused["status"], "rejected")
        self.assertEqual(self._code(reused), "MHS.SAFETY.PERMIT_INVALID")
        # Return the gate to the declared safe position with a fresh permit.
        safe_permit = self.client.permit(
            "cap.actuation.valve.v1", {"gate": "main"},
            resource=self.client.capability_resource(
                "cap.actuation.valve.v1", device_id=self.device_id
            ),
        )
        self.client.invoke("cap.actuation.valve.v1", {"gate": "main"},
                           device_id=self.device_id, permit_id=safe_permit["permit_id"])

    def test_estop_latches_blocks_and_reset_recovers(self):
        estop = self.client.estop("contract test", device_id=self.device_id)
        self.assertEqual(estop["status"], "completed")
        status = self.client.safety_status(self.device_id)
        self.assertTrue(status["estop"]["engaged"])
        blocked = self._step(1)
        self.assertEqual(blocked["status"], "rejected")
        self.assertIn(self._code(blocked),
                      ("MHS.SAFETY.ESTOP_ENGAGED", "MHS.SAFETY.INTERLOCK_OPEN"))
        reset = self.client.reset(self.device_id)
        self.assertEqual(reset["status"], "completed")
        status = self.client.safety_status(self.device_id)
        self.assertFalse(status["estop"]["engaged"])
        recovered = self._step(1)
        self.assertEqual(recovered["status"], "completed")

    # -- deadlines / cancellation -----------------------------------
    def test_deadline_returns_a_bounded_timeout_receipt(self):
        started = time.monotonic()
        receipt = self.client.invoke(
            "x-cap.mhs-test.delay.v1", {"ms": 800}, device_id=self.device_id, deadline_ms=100
        )
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 2.0, "deadline was not enforced")
        self.assertIn(receipt["status"], ("unknown", "rejected", "failed", "running", "accepted"))
        self.assertIn(self._code(receipt), (None, "MHS.OUTCOME.TIMEOUT"))
        if receipt.get("operation_id"):
            cancelled = self.client.cancel(receipt["operation_id"], 5000)
            self.assertIn(cancelled["status"], ("cancelled", "completed", "running"))
            if cancelled.get("status") == "cancelled":
                self.assertTrue(cancelled["cancellation"]["safe_state_achieved"])

    def test_cancellation_reaches_safe_state(self):
        running = self.client.invoke(
            "x-cap.mhs-test.delay.v1", {"ms": 1500}, device_id=self.device_id, deadline_ms=150
        )
        self.assertIn(running["status"], ("unknown", "running", "accepted"))
        self.assertTrue(running.get("operation_id"))
        result = self.client.cancel(running["operation_id"], 5000)
        self.assertIn(result["status"], ("cancelled", "completed", "running"))
        if result["status"] == "cancelled":
            self.assertTrue(result["cancellation"]["safe_state_achieved"])
        elif result["status"] == "running":
            self.assertFalse(result["cancellation"]["safe_state_achieved"])
        status = self.client.safety_status(self.device_id)
        self.assertTrue(status["safe_state"]["description"])
        ops = self.client.operations(device_id=self.device_id)["operations"]
        self.assertTrue(any(op["operation_id"] == running["operation_id"] for op in ops))

    # -- snapshots / evidence ---------------------------------------
    def test_snapshot_restore_revision_and_hash(self):
        before = self.client.read("workcell", device_id=self.device_id)
        snapshot = self.client.snapshot(self.device_id)
        self.assertEqual(snapshot["state_hash"], before["state_hash"])
        receipt = self._step(3)
        self.assertEqual(receipt["status"], "completed")
        restored = self.client.restore(snapshot, self.device_id)
        self.assertEqual(restored["status"], "completed", restored.get("error"))
        after = self.client.read("workcell", device_id=self.device_id)
        self.assertEqual(after["state_hash"], snapshot["state_hash"])
        self.assertGreater(after["revision"], before["revision"])

    def test_evidence_chain_and_receipt_schema(self):
        bundle = self.client.export_evidence()
        self.assertTrue(bundle["receipts"])
        result = self.client.verify_evidence(bundle)
        self.assertTrue(result["valid"], result.get("errors"))
        self.assertEqual(result["checked"], len(bundle["receipts"]))
        for receipt in bundle["receipts"]:
            errors = self.store.validate(receipt, "receipt.schema.json")
            self.assertEqual(errors, [], f"{receipt.get('receipt_id')}: {errors[:3]}")

    def test_conformance_report_validates(self):
        report = self.client.request("mhs.conformance.report",
                                     {"profile": "MHS-Sim", "level": "CL4"})
        self.assertEqual(self.store.validate(report, "conformance-report.schema.json"), [])
        self.assertEqual(report["subject"]["id"], self.hello["endpoint_id"])
        # No run_suite report is stored on the endpoint: nothing executed,
        # nothing claimed (finding SDK-12; WP-04 4a2).
        self.assertEqual(report["level_claimed"], "CL4")
        self.assertEqual(report["level_achieved"], "CL0")
        self.assertNotIn("pass", {test["status"] for test in report["tests"]})

    # -- subscriptions / batching ----------------------------------
    def test_subscriptions_and_event_sequence(self):
        subscription = self.client.subscribe(["state"], device_id=self.device_id, filter=None)
        try:
            self._step(1)
            self._step(1)
            # Wait deterministically for two distinct state events instead of
            # assuming both are delivered in one drain (timing-sensitive on 3.10).
            state_events: list[dict] = []
            seen_sequences: set[int] = set()
            for _attempt in range(80):
                for event in self.client.events(subscription, timeout=0.1):
                    if event.get("method") != "mhs.event":
                        continue
                    params = event.get("params") or {}
                    if params.get("stream") != "state":
                        continue
                    sequence = params.get("seq")
                    if isinstance(sequence, int) and sequence not in seen_sequences:
                        seen_sequences.add(sequence)
                        state_events.append(event)
                if len(state_events) >= 2:
                    break
            self.assertGreaterEqual(len(state_events), 2)
            sequences = [event["params"]["seq"] for event in state_events]
            self.assertEqual(sequences, sorted(sequences))
            self.assertEqual(len(set(sequences)), len(sequences))
        finally:
            end = self.client.unsubscribe(subscription)
            self.assertIn("seq_end", end)

    def test_batch_roundtrip(self):
        results = self.client.batch([
            {"method": "mhs.hello", "params": {}},
            {"method": "mhs.safety.status",
             "params": {"device_id": self.device_id, "deadline_ms": 1000}},
        ])
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]["ok"])
        self.assertEqual(results[0]["result"]["mhs_version"], "1.0")
        self.assertTrue(results[1]["ok"])


if __name__ == "__main__":
    unittest.main()
