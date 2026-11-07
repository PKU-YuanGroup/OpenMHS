"""Acceptance run of the furniture package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): the clone needs Python 3.7, MuJoCo 2.0 and Unity 2018.4.23f1
(docs/installation.md:3-7), which are not installed where the gate runs, so nothing here compares the fake with the
upstream environment.  The gate harness call is kept unchanged.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ZERO_ACTION = {"default": [0.0] * 8}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FurnitureCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"default": list(values)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_reset_and_step_reach_the_fake(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, [0.0] * 8)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        observation = output["observation"]
        self.assertEqual(sorted(observation), ["object_ob", "robot_ob"])
        # the registered environment's real lengths: (3 + 4) * 3 and 3 + 4 + 3 + 3 + 2
        self.assertEqual(len(observation["object_ob"]["values"]), 21)
        self.assertEqual(len(observation["robot_ob"]["values"]), 15)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 8)["status"], "completed")
        before = self.state(client)["tick"]
        for bad in ([1.5] + [0.0] * 7, [-1.5] + [0.0] * 7):
            refused = self.step(client, bad)
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE), bad)
        self.assertEqual(self.state(client)["tick"], before)      # refused before the fake was called

    def test_the_action_length_is_the_space(self) -> None:
        client = self.serve()
        for length in (7, 9):
            refused = self.step(client, [0.0] * length)
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", INPUT_INVALID), length)

    def test_a_step_moves_the_placeholder_robot_state(self) -> None:
        client = self.serve()
        self.reset(client)
        first = self.step(client, [0.5, -0.25, 0.0, 0.0, 0.0, 0.0, 1.0, -1.0])["output"]
        second = self.step(client, [0.5, -0.25, 0.0, 0.0, 0.0, 0.0, 1.0, -1.0])["output"]
        first_robot = first["observation"]["robot_ob"]["values"]
        second_robot = second["observation"]["robot_ob"]["values"]
        self.assertNotEqual(first_robot, second_robot)
        # the fake gain and the eef start are placeholders, not the clone's controller
        self.assertAlmostEqual(second_robot[2] - first_robot[2], 0.005, places=9)
        self.assertEqual(first_robot[9:12], [0.005, -0.0025, 0.0])
        self.assertEqual(second["observation"]["object_ob"]["values"],
                         first["observation"]["object_ob"]["values"])

    def test_the_2000_step_horizon_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, [0.0] * 8, ticks=2000)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 2000))
        ended = self.step(client, [0.0] * 8)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_is_recorded_but_does_not_reach_the_wrapper(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        second = self.reset(client, seed=99)["output"]
        self.assertEqual((first["seed"], second["seed"]), (7, 99))
        # FurnitureGym.reset takes no seed (furniture/env/furniture_gym.py:52-57): the fake start is the same
        self.assertEqual(first["observation"], second["observation"])
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_the_reset_options_are_not_served(self) -> None:
        client = self.serve()
        # FurnitureGym.reset takes only furniture_id and background, so the bridge's `options` input is refused
        refused = self.reset(client, options={"low": 0.0})
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", INPUT_INVALID))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gym:IKEASawyer-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 8)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 8), self.reset(client)):
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(self.state(client)["tick"], 1)           # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
