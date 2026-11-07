"""Acceptance run of the BlueSky-Gym DescentEnv package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
(BlueSky, gymnasium, numpy, pygame) is not installed where the gate runs, so nothing here compares the fake with the
upstream environment.
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


class DescentCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [0.5])["status"], "completed")
        for values in ([-1.5], [1.5]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_the_reset_draw_is_inside_the_upstream_range(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=7)["output"]["observation"]
        altitude = observation["altitude"]["values"][0] * 3000 + 1500
        target = observation["target_altitude"]["values"][0] * 3000 + 1500
        # np.random.randint(ALT_MIN, ALT_MAX) with ALT_MIN 2000 and ALT_MAX 4000 (descent_env.py:23-24, :169)
        self.assertGreaterEqual(altitude, 2000)
        self.assertLess(altitude, 4000)
        # np.random.randint(-TARGET_ALT_DIF, TARGET_ALT_DIF) with TARGET_ALT_DIF 500 (descent_env.py:25, :170)
        self.assertGreaterEqual(target - altitude, -500)
        self.assertLess(target - altitude, 500)

    def test_one_step_holds_the_action_for_thirty_simulation_steps(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=3)["output"]["observation"]
        receipt = self.step(client, [-1.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # ACTION_2_MS 12.5 m/s (descent_env.py:17) for ACTION_FREQUENCY 30 steps (descent_env.py:29): 375 m down,
        # normalised by ALT_STD 3000 (descent_env.py:104)
        self.assertAlmostEqual(output["observation"]["altitude"]["values"][0]
                               - start["altitude"]["values"][0], -375 / 3000, places=12)
        self.assertAlmostEqual(output["observation"]["vz"]["values"][0], -12.5 / 5, places=12)
        # abs(target - altitude) * ALT_DIF_REWARD_SCALE, -5/3000 (descent_env.py:19, :131)
        altitude = output["observation"]["altitude"]["values"][0] * 3000 + 1500
        target = output["observation"]["target_altitude"]["values"][0] * 3000 + 1500
        self.assertAlmostEqual(output["reward"], abs(target - altitude) * (-5 / 3000), places=12)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, False, 1))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                         # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, [value])["output"]["state_hash"] for value in (0.0, -0.5, 0.5, 0.0)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_descent_to_the_ground_terminates_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, [-1.0], ticks=20)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # the reset altitude is below 4000 m, so 20 ticks of -375 m reach the ground and CRASH_PENALTY ends it
        self.assertTrue(output["terminated"])
        self.assertLessEqual(output["observation"]["altitude"]["values"][0], (0 - 1500) / 3000)
        ended = self.step(client, [-1.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_level_flight_is_truncated_at_three_hundred_ticks(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=4)["output"]["observation"]
        receipt = self.step(client, [0.0], ticks=300)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # DescentEnv-v0 is registered with max_episode_steps=300 (bluesky_gym/__init__.py:9-10)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 300))
        self.assertEqual(output["observation"]["altitude"], start["altitude"])   # vz 0 keeps the altitude
        self.assertEqual(self.step(client, [0.0])["error"]["mhs_code"], PRECONDITION)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("bluesky:DescentEnv-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (30000.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
