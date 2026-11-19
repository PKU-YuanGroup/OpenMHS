"""Acceptance run of the AirSim-RL package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): AirSim, Unreal Engine
and the legacy gym/airsim packages are not installed where the gate runs, so nothing here compares the fake with a
live AirSim simulator or claims a captured camera frame.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AirSimCarCases(unittest.TestCase):
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

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 6)["status"], "completed")
        for index in (-1, 7):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_the_observation_and_the_legacy_reset(self) -> None:
        client = self.serve()
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["values"]
        self.assertEqual((len(values), len(values[0]), len(values[0][0])), (8, 8, 3))
        self.assertTrue(all(0 <= value <= 255 for row in values for pixel in row for value in pixel))
        self.assertEqual(receipt["output"]["seed"], 0)                  # the bridge's configured default seed
        # The upstream reset(self) takes no seed or options; the bridge falls back to a plain reset() call,
        # and the explicit reset is still accepted for the class contract.
        self.assertEqual(self.reset(client, seed=5)["output"]["seed"], 5)

    def test_a_straight_step_pays_the_center_reward(self) -> None:
        client = self.serve()
        receipt = self.step(client, 3)                                  # steering value 0.0
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (1.0, False, False, 1))
        self.assertEqual(self.state(client)["info"], {})

    def test_reaching_the_destination_terminates_the_episode(self) -> None:
        client = self.serve()
        receipt = self.step(client, 3, ticks=100)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # the fake advances 5 m per transition on a 300 m track, so the 5 m destination radius is reached on
        # step 60 (gym_airsim/airsim_car_env.py:95); every earlier step stays on the center line and pays 1
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 60))
        self.assertEqual(output["reward"], 60.0)
        ended = self.step(client, 3)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")      # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_steering_off_the_track_ends_the_episode(self) -> None:
        client = self.serve()
        receipt = self.step(client, 6, ticks=50)                        # maximum steering
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertTrue(output["terminated"], output)
        self.assertLess(output["tick"], 50)                             # it stops at the -1 reward, not at 50
        self.assertLess(output["reward"], 5.0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)
        self.assertEqual(self.reset(client, seed=22)["output"]["seed"], 22)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 3)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 3), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
