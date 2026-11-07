"""Acceptance run of the So101PourEnv package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): mujoco, gymnasium and
numpy are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
TILT = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class So101PourCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values or ZERO}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0, -1.0, 0.5, 0.0, -0.5, 1.0])["status"], "completed")
        for values in ([1.5, 0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0, -1.5]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_reset_returns_the_eighteen_value_observation(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=3)
        self.assertEqual(reset["status"], "completed")
        observation = reset["output"]["observation"]["values"]
        self.assertEqual(len(observation), 18)
        self.assertEqual(observation[-1], 0.0)                   # beaker_ml (pour_env.py:65-71)
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"], state["seed"]), (0, 1, 3))
        self.assertEqual((state["terminated"], state["truncated"]), (False, False))

    def test_a_step_applies_the_delta_and_moves_the_joints(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        receipt = self.step(client, [1.0, 0.0, 0.0, 0.0, 0.0, 1.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        observation = output["observation"]["values"]
        self.assertAlmostEqual(observation[0], 0.05, places=12)   # action[:5] * 0.05 (pour_env.py:45-46)
        self.assertAlmostEqual(observation[5], 25.0, places=9)    # placeholder velocity: 0.05 / 0.002
        self.assertAlmostEqual(observation[10], 1.0, places=12)   # ctrl[5] = action[5] (pour_env.py:47)
        self.assertEqual(observation[-1], 0.0)                    # the wrist is not tilted yet
        self.assertTrue(math.isfinite(output["reward"]))
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        self.assertEqual(self.state(client)["observation"], output["observation"])

    def test_water_flows_only_above_thirty_degrees(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        dry = self.step(client, TILT, ticks=10)                   # 10 * 0.05 rad = 28.65 degrees
        self.assertEqual(dry["status"], "completed")
        self.assertEqual(dry["output"]["observation"]["values"][-1], 0.0)
        wet = self.step(client, TILT, ticks=1)                    # 11 * 0.05 rad = 31.51 degrees
        self.assertEqual(wet["status"], "completed")
        volume = wet["output"]["observation"]["values"][-1]
        self.assertGreater(volume, 0.0)
        self.assertLess(volume, 0.01)                             # 25 ml/s * 0.002 s at the threshold
        self.assertEqual(wet["output"]["tick"], 11)

    def test_the_default_time_limit_ends_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, TILT, ticks=500)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # pour_env.py:60-61: 500 steps terminate; the maximum flow is 25 ml/s * 0.002 s, so 150 ml is unreachable
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 500))
        self.assertLess(output["observation"]["values"][-1], 150.0)
        ended = self.step(client, TILT)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"]
                    for action in ([1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                                   [0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
                                   [0.0, 0.0, 0.0, 1.0, 0.0, 1.0])]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_reset_options_are_accepted(self) -> None:
        client = self.serve()
        # upstream reset(seed, options) accepts options and does not use them (pour_env.py:34-39)
        receipt = self.reset(client, seed=5, options={"scene": "default"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(len(receipt["output"]["observation"]["values"]), 18)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual(device["safety"]["estop"]["kind"], "software")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertIn("kinematic fake", fidelity["engine"])
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
