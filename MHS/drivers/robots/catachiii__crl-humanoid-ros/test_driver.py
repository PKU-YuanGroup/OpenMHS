"""Acceptance run of the CRL Humanoid G1 package: the gate, plus cases for this MuJoCo scene.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py):
MuJoCo is not installed where the gate runs, so nothing here compares the stand-in with the real
engine.  Every number below is test data, not a bound or a fact of the model.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
#: Operator example data the gate serves too: the model gives no actuator a control range.
EXAMPLE_OVERLAY = HERE / "site-limits.example.json"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
NQ = 36          # the free base (7) plus 29 hinge joints (g1_29dof_crl.xml:44-242)
NV = 35          # the free base (6) plus 29 hinge joints
NU = 29          # the 29 motor actuators (g1_29dof_crl.xml:245-275)
CTRL = [0.0] * NU
MOVE = [1.0] * NU


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CrlHumanoidG1Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake", site_limits=EXAMPLE_OVERLAY)
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

    def test_the_model_shape_comes_from_the_card_scene(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 2.0)   # the model sets no timestep: the stand-in's placeholder
        self.assertEqual(state["tick"], 0)
        self.assertAlmostEqual(state["qpos"][2], 0.793, places=9)  # pelvis height from g1_29dof_crl.xml:44

    def test_a_step_advances_the_integration_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        first = self.step(client, MOVE)["output"]
        second = self.step(client, MOVE)["output"]
        self.assertNotEqual(first["observation"]["qpos"], second["observation"]["qpos"])
        self.assertGreater(second["observation"]["time"], first["observation"]["time"])
        self.assertEqual(second["tick"], 2)
        self.assertEqual(len(second["state_hash"]), len("sha256:") + 64)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, MOVE, ticks=3)["status"], "completed")
        output = self.reset(client)
        self.assertEqual(output["status"], "completed", output)
        self.assertEqual(output["output"]["observation"]["qpos"][2], 0.793)
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["output"]["observation"]["time"], 0.0)

    def test_a_wrong_control_length_is_refused_before_the_engine(self) -> None:
        client = self.serve()
        before = self.state(client)
        refused = self.step(client, [0.0])
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        after = self.state(client)
        self.assertEqual(before["qpos"], after["qpos"])
        self.assertEqual(before["tick"], after["tick"])

    def test_the_fidelity_contract_is_published(self) -> None:
        # The fake backend is a stand-in with no dynamics, so it publishes the F0 contract; the F1
        # MuJoCo contract belongs to the real engine path, which was not run (reviewer change).
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:stand-in mujoco module (no physics)", "F0"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        real = type(driver).fidelity
        self.assertEqual((real["engine"], real["fidelity_level"]), ("mujoco:g1 scene crl", "F1"))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, CTRL)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, CTRL), self.reset(client)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)   # readable, and not advanced


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
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(client.read("world", **ids)["state"]["tick"], 0)
        ticked = client.invoke("cap.world.step.v1", {"ticks": 1}, **ids)
        self.assertEqual(ticked["status"], "completed", ticked)
        self.assertEqual(client.read("world", **ids)["state"]["tick"], 1)

if __name__ == "__main__":
    unittest.main()
