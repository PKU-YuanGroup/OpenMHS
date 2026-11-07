"""Acceptance run of the Quadruped-RL-Locomotion package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the fake with the real engine.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO_CTRL = [0.0] * 12


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class QuadrupedCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, ctrl=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl or ZERO_CTRL)}},
                             **self.ids)

    def reset(self, client, seed=None):
        return client.invoke("cap.world.reset.v1", {} if seed is None else {"seed": seed}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_scene(self) -> None:
        client = self.serve()
        state = self.state(client)
        # go1_torque.xml: the trunk free joint (7 qpos / 6 qvel) plus 12 hinge joints, and 12 <motor> actuators.
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (19, 18, 12))
        self.assertEqual(state["timestep_ms"], 2.0)                       # dt(=0.002) in go1_mujoco_env.py:37
        self.assertEqual(state["seed"], 0)
        self.assertEqual(state["tick"], 0)

    def test_the_control_envelope_is_the_model_ctrlrange(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5] * 12)["status"], "completed")
        before = self.state(client)
        for ctrl in ([1.5] + [0.0] * 11, [-1.5] + [0.0] * 11):
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected", ctrl)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, ctrl)
        self.assertEqual(self.state(client)["tick"], before["tick"])       # a refused step changed nothing
        wrong_length = self.step(client, [0.0] * 11)
        self.assertEqual(wrong_length["status"], "rejected")
        self.assertEqual(wrong_length["error"]["mhs_code"], INPUT_INVALID)

    def test_a_step_advances_only_the_actuated_joints(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        ctrl = [1.0] + [0.0] * 11
        receipt = self.step(client, ctrl, ticks=5)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        state = self.state(client)
        self.assertEqual((output["tick"], state["tick"]), (5, 5))
        self.assertEqual(state["time_ms"], 10)                             # five 2 ms integration steps
        self.assertEqual(state["ctrl"], ctrl)
        self.assertNotEqual(state["qvel"][6], 0.0)                         # first hinge joint (FR_hip)
        self.assertEqual(state["qvel"][7], 0.0)                            # the next motor was left at zero
        self.assertNotEqual(state["qpos"][7], 0.0)
        self.assertEqual(state["qpos"][:7], [0.0, 0.0, 0.445, 1.0, 0.0, 0.0, 0.0])  # the free base is not integrated

    def test_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, [1.0] * 12, ticks=3)
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 0)                     # the class seed, not the accepted input
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qvel"], [0.0] * 18)
        self.assertEqual(state["ctrl"], ZERO_CTRL)
        self.assertEqual(state["qpos"], [0.0, 0.0, 0.445, 1.0, 0.0, 0.0, 0.0] + [0.0] * 12)

    def test_the_ticks_bound_is_the_bridge_bound(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ticks=1)["status"], "completed")
        for ticks in (0, 10001):
            refused = self.step(client, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:go1 scene", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
