"""Acceptance run of the Safety-Gymnasium package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py).  Safety-Gymnasium, Gymnasium, MuJoCo and numpy are not installed where
the gate runs, so nothing here compares the fake with the real environment.
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


class SafetyPointGoal1Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(values)}},
                             **self.ids)

    def reset(self, client, seed):
        return client.invoke("cap.world.reset.v1", {"seed": seed}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_step_moves_the_point_and_is_bounded_by_the_action_space(self) -> None:
        client = self.serve()
        refused = self.step(client, [2.0, 0.0])
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)                       # nothing was stepped
        completed = self.step(client, [1.0, 0.0])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["output"]["tick"], 1)
        observation = completed["output"]["observation"]["values"]
        self.assertEqual(len(observation), 60)                               # 12 sensors + 3 x 16 lidar bins
        self.assertAlmostEqual(observation[3], 0.5, places=9)                # velocimeter x at speed 0.5 m/s
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_observation_layout_is_the_upstream_one(self) -> None:
        client = self.serve()
        reset = self.reset(client, 7)
        self.assertEqual(reset["status"], "completed")
        observation = reset["output"]["observation"]["values"]
        self.assertEqual(len(observation), 60)
        # The lidar bins are closeness values in [0, 1]; the sensor values are finite.
        self.assertTrue(all(0.0 <= value <= 1.0 for value in observation[12:]))
        self.assertTrue(all(value == value and abs(value) < 1.0e9 for value in observation[:12]))

    def test_a_seed_repeats_the_initial_state_and_one_step(self) -> None:
        client = self.serve()
        first_reset = self.reset(client, 7)["output"]["observation"]
        first_step = self.step(client, [1.0, 0.25])["output"]["observation"]
        second_reset = self.reset(client, 7)["output"]["observation"]
        second_step = self.step(client, [1.0, 0.25])["output"]["observation"]
        self.assertEqual(first_reset, second_reset)
        self.assertEqual(first_step, second_step)

    def test_the_episode_truncates_at_one_thousand_environment_steps(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0, 0.0], ticks=1000)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1000)
        self.assertTrue(receipt["output"]["truncated"])
        self.assertFalse(receipt["output"]["terminated"])

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.5, 0.0]), self.reset(client, 7)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                      # readable, and not advanced
        self.assertEqual(client.reset(**self.ids)["status"], "completed")    # a simulator needs no operator
        self.assertEqual(self.step(client, [0.5, 0.0])["status"], "completed")

    def test_the_fidelity_contract_is_the_fake_model(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["resources"][0]["kind"], "world.sim")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual(fidelity["engine"], "gymnasium:SafetyPointGoal1Gymnasium-v0")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)


if __name__ == "__main__":
    unittest.main()
