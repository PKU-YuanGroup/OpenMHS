"""Acceptance run of the Pai 12-DoF package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): MuJoCo itself is not installed where the gate runs, so nothing here
compares the stand-in with the real engine. The model file is the card's MJCF in the read-only clone, and the fake
derives its shape from that file.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
# pai_12dof.xml:68-71 gives a floating base (three slides and one ball joint) and :80-141 twelve hinges.
NQ = 19
NV = 18
NU = 12
#: An in-range control vector: every actuator's ctrlrange is -200..200 (pai_12dof.xml:153-164).
ZERO = [0.0] * NU


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Pai12DofCases(unittest.TestCase):
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
        self.assertEqual(state["timestep_ms"], 1.0)          # pai_12dof.xml:3
        self.assertEqual(state["tick"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, ZERO, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        # every actuator is bounded by -200..200 (pai_12dof.xml:153-164)
        for index, value in ((0, 201.0), (5, -201.0), (11, 201.0)):
            refused = self.step(client, ZERO[:index] + [value] + ZERO[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_the_state_follows_the_control_target(self) -> None:
        client = self.serve()
        target = list(ZERO)
        target[0] = 10.0
        first = self.step(client, target)["output"]["observation"]
        second = self.step(client, target)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertEqual(second["time"], 0.002)              # two ticks of the 1 ms step
        self.assertGreater(second["qpos"][7], 0.0)           # the first actuated hinge moves toward its target
        self.assertAlmostEqual(second["qvel"][6], 0.1)       # placeholder gain of the stand-in, not a model fact

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, ZERO, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"][7], 0.0)
        self.assertEqual(output["observation"]["time"], 0.0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:pai_12dof_v2_0312", "F0"))
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (1.0, 0, "lockstep"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
