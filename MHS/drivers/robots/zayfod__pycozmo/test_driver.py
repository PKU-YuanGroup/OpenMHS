"""Acceptance run of the Cozmo package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
EXAMPLE = str(HERE / "site-limits.example.json")
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"

# The bounds the driver enforces (pycozmo/robot.py:33-51): head travel -25 to 44.5 degrees, lift travel as the arm
# angle of the 32.0 mm and 92.0 mm heights with the arm 66.0 mm long and the pivot 45.0 mm high.
HEAD_MIN_RAD = math.radians(-25.0)
HEAD_MAX_RAD = math.radians(44.5)
LIFT_MIN_RAD = math.asin((32.0 - 45.0) / 66.0)
LIFT_MAX_RAD = math.asin((92.0 - 45.0) / 66.0)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CozmoCases(unittest.TestCase):
    def serve(self, site_limits=EXAMPLE):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def move(self, client, head, lift):
        return client.invoke("cap.motion.joint_position.v1", {"joint_positions": [head, lift]}, **self.ids)

    def test_the_initial_state_is_the_client_start_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertAlmostEqual(state["head_angle"], HEAD_MIN_RAD, places=9)
        self.assertAlmostEqual(state["lift_height"], 32.0, places=9)
        self.assertAlmostEqual(state["lift_angle"], LIFT_MIN_RAD, places=9)
        self.assertEqual((state["is_picked_up"], state["is_moving"]), (False, False))

    def test_the_two_joints_move(self) -> None:
        client = self.serve()
        target_head, target_lift = 0.5, 0.3
        receipt = self.move(client, target_head, target_lift)
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(receipt["output"]["reached"])
        state = self.state(client)
        self.assertAlmostEqual(state["head_angle"], target_head, places=9)
        self.assertAlmostEqual(state["lift_angle"], target_lift, places=9)
        self.assertAlmostEqual(state["lift_height"], math.sin(target_lift) * 66.0 + 45.0, places=9)

    def test_an_out_of_range_joint_is_refused(self) -> None:
        client = self.serve()
        for head, lift in ((HEAD_MAX_RAD + 0.1, LIFT_MIN_RAD), (HEAD_MIN_RAD, LIFT_MAX_RAD + 0.1)):
            refused = self.move(client, head, lift)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertAlmostEqual(self.state(client)["head_angle"], HEAD_MIN_RAD, places=9)

    def test_a_move_waits_for_the_site_to_state_the_joint_ranges(self) -> None:
        client = self.serve(site_limits=None)
        refused = self.move(client, 0.2, 0.2)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertAlmostEqual(self.state(client)["head_angle"], HEAD_MIN_RAD, places=9)

    def test_the_estop_stops_the_motors_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.move(client, 0.2, 0.2)["status"], "completed")
        client.estop("test", **self.ids)
        refused = self.move(client, 0.1, 0.1)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
