"""Acceptance run of the robo-lab package: the gate, plus cases for this MuJoCo scene.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo is not installed
where the gate runs, so nothing here compares the stand-in with the real engine.  Every number below is test data,
not a bound or a fact of the model.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
NQ = 37          # 12 hinge joints + 4 gripper slides + 3 free bodies of 7 qpos each (scene_blocks.xml:82-196)
NV = 34          # 12 hinge joints + 4 gripper slides + 3 free bodies of 6 qvel each
NU = 16          # eight position actuators per arm (scene_blocks.xml:299-315)
#: placeholder test data: every channel accepts 0, and channel 0 accepts 1.0
MID = [0.0] * NU


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RoboLabCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client):
        return client.invoke("cap.world.reset.v1", {}, **self.ids)

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_blocks_scene(self) -> None:
        client = self.serve()
        state = self.state(client)
        # placeholder: the stand-in's library default, because scene_blocks.xml:4 sets no timestep
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (NQ, NV, NU))
        self.assertEqual(state["timestep_ms"], 2.0)
        self.assertEqual((state["tick"], state["seed"]), (0, 0))

    def test_a_step_is_bounded_by_every_actuator_range(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, MID, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        # placeholder test data: above the upper or below the lower ctrlrange of one channel each
        for index, value in ((0, 2.1), (6, 0.002), (8, -2.1), (15, -0.046)):
            refused = self.step(client, MID[:index] + [value] + MID[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)      # the refused steps changed nothing

    def test_a_step_moves_an_actuated_joint_and_reaches_the_stand_in(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        target = list(MID)
        target[0] = 1.0
        receipt = self.step(client, target)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertGreater(receipt["output"]["observation"]["qpos"][0], 0.0)
        state = self.state(client)
        self.assertEqual(state["ctrl"], target)
        self.assertEqual(state["qpos"], receipt["output"]["observation"]["qpos"])
        self.assertEqual(state["time_ms"], 2)                # one tick of the stand-in's 2 ms step
        self.assertAlmostEqual(receipt["output"]["observation"]["time"], 0.002)

    def test_a_reset_restores_the_stand_in_defaults(self) -> None:
        client = self.serve()
        target = list(MID)
        target[0] = 1.0
        self.assertEqual(self.step(client, target, ticks=3)["status"], "completed")
        output = self.reset(client)["output"]
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["qpos"], [0.0] * NQ)
        self.assertEqual(state["ctrl"], [0.0] * NU)
        self.assertEqual(output["observation"]["qpos"], [0.0] * NQ)
        self.assertEqual(output["seed"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:scene_blocks", "F1"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual(fidelity["timestep_ms"], 2.0)
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, MID)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, MID), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)      # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
