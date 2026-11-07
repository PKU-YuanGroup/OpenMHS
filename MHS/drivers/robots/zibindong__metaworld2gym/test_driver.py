"""Acceptance run of the metaworld2gym package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): gym, mujoco-py and torch are not installed where the gate runs, so
nothing here compares the fake with the upstream Meta-World environment.  The gate harness call is kept unchanged.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MetaWorld2GymCases(unittest.TestCase):
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

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": list(values)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_reset_and_step_reach_the_fake(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, [0.5, 0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        observation = output["observation"]
        self.assertEqual(sorted(observation), ["agent_pos", "depth", "full_state", "image", "point_cloud"])
        # the real shapes are (3, 224, 224), (224, 224), (1024, 6), (9,) and (39,); the fake shrinks only the arrays
        self.assertEqual(len(observation["image"]["values"]), 3)
        self.assertEqual(len(observation["depth"]["values"]), 8)
        self.assertEqual(len(observation["point_cloud"]["values"]), 16)
        self.assertEqual(len(observation["agent_pos"]["values"]), 9)
        self.assertEqual(len(observation["full_state"]["values"]), 39)

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0, 1.0, 1.0, 1.0])["status"], "completed")
        before = self.state(client)["tick"]
        refused = self.step(client, [1.5, 0.0, 0.0, 0.0])
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(self.state(client)["tick"], before)          # refused before the fake was called

    def test_a_step_moves_the_placeholder_state(self) -> None:
        client = self.serve()
        self.reset(client)
        first = self.step(client, [0.5, 0.0, 0.0, 0.0])["output"]["observation"]["agent_pos"]["values"]
        second = self.step(client, [0.5, 0.0, 0.0, 0.0])["output"]["observation"]["agent_pos"]["values"]
        self.assertNotEqual(first, second)
        self.assertAlmostEqual(second[0] - first[0], 0.005, places=9)  # the fake gain is a placeholder

    def test_the_200_step_horizon_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, [0.0, 0.0, 0.0, 0.0], ticks=200)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 200))
        ended = self.step(client, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_is_recorded_but_does_not_reach_the_wrapper(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        second = self.reset(client, seed=99)["output"]
        self.assertEqual((first["seed"], second["seed"]), (7, 99))
        # MetaWorldEnv.reset takes no seed (metaworld2gym/metaworld_env.py:302-308): the fixed fake start is the same
        self.assertEqual(first["observation"], second["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("metaworld2gym:MetaWorldEnv/assembly-v2-goal-observable", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (2.5, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [1.0, 0.0, 0.0, 0.0]), self.reset(client)):
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
