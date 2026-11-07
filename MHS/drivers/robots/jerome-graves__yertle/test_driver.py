"""Acceptance run of the Yertle package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): the upstream environment needs pybullet and the read-only clone, so
nothing here compares the fake with a PyBullet run.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO = [0.0] * 12
# learning/yertle_env.py:140 and :78-81: int(12 / (1/240 * 4)) at the default configuration.
MAX_STEPS = 720


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class YertleCases(unittest.TestCase):
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

    def step(self, client, values=None, ticks=1):
        action = {"values": list(values if values is not None else ZERO)}
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        refused = self.step(client, [2.0] + [0.0] * 11)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused step changed nothing

    def test_reset_and_step_publish_the_environment_contract(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=5)
        self.assertEqual(reset["status"], "completed")
        self.assertEqual(reset["output"]["seed"], 5)
        self.assertEqual(len(reset["output"]["observation"]["values"]), 48)      # learning/yertle_env.py:153-156
        receipt = self.step(client, [0.1] * 12)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(len(output["observation"]["values"]), 48)
        self.assertTrue(math.isfinite(output["reward"]))
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        state = self.state(client)
        self.assertEqual(state["tick"], 1)
        self.assertEqual(len(state["info"]["command"]), 3)                       # learning/yertle_env.py:299

    def test_a_seed_repeats_the_observation(self) -> None:
        def observation(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return self.reset(client, seed=seed)["output"]["observation"]["values"]

        first = observation(11)
        self.assertEqual(observation(11), first)
        self.assertNotEqual(observation(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_action_changes_the_reward(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        still = self.step(client, ZERO)["output"]["reward"]
        self.reset(client, seed=3)
        moved = self.step(client, [1.0] * 12)["output"]["reward"]
        self.assertLess(moved, still)                                            # energy and action-rate penalties

    def test_an_episode_truncates_at_the_step_limit(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        receipt = self.step(client, ZERO, ticks=MAX_STEPS)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (MAX_STEPS, False, True))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "gymnasium:learning.yertle_env:YertleEnv")
        self.assertEqual(fidelity["fidelity_level"], "F1")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
