"""Acceptance run of the uf-gym package: the gate, plus cases for the XArm6Reach-v3 driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gymnasium, pybullet and
panda-gym are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
The fake's goal, reward, success radius and observation values are placeholders; the action bounds, the 0.05 m step,
the height clip and the 50-step limit are the ones the clone states.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class XArm6ReachCases(unittest.TestCase):
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
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.step(client, [1.0, 0.0, 0.0])["status"], "completed")
        for values in ([1.1, 0.0, 0.0], [0.0, -1.1, 0.0], [0.0, 0.0, 1.1]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing
        short = self.step(client, [1.0, 0.0])
        self.assertEqual(short["error"]["mhs_code"], INPUT_INVALID)              # three values, never fewer

    def test_the_first_step_moves_the_end_effector(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, [1.0, 1.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]["values"]
        position, velocity = observation[:3], observation[3:6]
        # the fake starts at its placeholder origin and applies the clone's 0.05 m step (xarm6.py:85)
        self.assertAlmostEqual(position[0], 0.05, places=7)
        self.assertAlmostEqual(position[1], 0.05, places=7)
        self.assertAlmostEqual(position[2], 0.0, places=7)
        self.assertAlmostEqual(velocity[0], 1.0, places=7)
        self.assertAlmostEqual(velocity[1], 1.0, places=7)
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["tick"]), (-1.0, 1))
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["truncated"]), (False, False))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, values)["output"]["state_hash"]
                    for values in ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 1.0, 1.0])]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual((accepted["output"]["seed"], accepted["output"]["accepted"]), (21, True))
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_truncates_at_50_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        receipt = self.step(client, [0.0, 0.0, 0.0], ticks=50)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # XArm6Reach-v3 is registered with max_episode_steps=50 (uf_gym/__init__.py:19)
        self.assertEqual((output["truncated"], output["terminated"], output["tick"]), (True, False, 50))
        self.assertEqual(output["reward"], -50.0)
        ended = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:XArm6Reach-v3", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client, seed=5)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
