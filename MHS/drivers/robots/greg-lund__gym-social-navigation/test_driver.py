"""Acceptance run of the Social Navigation package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
(gym, numpy, matplotlib and the ETH data files) is not installed or imported where the gate runs, so nothing here
compares the fake with the upstream environment.
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


class SocialNavCases(unittest.TestCase):
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

    def test_the_observation_layout_and_the_action_bound(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=1)
        self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["values"]
        # 3 robot values + 2*4 agents*(3 history + 1 current) + 2*4 path points (social_nav_env.py:55)
        self.assertEqual(len(values), 43)
        self.assertTrue(all(0.0 <= value <= 1.0 for value in values), values)
        self.assertEqual(self.step(client, 1)["output"]["tick"], 1)
        for index in (-1, 10):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing

    def test_the_ticks_bound_is_refused_before_the_environment(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        for ticks in (0, 10001):
            refused = self.step(client, 0, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            # the bridge's step schema bounds ticks; the catalogue's step input is checked before env.step
            self.assertIn(refused["error"]["mhs_code"], (ENVELOPE, "MHS.CAPABILITY.INPUT_INVALID"), ticks)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_fake_world(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=5)["output"]["observation"]
        self.assertEqual(self.reset(client, seed=5)["output"]["observation"], first)
        self.assertNotEqual(self.reset(client, seed=6)["output"]["observation"], first)

    def test_the_seed_capability_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 11}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 11)
        self.assertEqual(self.reset(client, seed=11)["output"]["observation"], first["observation"])

    def test_a_stationary_step_reaches_the_episode_time_limit(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        output = self.step(client, 3, ticks=150)["output"]       # action 3 is S with speed 0
        # the episode time is 60 s / 0.4 s = 150 steps (social_nav_env.py:19,51-52)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (150, True, False))
        # the driver sets autoreset=True, so the next step resets and starts a new episode
        continued = self.step(client, 3)
        self.assertEqual(continued["status"], "completed")
        self.assertEqual(continued["output"]["tick"], 1)
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gym:social-nav-train-env-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (400.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
