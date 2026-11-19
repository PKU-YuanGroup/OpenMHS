"""Acceptance run of the SPDR Bot package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab and the upstream package are not installed
where the gate runs, so nothing here compares the fake with the simulator.  The harness call is kept.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ACTION_DIM = 12                                    # spdrbot3_env_cfg.py:54 (action_space = 12)
OBS_DIM = 48                                       # spdrbot3_env_cfg.py:55 (observation_space = 48)
TIME_OUT_STEP = 999                                # fake-only timeout assumption; see fake.py


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SpdrbotCases(unittest.TestCase):
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
        values = [0.0] * ACTION_DIM if values is None else values
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def policy(self, receipt):
        values = receipt["output"]["observation"]["policy"]["values"]
        self.assertEqual(len(values), 1)
        self.assertEqual(len(values[0]), OBS_DIM)
        return values[0]

    def test_the_spaces_are_the_configured_shape(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=7)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"]["seed"], 7)
        observation = self.policy(reset)
        self.assertEqual(len(observation), OBS_DIM)
        # spdrbot3_env.py:157-158: the three commands are sampled uniformly from -1.0 to 1.0.
        for value in observation[9:12]:
            self.assertGreaterEqual(value, -1.0)
            self.assertLessEqual(value, 1.0)
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["tick"], 1)
        self.policy(receipt)

    def test_the_action_reaches_the_joint_and_action_fields(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        values = [0.1 * index for index in range(ACTION_DIM)]
        receipt = self.step(client, values=values)
        self.assertEqual(receipt["status"], "completed", receipt)
        observation = self.policy(receipt)
        # spdrbot3_env.py:79-98: joint positions minus defaults occupy 12..24, actions occupy 36..48.  The fake's
        # defaults are the placeholder zero vector and action_scale is 1, so both slices repeat the action.
        for got, expected in zip(observation[12:24], values):
            self.assertAlmostEqual(got, expected)
        for got, expected in zip(observation[36:48], values):
            self.assertAlmostEqual(got, expected)

    def test_a_seed_repeats_the_command_sample(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=21)["output"]["observation"]
        second = self.reset(client, seed=21)["output"]["observation"]
        self.assertEqual(first, second)
        self.assertNotEqual(first, self.reset(client, seed=22)["output"]["observation"])

    def test_the_seed_binding_sets_the_next_reset(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 42}, **self.ids)
        self.assertEqual(seeded["status"], "completed", seeded)
        self.assertEqual(seeded["output"], {"seed": 42, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 42)
        second = self.reset(client, seed=42)["output"]
        self.assertEqual(first, second)

    def test_the_fake_episode_truncates_at_its_declared_time_out(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ticks=TIME_OUT_STEP)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]),
                         (TIME_OUT_STEP, False, True))
        ended = self.step(client)
        self.assertEqual(ended["status"], "failed")
        self.assertEqual(ended["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")

    def test_the_placeholder_box_accepts_large_finite_actions(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, values=[1e6] * ACTION_DIM)
        self.assertEqual(receipt["status"], "completed", receipt)
        observation = self.policy(receipt)
        self.assertEqual(observation[36:48], [1e6] * ACTION_DIM)

    def test_the_action_width_is_checked(self) -> None:
        client = self.serve()
        refused = self.step(client, values=[0.0] * (ACTION_DIM - 1))
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=9, options={"note": "the fake ignores reset options"})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 9)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["timestep_ms"], 20.0)
        self.assertEqual((fidelity["determinism"]["kind"], fidelity["determinism"]["seed_control"]),
                         ("seeded", "parameter"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertFalse(fidelity["snapshot_restore"])
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)               # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
