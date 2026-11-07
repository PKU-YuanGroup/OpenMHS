"""Acceptance run of the Cozmo package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
MOVE_HEAD = "cap.motion.joint_position.v1"
SET_LIFT = "x-cap.anki.set_lift_ratio.v1"
STOP = "x-cap.anki.stop_all_motors.v1"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CozmoCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads_start_at_the_fake_values(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["head_angle"], 0.0)
        self.assertEqual(state["lift_ratio"], 0.0)
        self.assertEqual(state["lift_height"], 32.0)       # the fake's placeholder mapping of ratio 0.0
        self.assertEqual((state["is_charging"], state["cliff_detected"]), (False, False))

    def test_the_head_move_changes_the_head_angle(self) -> None:
        client = self.serve()
        receipt = client.invoke(MOVE_HEAD, {"joint_positions": [0.5]}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["joint_positions"], [0.5])
        self.assertEqual(receipt["output"]["reached"], True)
        self.assertEqual(self.state(client)["head_angle"], 0.5)
        refused = client.invoke(MOVE_HEAD, {"joint_positions": [1.0]}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["head_angle"], 0.5)

    def test_the_lift_ratio_moves_the_lift(self) -> None:
        client = self.serve()
        receipt = client.invoke(SET_LIFT, {"lift_ratio": 0.5}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["lift_ratio"], 0.5)
        state = self.state(client)
        self.assertEqual((state["lift_ratio"], state["lift_height"]), (0.5, 62.0))
        refused = client.invoke(SET_LIFT, {"lift_ratio": 1.5}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["lift_ratio"], 0.5)

    def test_the_stop_action_and_the_estop(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke(STOP, {}, **self.ids)["output"]["stopped"], True)
        client.estop("test", **self.ids)
        refused = client.invoke(MOVE_HEAD, {"joint_positions": [0.2]}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
