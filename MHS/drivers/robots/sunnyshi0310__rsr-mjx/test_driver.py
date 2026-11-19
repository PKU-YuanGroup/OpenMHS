"""Acceptance run of the RSR-MJX Go2 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo and jax are not
installed where the gate runs, so nothing here compares the stand-in with the real engine or the upstream MJX
environment.  The numeric test vectors below are test data read from the scene's home keyframe, not new facts.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: The scene has a free base (7 qpos, 6 qvel) and twelve actuated hinges (go2_mjx_feetonly.xml:66-204).
NQ = 19
NV = 18
NU = 12
#: The model states a 0.004 s step (go2_mjx_feetonly.xml:4).
TIMESTEP_MS = 4.0
#: The home keyframe ctrl, inside every derived control range (scene_mjx_feetonly_flat_terrain.xml:27-35).
HOME_CTRL = [0.1, 0.9, -1.8, -0.1, 0.9, -1.8, 0.1, 0.9, -1.8, -0.1, 0.9, -1.8]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Go2FlatTerrainCases(unittest.TestCase):
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
        # the free base is at the trunk body position (go2_mjx_feetonly.xml:66); hinges start at zero
        self.assertEqual(state["qpos"][:7], [0.0, 0.0, 0.445, 1.0, 0.0, 0.0, 0.0])
        self.assertEqual(state["qpos"][7:], [0.0] * NU)
        self.assertEqual(state["ctrl"], [0.0] * NU)

    def test_a_step_is_bounded_by_every_inherited_joint_range(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HOME_CTRL, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        # abduction +-1.0472, hip -1.5708 to 3.4907, knee -2.7227 to -0.83776 (go2_mjx_feetonly.xml:15-24)
        for index, value in ((0, 1.05), (0, -1.05), (1, 3.5), (1, -1.6), (2, -0.83), (2, -2.8)):
            changed = list(HOME_CTRL)
            changed[index] = value
            refused = self.step(client, changed)
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)              # the refused steps changed nothing

    def test_a_step_moves_the_actuated_hinges_and_advances_simulated_time(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        first = self.step(client, HOME_CTRL, ticks=2)["output"]["observation"]
        second = self.step(client, HOME_CTRL)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertGreater(second["qpos"][7], first["qpos"][7])      # channel 0 moves toward its 0.1 target
        self.assertAlmostEqual(first["time"], 0.008)
        self.assertAlmostEqual(second["time"], 0.012)
        self.assertEqual(self.state(client)["tick"], 3)
        self.assertEqual(self.state(client)["ctrl"], HOME_CTRL)      # the last control vector is published

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, HOME_CTRL, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client)["output"]
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qvel"], [0.0] * NV)
        self.assertEqual(state["ctrl"], [0.0] * NU)
        self.assertEqual(output["observation"]["qpos"][:7], [0.0, 0.0, 0.445, 1.0, 0.0, 0.0, 0.0])
        self.assertEqual(output["seed"], 0)                          # the bridge's configured seed, not a class input

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "mujoco:go2 feetonly flat terrain scene")
        self.assertEqual(fidelity["fidelity_level"], "F0")           # the stand-in models no dynamics
        self.assertEqual(fidelity["timestep_ms"], TIMESTEP_MS)
        self.assertEqual((fidelity["determinism"]["kind"], fidelity["realtime_factor"], fidelity["clock"]),
                         ("none", 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)
        self.assertTrue(any("Joystick" in gap for gap in fidelity["gaps"]), fidelity["gaps"])

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HOME_CTRL)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, HOME_CTRL), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
