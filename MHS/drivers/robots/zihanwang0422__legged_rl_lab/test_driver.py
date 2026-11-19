"""Acceptance run of the legged_rl_lab package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim and Isaac Lab
are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ZERO_ACTION = {"values": [0.0] * 29}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CrossEmbodiedCases(unittest.TestCase):
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
    def parts(observation):
        policy = observation["policy"]["values"]
        critic = observation["critic"]["values"]
        return policy, critic

    def test_the_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:legged_rl_lab-g1go2-kinematic-fake", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_observations_keep_the_98_and_101_dimension_layout(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        policy, critic = self.parts(receipt["output"]["observation"])
        self.assertEqual((len(policy), len(critic)), (98, 101))
        self.assertEqual(policy[:2], [1.0, 0.0])                 # the fake models the G1 half of the scene
        self.assertEqual(policy[5:8], [0.0, 0.0, -1.0])          # projected gravity
        self.assertEqual(critic[2:5], [0.0, 0.0, 0.0])           # critic adds base linear velocity
        self.assertTrue(all(-1.0 <= value <= 1.0 for value in policy[8:11]))   # the command ranges

    def test_the_g1_observation_uses_raw_actions_and_scaled_velocities(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, [0.4] * 29)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        policy, critic = self.parts(output["observation"])
        self.assertEqual(policy[11:40], [0.2] * 29)              # 0.4 * scale_g1 0.5
        self.assertEqual(policy[40:69], [0.5] * 29)             # velocity 10 * ObsTerm scale 0.05
        self.assertEqual(critic[43:72], [0.5] * 29)
        self.assertEqual(policy[69:98], [0.4] * 29)             # last_action_cross reads raw manager action
        self.assertEqual(critic[72:101], [0.4] * 29)
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (0.15, False, False, 1))

    def test_a_seed_repeats_the_command_on_a_fresh_world(self) -> None:
        def command(seed):
            client = self.serve()
            return self.parts(self.reset(client, seed=seed)["output"]["observation"])[0][8:11]

        first = command(11)
        self.assertEqual(command(11), first)
        self.assertNotEqual(command(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.parts(self.reset(client)["output"]["observation"])[0]
        second = self.parts(self.reset(client, seed=21)["output"]["observation"])[0]
        self.assertEqual(first, second)

    def test_a_zero_action_episode_truncates_at_1000_control_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        receipt = self.step(client, [0.0] * 29, ticks=1000)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # 20 s episode / 0.02 s control period (g1go2_flat_env_cfg.py:533-535)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 1000))
        ended = self.step(client, [0.0] * 29)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_base_height_threshold_terminates_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, [1000.0] * 29)
        self.assertEqual(receipt["status"], "completed")
        # the 0.25 m base-fall term (g1go2_flat_env_cfg.py:493-497) is exercised by the fake's kinematic height
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["tick"]), (True, 1))
        self.assertEqual(receipt["output"]["reward"], 0.0)       # is_alive_cross is zero on termination
        ended = self.step(client, [0.0] * 29)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_a_wrong_action_width_is_an_input_error(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        refused = self.step(client, [0.0] * 28)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 29)["status"], "completed")
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        for refused in (self.step(client, [0.0] * 29), self.reset(client, seed=1),
                        client.invoke("cap.world.seed.v1", {"seed": 1}, **self.ids)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced
        stopped = self.state(client)
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertEqual(self.state(client), stopped)           # latch release does not restart the stand-in


if __name__ == "__main__":
    unittest.main()
