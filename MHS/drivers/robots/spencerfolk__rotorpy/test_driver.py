"""Acceptance run of the RotorPy package: the gate, plus cases for this driver's contract and fake.

The cases run on the fake backend only (``fake.py``); nothing here imports the clone or compares the fake with the
upstream environment.  Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
DETERMINISTIC = {"initial_states": "deterministic", "pos_bound": 0.0, "vel_bound": 0.0}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class QuadrotorCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        for values in ([2.0, 0.0, 0.0], [0.0, 0.0, -2.0], [0.0, 1.5, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                            # the refused steps changed nothing

    def test_a_velocity_command_moves_the_vehicle(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3, options=DETERMINISTIC)["status"], "completed")
        receipt = self.step(client, [1.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), 13)
        # the fake integrates 2 m/s for the 0.01 s step (max_vel 4/sqrt(4) at quadrotor_environments.py:163)
        self.assertAlmostEqual(values[0], 0.02, places=7)
        self.assertAlmostEqual(values[3], 2.0, places=7)
        # vec_hover_reward: -||x|| - 0.1*||v|| - 1e-5*||a|| + 2 (quadrotor_reward_functions.py:56-74)
        self.assertAlmostEqual(output["reward"], -0.02 - 0.1 * 2.0 - 1e-5 + 2.0, places=7)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, values)["output"]["state_hash"]
                    for values in ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0])]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_constant_velocity_command_leaves_the_world(self) -> None:
        client = self.serve()
        self.reset(client, seed=1, options=DETERMINISTIC)
        receipt = self.step(client, [0.5, 0.0, 0.0], ticks=450)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # the 1 m/s command starts at x = 0 and leaves the +-4 m default world on the 401st step
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 401))
        self.assertAlmostEqual(output["observation"]["values"][0], 4.01, places=7)
        ended = self.step(client, [1.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_time_limit_ends_the_episode_at_ten_seconds(self) -> None:
        client = self.serve()
        self.reset(client, seed=2, options=DETERMINISTIC)
        receipt = self.step(client, [0.0, 0.0, 0.0], ticks=1001)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # 1001 ticks * 0.01 s passes max_time 10 s (quadrotor_environments.py:80, :123, :371)
        self.assertEqual((output["terminated"], output["tick"]), (True, 1001))
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["error"]["mhs_code"], PRECONDITION)

    def test_the_reset_options_set_the_start_bounds(self) -> None:
        client = self.serve()
        values = self.reset(client, seed=2,
                            options={"initial_states": "random", "pos_bound": 0.25,
                                     "vel_bound": 0.5})["output"]["observation"]["values"]
        self.assertTrue(all(-0.25 <= value <= 0.25 for value in values[0:3]), values)
        self.assertTrue(all(-0.5 <= value <= 0.5 for value in values[3:6]), values)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("rotorpy:Quadrotor-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
