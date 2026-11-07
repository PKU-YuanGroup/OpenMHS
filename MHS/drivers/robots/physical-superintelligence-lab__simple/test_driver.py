"""Acceptance run of the SIMPLE package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
needs MuJoCo, IsaacSim and an RTX GPU and is not installed where the gate runs, so nothing here compares the fake
with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ARM = [0.0] * 7
LIFT = [1.0] * 7


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TabletopGraspCases(unittest.TestCase):
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

    def step(self, client, arm, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"arm": list(arm)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ARM)["status"], "completed")
        for arm in ([2.0] + [0.0] * 6, [0.0] * 6 + [-1.5]):
            refused = self.step(client, arm)
            self.assertEqual(refused["status"], "rejected", arm)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, arm)
        self.assertEqual(self.state(client)["tick"], 1)                   # the refused steps changed nothing

    def test_a_seed_repeats_the_start_and_a_different_seed_does_not(self) -> None:
        def observation(seed):
            client = self.serve()
            receipt = self.reset(client, seed=seed)
            self.assertEqual(receipt["status"], "completed")
            return receipt["output"]["observation"]

        self.assertEqual(observation(7), observation(7))
        self.assertNotEqual(observation(7), observation(8))

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_scalar_observation_is_published(self) -> None:
        client = self.serve()
        output = self.step(client, ARM)["output"]
        observation = output["observation"]
        self.assertEqual(sorted(observation), ["agent", "eef_pose", "joint_qpos"])
        self.assertEqual(len(observation["agent"]["values"]), 9)
        self.assertEqual(len(observation["joint_qpos"]["values"]), 9)
        self.assertEqual(len(observation["eef_pose"]["values"]), 7)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))

    def test_a_lifted_target_ends_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, LIFT)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["reward"]), (True, 1.0))
        # autoreset is on: the next step starts a new episode instead of refusing the step
        ended = self.step(client, ARM)
        self.assertEqual(ended["status"], "completed")
        self.assertEqual(ended["output"]["tick"], 1)
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:simple/FrankaTabletopGraspMP-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ARM)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ARM), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
