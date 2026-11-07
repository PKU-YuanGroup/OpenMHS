"""End-to-end tests for the MHS server + client over stdio (T1)."""

from __future__ import annotations

import json
import sys
import unittest

from mhs import __version__
from mhs.client import connect
from mhs.errors import MHSError


def _conveyor():
    return connect([sys.executable, "-m", "mhs.reference", "conveyor", "--stdio"])


class ConveyorContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _conveyor()
        cls.device_id = cls.client.devices()[0]["device_id"]
        cls.session = cls.client.open_session([cls.device_id], mode="simulated")

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_hello(self):
        result = self.client.hello()
        self.assertEqual(result["mhs_version"], "1.0")
        self.assertIn("MHS.SAFETY.NOT_CERTIFIED", result["features"])

    def test_devices_and_manifest(self):
        manifest = self.client.inspect(self.device_id)
        self.assertEqual(manifest["device_id"], self.device_id)
        self.assertEqual(manifest["mode"], "simulated")
        self.assertIn("fidelity", manifest)
        self.assertIn("gaps", manifest["fidelity"])

    def test_read_state(self):
        state = self.client.read("workcell", device_id=self.device_id)
        self.assertIn("state", state)
        self.assertIn("revision", state)
        self.assertTrue(str(state["state_hash"]).startswith("sha256:"))

    def test_step_and_idempotency(self):
        first = self.client.invoke("cap.world.step.v1", {"ticks": 3}, device_id=self.device_id)
        self.assertEqual(first["status"], "completed")
        replay = self.client.invoke("cap.world.step.v1", {"ticks": 3}, device_id=self.device_id,
                                    command_id=first["command_id"])
        self.assertTrue(replay["replayed"])

    def test_command_id_reuse_conflict(self):
        # A conflicting reuse is refused without effect and reported as a
        # rejected receipt (the retained receipt of the first call is untouched).
        first = self.client.invoke("cap.world.step.v1", {"ticks": 1}, device_id=self.device_id)
        conflict = self.client.invoke("cap.world.step.v1", {"ticks": 2}, device_id=self.device_id,
                                      command_id=first["command_id"])
        self.assertEqual(conflict["status"], "rejected")
        self.assertEqual(conflict["error"]["mhs_code"], "MHS.CONFLICT.COMMAND_ID_REUSE")

    def test_invalid_input_rejected(self):
        # A refused physical action is a receipt (evidence), not an exception.
        receipt = self.client.invoke("cap.world.step.v1", {"ticks": "five"}, device_id=self.device_id)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        # A shape-correct value outside the limited range is a safety refusal
        # (WP-04 4c: limits are evaluated before the schema's own bounds).
        receipt = self.client.invoke("cap.world.step.v1", {"ticks": -5}, device_id=self.device_id)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(receipt["error"]["details"]["path"], "ticks")

    def test_exclusive_unknown_capability(self):
        before = self.client.read("workcell", device_id=self.device_id)["revision"]
        receipt = self.client.invoke("cap.does.not_exist.v1", {}, device_id=self.device_id)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.UNKNOWN")
        after = self.client.read("workcell", device_id=self.device_id)["revision"]
        self.assertEqual(before, after, "a rejected command must not advance the revision")

    def test_snapshot_and_restore(self):
        snap = self.client.snapshot(device_id=self.device_id)
        self.assertIn("snapshot", snap)
        # Restore takes the full snapshot document: identity/fidelity metadata
        # is part of the contract (LEAD-FID-004), the inner state alias is not.
        restored = self.client.restore(snap, device_id=self.device_id)
        self.assertEqual(restored["status"], "completed")

    def test_estop_latches_and_reset(self):
        try:
            estop = self.client.estop("test stop", device_id=self.device_id)
            self.assertTrue(estop["output"]["latched"])
            status = self.client.safety_status(self.device_id)
            self.assertTrue(status["estop"]["engaged"])
            refused = self.client.invoke("cap.world.step.v1", {"ticks": 1}, device_id=self.device_id)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
        finally:
            reset = self.client.reset(device_id=self.device_id)
        self.assertTrue(reset["output"]["reset"])

    def test_evidence_chain_verifies(self):
        bundle = self.client.export_evidence()
        result = self.client.verify_evidence(bundle)
        self.assertTrue(result["valid"], result.get("errors"))
        self.assertGreater(result["checked"], 0)

    def test_subscriptions_sequence(self):
        subscription_id = self.client.subscribe(["state"], device_id=self.device_id)
        self.client.invoke("cap.world.step.v1", {"ticks": 1}, device_id=self.device_id)
        events = []
        for _ in range(50):
            events = [e for e in self.client.events() if e.get("method") == "mhs.event"]
            if events:
                break
        self.client.unsubscribe(subscription_id)
        self.assertTrue(any(e.get("params", {}).get("subscription_id") == subscription_id for e in events))


class ErrorPathTest(unittest.TestCase):
    def test_missing_session(self):
        with _conveyor() as client:
            with self.assertRaises(MHSError) as ctx:
                client.read("workcell")
            self.assertEqual(ctx.exception.code, "MHS.SESSION.UNKNOWN")

    def test_permit_required_for_actuation(self):
        with _conveyor() as client:
            device_id = client.devices()[0]["device_id"]
            client.open_session([device_id], mode="simulated")
            manifest = client.inspect(device_id)
            gated = [c["capability_id"] for c in manifest["capabilities"] if c.get("requires_permit")]
            if not gated:
                self.skipTest("endpoint has no permit-gated capability")
            receipt = client.invoke(gated[0], {"gate": "main"}, device_id=device_id)
            self.assertEqual(receipt["status"], "rejected")
            self.assertIn(
                receipt["error"]["mhs_code"],
                ("MHS.SAFETY.PERMIT_INVALID", "MHS.CAPABILITY.INPUT_INVALID"),
            )


if __name__ == "__main__":
    unittest.main()
