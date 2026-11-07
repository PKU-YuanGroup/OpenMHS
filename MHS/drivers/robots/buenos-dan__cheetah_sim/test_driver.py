"""Acceptance run of the cheetah_sim package: the gate, plus repository cases.

Add cases, never remove the check_driver call.  Since the model review of
2026-11-05 the package claims no safe state: the e-stop sends the
unacknowledged upstream stand posture command and reports
SAFE_STATE_UNREACHED with the latch held, so the gate fails G6.ESTOP_FAILED
(and G8 SAFE-028 at R2) and the package is blocked; the cases below keep the
contract and the honest stop outcome exercised.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
LEG_CAP = "x-cap.buenos-dan.leg_position.v1"
STAND_CAP = "x-cap.buenos-dan.stand.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CheetahCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.served_native = next(iter(server.devices.values())).bridge.native
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def example_overlay(self):
        return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))

    def test_stand_reaches_the_upstream_stand_method(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call(STAND_CAP, {})
        self.assertTrue(output["commanded"])
        self.assertFalse(output["confirmed"])
        self.assertGreaterEqual(driver.native.stand_calls, 1)

    def test_joint_command_reaches_the_leg_controller(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call(LEG_CAP, {"leg": "RF", "joint": "calf", "angle_rad": 0.5})
        self.assertEqual(output["joint_index"], 2)
        self.assertEqual(output["leg"], "RF")
        # Cheetah.controllers is a dict keyed by leg name, as upstream (stand_demo.py:18).
        self.assertIsInstance(driver.native.controllers, dict)
        self.assertEqual(driver.native.controllers["RF"].commands[-1], (2, 0.5))

    def test_operator_required_angle_is_refused_without_an_overlay(self) -> None:
        client = self.serve()
        receipt = client.invoke(LEG_CAP, {"leg": "LF", "joint": "hip", "angle_rad": 0.2}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.served_native.controllers["LF"].commands, [])

    def test_example_overlay_allows_the_joint_command(self) -> None:
        client = self.serve(site_limits=self.example_overlay())
        receipt = client.invoke(LEG_CAP, {"leg": "LF", "joint": "hip", "angle_rad": 0.2}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["joint_index"], 0)
        self.assertTrue(receipt["output"]["published"])
        self.assertEqual(self.served_native.controllers["LF"].commands[-1], (0, 0.2))

    def test_estop_sends_stand_but_does_not_claim_a_safe_state(self) -> None:
        # The stand posture command is twelve unacknowledged publications: the e-stop must not report
        # success, and the latch still refuses motion.
        client = self.serve(site_limits=self.example_overlay())
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        self.assertGreaterEqual(self.served_native.stand_calls, 1)
        refused = client.invoke(LEG_CAP, {"leg": "LF", "joint": "hip", "angle_rad": 0.2}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_stand_is_not_a_safe_state_action_while_latched(self) -> None:
        client = self.serve()
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "failed", estop)
        receipt = client.invoke(STAND_CAP, {}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ESTOP, receipt)

    def test_unknown_leg_is_refused_by_the_schema(self) -> None:
        client = self.serve()
        receipt = client.invoke(LEG_CAP, {"leg": "XX", "joint": "hip", "angle_rad": 0.2}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertIn(receipt["error"]["mhs_code"],
                      {"MHS.CAPABILITY.INPUT_INVALID", "MHS.SCHEMA.INVALID", "MHS.SAFETY.ENVELOPE_VIOLATION"})


if __name__ == "__main__":
    unittest.main()
