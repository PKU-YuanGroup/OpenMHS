"""Acceptance run of the kindergarden RBY1A package: the gate, plus cases specific to this model.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo is not installed
where the gate runs, so nothing here compares the stand-in with the engine or with a robot.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: derived from the clone's model: 24 motors, one free joint plus 28 one-coordinate joints
CTRL = 24
QPOS = 35
QVEL = 34


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RBY1ACases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl)}}, **self.ids)

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_is_the_clone(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (QPOS, QVEL, CTRL))
        self.assertEqual((state["time_ms"], state["tick"], state["seed"]), (0, 0, 0))
        self.assertEqual(state["timestep_ms"], 2.0)

    def test_the_control_range_is_the_model_default(self) -> None:
        client = self.serve()
        valid = self.step(client, [1.0] + [0.0] * (CTRL - 1))
        self.assertEqual(valid["status"], "completed", valid)
        state = self.state(client)
        self.assertEqual((state["time_ms"], state["tick"]), (2, 1))
        self.assertGreater(state["qpos"][0], 0.0)                        # the placeholder step moved the first coordinate
        self.assertEqual(state["ctrl"][0], 1.0)
        for value in (3000001.0, -3000001.0):
            refused = self.step(client, [value] + [0.0] * (CTRL - 1))
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0] + [0.0] * (CTRL - 1), ticks=3)["status"], "completed")
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 0)
        state = self.state(client)
        self.assertEqual((state["time_ms"], state["tick"]), (0, 0))
        self.assertTrue(all(value == 0.0 for value in state["qpos"]))
        self.assertTrue(all(value == 0.0 for value in state["qvel"]))
        self.assertTrue(all(value == 0.0 for value in state["ctrl"]))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * CTRL)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * CTRL), self.reset(client)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
