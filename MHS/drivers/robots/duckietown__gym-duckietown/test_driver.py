"""Acceptance run of the Gym-Duckietown package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream OpenGL
simulator is not installed where the gate runs, so nothing here compares the fake with an upstream run.
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


class MultiMapCases(unittest.TestCase):
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

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5, 0.5])["status"], "completed")
        for values in ([1.5, 0.0], [0.0, -1.5], [2.0, 2.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_the_action_is_a_velocity_and_a_steering_angle(self) -> None:
        # DuckietownEnv.step: rotation rates (vel -/+ 0.5 * angle * wheel distance) / radius, duty cycles rate / k,
        # each limited to 1 (envs/duckietown_env.py:36-63); the Simulator reports the duty cycles it applied
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")

        def wheels(values):
            self.assertEqual(self.step(client, values)["status"], "completed", values)
            return self.state(client)["info"]["Simulator"]["action"]

        ahead = 0.5 / (0.0318 * 27.0)                                    # a velocity alone drives both wheels alike
        for wheel in wheels([0.5, 0.0]):
            self.assertAlmostEqual(wheel, ahead)
        turn = 0.5 * 1.0 * 0.102 / (0.0318 * 27.0)                       # the fake's nominal wheel distance 0.102
        left, right = wheels([0.0, 1.0])                                 # a steering angle alone turns them apart
        self.assertAlmostEqual(left, -turn)
        self.assertAlmostEqual(right, turn)
        self.assertEqual(wheels([1.0, 1.0]), [1.0, 1.0])                 # at full velocity both reach the limit
        rates = self.state(client)["info"]["DuckietownEnv"]
        self.assertAlmostEqual(rates["omega_r"], (1.0 + 0.5 * 0.102) / 0.0318)
        self.assertAlmostEqual(rates["omega_l"], (1.0 - 0.5 * 0.102) / 0.0318)

    def test_reset_cycles_through_the_two_maps(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=4)
        second = self.reset(client, seed=4)
        self.assertEqual((first["status"], second["status"]), ("completed", "completed"))
        self.assertEqual(first["output"]["seed"], 4)
        # the fake puts the map index in the blue sample, so two resets of one world must differ
        self.assertNotEqual(first["output"]["observation"]["values"],
                            second["output"]["observation"]["values"])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_step_advances_the_tick_and_changes_the_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        before = self.state(client)
        receipt = self.step(client, [0.5, 0.5])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), 3)                                 # the fake's reduced RGB sample
        self.assertTrue(all(0 <= value <= 255 for value in values), values)
        self.assertEqual(output["tick"], 1)
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertEqual(self.state(client)["info"]["Simulator"]["msg"], "")
        self.assertRegex(output["state_hash"], r"^sha256:[0-9a-f]{64}$")
        after = self.state(client)
        self.assertEqual(after["tick"], 1)
        self.assertNotEqual(before["observation"], after["observation"])

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, values)["output"]["state_hash"]
                    for values in ([1.0, 0.0], [1.0, 0.5], [0.0, -0.5], [0.5, 0.5])]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        pending = self.reset(client)["output"]
        self.assertEqual(pending["seed"], 21)
        fresh = self.serve()
        supplied = self.reset(fresh, seed=21)["output"]
        self.assertEqual(pending["observation"], supplied["observation"])

    def test_an_invalid_pose_ends_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, [0.5, 1.0], ticks=150)               # half the velocity, full steering
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertGreater(output["tick"], 1)
        self.assertLess(output["reward"], 0.0)                  # the -1000 terminal step dominates the sum
        self.assertEqual(self.state(client)["info"]["Simulator"]["msg"],
                         "Stopping the simulator because we are at an invalid pose.")
        ended = self.step(client, [0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_max_steps_reports_the_upstream_sentence(self) -> None:
        # Pinned simulator.py:1694-1704 returns the sentence, not its internal done_code.
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, [0.0, 0.0], ticks=1500)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["terminated"])
        self.assertEqual(self.state(client)["info"]["Simulator"]["msg"],
                         "Stopping the simulator because we reached max_steps = 1500")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gym-duckietown:MultiMap-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 30.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5, 0.5])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.5, 0.5]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
