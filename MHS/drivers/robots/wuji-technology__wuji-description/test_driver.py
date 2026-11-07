"""Acceptance run of the Wuji Hand left package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the stand-in with the real engine.  The numbers used as
control inputs are test data, not device facts; the model's own ctrlrange is the bound the driver enforces.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: Five fingers with four hinge joints each (hand/body-with-soft/mjcf/left.xml:39-160); there is no free joint.
NQ = 20
NV = 20
#: 20 position actuators, one per hinge joint (hand/body-with-soft/mjcf/left.xml:171-190).
NU = 20
#: The first actuator's ctrlrange (hand/body-with-soft/mjcf/left.xml:171).
FIRST_LOW = 0.0475
FIRST_HIGH = 1.6033
#: Test data inside the model's control space (the first joint starts at 0.0475 rad).
TARGET = [0.0] * NU
TARGET[0] = 0.5                                     # placeholder: a value inside the first ctrlrange


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WujiHandCases(unittest.TestCase):
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

    def step(self, client, ctrl=None, ticks=1):
        args = {"ticks": ticks}
        if ctrl is not None:
            args["action"] = {"ctrl": list(ctrl)}
        return client.invoke("cap.world.step.v1", args, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_card_model(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 2.0)          # the model sets timestep="0.002"
        self.assertEqual(state["tick"], 0)

    def test_a_step_outside_the_first_actuator_range_is_refused(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        for value in (FIRST_LOW - 0.5, FIRST_HIGH + 0.5):   # placeholders: outside the sourced ctrlrange
            ctrl = list(TARGET)
            ctrl[0] = value
            receipt = self.step(client, ctrl)
            self.assertEqual(receipt["status"], "rejected")
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)
            self.assertEqual(self.state(client)["tick"], 0)  # refused before any native step

    def test_a_step_advances_time_and_moves_the_actuated_joints(self) -> None:
        client = self.serve()
        first = self.step(client, TARGET)["output"]["observation"]
        second = self.step(client, TARGET)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertEqual(second["time"], 0.004)              # two ticks of the 2 ms model step
        self.assertGreater(second["qpos"][0], 0.0)           # the first joint moves toward its target
        self.assertEqual(self.state(client)["tick"], 2)

    def test_a_step_without_an_action_is_allowed(self) -> None:
        client = self.serve()
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertEqual(self.state(client)["ctrl"], [0.0] * NU)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, TARGET, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client, seed=7)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"], [0.0] * NQ)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["seed"], 0)                  # the bridge's configured seed, not the class input

    def test_the_fidelity_contract_is_published(self) -> None:
        # The fake backend is a stand-in with no dynamics, so it publishes the F0 contract; the F1 MuJoCo contract
        # belongs to the real engine path, which was not run (reviewer change).
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:stand-in mujoco module (no physics)", "F0"))
        self.assertEqual(fidelity["timestep_ms"], 2.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        real = type(driver).fidelity
        self.assertEqual((real["engine"], real["fidelity_level"]), ("mujoco:wujihand-left", "F1"))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, TARGET)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, TARGET), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
