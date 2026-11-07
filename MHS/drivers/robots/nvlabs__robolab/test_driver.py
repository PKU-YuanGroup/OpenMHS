"""Acceptance run of the RoboLab package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab and a GPU are not installed where the
gate runs, so nothing here compares the fake with an upstream RoboLab episode.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ZERO_ACTION = {"values": [0.0] * 8}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RobolabCases(unittest.TestCase):
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

    def step(self, client, action=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action or dict(ZERO_ACTION)},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_documented_action_layout_is_served(self) -> None:
        client = self.serve()
        manifest = client.inspect(self.ids["device_id"])
        step = next(item for item in manifest["capabilities"] if item["capability_id"] == "cap.world.step.v1")
        values = step["input_schema"]["properties"]["action"]["properties"]["values"]
        # robolab/robots/README.md:28: 7 arm joint targets plus a binary gripper
        self.assertEqual((values["minItems"], values["maxItems"]), (8, 8))

    def test_a_seed_repeats_the_reset_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)
        self.assertEqual(first["output"]["seed"], 7)
        second = self.reset(client, seed=7)
        self.assertEqual(first["output"]["observation"], second["output"]["observation"])
        other = self.reset(client, seed=8)
        self.assertNotEqual(first["output"]["observation"], other["output"]["observation"])

    def test_a_step_changes_the_observation_and_advances_the_tick(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=1)["output"]["observation"]
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual(output["reward"], 0.0)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertNotEqual(output["observation"], before)

    def test_ticks_advance_one_transition_at_a_time(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        receipt = self.step(client, ticks=5)
        self.assertEqual(receipt["output"]["tick"], 5)
        self.assertEqual(self.state(client)["tick"], 5)

    def test_the_gripper_is_binary(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        closed = dict(ZERO_ACTION)
        closed["values"] = list(closed["values"])
        closed["values"][7] = 1.0
        self.assertEqual(self.step(client, action=closed)["output"]["observation"]["proprio_obs"]["gripper_pos"],
                         {"values": [0.0]})
        opened = dict(ZERO_ACTION)
        opened["values"] = list(opened["values"])
        opened["values"][7] = 0.0
        self.assertEqual(self.step(client, action=opened)["output"]["observation"]["proprio_obs"]["gripper_pos"],
                         {"values": [1.0]})

    def test_an_action_of_the_wrong_length_is_refused(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        refused = self.step(client, action={"values": [0.0] * 7})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_observation_groups_match_the_registration(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]
        # the built-in DROID registration has image_obs, proprio_obs and viewport_cam
        self.assertEqual(sorted(observation), ["image_obs", "proprio_obs", "viewport_cam"])
        wrist = observation["image_obs"]["wrist_cam"]["values"]
        self.assertEqual((len(wrist), len(wrist[0]), len(wrist[0][0])), (4, 6, 3))
        self.assertEqual(sorted(observation["proprio_obs"]),
                         ["arm_joint_pos", "ee_pos", "ee_quat", "eef_pos", "eef_quat", "gripper_pos"])
        self.assertEqual(len(observation["proprio_obs"]["arm_joint_pos"]["values"]), 7)
        view = observation["viewport_cam"]["egocentric_mirrored_camera"]["values"]
        self.assertEqual((len(view), len(view[0]), len(view[0][0])), (2, 3, 3))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:BananaInBowlTask", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 66.66666666666667, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"], fidelity["reset"]),
                         (0, "lockstep", "full"))
        self.assertFalse(fidelity["snapshot_restore"])
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)


if __name__ == "__main__":
    unittest.main()
