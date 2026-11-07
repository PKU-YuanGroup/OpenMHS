"""Acceptance run of the SmarPod package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the ``check_driver`` call.  The temporary site overlay below admits exactly the test target
used by one case; it is test data, not a device bound, and it is not shipped as ``site-limits.example.json``.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
DEVICE = "mhs://localhost/smarpod-hexapod"
POSE_ACTION = "x-cap.bsh90.hexapod_pose.v1"
STOP_ACTION = "cap.motion.stop.v1"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
TARGET = [0.04, 0.05, 0.06, 4.0, 5.0, 6.0]  # placeholder: a test target, not a workspace bound


def _overlay(target=TARGET):
    """A test-only overlay that admits exactly the test target's numeric range (not a device fact)."""
    rule = {"min": min(target), "max": max(target), "source": "operator",
            "reason": "test-only overlay for this driver's acceptance cases, not a device bound"}
    return {"openmhs": "0.9", "site": "test-only overlay (not a device bound)", "devices": {
        DEVICE: {"pose": rule, POSE_ACTION: {"pose": rule}}}}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SmarPodCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def test_the_pose_read_comes_from_the_native_get(self) -> None:
        client, fake = self.serve()
        self.assertEqual(self.state(client)["pose"], fake.get())
        fake._pose = [0.11, 0.12, 0.13, 1.1, 1.2, 1.3]  # placeholder
        self.assertEqual(self.state(client)["pose"], fake.get())

    def test_the_pose_write_needs_the_site_envelope(self) -> None:
        client, fake = self.serve()
        before = fake.get()
        refused = self.configure(client, pose=TARGET)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(fake.get(), before)

    def test_the_site_envelope_admits_the_pose_write(self) -> None:
        client, fake = self.serve(_overlay())
        receipt = self.configure(client, pose=TARGET)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(fake.get(), TARGET)
        self.assertEqual(self.state(client)["pose"], TARGET)

    def test_the_extension_action_moves_the_pose(self) -> None:
        client, fake = self.serve(_overlay())
        receipt = client.invoke(POSE_ACTION, {"pose": TARGET}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["pose"], TARGET)
        self.assertEqual(fake.get(), TARGET)

    def test_the_extension_action_needs_the_site_envelope(self) -> None:
        client, fake = self.serve()
        before = fake.get()
        refused = client.invoke(POSE_ACTION, {"pose": TARGET}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(fake.get(), before)

    def test_the_stop_action_reaches_the_native_stop(self) -> None:
        client, fake = self.serve()
        before = fake._stop_count
        receipt = client.invoke(STOP_ACTION, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["stopped"])
        self.assertGreater(fake._stop_count, before)

    def test_a_failed_native_stop_is_a_failed_receipt(self) -> None:
        client, fake = self.serve()

        def broken():
            raise RuntimeError("placeholder: the controller rejected smarpod.Stop")

        fake.stop = broken
        receipt = client.invoke(STOP_ACTION, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)

    def test_an_unreachable_pose_is_refused_before_the_move(self) -> None:
        client, fake = self.serve(_overlay())

        def unreachable(_pose):
            return False

        fake.check_pose = unreachable
        receipt = client.invoke(POSE_ACTION, {"pose": TARGET}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")

    def test_a_failed_native_move_is_a_failed_receipt(self) -> None:
        client, fake = self.serve(_overlay())

        def broken(_pose):
            raise RuntimeError("placeholder: the controller rejected smarpod.Move")

        fake.set = broken
        receipt = client.invoke(POSE_ACTION, {"pose": TARGET}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)

    def test_the_estop_reaches_the_native_stop_and_latches(self) -> None:
        client, fake = self.serve()
        before = fake._stop_count
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertGreater(fake._stop_count, before)
        refused = client.invoke(POSE_ACTION, {"pose": TARGET}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertIn("pose", self.state(client))


if __name__ == "__main__":
    unittest.main()
