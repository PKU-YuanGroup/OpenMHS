"""Acceptance run of the GSWorld package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): ManiSkill/SAPIEN is not installed where the gate runs, so nothing here
compares the kinematic stand-in with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = [0.0] * 8


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RealFr3Cases(unittest.TestCase):
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

    def step(self, client, values=None, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": list(values or ZERO_ACTION)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.25] * 8)["status"], "completed")
        for values in ([1.5] * 8, [-1.5] * 8):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_step_integrates_the_normalised_joint_delta(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")
        before = self.state(client)["observation"]["values"]
        self.assertEqual(len(before), 18)                                       # 9 qpos + 9 qvel
        receipt = self.step(client, [0.5] * 7 + [0.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        after = output["observation"]["values"]
        for index in range(7):
            self.assertAlmostEqual(after[index], before[index] + 0.05, places=7)   # 0.5 * 0.1 rad
            self.assertAlmostEqual(after[9 + index], 1.0, places=7)                 # 0.05 rad / 0.05 s
        # the gripper command 0 maps to the middle of -0.01..0.04 (fr3_umi.py:114-121)
        self.assertAlmostEqual(after[7], 0.015, places=7)
        self.assertAlmostEqual(after[8], 0.015, places=7)
        self.assertAlmostEqual(after[16], (0.015 - before[7]) / 0.05, places=7)
        self.assertAlmostEqual(after[17], (0.015 - before[8]) / 0.05, places=7)
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (0.0, False, False, 1))

    def test_a_seed_repeats_the_reset_state(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            first = self.reset(client, seed=seed)["output"]["observation"]
            hashes = [self.step(client, [0.1] * 7 + [0.2])["output"]["state_hash"] for _ in range(3)]
            return first, hashes

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_is_truncated_at_200000_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        for _ in range(20):
            receipt = self.step(client, ticks=10000)
            self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # RealFr3-v1 is registered with max_episode_steps=200000 (real_fr3_env.py:22).
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 200000))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:RealFr3-v1", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
