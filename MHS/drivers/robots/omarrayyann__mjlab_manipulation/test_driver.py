"""Acceptance run of the mjlab manipulation package: the gate, plus cases for this driver.

The cases run on the fake backend (fake.py): MuJoCo itself is not installed where the gate runs, so nothing here
compares the stand-in with the real engine.  The model file is the card's first MJCF model in the read-only clone,
and the fake derives its shape from that file.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
MODEL_PATH = "../../../../robots/omarrayyann/mjlab_manipulation/src/mjlab_manipulation/robots/droid/xmls/droid.xml"
#: Droid is a fixed-base seven-joint arm (droid.xml:82-157)
NQ = NV = NU = 7
#: a control vector inside every joint range: joint_4 accepts -1 and joint_6 accepts 1 (droid.xml:115, :130)
CTRL = [0.0, 0.0, 0.0, -1.0, 0.0, 1.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MjlabDroidCases(unittest.TestCase):
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

    def test_the_model_shape_comes_from_the_card_model(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (NQ, NV, NU))
        self.assertEqual(state["tick"], 0)
        self.assertGreater(state["timestep_ms"], 0)

    def test_the_control_envelope_is_the_joint_range(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, CTRL, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        # joint_1 is -2.7437..2.7437, joint_4 is -3.0421..-0.1518 and joint_6 is 0.5445..4.5169 (droid.xml:96, :115,
        # :130); the bridge derives those intervals from the model's actuator_ctrlrange.
        for index, value in ((0, 3.0), (0, -3.0), (3, 0.0), (3, -3.1), (5, 0.0), (5, 5.0)):
            ctrl = list(CTRL)
            ctrl[index] = value
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_a_step_moves_the_actuated_joints(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, CTRL)
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]
        self.assertEqual(receipt["output"]["tick"], 1)
        state = self.state(client)
        self.assertAlmostEqual(observation["time"], state["timestep_ms"] / 1000.0, places=9)
        self.assertLess(observation["qpos"][3], 0.0)                  # joint_4 follows the -1 control
        self.assertGreater(observation["qpos"][5], 0.0)               # joint_6 follows the +1 control
        self.assertEqual(state["ctrl"], CTRL)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, CTRL, ticks=3)["status"], "completed")
        self.assertEqual(self.reset(client)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["tick"], state["qpos"], state["qvel"], state["ctrl"]), (0, [0.0] * NQ, [0.0] * NV,
                                                                                        [0.0] * NU))
        self.assertEqual(state["time_ms"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:franka_droid", "F1"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual(fidelity["reset"], "full")
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, CTRL)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, CTRL), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced

    def test_the_card_model_is_available_in_the_clone(self) -> None:
        model = (HERE / MODEL_PATH).resolve()
        self.assertTrue(model.is_file())
        self.assertEqual(model.name, "droid.xml")


if __name__ == "__main__":
    unittest.main()
