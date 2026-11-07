"""Acceptance run of the pointfoot flat package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): Isaac Sim and Isaac Lab are not installed where the gate runs, so
nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ACTION = [0.4, -0.4, 0.8, -0.8, 0.4, -0.4]
DEFAULT_JOINT_POS = [0.0, 0.0, 0.0918, 0.0918, -0.057, -0.057]
ACTION_SCALE = 0.25
N_OBSERVATIONS = 185


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PointfootFlatCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(values)}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_first_step_applies_the_joint_position_action(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ACTION)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        observation = output["observation"]["values"]
        self.assertEqual(len(observation), N_OBSERVATIONS)
        # base_env_cfg.py:112-117: target = default + scale * action over the six leg joints, then the two foot
        # joints of pointfoot_cfg.py:38-39.
        expected = [default + ACTION_SCALE * value for default, value in zip(DEFAULT_JOINT_POS, ACTION)] + [0.0, 0.0]
        self.assertEqual(observation[6:14], expected)
        self.assertEqual(observation[22:28], ACTION)                               # last_action term
        self.assertEqual((output["reward"], output["tick"]), (0.0, 1))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))

    def test_the_action_length_is_the_space(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        for values in ([0.0] * 5, [0.0] * 7):
            refused = self.step(client, values)
            self.assertEqual(refused["error"]["mhs_code"], INVALID, values)
        self.assertEqual(self.state(client)["tick"], 0)                            # no refused step was executed

    def test_no_action_bound_is_invented(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, [1.0e6, -1.0e6, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        # the clone configures no action clip (base_env_cfg.py:112-117): the fake does not clamp either
        self.assertEqual(receipt["output"]["observation"]["values"][6], 250000.0)

    def test_a_seed_repeats_the_observation(self) -> None:
        def observation(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return self.reset(client, seed=seed)["output"]["observation"]["values"]

        first = observation(7)
        self.assertEqual(observation(7), first)
        self.assertNotEqual(observation(8), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_default_seed_is_the_configured_seed(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["output"]["seed"], 42)                 # base_env_cfg.py:440

    def test_the_episode_truncates_at_the_time_out(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, [0.0] * 6, ticks=1000)                         # 20.0 s / 0.02 s
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 1000))
        ended = self.step(client, [0.0] * 6)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:Isaac-PF-Blind-Flat-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 6)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 6), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                            # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
