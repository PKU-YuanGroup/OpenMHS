"""Acceptance run of the DexVerse GraspKettle package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.  Every case runs on the fake backend (fake.py): Isaac Sim, Isaac Lab and
the gated assets are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ACTION_DIM = 28


def vector(value=0.0):
    return [value] * ACTION_DIM


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DexVerseGraspKettleCases(unittest.TestCase):
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

    def test_the_action_vector_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        completed = self.step(client, vector(0.5))
        self.assertEqual(completed["status"], "completed")
        for values in (vector(1.1), vector(-1.1)):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values[0])
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values[0])
        short = self.step(client, [0.0] * (ACTION_DIM - 1))
        self.assertEqual(short["error"]["mhs_code"], INVALID)
        self.assertEqual(self.state(client)["tick"], 1)                     # the refused steps changed nothing

    def test_a_step_applies_the_joint_target_and_the_configured_penalties(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.step(client, vector(1.0))["output"]
        observation = output["observation"]
        self.assertEqual(observation["proprio"]["values"], vector(1.0))
        self.assertEqual(observation["policy"]["values"], vector(1.0))
        # -0.005 * sum(action^2) - 0.005 * sum((action - previous)^2), both with 28 ones from zero
        self.assertAlmostEqual(output["reward"], -0.28, places=9)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, False, 1))

    def test_reset_publishes_the_observation_groups(self) -> None:
        client = self.serve()
        output = self.reset(client)["output"]
        observation = output["observation"]
        self.assertEqual(sorted(observation), ["goal", "policy", "proprio", "state"])
        self.assertEqual(len(observation["policy"]["values"]), ACTION_DIM)
        self.assertEqual(len(observation["proprio"]["values"]), ACTION_DIM)
        self.assertEqual(len(observation["state"]["values"]), 7)
        self.assertEqual(len(observation["goal"]["values"]), 3)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, vector(value))["output"]["state_hash"] for value in (0.1, -0.2, 0.3)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        other = self.serve()
        self.assertEqual(self.reset(other, seed=21)["output"]["observation"], first["observation"])

    def test_an_episode_truncates_at_twenty_seconds(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.step(client, vector(0.0), ticks=1200)["output"]
        # 20 s / (1/60 s per control step) = 1200 steps (base_cfg.py:467, base_env_cfg.py:1252 and :1318)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 1200))
        ended = self.step(client, vector(0.0))
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")         # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:Dexverse-GraspKettle-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, vector(0.0))["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, vector(0.0)), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                     # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
