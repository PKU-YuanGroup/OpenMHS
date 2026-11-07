"""Acceptance run of the gym-line-follower package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gym, pybullet,
opencv-python, shapely and numpy are not installed where the gate runs, so nothing here compares the fake
with the upstream environment.  The fake is a kinematic model, not the upstream PyBullet simulation.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LineFollowerCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        for values in ([1.01, 0.0], [0.0, -1.01]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        wrong_shape = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual(wrong_shape["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(self.state(client)["tick"], 1)                     # the refused steps changed nothing

    def test_the_observation_is_sixteen_bounded_points(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, [0.25, 0.25])
        self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), 16)
        for index in range(0, len(values), 2):
            self.assertGreaterEqual(values[index], 0.0)
            self.assertLessEqual(values[index], 0.3)
            self.assertGreaterEqual(values[index + 1], -0.2)
            self.assertLessEqual(values[index + 1], 0.2)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, values)["output"]["state_hash"]
                    for values in ([0.5, 0.5], [0.4, 0.6], [0.6, 0.4], [0.2, 0.2])]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_zero_action_does_not_move_the_bot(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        before = self.state(client)["info"]
        receipt = self.step(client, [0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        after = self.state(client)["info"]
        self.assertEqual((after["x"], after["y"], after["yaw"]), (before["x"], before["y"], before["yaw"]))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_an_episode_ends_when_the_bot_leaves_the_line(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, [1.0, 0.0], ticks=150)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertLess(output["tick"], 150)                               # the run stopped at the terminal state
        self.assertLess(output["reward"], 0.0)                             # the failed episode pays -100
        self.assertEqual(self.step(client, [0.0, 0.0])["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")  # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:line-follower-kinematics", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (40.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                     # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
