"""Acceptance run of the Adroit package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is
not installed where the gate runs, so nothing here compares the stand-in with the real engine.  The numbers
below are test data inside the derived control ranges, not facts of the model.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: The stand-in counts 24 hinge joints of resources/chain.xml and the free joint of the ball.
NQ = 31
NV = 30
#: The 24 position actuators of resources/joint_position_actuation.xml.
NU = 24
#: Test data: one valid control value per actuator, inside every ctrlrange.
MID = [0.0, 0.0, 0.0, 0.5, 0.5, 0.5, 0.0, 0.5, 0.5, 0.5, 0.0, 0.5, 0.5, 0.5, 0.3, 0.0, 0.5, 0.5, 0.5, 0.0, 0.5,
       0.0, 0.0, -0.5]
#: Test data: another valid control vector, close to the upper part of the ranges.
TARGET = [0.1, 0.3, 0.2, 0.8, 0.8, 0.8, 0.2, 0.8, 0.8, 0.8, 0.2, 0.8, 0.8, 0.8, 0.5, 0.2, 0.8, 0.8, 0.8, 0.5, 0.8,
          0.1, 0.2, -0.2]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AdroitHandCases(unittest.TestCase):
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
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 2.0)          # resources/assets.xml:22
        self.assertEqual(state["tick"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, MID, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        for index, value in ((0, 0.18), (3, -0.01), (14, 0.71), (19, 1.1), (23, 0.1)):
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
        self.assertGreater(second["qpos"][3], 0.0)           # FFJ2 moves toward its positive target
        self.assertEqual(self.state(client)["tick"], 2)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, TARGET, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client, seed=7)["output"]
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(output["observation"]["qpos"][:NU], [0.0] * NU)
        self.assertEqual(output["observation"]["qpos"][27], 1.0)   # the ball's free-joint quaternion
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["seed"], 0)                  # the bridge's configured seed, not the class input

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:Adroit_hand", "F1"))
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"]), (2.0, 0))
        self.assertEqual(fidelity["clock"], "lockstep")
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
