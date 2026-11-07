"""Acceptance run of the pc-gym package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): pc-gym itself is not
installed where the gate runs, so nothing here compares the fake with the upstream environment.
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


class PcGymCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [0.0])["status"], "completed")
        for value in (-1.5, 1.5):
            refused = self.step(client, [value])
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_reset_returns_the_normalised_quick_start_state(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=3)["output"]
        self.assertEqual(output["seed"], 3)
        values = output["observation"]["values"]
        self.assertEqual(len(values), 3)                                         # [Ca, T, Ca_SP]
        # by hand with x0 [0.8, 330, 0.8] and the README bounds (2*(x-low)/(high-low) - 1)
        self.assertAlmostEqual(values[0], 2 * (0.8 - 0.7) / 0.3 - 1, places=9)
        self.assertAlmostEqual(values[1], 2 * (330 - 300) / 50 - 1, places=9)
        self.assertAlmostEqual(values[2], 2 * (0.8 - 0.8) / 0.1 - 1, places=9)

    def test_a_step_advances_the_cstr_balances(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, [0.0])                                       # tc = 298.5 K
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        values = output["observation"]["values"]
        self.assertEqual(len(values), 3)
        # the reactor consumes A faster than it is fed and the jacket cools it: Ca rises and T falls
        self.assertGreater(values[0], 2 * (0.8 - 0.7) / 0.3 - 1)
        self.assertLess(values[1], 2 * (330 - 300) / 50 - 1)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_episode_ends_at_n_minus_one(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        output = self.step(client, [0.0], ticks=99)["output"]
        self.assertEqual((output["tick"], output["terminated"]), (99, True))
        ended = self.step(client, [0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, [value])["output"]["state_hash"] for value in (0.0, 0.5, -0.5, 1.0)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("pcgym:cstr", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (250.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
