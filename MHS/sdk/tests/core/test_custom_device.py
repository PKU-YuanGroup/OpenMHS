"""Full contract test against a purpose-built in-test device over stdio."""

from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path

from mhs import canonical, connect
from mhs.errors import MHSError
from mhs.schema import SchemaStore

HERE = Path(__file__).resolve().parent
SERVER = HERE / "_device_server.py"


class CustomDeviceTest(unittest.TestCase):
    def setUp(self):
        # A fresh endpoint per test keeps the safety state independent between
        # cases (latching e-stops and open doors are sticky by design).
        self.client = connect([sys.executable, str(SERVER)])
        self.store = SchemaStore()
        self.hello = self.client.hello()
        self.manifest = self.client.devices()[0]
        self.device_id = self.manifest["device_id"]
        self.client.open_session([self.device_id], capabilities=None, mode="simulated", ttl_s=600)

    def tearDown(self):
        self.client.close()

    def test_manifest_and_discovery(self):
        self.assertEqual(self.store.validate(self.manifest, "device.schema.json"), [])
        self.assertEqual(self.manifest["mode"], "simulated")
        self.assertEqual(self.manifest["safety"]["risk_class"], "R1")
        self.assertIn("MHS.SAFETY.NOT_CERTIFIED", self.hello["features"])

    def test_state_hash_and_step_receipts(self):
        before = self.client.read("world", device_id=self.device_id)
        self.assertEqual(
            before["state_hash"],
            canonical.state_hash(before["state"], ["/mono_ms"]),
        )
        receipt = self.client.invoke(
            "cap.world.step.v1", {"ticks": 4}, device_id=self.device_id
        )
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["state_revision_after"], before["revision"] + 1)
        self.assertEqual(
            receipt["state_hash_after"],
            self.client.read("world", device_id=self.device_id)["state_hash"],
        )
        replay = self.client.invoke(
            "cap.world.step.v1", {"ticks": 4}, device_id=self.device_id,
            command_id=receipt["command_id"],
        )
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["receipt_id"], receipt["receipt_id"])

    def test_negative_receipts(self):
        revision = self.client.read("world", device_id=self.device_id)["revision"]
        stale = self.client.invoke(
            "cap.world.step.v1", {"ticks": 1}, device_id=self.device_id,
            expected_revision=revision + 10,
        )
        self.assertEqual(stale["status"], "rejected")
        self.assertEqual(stale["error"]["mhs_code"], "MHS.CONFLICT.REVISION")
        self.assertEqual(stale["error"]["current_revision"], revision)
        invalid = self.client.invoke(
            "cap.world.step.v1", {"ticks": 1000}, device_id=self.device_id
        )
        self.assertEqual(invalid["status"], "rejected")
        self.assertIn(invalid["error"]["mhs_code"],
                      ("MHS.CAPABILITY.INPUT_INVALID", "MHS.SAFETY.ENVELOPE_VIOLATION"))
        unknown = self.client.invoke("cap.nope.v1", {}, device_id=self.device_id)
        self.assertEqual(unknown["status"], "rejected")
        self.assertEqual(unknown["error"]["mhs_code"], "MHS.CAPABILITY.UNKNOWN")
        self.assertEqual(self.client.read("world", device_id=self.device_id)["revision"], revision)

    def test_interlock_and_reset(self):
        opened = self.client.invoke(
            "cap.test.set_door.v1", {"state": "open"}, device_id=self.device_id
        )
        self.assertEqual({"completed", "rejected"}.__contains__(opened["status"]), True)
        # Plan 3.6: the permit (step 10) comes before the interlocks (step 11).
        permit = self.client.permit(
            "cap.actuation.valve.v1", {"gate": "main"},
            resource=self.client.capability_resource("cap.actuation.valve.v1", device_id=self.device_id),
        )
        blocked = self.client.invoke(
            "cap.actuation.valve.v1", {"gate": "main"}, device_id=self.device_id,
            permit_id=permit["permit_id"],
        )
        self.assertEqual(blocked["status"], "rejected")
        self.assertIn(blocked["error"]["mhs_code"],
                      ("MHS.SAFETY.ESTOP_ENGAGED", "MHS.SAFETY.INTERLOCK_OPEN"))
        self.client.invoke("cap.test.set_door.v1", {"state": "closed"}, device_id=self.device_id)
        self.client.reset(self.device_id)

    def test_permit_bound_to_input_and_single_use(self):
        payload = {"gate": "divert"}
        missing = self.client.invoke("cap.actuation.valve.v1", payload, device_id=self.device_id)
        self.assertEqual(missing["status"], "rejected")
        self.assertIn(missing["error"]["mhs_code"],
                      ("MHS.SAFETY.PERMIT_INVALID", "MHS.SAFETY.APPROVAL_REQUIRED"))
        permit = self.client.permit(
            "cap.actuation.valve.v1", payload,
            resource=self.client.capability_resource(
                "cap.actuation.valve.v1", device_id=self.device_id
            ),
        )
        granted = self.client.invoke(
            "cap.actuation.valve.v1", payload, device_id=self.device_id,
            permit_id=permit["permit_id"],
        )
        self.assertEqual(granted["status"], "completed")
        self.assertEqual(granted["approvals"][0]["permit_id"], permit["permit_id"])
        reused = self.client.invoke(
            "cap.actuation.valve.v1", payload, device_id=self.device_id,
            permit_id=permit["permit_id"],
        )
        self.assertEqual(reused["status"], "rejected")
        self.assertEqual(reused["error"]["mhs_code"], "MHS.SAFETY.PERMIT_INVALID")
        self.client.invoke("cap.motion.stop.v1", {}, device_id=self.device_id)

    def test_estop_reset(self):
        estop = self.client.estop("unit test", device_id=self.device_id)
        self.assertEqual(estop["status"], "completed")
        self.assertTrue(self.client.safety_status(self.device_id)["estop"]["engaged"])
        blocked = self.client.invoke("cap.world.step.v1", {"ticks": 1}, device_id=self.device_id)
        self.assertEqual(blocked["status"], "rejected")
        self.assertIn(blocked["error"]["mhs_code"],
                      ("MHS.SAFETY.ESTOP_ENGAGED", "MHS.SAFETY.INTERLOCK_OPEN"))
        reset = self.client.reset(self.device_id)
        self.assertEqual(reset["status"], "completed")
        recovered = self.client.invoke("cap.world.step.v1", {"ticks": 1}, device_id=self.device_id)
        self.assertEqual(recovered["status"], "completed")

    def test_snapshot_restore(self):
        snapshot = self.client.snapshot(self.device_id)
        self.assertEqual(snapshot["state_hash"],
                         self.client.read("world", device_id=self.device_id)["state_hash"])
        self.client.invoke("cap.world.step.v1", {"ticks": 7}, device_id=self.device_id)
        restored = self.client.restore(snapshot, self.device_id)
        self.assertEqual(restored["status"], "completed")
        self.assertEqual(
            self.client.read("world", device_id=self.device_id)["state_hash"],
            snapshot["state_hash"],
        )

    def test_exclusive_busy_over_http(self):
        # stdio serialises requests, so exercise the concurrency lease over the
        # threaded HTTP binding with a slow, non-cancellable exclusive command.
        sys.path.insert(0, str(HERE))
        import _device_server  # noqa: PLC0415 - test helper next to this file

        server = _device_server.build_server()
        handle = server.start_http("127.0.0.1", 0)
        client = connect(handle.url)
        try:
            device_id = client.devices()[0]["device_id"]
            client.open_session([device_id], capabilities=None, mode="simulated")
            result: dict = {}
            worker = threading.Thread(
                target=lambda: result.update(
                    client.invoke("cap.test.block.v1", {"ms": 400}, device_id=device_id)
                ),
                daemon=True,
            )
            worker.start()
            time.sleep(0.1)  # let the first command take the exclusive lease
            busy = client.invoke("cap.world.step.v1", {"ticks": 1}, device_id=device_id)
            worker.join(timeout=5)
            self.assertEqual(busy["status"], "rejected")
            self.assertEqual(busy["error"]["mhs_code"], "MHS.DEVICE.BUSY")
            self.assertEqual(result.get("status"), "completed")
        finally:
            client.close()
            handle.shutdown()

    def test_resource_write(self):
        before = self.client.read("world", device_id=self.device_id)
        receipt = self.client.write("world", {"tick": 5}, device_id=self.device_id)
        self.assertEqual(receipt["status"], "completed")
        # WP-04 4d: a write is a command of the resource's configure binding.
        self.assertEqual(receipt["capability_id"], "cap.device.configure.v1")
        self.assertEqual(receipt["output"], {"applied": {"tick": 5}, "revision": before["revision"] + 1})
        after = self.client.read("world", device_id=self.device_id)
        self.assertEqual(after["state"]["tick"], 5)
        self.assertEqual(after["revision"], before["revision"] + 1)
        bad = self.client.write("world", {"not_a_field": 1}, device_id=self.device_id)
        self.assertEqual(bad["status"], "rejected")
        self.assertEqual(bad["error"]["mhs_code"], "MHS.RESOURCE.FIELD_UNKNOWN")
        self.assertEqual(self.client.read("world", device_id=self.device_id)["revision"],
                         after["revision"])

    def test_evidence_and_receipt_schema(self):
        bundle = self.client.export_evidence()
        report = self.client.verify_evidence(bundle)
        self.assertTrue(report["valid"], report.get("errors"))
        for receipt in bundle["receipts"]:
            self.assertEqual(self.store.validate(receipt, "receipt.schema.json"), [])


if __name__ == "__main__":
    unittest.main()
