"""Acceptance run of the gym_fastsim package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Everything runs on the fake backend (fake.py); gym and pyfastsim are
not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FastsimNavCases(unittest.TestCase):
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

    def step(self, client, left, right, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks,
                                                   "action": {"values": [left, right]}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_envelope(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1.0, -1.0)["status"], "completed")
        for action in ((4.1, 0.0), (-4.1, 0.0), (0.0, 4.1), (0.0, -4.1)):
            refused = self.step(client, *action)
            self.assertEqual(refused["status"], "rejected", action)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, action)
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing
        self.assertEqual(self.step(client, 4.0, -4.0)["status"], "completed")

    def test_a_step_reaches_the_fake_and_moves_the_placeholders(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)
        receipt = self.step(client, -4.0, -4.0)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        self.assertEqual(len(output["observation"]["values"]), 10)       # nav_env.py:182-184
        # The stand-in moves x by -4 * 0.1 = -0.4 from x=2 (STEP_S is a placeholder in fake.py).
        robot_pos = self.state(client)["info"]["robot_pos"]
        self.assertAlmostEqual(robot_pos[0], 1.6, places=9)
        self.assertAlmostEqual(robot_pos[1], 4.0, places=9)
        self.assertAlmostEqual(robot_pos[2], 0.0, places=9)
        self.assertLess(self.state(client)["info"]["dist_obj"], 3.8078865529319543)   # toward the goal at (0.5, 0.5)

    def test_reset_returns_ten_in_range_laser_readings(self) -> None:
        client = self.serve()
        output = self.reset(client)["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), 10)
        self.assertTrue(all(0.0 <= value <= 1.0 for value in values), values)
        self.assertEqual(output["seed"], 0)                              # the bridge's default seed
        self.assertEqual(self.state(client)["observation"]["values"], values)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(second["seed"], 21)
        self.assertEqual(second["observation"], first["observation"])   # the upstream reset ignores the seed

    def test_a_trajectory_repeats(self) -> None:
        def run():
            client = self.serve()
            self.assertEqual(self.reset(client, seed=5)["status"], "completed")
            return [self.step(client, 2.0, -1.0)["output"]["state_hash"],
                    self.step(client, 1.0, 1.0)["output"]["state_hash"],
                    self.step(client, -3.0, 3.0)["output"]["state_hash"]]

        first = run()
        self.assertEqual(run(), first)
        self.assertNotEqual(first[0], first[1])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("libfastsim:kitchen-v1", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_fake_mirrors_the_upstream_spaces_and_the_observation_mismatch(self) -> None:
        driver = load_driver(HERE, backend="fake")
        self.addCleanup(driver.close)
        fake = driver.native
        self.assertEqual(fake.action_space.shape, (2,))
        self.assertEqual((fake.action_space.low, fake.action_space.high), ([-4.0, -4.0], [4.0, 4.0]))
        # nav_env.py:118-119 declares n_lasers+2+n_lightsensors = 12 bounds; nav_env.py:182-184 returns 10 values.
        self.assertEqual(fake.observation_space.shape, (12,))
        fake.reset()
        self.assertEqual(len(fake.get_all_sensors()), 10)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1.0, 0.0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1.0, 0.0), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
