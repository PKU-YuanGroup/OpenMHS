"""Acceptance run of the roboverse package: the gate, plus cases for this driver.

The cases run on the fake backend (fake.py): the upstream legacy Gym / PyBullet environment is never imported or
run.  Add cases, never remove the check_driver call.
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


class Widow250Cases(unittest.TestCase):
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

    @staticmethod
    def values(receipt):
        return receipt["output"]["observation"]["state"]["values"]

    def test_the_action_box_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 8)["status"], "completed")
        for bad in ([2.0] + [0.0] * 7, [-2.0] + [0.0] * 7):
            refused = self.step(client, bad)
            self.assertEqual(refused["status"], "rejected", bad)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, bad)
        short = self.step(client, [0.0] * 7)
        self.assertEqual(short["status"], "rejected")
        self.assertIn(short["error"]["mhs_code"], ("MHS.CAPABILITY.INPUT_INVALID", "MHS.SCHEMA.INVALID"))
        self.assertEqual(self.state(client)["tick"], 1)                 # no refused step reached the fake

    def test_the_first_step_is_the_kinematic_delta(self) -> None:
        client = self.serve()
        start = self.values(self.reset(client, seed=3))
        receipt = self.step(client, [0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["state"]["values"]
        # xyz_action_scale is 0.2 (roboverse/envs/widow250.py:57), so 0.5 * 0.2 = 0.1 on x
        self.assertAlmostEqual(values[0], start[0] + 0.1, places=7)
        self.assertAlmostEqual(values[1], start[1], places=7)
        self.assertAlmostEqual(values[2], start[2], places=7)
        self.assertEqual((output["reward"], output["tick"], output["terminated"], output["truncated"]),
                         (0.0, 1, False, False))

    def test_the_ee_position_is_clipped(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        output = self.step(client, [1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], ticks=5)["output"]
        values = output["observation"]["state"]["values"]
        # ee_pos_high is (0.8, 0.4, -0.1) (roboverse/envs/widow250.py:61-62)
        self.assertAlmostEqual(values[0], 0.8, places=7)
        self.assertAlmostEqual(values[1], 0.4, places=7)
        self.assertAlmostEqual(values[2], -0.1, places=7)
        self.assertEqual(output["tick"], 5)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                      # a fresh world: the state hash counts episodes
            reset = self.reset(client, seed=seed)["output"]
            steps = [self.step(client, [0.1, 0.2, -0.3, 0.4, 0.5, 0.6, 0.7, 0.8])["output"]["state_hash"]
                     for _ in range(3)]
            return reset["observation"], steps

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_observation_has_the_upstream_keys(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=1)["output"]["observation"]
        for key in ("object_position", "object_orientation", "state", "image"):
            self.assertIn(key, observation)
        self.assertEqual(len(observation["object_position"]["values"]), 3)
        self.assertEqual(len(observation["object_orientation"]["values"]), 4)
        self.assertEqual(len(observation["state"]["values"]), 10)       # roboverse/envs/widow250.py:342
        # the fake returns 12 values, the real image is 48x48x3 = 6912 (roboverse/envs/widow250.py:339-341)
        self.assertEqual(len(observation["image"]["values"]), 12)

    def test_closing_the_gripper_near_the_object_then_lifting_rewards(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=7)["output"]["observation"]
        target = observation["object_position"]["values"]
        for _ in range(3):
            current = self.state(client)["observation"]["state"]["values"][:3]
            action = [0.0] * 8
            for index in range(3):
                action[index] = max(-1.0, min(1.0, (target[index] - current[index]) / 0.2))
            self.assertEqual(self.step(client, action)["status"], "completed")
        closed = self.step(client, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0])
        self.assertEqual(closed["status"], "completed")
        lifted = self.step(client, [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(lifted["status"], "completed")
        # check_grasp: object height above -0.25 and distance below 0.1 (roboverse/bullet/object_utils.py:46-56)
        self.assertEqual(lifted["output"]["reward"], 1.0)

    def test_the_legacy_step_never_terminates(self) -> None:
        client = self.serve()
        output = self.step(client, [0.0] * 8, ticks=100)["output"]
        # Widow250Env.step sets done = False and registration adds no time limit (roboverse/envs/widow250.py:274)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (100, False, False))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertIn("pybullet", fidelity["engine"])
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual(fidelity["timestep_ms"], 41.6667)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 8)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 8), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
