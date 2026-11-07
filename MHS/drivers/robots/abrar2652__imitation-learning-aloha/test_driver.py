"""Acceptance run of the Gym Aloha package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): gymnasium, dm_control and MuJoCo are not installed where the gate runs,
so nothing here compares the fake with the upstream MuJoCo environment.  The fake's success rule and its 4 x 4 x 3
stand-in image are test data, not facts about the clone.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = [0.0] * 14
SUCCESS_ACTION = [0.0] * 14
SUCCESS_ACTION[0] = 0.9
SUCCESS_ACTION[6] = 0.9


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AlohaCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        high = list(ZERO_ACTION)
        high[0] = 1.5
        low = list(ZERO_ACTION)
        low[13] = -1.5
        for values in (high, low):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_the_first_step_returns_the_fake_observation_and_flags(self) -> None:
        client = self.serve()
        receipt = self.step(client, ZERO_ACTION)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        observation = output["observation"]
        self.assertEqual(list(observation), ["top"])
        self.assertEqual(len(observation["top"]["values"]), 4)            # stand-in rows, not the 480 x 640 device image
        self.assertEqual((output["reward"], output["tick"]), (0.0, 1))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))

    def test_a_seed_repeats_the_fake_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            hashes = []
            for values in (ZERO_ACTION, SUCCESS_ACTION, ZERO_ACTION, SUCCESS_ACTION):
                hashes.append(self.step(client, values)["output"]["state_hash"])
            return hashes

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_fake_reaches_success_after_four_action_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        output = None
        for expected in (1.0, 2.0, 3.0, 4.0):
            receipt = self.step(client, SUCCESS_ACTION)
            self.assertEqual(receipt["status"], "completed", expected)
            output = receipt["output"]
            self.assertEqual(output["reward"], expected)
        self.assertEqual(output["terminated"], True)
        self.assertEqual(output["truncated"], False)
        state = self.state(client)
        self.assertEqual(state["info"]["is_success"], True)
        ended = self.step(client, SUCCESS_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_an_episode_is_truncated_at_300_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        receipt = self.step(client, ZERO_ACTION, ticks=300)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # the registration's max_episode_steps=300 is the time limit (gym_aloha/__init__.py:6), not AlohaEnv's flag
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (300, False, True))
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "gym_aloha:AlohaInsertion-v0 (dm_control MuJoCo)")
        self.assertEqual(fidelity["fidelity_level"], "F1")
        self.assertEqual(fidelity["determinism"]["kind"], "statistical")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
