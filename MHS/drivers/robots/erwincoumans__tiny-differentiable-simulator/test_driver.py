"""Acceptance run of the tiny-differentiable-simulator package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the compiled
pytinydiffsim extension, the legacy gym package and numpy are not installed where the gate runs, so nothing here
compares the fake with the upstream engine.
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


class CartpoleTinyDiffSimCases(unittest.TestCase):
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

    def step(self, client, force=0.0, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": [force]}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    @staticmethod
    def observation(receipt):
        return receipt["output"]["observation"]["values"]

    # -- the action space is the envelope -------------------------------------------------------------------
    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0.0)["status"], "completed")
        for force in (-10.5, 10.5):
            refused = self.step(client, force)
            self.assertEqual(refused["status"], "rejected", force)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, force)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    # -- the analytic cart-pole of the fake ----------------------------------------------------------------
    def test_a_positive_force_pushes_the_cart_and_the_pole(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, 10.0)
        self.assertEqual(receipt["status"], "completed")
        x, theta, x_dot, theta_dot = self.observation(receipt)
        # one Euler step from the seed 3 start: x_dot = start + dt*xacc and theta_dot = start + dt*thetaacc
        self.assertGreater(x_dot, 0.1)                            # the force accelerates the cart to the right
        self.assertLess(theta_dot, -0.19)                         # and tips the pole in the negative direction
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["tick"]), (1.0, 1))
        self.assertFalse(receipt["output"]["terminated"])

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.observation(self.step(client, force)) for force in (10.0, 0.0, -10.0)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_ends_at_the_position_and_angle_thresholds(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, 10.0, ticks=50)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # the environment's own done flag stops the bridge before the 50 requested ticks
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertLess(output["tick"], 50)
        self.assertEqual(output["reward"], float(output["tick"]))  # reward 1 for every tick (cartpole_tds_env.py:72)
        values = self.observation(receipt)
        self.assertTrue(abs(values[0]) > 0.4 or abs(values[1]) > 12 * 2 * 3.141592653589793 / 360)
        ended = self.step(client, 0.0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_reset_clears_the_step_counter(self) -> None:
        client = self.serve()
        self.step(client, 1.0, ticks=3)
        self.assertEqual(self.state(client)["tick"], 3)
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["tick"], state["terminated"], state["truncated"]), (0, False, False))

    # -- the contract and the e-stop ------------------------------------------------------------------------
    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("tds:pytinydiffsim.CartpoleEnv", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1.0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1.0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)           # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
