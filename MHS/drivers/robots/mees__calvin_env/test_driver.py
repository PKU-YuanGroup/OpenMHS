"""Acceptance run of the CALVIN package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py).  pybullet, EGL, hydra and a CALVIN dataset are not installed where the
gate runs, so nothing here compares the fake with the upstream simulator.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
FAULTED = "MHS.DEVICE.FAULTED"
RELATIVE_STOP = {"type": "cartesian_rel", "action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CalvinCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": dict(action or RELATIVE_STOP)}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_a_relative_action_moves_the_tcp(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=3)["output"]["observation"]["robot_obs"]["values"]
        action = {"type": "cartesian_rel", "action": [0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]}
        receipt = self.step(client, action)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        after = output["observation"]["robot_obs"]["values"]
        # relative_to_absolute scales the position by max_rel_pos 0.02 (robot.py:33-34 and :232-233)
        self.assertAlmostEqual(after[0] - before[0], 0.5 * 0.02, places=9)
        self.assertEqual((after[1], after[2]), (before[1], before[2]))
        self.assertEqual(output["tick"], 1)

    def test_a_joint_action_moves_a_joint_and_the_gripper(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=4)["output"]["observation"]["robot_obs"]["values"]
        action = {"type": "joint_rel", "action": [0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]}
        after = self.step(client, action)["output"]["observation"]["robot_obs"]["values"]
        self.assertAlmostEqual(after[7] - before[7], 0.1, places=9)
        self.assertEqual(after[14], -1)                      # the gripper command (robot.py:293-295)
        self.assertEqual(after[6], 0.0)                      # closed: the configured limit 0 (panda.yaml:12)

    def test_the_gripper_command_is_validated(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        bad = {"type": "cartesian_rel", "action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}
        receipt = self.step(client, bad)
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", FAULTED))

    def test_out_of_schema_ticks_are_refused(self) -> None:
        client = self.serve()
        self.reset(client, seed=6)
        for ticks in (0, 10001):
            refused = self.step(client, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            # ticks is a schema bound of the bridge, not a declared driver Limit: the refusal is INPUT_INVALID
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)      # the refused steps changed nothing

    def test_the_first_step_starts_an_episode(self) -> None:
        client = self.serve()                                # no explicit reset
        output = self.step(client)["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))

    def test_a_seed_repeats_the_scene(self) -> None:
        def scene(seed):
            client = self.serve()
            observation = self.reset(client, seed=seed)["output"]["observation"]
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return observation["scene_obs"]["values"]

        first = scene(11)
        self.assertEqual(scene(11), first)
        self.assertNotEqual(scene(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_camera_arrays_are_reduced_placeholders(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=2)["output"]["observation"]
        rgb = observation["rgb_obs"]
        depth = observation["depth_obs"]
        self.assertEqual(sorted(rgb), ["rgb_gripper", "rgb_static"])
        self.assertEqual(len(rgb["rgb_static"]["values"]), 4)                 # placeholder height
        self.assertEqual(len(rgb["rgb_static"]["values"][0]), 4)              # placeholder width
        self.assertEqual(len(rgb["rgb_static"]["values"][0][0]), 3)           # RGB channels
        self.assertEqual(len(depth["depth_static"]["values"]), 4)             # placeholder height
        self.assertEqual(len(depth["depth_static"]["values"][0]), 4)          # placeholder width

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("pybullet:PlayTableSimEnv", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 30.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)      # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
