"""Acceptance run of the EBiM Task 1 package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): MuJoCo itself is not installed where the gate runs, so nothing here
compares the stand-in with the real engine.  The model file is the card's MJCF in the read-only clone, and the fake
derives its shape and control ranges from that file.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
NQ = 39          # the explicitly declared joints of duo_full_scene_grasp.xml; the composite cable is not expanded
NV = 39          # the same explicit joints (each is a hinge or a slide, one dof)
NU = 28          # the actuators of duo_full_scene_grasp.xml:1030-1060
DT_MS = 0.5      # duo_full_scene_grasp.xml:7, timestep 0.0005 s
SPINE_LOW, SPINE_HIGH = 0.0, 0.85       # duo_full_scene_grasp.xml:1030
BASE_X_LOW, BASE_X_HIGH = -2.0, 2.0     # duo_full_scene_grasp.xml:1034


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CableRoutingCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl)}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    @staticmethod
    def ctrl(values=None):
        values = dict(values or {})
        vector = [0.0] * NU
        for index, value in values.items():
            vector[index] = value
        return vector

    def test_the_model_shape_comes_from_the_card_model(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], DT_MS)     # duo_full_scene_grasp.xml:7
        self.assertEqual(state["tick"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_range(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, self.ctrl(), ticks=2)["status"], "completed")
        cases = [(0, SPINE_LOW - 0.1, SPINE_HIGH + 0.1), (1, BASE_X_LOW - 0.5, BASE_X_HIGH + 0.5)]
        for index, low, high in cases:
            for value in (low, high):
                refused = self.step(client, self.ctrl({index: value}))
                self.assertEqual(refused["status"], "rejected", (index, value))
                self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
                self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)   # the refused steps changed nothing

    def test_the_state_follows_the_control(self) -> None:
        client = self.serve()
        first = self.step(client, self.ctrl({1: 1.0}))["output"]["observation"]
        second = self.step(client, self.ctrl({1: 1.0}))
        self.assertEqual(second["status"], "completed")
        observation = second["output"]["observation"]
        self.assertGreater(observation["qpos"][0], first["qpos"][0])   # base_planar_x is the first joint
        self.assertEqual(observation["qvel"][0], 1.0)                  # the velocity actuator sets it
        self.assertAlmostEqual(observation["time"], 0.001)             # two ticks of 0.0005 s

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, self.ctrl({1: 1.0}), ticks=3)["status"], "completed")
        output = self.reset(client)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"][0], 0.0)
        self.assertEqual(output["observation"]["qvel"][0], 0.0)
        self.assertEqual(output["observation"]["time"], 0.0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:full_robot_board_cable_routing", "F1"))
        self.assertEqual(fidelity["timestep_ms"], DT_MS)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertEqual((fidelity["determinism"]["kind"], fidelity["determinism"]["seed_control"]),
                         ("seeded", "none"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, self.ctrl())["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, self.ctrl()), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)   # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
