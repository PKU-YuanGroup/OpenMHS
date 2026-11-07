"""Acceptance run of the SUMO-RL package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): sumo-rl, SUMO, sumolib,
traci and numpy are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
OBSERVATION_SIZE = 11          # placeholder: 2 green phases + 1 min-green flag + 2 * 4 lanes
HORIZON_TICKS = 20             # placeholder: num_seconds 100 / delta_time 5


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SumoRLCases(unittest.TestCase):
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
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_step_advances_the_simulation_and_changes_the_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3)["output"]["observation"]["values"]
        self.assertEqual(len(first), OBSERVATION_SIZE)                           # observations.py:45-50
        self.assertTrue(all(0.0 <= value <= 1.0 for value in first), first)      # Box(0, 1)
        self.assertEqual(sum(first[:2]), 1.0)                                    # one-hot green phase
        receipt = self.step(client, 1)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), OBSERVATION_SIZE)
        self.assertNotEqual(values, first)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        self.assertIsInstance(output["reward"], float)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
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

    def test_the_episode_truncates_at_the_configured_horizon(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, 1, ticks=HORIZON_TICKS)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # sim_max_time is begin_time + num_seconds (env.py:142) and step truncates at sim_step >= sim_max_time
        # (env.py:341-344); the stand-in uses the 100 s horizon of the upstream gym test (tests/gym_test.py:10).
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]),
                         (HORIZON_TICKS, False, True))
        ended = self.step(client, 1)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")               # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        summary = client.hello()["devices"][0]
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(summary["risk_class"], "R0")
        self.assertEqual(device["resources"][0]["kind"], "world.sim")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("sumo-rl:SUMO traffic signal control", "F0"))
        self.assertEqual((fidelity["determinism"]["kind"], fidelity["determinism"]["seed_control"]),
                         ("seeded", "parameter"))
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (5000.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
