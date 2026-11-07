"""Acceptance run of the Unitree MuJoCo H2 package: the gate, plus cases for what is specific to this driver.

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
#: The H2 model has a free base and 31 actuated hinge joints (h2_mujoco.xml:47 and :241-277).
NQ = 38
NV = 37
NU = 31
#: The model states a 0.001 s step (h2_mujoco.xml:8).
TIMESTEP_MS = 1.0
#: Test data inside the model's control ranges (h2_mujoco.xml:242-277); not device facts.
CTRL = [0.0] * NU
CTRL[0] = 360.0
TARGET = list(CTRL)
TARGET[30] = 50.0


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UnitreeH2Cases(unittest.TestCase):
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

    def test_the_model_shape_comes_from_the_scene_and_its_include(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], TIMESTEP_MS)
        self.assertEqual(state["tick"], 0)
        # the free base is at the pelvis body position of h2_mujoco.xml:45
        self.assertEqual(state["qpos"][:3], [0.0, 0.0, 1.2])
        self.assertEqual(state["qpos"][3:7], [1.0, 0.0, 0.0, 0.0])

    def test_a_step_is_bounded_by_every_actuator_control_range(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, TARGET, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        for index, value in ((0, 361.0), (4, 20.0), (5, 67.0), (30, 51.0)):
            refused = self.step(client, TARGET[:index] + [value] + TARGET[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)              # the refused steps changed nothing

    def test_a_step_moves_the_actuated_joints_and_advances_time(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        first = self.step(client, CTRL, ticks=2)["output"]["observation"]
        second = self.step(client, CTRL)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertGreater(first["qvel"][6], 0.0)                   # the first hinge (left hip pitch) is turning
        self.assertGreater(second["qpos"][7], 0.0)                  # its position has moved after three steps
        self.assertAlmostEqual(second["time"], 0.003)               # three ticks of the 1 ms model step
        self.assertEqual(self.state(client)["tick"], 3)
        self.assertEqual(self.state(client)["ctrl"][0], 360.0)      # the last control vector is published

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, TARGET, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client)["output"]
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qvel"], [0.0] * NV)
        self.assertEqual(state["ctrl"], [0.0] * NU)
        self.assertEqual(output["observation"]["qpos"][:3], [0.0, 0.0, 1.2])
        self.assertEqual(output["seed"], 0)                         # the bridge's configured seed, not a class input

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:H2", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (TIMESTEP_MS, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)
        self.assertTrue(any("0.005" in gap for gap in fidelity["gaps"]), fidelity["gaps"])

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, CTRL)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, CTRL), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)             # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
