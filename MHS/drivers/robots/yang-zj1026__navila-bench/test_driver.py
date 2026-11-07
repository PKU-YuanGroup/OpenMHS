"""Acceptance run of the NaVILA-Bench go2_matterport_vision package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab and
the Matterport assets are not installed where the gate runs, so nothing here compares the fake with the upstream
environment or claims a simulator run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ACTION = 12
IMAGE_VALUES = 8 * 8 * 3


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Go2MatterportVisionCases(unittest.TestCase):
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
                             {"ticks": ticks, "action": {"values": list(values)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_a_step_returns_the_contract_observation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, [0.0] * ACTION)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (1, 0.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        observation = output["observation"]
        self.assertEqual(set(observation), {"policy", "proprio", "camera_obs"})
        self.assertEqual(len(observation["policy"]["values"]), ACTION)
        self.assertEqual(len(observation["proprio"]["values"]), 6)
        self.assertEqual(len(observation["camera_obs"]["values"]), IMAGE_VALUES)
        self.assertTrue(all(0 <= value <= 255 for value in observation["camera_obs"]["values"]))

    def test_the_applied_action_is_observable(self) -> None:
        client = self.serve()
        values = [0.5, -0.25, 0.0, 1.0, -1.0, 2.0, -2.0, 0.125, -0.125, 3.0, -3.0, 0.75]
        receipt = self.step(client, values)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"]["policy"]["values"], values)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_unbounded_action_accepts_large_values(self) -> None:
        client = self.serve()
        values = [1.0e6] * ACTION
        receipt = self.step(client, values)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"]["policy"]["values"], values)

    def test_an_action_of_the_wrong_length_is_refused(self) -> None:
        client = self.serve()
        refused = self.step(client, [0.0] * (ACTION - 1))
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_camera_placeholder(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=9)["output"]["observation"]["camera_obs"]["values"]
        again = self.reset(client, seed=9)["output"]["observation"]["camera_obs"]["values"]
        other = self.reset(client, seed=10)["output"]["observation"]["camera_obs"]["values"]
        self.assertEqual(first, again)
        self.assertNotEqual(first, other)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        again = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], again["observation"])

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=1, options={"note": "the fake ignores options"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.state(client)["episode"], 1)

    def test_the_first_step_starts_an_episode(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0] * ACTION)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertIn("go2_matterport_vision", fidelity["engine"])
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_world(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)


if __name__ == "__main__":
    unittest.main()
