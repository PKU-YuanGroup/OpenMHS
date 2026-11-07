"""Acceptance run of the Google Research Football package: the gate plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); the upstream environment
needs the C++ gfootball_engine and is not installed where the gate runs, so nothing here compares the fake with an
upstream run.
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


class FootballCases(unittest.TestCase):
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

    def observation(self, client):
        return self.state(client)["observation"]["values"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 5)["status"], "completed")
        before = self.state(client)["tick"]
        for index in (-1, 19):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], before)        # the refused steps changed nothing

    def test_the_simple115_observation_has_the_upstream_size_and_layout(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        values = self.observation(client)
        self.assertEqual(len(values), 115)
        # wrappers.py:161-165: 88 player values, backfilled with -1 by this fake; then ball, possession, active
        # player and game mode (wrappers.py:167-186)
        self.assertEqual(values[:88], [-1.0] * 88)
        self.assertEqual(values[88:91], [0.0, 0.0, 0.0])            # ball position, fake start
        self.assertEqual(values[91:94], [0.0, 0.0, 0.0])            # ball direction
        self.assertEqual(values[94:97], [1.0, 0.0, 0.0])            # possession: nobody
        self.assertEqual(values[97:108], [0.0] * 11)                # active player: none
        self.assertEqual(values[108:115], [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])  # game mode: normal

    def test_a_directional_action_moves_the_ball(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, 5)                              # right, the fifth directional action
        self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["values"]
        self.assertAlmostEqual(values[88], 0.01)                    # fake placeholder: BALL_STEP
        self.assertEqual(values[89], 0.0)
        self.assertEqual(values[91:94], [1.0, 0.0, 0.0])
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["tick"]), (0.0, 1))

    def test_the_episode_ends_at_the_scenario_duration(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, 0, ticks=3000)                  # 11_vs_11_stochastic game_duration
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 3000))
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")  # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_is_recorded_but_the_upstream_reset_takes_none(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 7}, **self.ids)["output"]["accepted"], True)
        seeded = self.reset(client)
        self.assertEqual(seeded["output"]["seed"], 7)
        explicit = self.reset(client, seed=8)
        self.assertEqual(explicit["output"]["seed"], 8)
        # the fake's upstream-style reset takes no seed, so the observation is the same start state
        self.assertEqual(seeded["output"]["observation"], explicit["output"]["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gfootball:fake-simple115", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)             # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
