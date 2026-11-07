"""Acceptance run of the Franka Panda package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py, a stand-in ``mujoco``
module): the MuJoCo engine is not installed where the gate runs, so nothing here compares the stand-in with it.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: The first gripper actuator: ctrlrange 0 to 0.04 m (panda_mocap.xml:281), after the 7 arm actuators.
FIRST_GRIPPER = 7
#: The neutral joint values the environment sets as the arm's control (panda_mujoco_gym/envs/panda_env.py:47); every
#: value is inside the actuator ctrlrange of the carried model, so it is a valid step action.
NEUTRAL_CTRL = [0.00, 0.41, 0.00, -1.85, 0.00, 2.26, 0.79, 0.00, 0.00]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FrankaPandaCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def step(self, client, ticks=1, ctrl=None):
        if ctrl is None:
            ctrl = list(NEUTRAL_CTRL)
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": ctrl}}, **self.ids)

    def test_the_model_dimensions_come_from_the_model_files(self) -> None:
        client = self.serve()
        state = self.state(client)
        # 9 arm and gripper joints plus the object's free joint: 16 coordinates and 15 degrees of freedom
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (16, 15, 9))
        self.assertEqual(state["timestep_ms"], 2.0)                 # 0.002 s of the model's <option> element
        self.assertEqual(state["tick"], 0)

    def test_a_step_advances_the_model_and_the_receipt_reports_it(self) -> None:
        client = self.serve()
        receipt = self.step(client, ticks=10)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 10)
        self.assertAlmostEqual(output["observation"]["time"], 0.02, places=12)
        self.assertEqual(len(output["observation"]["qpos"]), 16)
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (10, 20))

    def test_a_control_outside_the_model_range_is_refused(self) -> None:
        client = self.serve()
        ctrl = list(NEUTRAL_CTRL)
        ctrl[FIRST_GRIPPER] = 0.5                                   # the gripper range is 0 to 0.04 m
        refused = self.step(client, ctrl=ctrl)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_reset_returns_the_world_to_its_start(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ticks=3)["status"], "completed")
        receipt = client.invoke("cap.world.reset.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), client.invoke("cap.world.reset.v1", {}, **self.ids)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)             # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
