"""Acceptance run of the CoppeliaSim cart-pole package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): CoppeliaSim, the scene
``cart_pole.ttt`` and the remoteApi library are not available where the gate runs, so nothing here compares the fake
with a simulator.
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
CART_STEP = 0.02  # placeholder dynamics of fake.py, not a device fact
POLE_STEP = 0.02  # placeholder dynamics of fake.py, not a device fact


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CartPoleCases(unittest.TestCase):
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
        for index in (0, 1, 2):
            self.assertEqual(self.step(client, index)["status"], "completed", index)
        for index in (-1, 3):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 3)                 # the refused steps changed nothing

    def test_a_seed_repeats_the_start_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3)["output"]
        second = self.reset(client, seed=3)["output"]
        self.assertEqual(first["seed"], 3)
        self.assertEqual(first["observation"], second["observation"])
        values = first["observation"]["values"]
        self.assertEqual(len(values), 4)
        self.assertTrue(all(-0.05 <= value <= 0.05 for value in values[:2]), values)
        self.assertEqual(values[2:], [0.0, 0.0])

    def test_the_discrete_force_mapping(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=3)["output"]["observation"]["values"]
        receipt = self.step(client, 1)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # CartPoleEnv.py:84-90: action 1 is +1.0 force, action 2 is -1.0, action 0 is zero.
        self.assertAlmostEqual(output["observation"]["values"][0], start[0] + CART_STEP, places=9)
        self.assertAlmostEqual(output["observation"]["values"][1], start[1] + POLE_STEP, places=9)
        self.assertAlmostEqual(output["observation"]["values"][2], CART_STEP / 0.005, places=9)
        self.assertAlmostEqual(output["observation"]["values"][3], POLE_STEP / 0.005, places=9)
        self.assertEqual((output["reward"], output["tick"], output["terminated"]), (1.0, 1, False))
        back = self.step(client, 2)["output"]["observation"]["values"]
        self.assertAlmostEqual(back[0], start[0], places=9)
        self.assertAlmostEqual(back[1], start[1], places=9)
        self.assertAlmostEqual(back[2], -CART_STEP / 0.005, places=9)
        still = self.step(client, 0)["output"]["observation"]["values"]
        self.assertAlmostEqual(still[0], start[0], places=9)
        self.assertAlmostEqual(still[1], start[1], places=9)
        self.assertEqual(still[2:], [0.0, 0.0])

    def test_a_constant_push_ends_the_episode_at_the_threshold(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, 1, ticks=100)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # CartPoleEnv.py:99: the cart stops at +-0.8 or the pole leaves +-40*pi/360 rad; every step including the
        # one that ends the episode pays 1.0 (CartPoleEnv.py:102-107), so the reward is the tick count.
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertGreaterEqual(output["tick"], 2)
        self.assertLessEqual(output["tick"], 50)
        self.assertEqual(output["reward"], float(output["tick"]))
        cart, pole = output["observation"]["values"][:2]
        self.assertTrue(abs(cart) >= 0.8 or abs(pole) > 40 * math.pi / 360, (cart, pole))
        ended = self.step(client, 1)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")      # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (1, 0, 2, 1)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_ticks_advance_that_many_steps(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=2)["output"]["observation"]["values"]
        receipt = self.step(client, 1, ticks=5)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (5, 5.0))
        self.assertFalse(output["terminated"])
        self.assertAlmostEqual(output["observation"]["values"][0], start[0] + 5 * CART_STEP, places=9)
        self.assertAlmostEqual(output["observation"]["values"][2], CART_STEP / 0.005, places=9)

    def test_the_reset_options_are_ignored_like_the_legacy_api(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"low": 0.2, "high": 0.3})
        self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["values"]
        self.assertTrue(all(-0.05 <= value <= 0.05 for value in values[:2]), values)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("coppeliasim", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (5.0, 0, "lockstep"))
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
