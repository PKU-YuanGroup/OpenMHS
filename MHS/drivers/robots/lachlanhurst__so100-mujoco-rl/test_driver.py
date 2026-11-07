"""Acceptance run of the SO-100 Env01 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); mujoco and gymnasium are
not installed where the gate runs, so nothing here compares the fake with the upstream environment.  The fake is a
kinematic stand-in (see fake.py): its seed repeatability is a property of the test data, not of the upstream model.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Env01Cases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(values)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        for value in (-1.5, 1.5):
            refused = self.step(client, [value, 0.0, 0.0, 0.0, 0.0, 0.0])
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["tick"], 1)               # the refused steps changed nothing

    def test_the_observation_has_fifteen_values_and_a_block_inside_the_reset_ring(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=3)["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), 15)
        self.assertEqual(output["seed"], 3)
        block = values[9:12]
        radius = (block[0] ** 2 + block[1] ** 2) ** 0.5
        # env01_v1.py:45 draws the distance from 0.18 to 0.42 m and puts z at 0.0
        self.assertGreaterEqual(radius, 0.18 - 1e-9)
        self.assertLessEqual(radius, 0.42 + 1e-9)
        self.assertEqual(block[2], 0.0)

    def test_the_fake_reset_repeats_for_a_seed(self) -> None:
        # This is the fake's own behaviour (random.Random(seed) in fake.py).  The upstream reset draws from numpy's
        # global generator (env01_v1.py:45-55), which reset(seed=...) does not seed, so the published fidelity is
        # statistical and this case makes no claim about the upstream model.
        client = self.serve()
        first = self.reset(client, seed=7)["output"]["observation"]["values"]
        second = self.reset(client, seed=7)["output"]["observation"]["values"]
        self.assertEqual(first, second)
        self.assertNotEqual(self.reset(client, seed=8)["output"]["observation"]["values"], first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]
        self.assertEqual(accepted["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_truncates_at_the_registered_time_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        output = self.step(client, ZERO_ACTION, ticks=4000)["output"]
        # Env01-v1 is registered with max_episode_steps=4000 (src/so100_mujoco_rl/__init__.py:8); Env01 itself
        # always returns terminated=False (env01_v1.py:29-37), so the only end is the truncation.
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 4000))
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:Env01-v1", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "statistical")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (32.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)               # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
