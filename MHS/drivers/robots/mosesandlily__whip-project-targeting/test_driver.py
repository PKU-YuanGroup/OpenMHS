"""Acceptance run of the whip-project-targeting package: the gate, plus cases for this MuJoCo scene.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo and mujoco-py are
not installed where the gate runs, so nothing here compares the stand-in with the real engine or a physical arm.

The model has 54 hinge joints (four arm hinges plus 25 whip nodes with an X and a Y hinge each) and four motor
actuators (models/3D_model_w_whip_T1.xml:41-52, 61-186, 220-225).  Its motors state no ctrlrange, so every step that
sets action.ctrl needs the operator example overlay; the overlay is example data, not a model bound.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
#: Operator example data the gate serves too: the model gives no actuator a control range.
EXAMPLE_OVERLAY = HERE / "site-limits.example.json"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
#: Four arm hinges plus 25 whip bodies carrying one X and one Y hinge each.
NQ = 54
NV = 54
NU = 4
#: Test input: the first motor only; this is test data, not a control bound of the model.
CTRL = [0.0] * NU
CTRL[0] = 1.0


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WhipTargetingCases(unittest.TestCase):
    def serve(self, overlay=True):
        server = load(HERE, backend="fake", site_limits=EXAMPLE_OVERLAY if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, ctrl=None, ticks=1):
        fields = {"ticks": ticks}
        if ctrl is not None:
            fields["action"] = {"ctrl": list(ctrl)}
        return client.invoke("cap.world.step.v1", fields, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_scene(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 0.1)          # <option timestep="0.0001"> (T1:3)
        self.assertEqual((state["tick"], state["time_ms"], state["seed"]), (0, 0, 0))

    def test_a_step_moves_an_actuated_joint_and_advances_time(self) -> None:
        client = self.serve()
        receipt = self.step(client, CTRL, ticks=5000)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 5000)
        state = self.state(client)
        self.assertEqual(state["time_ms"], 500)               # 5000 ticks of 0.0001 s
        self.assertGreater(state["qpos"][0], 0.0)             # motor 0 targets joint_shoulder_flex_ext
        self.assertEqual(state["ctrl"], CTRL)

    def test_a_wrong_number_of_controls_is_refused(self) -> None:
        client = self.serve()
        receipt = self.step(client, CTRL[:-1])
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, CTRL, ticks=2)
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 0)        # the bridge's configured seed, not the class input
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qpos"], [0.0] * NQ)
        self.assertEqual(state["qvel"], [0.0] * NV)
        self.assertEqual(state["ctrl"], [0.0] * NU)

    def test_the_fake_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["engine"], "analytic:stand-in mujoco module (no physics)")
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.1, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertIn("NOT COVERED", " ".join(fidelity["gaps"]))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, CTRL)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, CTRL), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced

    def test_a_control_step_needs_an_operator_bound(self) -> None:
        # The model gives no actuator a ctrlrange: without an operator overlay the endpoint refuses every step that
        # sets action.ctrl (LIMITS_UNSET) before the engine runs, and a step without an action still advances.
        client = self.serve(overlay=False)
        width = len(self.state(client)["ctrl"])
        refused = self.step(client, [0.0] * width)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(self.state(client)["tick"], 0)
        ticked = self.step(client, None)
        self.assertEqual(ticked["status"], "completed", ticked)
        self.assertEqual(self.state(client)["tick"], 1)


if __name__ == "__main__":
    unittest.main()
