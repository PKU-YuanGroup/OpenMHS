"""Acceptance run of the SunblazeCartPole package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
needs gym 0.10.8r1 and its pinned dependencies (setup.py:42-51), which are not installed where the gate runs, so
nothing here compares the fake with the upstream environment.
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


class SunblazeCartPoleCases(unittest.TestCase):
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

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        for index in (-1, 2):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                     # the refused steps changed nothing
        for ticks in (0, 10001):
            # ticks is a schema bound of cap.world.step.v1, not a derived action-space limit: the server refuses
            # the shape before the action envelope check
            refused = client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": 1}}, **self.ids)
            self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID", ticks)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                              # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (1, 0, 0, 1, 1)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_constant_push_ends_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, 1, ticks=50)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # the constant +1 push passes the placeholder pole-angle threshold on the 10th step; every step pays +1
        self.assertEqual((output["terminated"], output["truncated"]), (True, False))
        self.assertEqual((output["tick"], output["reward"]), (10, 10.0))
        ended = self.step(client, 1)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")  # a reset starts the next episode
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"]), (0, 2))

    def test_a_balanced_pole_reaches_the_200_step_limit(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=4)["output"]["observation"]["values"]
        for expected_tick in range(1, 201):
            receipt = self.step(client, 1 if observation[2] * 10 + observation[3] > 0 else 0)
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
            observation = output["observation"]["values"]
        # SunblazeCartPole-v0 sets max_episode_steps=200 (sunblaze_envs/__init__.py:10); the legacy 4-tuple
        # TimeLimit reports the limit through done, so the bridge marks it terminated, not truncated
        self.assertEqual((output["terminated"], output["truncated"]), (True, False))
        self.assertEqual(self.step(client, 0)["error"]["mhs_code"], PRECONDITION)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("sunblaze:SunblazeCartPole-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1),
                        client.invoke("cap.world.seed.v1", {"seed": 2}, **self.ids)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                     # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
