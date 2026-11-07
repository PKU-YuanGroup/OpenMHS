"""Acceptance run of the d3il sorting package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py).  The upstream environment needs MuJoCo, numpy, gym and cv2 and was not
imported or run; nothing here compares the fake with it.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
REGISTERED_STEPS = 100


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SortingCases(unittest.TestCase):
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

    def test_a_step_moves_the_robot_and_pays_zero(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=3)["output"]["observation"]["values"]
        self.assertEqual(len(start), 8)                                    # the declared observation space (8,)
        receipt = self.step(client, [0.01, 0.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        moved = output["observation"]["values"]
        self.assertAlmostEqual(moved[0], start[0] + 0.01, places=9)
        self.assertAlmostEqual(moved[1], start[1], places=9)
        self.assertEqual((output["reward"], output["tick"], output["terminated"]), (0.0, 1, False))

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        for values in ([0.011, 0.0], [0.0, -0.011]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 0)                    # the refused steps changed nothing

    def test_a_seed_repeats_the_start(self) -> None:
        first = self.reset(self.serve(), seed=11)["output"]["observation"]
        again = self.reset(self.serve(), seed=11)["output"]["observation"]
        other = self.reset(self.serve(), seed=12)["output"]["observation"]
        self.assertEqual(first, again)
        self.assertNotEqual(first, other)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_registered_episode_limit_ends_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        output = None
        for expected in range(1, REGISTERED_STEPS + 1):
            receipt = self.step(client, [0.0, 0.0])
            self.assertEqual(receipt["status"], "completed", expected)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected)
        # sorting-v0 passes max_steps_per_episode=100 (gym_sorting/__init__.py:7); the wrapper's step limit is
        # env_step_counter >= max_steps_per_episode - 1 (gym_env_wrapper.py:131-136)
        self.assertTrue(output["terminated"])
        ended = self.step(client, [0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")  # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gym:sorting-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (35.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.01, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.01, 0.0]), self.reset(client, seed=1),
                        client.invoke("cap.world.seed.v1", {"seed": 4}, **self.ids)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
