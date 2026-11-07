"""Acceptance run of the TactilePush package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); the upstream DiffRedMax
environment is not installed where the gate runs, so nothing here compares the fake with it.
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


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TactilePushCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        for values in ([1.5, 0.0, 0.0], [0.0, -1.5, 0.0], [0.0, 0.0, 2.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing

    def test_the_observation_has_the_upstream_shapes(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=4)["output"]["observation"]["values"]
        # envs/tactile_push_env.py:34-36 and :114-119: 3 state numbers followed by 13*10*3 tactile numbers
        self.assertEqual(len(observation), 3 + 13 * 10 * 3)
        self.assertTrue(all(isinstance(value, (int, float)) for value in observation))

    def test_a_seed_repeats_the_reset_and_sets_the_next_reset(self) -> None:
        def initial(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return self.reset(client, seed=seed)["output"]["observation"]

        self.assertEqual(initial(11), initial(11))
        self.assertNotEqual(initial(11), initial(12))

        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_step_is_observable_and_pays_the_reward(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=5)["output"]
        receipt = self.step(client, [1.0, 0.5, -0.5])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertTrue(math.isfinite(output["reward"]))
        self.assertNotEqual(output["observation"], start["observation"])
        self.assertNotEqual(output["state_hash"], start.get("state_hash"))
        state = self.state(client)
        self.assertEqual(state["tick"], 1)
        self.assertEqual(state["observation"], output["observation"])
        self.assertIn("reward_pos", state["info"])
        self.assertIn("final_pos_error", state["info"])

    def test_one_step_is_25_ms_at_the_model_timestep(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        # envs/tactile_push_env.py:66-67 with envs/assets/pusher/pusher.xml:2: frame_skip 5 * 5e-3 s
        self.assertEqual(fidelity["timestep_ms"], 25.0)
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:tactilesimulation/TactilePush-v1", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_episode_is_truncated_at_100_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, [0.0, 0.0, 0.0], ticks=100)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # envs/__init__.py:12: max_episode_steps=100, applied by the TimeLimit wrapper that gym.make adds
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 100))
        ended = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
