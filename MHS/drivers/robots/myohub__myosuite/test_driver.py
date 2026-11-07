"""Acceptance run of the MyoSuite package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py); MyoSuite, MuJoCo, gymnasium and numpy are not installed where the gate
runs, so nothing here compares the fake with the upstream environment.  The action vector has one value per muscle
actuator of the fake's stand-in space; the real size comes from the model's actuator block.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ACTION_SIZE = 39                       # the fake's action space (the model's muscle actuators)
ZERO_ACTION = [0.0] * ACTION_SIZE
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BaodingCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(values)}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_reaches_the_fake_and_changes_the_observation(self) -> None:
        client = self.serve()
        first = self.step(client, ZERO_ACTION)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["output"]["tick"], 1)
        values = first["output"]["observation"]["values"]
        self.assertEqual(len(values), 86)
        self.assertEqual(values[-1], 0.0)
        second = self.step(client, [1.0] * ACTION_SIZE)
        self.assertEqual(second["status"], "completed")
        self.assertEqual(second["output"]["tick"], 2)
        self.assertEqual(second["output"]["observation"]["values"][-1], 1.0)
        self.assertGreaterEqual(len(second["output"]["observation"]["values"]), 86)

    def test_an_action_outside_the_space_is_refused(self) -> None:
        client = self.serve()
        refused = self.step(client, [2.0] * ACTION_SIZE)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)                         # the refused step changed nothing
        edge = [0.0] * ACTION_SIZE
        edge[7] = -1.5
        self.assertEqual(self.step(client, edge)["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_episode(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            receipt = self.reset(client, seed=seed)
            self.assertEqual(receipt["output"]["seed"], seed)
            return receipt["output"]["observation"]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_truncates_at_the_registered_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        for expected_tick in range(1, 201):
            receipt = self.step(client, ZERO_ACTION)
            self.assertEqual(receipt["status"], "completed", expected_tick)
            self.assertEqual(receipt["output"]["tick"], expected_tick)
        output = receipt["output"]
        # myoChallengeBaodingP1-v1 is registered with max_episode_steps=200 (challenge/__init__.py:503)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 200))
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "analytic:myosuite-baoding-stand-in")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (25.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
