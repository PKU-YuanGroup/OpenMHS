"""Acceptance run of the simpler-env package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream
environment needs SAPIEN, gymnasium and the asset directory, so nothing here compares the fake with the upstream
simulator.  The observation array is the 47-number layout of the default state mode; the test data values below are
placeholders of this package's fake.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
ALIGNED = {"obj_init_options": {"init_xy": [0.35, 0.10]},
           "robot_init_options": {"init_xy": [0.35, 0.10]}}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GraspCases(unittest.TestCase):
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

    def step(self, client, values=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values or ZERO}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_is_a_seven_element_box(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ticks=1)["status"], "completed")
        for index, value in ((0, -2.0), (6, 2.0)):
            values = list(ZERO)
            values[index] = value
            refused = self.step(client, values=values)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)             # the refused steps changed nothing

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            return [self.step(client)["output"]["state_hash"] for _ in range(3)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_is_truncated_at_80_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        output = None
        for expected_tick in range(1, 81):
            receipt = self.step(client)
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        self.assertEqual(self.step(client)["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_grasp_and_lift_terminates_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3, options=ALIGNED)["status"], "completed")
        receipt = self.step(client, values=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 1))
        self.assertEqual(output["reward"], 1.0)
        self.assertEqual(self.step(client)["error"]["mhs_code"], PRECONDITION)

    def test_reset_options_place_the_object_and_the_base(self) -> None:
        client = self.serve()
        options = {"obj_init_options": {"init_xy": [0.12, 0.24]},
                   "robot_init_options": {"init_xy": [0.31, 0.07]}}
        self.assertEqual(self.reset(client, seed=2, options=options)["status"], "completed")
        values = self.state(client)["observation"]["values"]
        self.assertEqual(len(values), 47)
        self.assertEqual((values[23], values[24]), (0.31, 0.07))     # base pose x, y
        self.assertEqual((values[30], values[31]), (0.31, 0.07))     # tcp pose x, y
        self.assertEqual((values[37], values[38]), (0.12, 0.24))     # object pose x, y
        for actual, expected in zip(values[44:47],
                                    [obj - tcp for obj, tcp in zip(values[37:40], values[30:33])]):
            self.assertAlmostEqual(actual, expected, places=7)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("simplerenv:GraspSingleCokeCanInScene-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
