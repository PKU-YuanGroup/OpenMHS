"""Acceptance run of the manipulator-learning package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): pybullet, numpy and gym
are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
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


class PandaInsertTrayCases(unittest.TestCase):
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
                             {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0, -1.0, 1.0, -1.0])["status"], "completed")
        for values in ([1.0001, 0.0, 0.0, 0.0], [0.0, -1.0001, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)  # the refused steps changed nothing

    def test_a_step_applies_the_upstream_action_scale_and_gripper(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        before = self.state(client)["observation"]["values"]
        receipt = self.step(client, [0.5, -0.25, 1.0, 1.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        values = output["observation"]["values"]
        self.assertEqual(len(values), 59)                       # panda_play.py:419
        # action_multiplier 0.002 * n_substeps 5 = 1 cm per full-scale action (panda_play.py:429-430)
        self.assertAlmostEqual(values[0] - before[0], 0.005, places=9)
        self.assertAlmostEqual(values[1] - before[1], -0.0025, places=9)
        self.assertAlmostEqual(values[2] - before[2], 0.01, places=9)
        # the fourth value is the gripper: non-negative closes, negative opens (manipulator_env_generic.py:190-194)
        self.assertEqual(values[6:8], [1.0, 1.0])
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, -1.0])["output"]["observation"]["values"][6:8],
                         [0.0, 0.0])

    def test_a_seed_repeats_the_start_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        self.assertEqual(first["seed"], 7)
        self.step(client, [0.1, 0.05, -0.1, 0.0])
        again = self.reset(client, seed=7)["output"]
        self.assertEqual(first["observation"], again["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(seeded["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_ends_at_the_upstream_time_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, [0.0, 0.0, 0.0, 0.0], ticks=360)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # max_real_time 18 s / (0.01 s * 5 substeps) = 360 environment steps (manipulator_env_generic.py:88-89)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 360))
        ended = self.step(client, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R1")
        self.assertEqual(device["safety"]["estop"]["kind"], "software")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:manipulator_learning/PandaPlayInsertTrayXYZState", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.1, 0.1, 0.1, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.1, 0.1, 0.1, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
