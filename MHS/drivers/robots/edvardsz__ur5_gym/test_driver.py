"""Acceptance run of the UR5 Reach package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): Ignition Gazebo, gym-ignition and numpy are not installed where the gate
runs, and nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
START_X = 0.50143738
TARGET_X = 0.70143738


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ReachCases(unittest.TestCase):
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

    def test_the_first_step_starts_the_first_episode(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (1, -1.0))   # 0.2 m from the target
        self.assertEqual(self.state(client)["episode"], 1)

    def test_set_action_scales_by_0_1_and_clamps(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        output = self.step(client, [1.0, 0.0, 0.0])["output"]
        values = output["observation"]["values"]
        self.assertAlmostEqual(values[0], START_X + 0.1, places=7)         # reach.py:55
        self.assertEqual(values[1:3], [0.15, 1.36])
        self.assertEqual(values[3:], [TARGET_X, 0.15, 1.36])
        # three 0.1 m pushes along y and z clamp at the workspace box (reach.py:31-32 and :59-63)
        clamped = self.step(client, [0.0, 1.0, 1.0], ticks=3)["output"]["observation"]["values"]
        self.assertAlmostEqual(clamped[0], START_X + 0.1, places=7)
        self.assertAlmostEqual(clamped[1], 0.15 + 0.2, places=7)
        self.assertAlmostEqual(clamped[2], 1.36 + 0.2, places=7)

    def test_the_reward_is_plus_one_within_0_05(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        first = self.step(client, [1.0, 0.0, 0.0])["output"]
        self.assertEqual(first["reward"], -1.0)                             # 0.1 m away (reach.py:86)
        second = self.step(client, [1.0, 0.0, 0.0])["output"]
        self.assertEqual(second["reward"], 1.0)                             # 0.0 m away
        self.assertEqual(self.state(client)["info"], {"is_success": True})

    def test_a_seed_is_echoed_and_repeats_the_reset(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=7)["output"]["seed"], 7)
        first = self.step(client, [1.0, 0.0, 0.0])["output"]["observation"]
        self.assertEqual(self.reset(client, seed=7)["output"]["seed"], 7)
        repeated = self.step(client, [1.0, 0.0, 0.0])["output"]["observation"]
        self.assertEqual(repeated, first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"],
                         {"seed": 21, "accepted": True})
        self.assertEqual(self.reset(client)["output"]["seed"], 21)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)          # reused until a new seed arrives

    def test_the_episode_truncates_at_100_ticks(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        output = self.step(client, [0.0, 0.0, 0.0], ticks=100)["output"]
        self.assertEqual((output["truncated"], output["terminated"], output["tick"]), (True, False, 100))
        self.assertEqual(output["reward"], -100.0)
        ended = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_action_box_is_the_envelope(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        for values in ([1.1, 0.0, 0.0], [0.0, -1.1, 0.0], [0.0, 0.0, 2.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 0)
        missing = client.invoke("cap.world.step.v1", {"action": {"x": 0}}, **self.ids)
        self.assertEqual(missing["error"]["mhs_code"], INPUT_INVALID)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client, seed=5)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_state_reports_the_task_outputs(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        state = self.state(client)
        self.assertEqual(len(state["observation"]["values"]), 6)
        self.assertEqual(state["reward"], 0.0)
        self.assertEqual((state["terminated"], state["truncated"], state["tick"]), (False, False, 0))
        self.assertEqual((state["episode"], state["seed"]), (1, 3))
        self.assertEqual(state["info"], {"is_success": False})

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertTrue(fidelity["engine"].startswith("gym-ignition:ReachUR5-v0"))
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (400.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)


if __name__ == "__main__":
    unittest.main()
