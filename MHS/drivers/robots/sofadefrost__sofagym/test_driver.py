"""Acceptance run of the SofaGym package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): SOFA, SofaPython3 and
SoftRobots are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
GOALS = ((40.0, 40.0, 100.0), (-10.0, 20.0, 80.0))
TIMER_LIMIT = 250


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TrunkCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, 0)["status"], "completed")
        for index in (-1, 16):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_the_observation_is_66_coordinates_and_the_goal(self) -> None:
        client = self.serve()
        values = self.reset(client, seed=5)["output"]["observation"]["values"]
        self.assertEqual(len(values), 66)                                # TrunkEnv.py:32, :75-77
        self.assertIn(tuple(values[-3:]), GOALS)                         # TrunkEnv.py:38, appended at :231-233
        self.assertGreater(values[62], 40.0)                             # the tip height / 4 (TrunkScene.py:89-91)
        self.assertEqual(self.state(client)["observation"]["values"], values)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_pull_and_release_return_the_cable(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=7)["output"]["observation"]["values"]
        receipt = self.step(client, 0)                                   # cable 0, displacement +1
        self.assertEqual(receipt["status"], "completed")
        pulled = receipt["output"]["observation"]["values"]
        self.assertGreater(pulled[61], before[61])                       # cable 0 pulls toward +y (TrunkScene.py:76)
        self.assertEqual(pulled[62], before[62])                         # the pull does not change the height
        self.assertGreaterEqual(receipt["output"]["reward"], 0.0)
        self.assertLessEqual(receipt["output"]["reward"], 1.0)           # TrunkToolbox.py:82
        self.assertEqual(self.step(client, 8)["status"], "completed")    # cable 0, displacement -1
        self.assertEqual(self.state(client)["observation"]["values"], before)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (0, 3, 8, 15, 0)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_timer_limit_does_not_end_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        output = None
        for tick in range(1, TIMER_LIMIT + 11):
            receipt = self.step(client, 0)
            self.assertEqual(receipt["status"], "completed", tick)
            output = receipt["output"]
        # AbstractEnv.py:359-367 computes a local truncated flag at timer_limit 250 but returns the four-tuple
        # without it, so neither the bridge nor the fake truncates the episode.
        self.assertEqual(output["tick"], TIMER_LIMIT + 10)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(self.state(client)["tick"], TIMER_LIMIT + 10)

    def test_the_reset_options_are_refused(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.world.reset.v1", {"options": {"low": 0.0}}, **self.ids)
        self.assertEqual(refused["status"], "failed")                    # TrunkEnv.reset takes no options

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("sofagym:trunk-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 7)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced
        self.assertNotEqual(self.state(client)["tick"], 2)
        # the state is read, not stepped, after the latch
        self.assertEqual(self.step(client, 0)["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
