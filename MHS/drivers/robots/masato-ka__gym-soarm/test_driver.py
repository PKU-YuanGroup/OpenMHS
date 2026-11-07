"""Acceptance run of the SoArm-v0 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream clone needs
MuJoCo, dm-control and a missing reward_wrapper module, so nothing here compares the fake with the upstream
environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
START = [0.0, 0.0, -1.57, 0.0, 0.0, 0.0]
GRIPPER_OPEN = 1.74533
GRIPPER_CLOSE = -0.17453


def normalized_gripper(value):
    return (value - GRIPPER_CLOSE) / (GRIPPER_OPEN - GRIPPER_CLOSE)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SoArmCases(unittest.TestCase):
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

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, START)["status"], "completed")
        for values in ([low - 0.001 for low in [-1.91986, -1.74533, -1.69, -1.65806, -2.74385, -0.17453]],
                       [1.91986 + 0.001, 0.0, 0.0, 0.0, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                    # the refused steps changed nothing

    def test_the_first_step_moves_toward_the_target(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, [0.0, 0.0, -1.32, 0.1, 0.0, -0.1])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["agent_pos"]["values"]
        self.assertAlmostEqual(values[2], -1.32, places=7)                 # -1.57 + 0.25 (the fake's step bound)
        self.assertAlmostEqual(values[3], 0.1, places=7)
        self.assertAlmostEqual(values[5], normalized_gripper(-0.1), places=7)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        self.assertGreaterEqual(output["reward"], 0.0)
        self.assertLessEqual(output["reward"], 1.0)

    def test_a_seed_repeats_the_cube_placement(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=5)["output"]
        placed = self.state(client)["info"]["blue_cube_position"]
        self.assertEqual(first["seed"], 5)
        self.assertEqual(self.reset(client, seed=5)["output"]["seed"], 5)
        self.assertEqual(self.state(client)["info"]["blue_cube_position"], placed)
        self.reset(client, seed=6)
        self.assertNotEqual(self.state(client)["info"]["blue_cube_position"], placed)

    def test_the_reset_options_place_the_cube(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, options={"cube_grid_position": 0})["status"], "completed")
        self.assertEqual(self.state(client)["info"]["blue_cube_position"], [-0.1, 0.325, 0.05])
        at_goal = self.reset(client, options={"cube_grid_position": -1, "cube_x": -0.2, "cube_y": 0.4})
        self.assertEqual(at_goal["status"], "completed")
        receipt = self.step(client, START)
        self.assertEqual(receipt["output"]["terminated"], True)             # the cube is on the goal plate
        for options in ({"cube_grid_position": 9}, {"cube_grid_position": -1, "cube_x": 0.0}):
            refused = self.reset(client, options=options)
            self.assertEqual(refused["status"], "failed", options)

    def test_the_episode_is_truncated_at_200_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1, options={"cube_grid_position": 0})["status"], "completed")
        receipt = self.step(client, START, ticks=200)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (200, False, True))
        ended = self.step(client, START)
        self.assertEqual(ended["status"], "failed")
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)

    def test_the_observations_use_the_registered_cameras(self) -> None:
        client = self.serve()
        observation = self.reset(client)["output"]["observation"]
        self.assertEqual(sorted(observation["pixels"]), ["front_camera", "wrist_camera"])
        for camera in ("front_camera", "wrist_camera"):
            values = observation["pixels"][camera]["values"]
            self.assertEqual((len(values), len(values[0]), len(values[0][0])), (2, 2, 3))
        self.assertAlmostEqual(observation["agent_pos"]["values"][5], normalized_gripper(0.0), places=7)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:SoArm-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, START)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, START), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
