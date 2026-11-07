"""Acceptance run of the vikashplus/franka_sim package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the stand-in with the real engine.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: The served scene has 18 one-DOF joints: seven arm and two finger joints per arm (chain0.xml:16-88,
#: chain1.xml:14-84).
NQ = 18
#: The scene has 16 position actuators: seven left arm (actuator0.xml:11-17) and seven right arm plus two right
#: finger actuators (actuator1.xml:10-18).
NU = 16
#: Test data inside the ctrlranges: the left arm, the right arm and the two right fingers.
MID = [0.0] * NU
TARGET = [0.5, 0.5, 0.5, -0.5, 0.5, 0.5, 0.5,
          0.5, 0.5, 0.5, -0.5, 0.5, 0.5, 0.5, 0.02, 0.02]
#: Index, value outside that actuator's ctrlrange (actuator0.xml:11-17, actuator1.xml:10-18).
OUTSIDE = ((0, 3.0), (1, -2.0), (2, 3.0), (3, 0.1), (4, 3.0), (5, -2.0), (6, 3.0),
           (7, 3.0), (8, -2.0), (9, 3.0), (10, 0.1), (11, 3.9), (12, -0.1), (13, 3.9),
           (14, 0.05), (15, -0.01))


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FrankaSimCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_scene_and_its_includes(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NQ))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 2.0)          # assets/assets.xml:12
        self.assertEqual(state["tick"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, MID, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        for index, value in OUTSIDE:
            refused = self.step(client, MID[:index] + [value] + MID[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_a_step_moves_the_actuated_joints_and_advances_time(self) -> None:
        client = self.serve()
        first = self.step(client, TARGET)["output"]["observation"]
        second = self.step(client, TARGET)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertEqual(second["time"], 0.004)              # two ticks of the 2 ms step
        self.assertGreater(second["qpos"][0], 0.0)           # panda0_joint1 moves toward its positive target
        self.assertEqual(self.state(client)["tick"], 2)

    def test_the_left_fingers_are_unactuated(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        before = self.state(client)["qpos"]
        self.assertEqual(self.step(client, TARGET)["status"], "completed")
        after = self.state(client)["qpos"]
        # assets/actuator0.xml:11-17 actuates the seven left arm joints only; the left finger joints come after
        # them in the traversal (chain0.xml:62 and :88), at qpos indices 7 and 8.
        self.assertEqual((before[7], before[8]), (0.0, 0.0))
        self.assertEqual((after[7], after[8]), (0.0, 0.0))
        self.assertNotEqual(after[0], before[0])             # the left arm joints do move

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, TARGET, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client, seed=7)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"], [0.0] * NQ)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["seed"], 0)                  # the bridge's configured seed, not the class input

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:bi-franka_panda v200", "F1"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, MID)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, MID), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
