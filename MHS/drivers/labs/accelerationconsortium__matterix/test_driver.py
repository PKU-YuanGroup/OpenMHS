"""Acceptance run of the Matterix Beakers package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): Isaac Sim and Isaac Lab are not installed where the gate runs, so nothing
here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INVALID = "MHS.CAPABILITY.INPUT_INVALID"
#: placeholder action of the fake: 16 values, two arms of seven joints plus one gripper each
ACTION = [0.0] * 16


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MatterixCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(values or ACTION)}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    @staticmethod
    def arms(receipt):
        policy = receipt["output"]["observation"]["policy"]
        return policy["ee_pos_robot"]["values"], policy["ee_pos_robot2"]["values"]

    def test_the_contract_and_fidelity_are_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("matterix:isaaclab", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_observation_is_the_policy_group_of_two_end_effectors(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        first, second = self.arms(receipt)
        self.assertEqual((len(first), len(first[0]), len(second), len(second[0])), (1, 3, 1, 3))

    def test_a_seed_repeats_the_initial_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3)["output"]["observation"]
        self.assertEqual(self.reset(client, seed=3)["output"]["observation"], first)
        other = self.reset(client, seed=4)["output"]["observation"]
        self.assertNotEqual(other, first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_step_advances_the_tick_and_the_action_moves_the_arms(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=5)["output"]["observation"]
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (1, 0.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(output["observation"], start)          # the zero action changes no joint
        moved = self.step(client, [1.0] * 16)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"]["tick"], 2)
        self.assertNotEqual(moved["output"]["observation"], start)
        self.assertNotEqual(moved["output"]["state_hash"], output["state_hash"])
        self.assertEqual(self.state(client)["tick"], 2)

    def test_the_action_shape_is_the_step_input_schema(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        for values in (ACTION[:-1], ACTION + [0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", len(values))
            self.assertEqual(refused["error"]["mhs_code"], INVALID, len(values))
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_the_episode_truncates_at_the_matterix_time_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ticks=360)                  # ceil(30 s / (5 * 1/60 s)), from the upstream defaults
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 360))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_a_short_trajectory(self) -> None:
        actions = ([1.0] * 16, ACTION, [0.5] * 16)

        def trajectory(seed):
            client = self.serve()                              # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            return [self.step(client, action)["output"]["state_hash"] for action in actions]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
