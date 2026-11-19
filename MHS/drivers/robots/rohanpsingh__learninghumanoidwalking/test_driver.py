"""Acceptance run of the JVRC1 world package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the stand-in with the real engine or with the upstream
environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
#: Operator example data the gate serves too: the model gives no actuator a control range.
EXAMPLE_OVERLAY = HERE / "site-limits.example.json"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: The scene includes jvrc1.xml: one free root joint (7 qpos, 6 qvel) plus 44 hinges.
NQ = 51
NV = 50
#: The actuator section has 34 motors (models/jvrc_mj_description/xml/jvrc1.xml:451-492).
NU = 34
#: Test data inside the example overlay's illustrative control interval.
MID = [0.0] * NU
TARGET = [0.0] * NU
TARGET[0] = 0.5                                     # placeholder: positive R_HIP_P motor control, not a position


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Jvrc1Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake", site_limits=EXAMPLE_OVERLAY)
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

    def test_the_model_shape_comes_from_the_scene_and_its_include(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 1.0)          # the model sets timestep="0.001"
        self.assertEqual(state["tick"], 0)

    def test_the_model_declares_no_actuator_control_range(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        ctrl = list(MID)
        ctrl[0] = 1.0e6                                  # placeholder: far outside the example overlay's bound
        receipt = self.step(client, ctrl)
        # The model states no control range, so the bound is the operator's (here the example overlay's
        # illustrative interval): the refusal names an operator bound, not one of the model or the catalogue.
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(receipt["error"]["details"]["provenance"]["source"], "operator")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_step_advances_time_and_moves_the_actuated_joints(self) -> None:
        client = self.serve()
        first = self.step(client, TARGET)["output"]["observation"]
        second = self.step(client, TARGET)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertEqual(second["time"], 0.002)              # two ticks of the 1 ms model step
        self.assertGreater(second["qpos"][7], 0.0)           # positive motor control accelerates R_HIP_P
        self.assertEqual(self.state(client)["tick"], 2)

    def test_motor_control_uses_the_joint_velocity_address_and_retains_momentum(self) -> None:
        client = self.serve()
        first = self.step(client, TARGET)["output"]["observation"]
        # A free joint has seven qpos values but six qvel values: the first hinge uses qvel[6], not qvel[7].
        self.assertGreater(first["qvel"][6], 0.0)
        self.assertEqual(first["qvel"][:6] + first["qvel"][7:], [0.0] * (NV - 1))
        coast = self.step(client, MID)["output"]["observation"]
        # Zero motor torque is not a command to return the hinge to position zero.
        self.assertGreater(coast["qpos"][7], first["qpos"][7])

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
        expected = [0.0, 0.0, 1.4, 1.0, 0.0, 0.0, 0.0] + [0.0] * (NQ - 7)
        self.assertEqual(output["observation"]["qpos"], expected)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["seed"], 0)                  # the bridge's configured seed, not the class input

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic:jvrc1-motor-fake", "F0"))
        self.assertEqual(fidelity["timestep_ms"], 1.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, MID)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, MID), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced

    def test_a_control_step_needs_an_operator_bound(self) -> None:
        # The model gives no actuator a ctrlrange: without an operator overlay the endpoint refuses every step that
        # sets action.ctrl (LIMITS_UNSET) before the engine runs, and a step without an action still advances.
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        width = len(client.read("world", **ids)["state"]["ctrl"])
        refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"ctrl": [0.0] * width}}, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(client.read("world", **ids)["state"]["tick"], 0)
        ticked = client.invoke("cap.world.step.v1", {"ticks": 1}, **ids)
        self.assertEqual(ticked["status"], "completed", ticked)
        self.assertEqual(client.read("world", **ids)["state"]["tick"], 1)


if __name__ == "__main__":
    unittest.main()
