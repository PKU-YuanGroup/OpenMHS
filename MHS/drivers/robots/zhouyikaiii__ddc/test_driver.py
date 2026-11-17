"""Acceptance run of the Unitree G1 29-DoF package: the gate, plus cases for this MuJoCo model.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo is not
installed where the gate runs, so nothing here compares the stand-in with the real engine.  Every number below is
test data, not a bound or a fact of the model; the dimensions and control ranges are read from the model XML by
fake.py.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: The card model has one free joint (7 qpos, 6 qvel) and 29 hinge joints.
NQ = 36
NV = 35
NU = 29
#: An in-range control vector: every motor accepts 0.
MID = [0.0] * NU
#: A control that moves the first actuated joint (left hip pitch) toward +5 N m.
TARGET = [5.0] + [0.0] * (NU - 1)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UnitreeG1Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client):
        return client.invoke("cap.world.reset.v1", {}, **self.ids)

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_card_model(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 0.5)
        self.assertEqual(state["tick"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, MID, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        for index, value in ((0, 88.1), (3, 139.1), (5, 50.1), (14, 50.1), (20, 25.1), (27, 5.1)):
            refused = self.step(client, MID[:index] + [value] + MID[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)   # the refused steps changed nothing

    def test_the_state_follows_the_control_value(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        initial = self.state(client)["qpos"]
        output = self.step(client, TARGET)["output"]
        self.assertAlmostEqual(output["observation"]["time"], 0.0005)
        self.assertGreater(output["observation"]["qpos"][7], initial[7])
        self.assertEqual(self.state(client)["ctrl"][0], 5.0)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        initial = self.state(client)["qpos"]
        self.assertEqual(self.step(client, TARGET, ticks=3)["status"], "completed")
        output = self.reset(client)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"], initial)
        self.assertEqual(output["observation"]["time"], 0.0)

    def test_fake_motor_controls_are_efforts_not_position_targets(self) -> None:
        # The MJCF uses motors, not position actuators. This checks the stand-in's
        # effort interpretation only; its placeholder inertia is not MuJoCo physics.
        client = self.serve()
        self.assertEqual(self.step(client, TARGET)["status"], "completed")
        first = self.state(client)["qvel"][6]
        self.assertGreater(first, 0.0)
        self.assertEqual(self.step(client, TARGET)["status"], "completed")
        second = self.state(client)["qvel"][6]
        self.assertGreater(second, first)
        self.assertEqual(self.step(client, MID)["status"], "completed")
        self.assertAlmostEqual(self.state(client)["qvel"][6], second)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:g1-29dof-effort-fake", "F0"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual(fidelity["timestep_ms"], 0.5)
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, MID)["status"], "completed")
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        for refused in (self.step(client, MID), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)   # readable, and not advanced
        stopped = self.state(client)
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertEqual(self.state(client), stopped)    # safety reset integrates no physics


if __name__ == "__main__":
    unittest.main()
