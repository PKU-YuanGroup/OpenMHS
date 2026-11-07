"""Acceptance run of the ArrayCan package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): ManiSkill and SAPIEN are
not installed where the gate runs, so nothing here compares the fake with the upstream environment.  The fake's
observation has no space of its own, so the bridge wraps each leaf: a list is ``{"values": [...]}``.
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


def values(leaf):
    return leaf["values"] if isinstance(leaf, dict) else leaf


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ArrayCanCases(unittest.TestCase):
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

    def step(self, client, action=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action or {}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_step_action_is_an_open_object(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        for action in ({}, {"values": [0.0]}):
            receipt = self.step(client, action)
            self.assertEqual(receipt["status"], "completed", action)
            self.assertEqual(receipt["output"]["tick"], 1 if action == {} else 2)
        self.assertEqual(self.state(client)["tick"], 2)

    def test_a_seed_repeats_the_initial_cans(self) -> None:
        def observation(seed):
            client = self.serve()
            return self.reset(client, seed=seed)["output"]["observation"]

        first = observation(11)
        self.assertEqual(observation(11), first)
        self.assertNotEqual(observation(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_observation_has_the_extra_keys_of_the_clone(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=4)["output"]["observation"]
        for name in ("tcp_pose", "coke0_pose", "coke4_pose", "tcp_to_coke0_pos", "coke0_to_coke1_pos"):
            self.assertIn(name, observation)
        self.assertEqual(len(values(observation["tcp_pose"])), 7)
        self.assertEqual(len(values(observation["coke0_pose"])), 7)
        self.assertEqual(len(values(observation["coke0_to_coke1_pos"])), 3)

    def test_the_reward_is_the_reaching_formula(self) -> None:
        client = self.serve()
        receipt = self.step(client, {"values": []})
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]
        tcp = values(observation["tcp_pose"])[:3]
        distances = []
        for idx in range(5):
            can = values(observation[f"coke{idx}_pose"])[:3]
            distances.append(math.dist(tcp, can))
        self.assertAlmostEqual(receipt["output"]["reward"], 2.0 * (1.0 - math.tanh(5.0 * min(distances))),
                               places=12)

    def test_fifty_steps_truncate_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, {}, ticks=50)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # ArrayCan-v1 is registered with max_episode_steps=50 (envs/array_can.py:21)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (50, False, True))
        ended = self.step(client, {})
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("ManiSkill:SAPIEN/ArrayCan-v1", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, {})["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, {}), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced

    def test_ticks_must_be_inside_the_class_schema(self) -> None:
        client = self.serve()
        for ticks in (0, 10001):
            refused = self.step(client, {}, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            # The class schema bounds ticks to 1..10000; the bridge checks the step limits first.
            self.assertIn(refused["error"]["mhs_code"], (ENVELOPE, "MHS.CAPABILITY.INPUT_INVALID"), ticks)
        self.assertEqual(self.state(client)["tick"], 0)


if __name__ == "__main__":
    unittest.main()
