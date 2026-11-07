"""Acceptance and package-specific cases for the Panda Servo trajectory fake contract.

The package is blocked: the pinned clone declares no source-backed stop or
safe-state endpoint, so the stock gate must refuse a safe-state claim.  The
cases still exercise the one command endpoint the package exposes and its
input envelope.  Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
INPUT = "MHS.CAPABILITY.INPUT_INVALID"
ACTION = "x-cap.andrejorsula.joint_trajectory.v1"
TOPIC = "/joint_trajectory_controller/joint_trajectory"
JOINTS = ["panda_joint1", "panda_joint2", "panda_joint3", "panda_joint4",
          "panda_joint5", "panda_joint6", "panda_joint7"]
READY = [0.0, -0.7853981633974483, 0.0, -2.356194490192345,
         0.0, 1.5707963267948966, 0.7853981633974483]


def trajectory(positions, sec=1, nanosec=0):
    return {"points": [{"positions": list(positions),
                        "time_from_start": {"sec": sec, "nanosec": nanosec}}]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        # The package has no source-backed stop or safe-state action.  Keep
        # running the full stock gate and require its specific safety refusal.
        self.assertEqual(report["failed"], ["G6", "G8"], report)
        codes = {finding["code"] for gate in report["gates"] for finding in gate["findings"]}
        self.assertIn("G6.ESTOP_FAILED", codes)


class PandaTrajectoryCases(unittest.TestCase):
    def serve(self, *, overlay=True):
        server = load(HERE, backend="fake", site_limits=OVERLAY if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.server = server
        return client

    def native(self):
        return self.server.devices[self.ids["device_id"]].bridge.native

    def test_the_publication_completes_and_is_never_confirmed(self) -> None:
        client = self.serve()
        receipt = client.invoke(ACTION, trajectory(READY), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["published"])
        self.assertFalse(receipt["output"]["confirmed"])
        self.assertEqual(self.native().publish_count, 1)

    def test_the_fake_records_the_declared_message_shape(self) -> None:
        client = self.serve()
        target = [0.1, -0.2, 0.3, -0.4, 0.5, 0.7, -0.6]
        receipt = client.invoke(ACTION, trajectory(target, sec=2, nanosec=500000000), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        recorded = self.native().last_trajectory
        self.assertEqual(recorded["joint_names"], JOINTS)
        self.assertEqual(recorded["points"][0]["positions"], target)
        self.assertEqual(recorded["points"][0]["time_from_start"], {"sec": 2, "nanosec": 500000000})

    def test_an_out_of_envelope_joint_position_is_refused_before_the_fake(self) -> None:
        client = self.serve()
        receipt = client.invoke(ACTION, trajectory([3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.native().publish_count, 0)

    def test_operator_required_time_is_refused_without_the_overlay(self) -> None:
        client = self.serve(overlay=False)
        receipt = client.invoke(ACTION, trajectory(READY), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)
        self.assertEqual(self.native().publish_count, 0)

    def test_a_wrong_length_point_is_an_input_error(self) -> None:
        client = self.serve()
        receipt = client.invoke(ACTION, trajectory([0.0] * 6), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], INPUT)
        self.assertEqual(self.native().publish_count, 0)

    def test_a_failed_publication_is_not_a_completed_receipt(self) -> None:
        client = self.serve()
        self.native().fail_publish = True
        receipt = client.invoke(ACTION, trajectory(READY), **self.ids)
        self.assertNotEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.native().publish_count, 0)

    def test_the_missing_stop_leaves_the_estop_unsafe_and_latched(self) -> None:
        client = self.serve()
        estop = client.estop("package test", **self.ids)
        # No source-backed stop exists, so the runtime must not report a safe
        # state even though the software latch is engaged.
        self.assertEqual(estop["status"], "failed", estop)
        self.assertEqual(estop["output"]["estop"], "software_only")
        self.assertFalse(estop["output"]["safe_state_achieved"])
        self.assertEqual(estop["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        receipt = client.invoke(ACTION, trajectory(READY), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
