"""Acceptance run of the AirSim UAV driver package: the gate plus cases for this driver.

The cases run on the fake backend: the upstream environment needs AirSim 1.6.0, gym 0.21.0, PyQt5 and torch, so
nothing here compares the fake with a real AirSim scene.  Add cases, never remove the check_driver call.
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


class AirsimNavigationCases(unittest.TestCase):
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
    def observation(receipt):
        values = receipt["output"]["observation"]["values"]
        return values[0] if values and isinstance(values[0], list) else values

    def test_the_action_space_is_the_limits(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [2.0, 0.0, 0.0])["status"], "completed")
        tick = self.state(client)["tick"]
        for values in ([0.49, 0.0, 0.0], [5.01, 0.0, 0.0],
                       [2.0, 2.01, 0.0], [2.0, -2.01, 0.0],
                       [2.0, 0.0, 0.53], [2.0, 0.0, -0.53]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        wrong_shape = self.step(client, [2.0, 0.0])
        self.assertEqual((wrong_shape["status"], wrong_shape["error"]["mhs_code"]),
                         ("rejected", "MHS.CAPABILITY.INPUT_INVALID"))
        self.assertEqual(self.state(client)["tick"], tick)  # a refused step changed nothing

    def test_a_reset_and_a_step_return_the_contract(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=4)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 4)
        observation = self.observation(receipt)
        self.assertEqual(len(observation), 8)  # five placeholder depth features + three state features
        self.assertEqual(self.step(client, [2.0, 0.0, 0.0])["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"], state["terminated"]), (1, 1, False))
        self.assertIsInstance(state["reward"], float)

    def test_the_vertical_action_moves_the_altitude_feature(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, [2.0, 2.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        # z grows by v_z * dt = 0.2 (multirotor_simple.py:109); the goal z is the start z, so
        # vertical_distance_norm = (0.2 / 5 / 2 + 0.5) * 255 (multirotor_simple.py:199) and the observation
        # divides it by 255 (airsim_env.py:417).  Index 6 is the vertical state feature.
        self.assertAlmostEqual(self.observation(receipt)[6], 0.52, places=6)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)
        first_step = self.step(client, [3.0, 1.0, 0.2])
        second = self.reset(client, seed=11)
        second_step = self.step(client, [3.0, 1.0, 0.2])
        self.assertEqual(self.observation(first), self.observation(second))
        self.assertEqual(self.observation(first_step), self.observation(second_step))
        self.assertEqual(first_step["output"]["reward"], second_step["output"]["reward"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        seeded = self.reset(client)
        self.assertEqual(seeded["output"]["seed"], 21)
        again = self.reset(client, seed=21)
        self.assertEqual(self.observation(seeded), self.observation(again))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [2.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        tick = self.state(client)["tick"]
        for refused in (self.step(client, [2.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], tick)  # readable, and not advanced

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:airsim-env-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)


if __name__ == "__main__":
    unittest.main()
