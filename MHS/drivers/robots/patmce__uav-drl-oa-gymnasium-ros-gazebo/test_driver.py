"""Acceptance run of the DroneGymGazeboEnv-v0 package: the gate, plus cases for this environment.

The cases run on the fake backend (fake.py): ROS Noetic, Gazebo, PX4 SITL, MAVROS, the
external mavros_px4_vehicle package and the depth camera are not installed where the gate
runs, so nothing here compares the fake with the upstream Gazebo environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DroneGymGazeboCases(unittest.TestCase):
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

    def step(self, client, index=0, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_contract_and_fidelity_are_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:DroneGymGazeboEnv-v0 kinematic setpoint stand-in", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_action_space_is_the_upstream_discrete_three(self) -> None:
        client = self.serve()
        step = client.inspect(self.ids["device_id"])["capabilities"]
        binding = next(item for item in step if item["capability_id"] == "cap.world.step.v1")
        index = binding["input_schema"]["properties"]["action"]["properties"]["index"]
        self.assertEqual((index["minimum"], index["maximum"]), (0, 2))
        self.assertEqual(self.step(client, index=0, ticks=1)["status"], "completed")

    def test_forward_motion_reaches_the_desired_point(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, index=0, ticks=15)          # 14 * 0.5 m = 7.0 m enters the 0.5 m goal radius
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (14, True, False))
        self.assertAlmostEqual(output["reward"], 100.0 - 13 * 0.5, places=6)
        ended = self.step(client, index=0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_left_motion_leaves_the_workspace_and_terminates(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        receipt = self.step(client, index=1, ticks=4)          # 4 * 0.5 m = 2.0 m > 1.7 m
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["terminated"])
        self.assertLess(receipt["output"]["reward"], 0)
        self.assertEqual(receipt["output"]["tick"], 4)

    def test_the_observation_is_the_small_placeholder_with_position_deltas(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        values = receipt["output"]["observation"]["values"]
        self.assertEqual((len(values), len(values[0]), len(values[0][0])), (3, 8, 8))
        self.assertEqual((values[2][0][0], values[2][0][1]), (7.0, 0.0))
        moved = self.step(client, index=0, ticks=1)["output"]["observation"]["values"]
        self.assertEqual(moved[2][0][0], 6.5)

    def test_a_later_reset_starts_the_drone_in_the_chosen_lane(self) -> None:
        # Upstream semantics (step1:120, :144-149): a later reset flies the drone to the chosen start y, so the
        # position deltas restart at (7.0, 0.0) and a forward step stays inside the lane's workspace.  The seed
        # itself is fake-only: the upstream draws the lane with np.random.choice, which random.seed does not reach.
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")   # the first reset keeps y=0
        for seed in (7, 8, 9, 11):
            values = self.reset(client, seed=seed)["output"]["observation"]["values"]
            self.assertEqual((values[2][0][0], values[2][0][1]), (7.0, 0.0), seed)
            stepped = self.step(client, index=0)
            self.assertEqual(stepped["status"], "completed", stepped)
            self.assertFalse(stepped["output"]["terminated"], (seed, stepped))
            self.assertAlmostEqual(stepped["output"]["reward"], -0.5, places=6)

    def test_the_step_refuses_an_action_outside_the_space_without_mutation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        for index in (-1, 3):
            refused = self.step(client, index=index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
