"""Acceptance run of the Robot SF package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Robot SF itself is not
installed where the gate runs, so nothing here compares the fake with the upstream environment.
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


class RobotSFCases(unittest.TestCase):
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
    def drive_state(receipt):
        return receipt["output"]["observation"]["drive_state"]["values"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        for values in ([2.0, 0.0], [0.0, -2.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)       # the refused steps changed nothing

    def test_the_first_step_follows_the_acceleration_model(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, [1.0, 0.5])
        self.assertEqual(receipt["status"], "completed")
        # robot_sf/robot/differential_drive.py:181-193: d_t is 0.1 s, so one step adds 0.1 m/s and 0.05 rad/s
        drive_state = self.drive_state(receipt)
        self.assertAlmostEqual(drive_state[0], 0.1, places=7)
        self.assertAlmostEqual(drive_state[1], 0.05, places=7)
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertEqual(receipt["output"]["terminated"], False)

    def test_the_speeds_are_clipped_to_their_bounds(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        # max_linear_speed 2.0 and max_angular_speed 1.0 (robot_sf/robot/differential_drive.py:30-32)
        drive_state = self.drive_state(self.step(client, [1.0, 1.0], ticks=30))
        self.assertEqual(drive_state[0], 2.0)
        self.assertEqual(drive_state[1], 1.0)

    def test_a_seed_repeats_the_start(self) -> None:
        def target_vector(seed):
            client = self.serve()                                  # a fresh world, so no episode counter in the way
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return self.drive_state(self.reset(client, seed=seed))

        first = target_vector(7)
        self.assertEqual(target_vector(7), first)
        self.assertNotEqual(target_vector(8), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_simulated_time_limit_terminates_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        # sim_time_in_secs 200.0 and d_t 0.1 s (robot_sf/sim/sim_config.py:257-260) give 2000 steps
        receipt = self.step(client, [0.0, 0.0], ticks=2000)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 2000))
        ended = self.step(client, [0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode

    def test_the_fused_observation_members_are_published(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        observation = self.state(client)["observation"]
        self.assertEqual(sorted(observation), ["drive_state", "rays"])
        self.assertEqual(len(observation["drive_state"]["values"]), 4)
        self.assertEqual(len(observation["rays"]["values"]), 8)          # the fake's reduced ray count

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("robot_sf:RobotEnv-kinematic", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
