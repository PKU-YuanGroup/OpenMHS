"""Acceptance run of the LIBERO package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py).  The upstream simulator (robosuite 1.4.0 and MuJoCo) is not installed
where the gate runs and package code never imports the clone, so nothing here compares the fake with the upstream
environment or claims a hardware run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ZERO_ACTION = {"values": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LiberoOffScreenCases(unittest.TestCase):
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

    def test_the_observation_is_the_low_dimensional_clone_vector(self) -> None:
        client = self.serve()
        observation = self.state(client)["observation"]
        # bddl_base_domain.py:828 concatenates these three robosuite observation members for the robot state vector
        self.assertEqual(set(observation), {"robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos"})
        self.assertEqual((len(observation["robot0_eef_pos"]), len(observation["robot0_eef_quat"]),
                          len(observation["robot0_gripper_qpos"])), (3, 4, 2))
        self.assertEqual((self.state(client)["tick"], self.state(client)["episode"]), (0, 0))

    def test_reset_seeds_the_world_and_zeros_the_tick(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["output"]["seed"], 11)
        self.assertEqual(self.state(client)["seed"], 11)
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(self.state(client)["episode"], 1)

    def test_step_advances_the_tick_and_returns_a_digest(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, ZERO_ACTION["values"], ticks=4)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 4)
        self.assertEqual((output["reward"], output["terminated"], output["truncated"]), (0.0, False, False))
        self.assertTrue(output["state_hash"].startswith("sha256:"), output["state_hash"])
        self.assertEqual(self.state(client)["tick"], 4)

    def test_the_action_moves_the_end_effector(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        before = self.state(client)["observation"]["robot0_eef_pos"]
        moved = self.step(client, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(moved["status"], "completed")
        after = self.state(client)["observation"]["robot0_eef_pos"]
        self.assertAlmostEqual(after[0], before[0] + 0.01, places=9)        # fake.py placeholder gain
        self.assertEqual(after[1:], before[1:])

    def test_a_seed_repeats_the_placements(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=21)["output"]["observation"]
        second = self.reset(client, seed=21)["output"]["observation"]
        self.assertEqual(first, second)

    def test_the_catalogue_schema_bounds_ticks_and_seed(self) -> None:
        client = self.serve()
        for refused in (self.step(client, ZERO_ACTION["values"], ticks=0),
                        self.step(client, ZERO_ACTION["values"], ticks=10001),
                        self.reset(client, seed=-1)):
            self.assertEqual(refused["status"], "rejected", refused)
            # the catalogue class's input schema carries the bound, so the runtime refuses it as input-invalid
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, refused)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["resources"][0]["kind"], "world.sim")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:libero", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION["values"])["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)
        client.estop("test the software latch", **self.ids)
        for refused in (self.step(client, ZERO_ACTION["values"]), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
        self.assertEqual(self.state(client)["tick"], 1)                     # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
