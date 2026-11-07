"""Acceptance run of the HoME package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py), a kinematic stand-in for
``HomeEnv``: the upstream package is Python 2 / Panda3D and is not importable where the gate runs, so nothing here
compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
START = [42.0, -39.0, 1.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HomeCases(unittest.TestCase):
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

    def test_the_documented_two_component_action_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1, 1])["status"], "completed")
        for values in ([-1, 0], [5, 0], [0, -1], [0, 5]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                   # the refused steps changed nothing

    def test_the_first_step_moves_and_turns_by_the_documented_amounts(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, [1, 1])
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]
        # moving action 1 applies +moving_speed on y (home_env_basic.py:116); the kinematic stand-in moves
        # impulse / agentMass * dt = 100 / 60 * 0.1 = 1/6; looking action 1 subtracts turning_speed from heading
        self.assertAlmostEqual(observation["position"]["values"][1], START[1] + 100.0 / 60.0 * 0.1, places=7)
        self.assertAlmostEqual(observation["orientation"]["values"][0], -0.1, places=7)
        self.assertEqual(observation["collision"]["index"], 0)
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["tick"]), (0.0, 1))

    def test_ticks_apply_the_action_once_per_tick(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, [2, 0], ticks=3)
        self.assertEqual(receipt["status"], "completed")
        position = receipt["output"]["observation"]["position"]["values"]
        self.assertAlmostEqual(position[0], START[0] + 3 * 100.0 / 60.0 * 0.1, places=7)
        self.assertEqual(receipt["output"]["tick"], 3)

    def test_a_reset_restores_the_fixed_pose(self) -> None:
        client = self.serve()
        self.step(client, [2, 2])
        self.assertNotEqual(self.state(client)["observation"]["position"]["values"], START)
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]
        self.assertEqual(observation["position"]["values"], START)
        self.assertEqual(observation["orientation"]["values"], [0.0, 0.0, 0.0])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_is_echoed_and_selects_the_only_house(self) -> None:
        client = self.serve()
        for seed in (0, 1, 42):
            seeded = client.invoke("cap.world.seed.v1", {"seed": seed}, **self.ids)
            self.assertEqual(seeded["output"]["seed"], seed)
            receipt = self.reset(client)
            self.assertEqual(receipt["status"], "completed")
            self.assertEqual(receipt["output"]["seed"], seed)
            self.assertEqual(receipt["output"]["observation"]["position"]["values"], START)
        # home_env_basic.py:68 ships one house and :85 asserts seed < len(list_of_houses); the fake maps every
        # non-negative seed to that house (a fidelity gap), so the generic cap.world.* contract stays usable

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("home-platform:Home-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0, 0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [1, 1]), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                   # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
