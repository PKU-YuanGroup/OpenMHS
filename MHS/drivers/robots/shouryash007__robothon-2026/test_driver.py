"""Acceptance and package-specific cases for the SO-101 Gazebo package.

Add cases, never remove the check_driver call.  The package has no
source-backed stop, so the stock gate must record the honest G6/G8 safety
refusal; the remaining cases exercise the trajectory publication, the
operator-required time envelope and the transmission-only receipt.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import OutcomeUnknown, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
ACTION = "x-cap.shouryash007.arm_trajectory.v1"
JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex",
          "wrist_roll", "gripper"]


def trajectory(positions, sec=1, nanosec=0):
    return {"points": [{"positions": list(positions),
                        "time_from_start": {"sec": sec, "nanosec": nanosec}}]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        # The pinned clone has no source-backed stop for the trajectory
        # publication.  Keep the full stock gate and require its specific
        # safety refusal rather than presenting the software latch as a stop.
        self.assertEqual(report["failed"], ["G6", "G8"], report)
        codes = {finding["code"] for gate in report["gates"] for finding in gate["findings"]}
        self.assertIn("G6.ESTOP_FAILED", codes)
        self.assertIn("G8.TEST", codes)


class So101GazeboCases(unittest.TestCase):
    def serve(self, *, overlay=True):
        server = load(HERE, backend="fake", site_limits=OVERLAY if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def service_with_overlay(self):
        driver = load_driver(HERE, "fake")
        server = build_server(driver, site_limits=OVERLAY)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def test_the_publication_reaches_the_fake_with_the_upstream_joint_order(self) -> None:
        driver, client = self.service_with_overlay()
        target = [0.1, -0.2, 0.3, -0.4, 0.5, 0.6]
        receipt = client.invoke(ACTION, trajectory(target), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})
        self.assertEqual(len(driver.native.published), 1)
        sent = driver.native.published[0]
        self.assertEqual(sent["joint_names"], JOINTS)
        self.assertEqual(sent["points"][0]["positions"], target)
        self.assertEqual(sent["points"][0]["time_from_start"], {"sec": 1, "nanosec": 0})
        self.assertEqual(driver.native.advertised[0]["topic"], "/arm_controller/joint_trajectory")

    def test_the_client_receipt_is_transmission_only(self) -> None:
        client = self.serve()
        receipt = client.invoke(ACTION, trajectory([0.0] * 6), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})

    def test_an_out_of_envelope_joint_position_is_refused_before_the_fake(self) -> None:
        client = self.serve()
        receipt = client.invoke(ACTION, trajectory([2.0, 0.0, 0.0, 0.0, 0.0, 0.0]), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_operator_required_time_is_refused_without_the_overlay(self) -> None:
        client = self.serve(overlay=False)
        receipt = client.invoke(ACTION, trajectory([0.0] * 6), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_the_overlay_fills_the_time_envelope(self) -> None:
        client = self.serve()
        receipt = client.invoke(ACTION, trajectory([0.0] * 6, sec=10, nanosec=999999999), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_a_failed_publication_is_an_unknown_outcome(self) -> None:
        driver, client = self.service_with_overlay()
        driver.native.fail_publish = True
        with self.assertRaises(OutcomeUnknown):
            driver.call(ACTION, trajectory([0.0] * 6))
        self.assertEqual(driver.native.published, [])

    def test_the_missing_stop_leaves_the_estop_unsafe_and_latched(self) -> None:
        client = self.serve()
        estop = client.estop("package test", **self.ids)
        # No source-backed stop exists, so the runtime must not report a safe
        # state even though the software latch is engaged.
        self.assertEqual(estop["status"], "failed", estop)
        self.assertEqual(estop["output"]["estop"], "software_only")
        self.assertFalse(estop["output"]["safe_state_achieved"])
        self.assertEqual(estop["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        receipt = client.invoke(ACTION, trajectory([0.0] * 6), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
