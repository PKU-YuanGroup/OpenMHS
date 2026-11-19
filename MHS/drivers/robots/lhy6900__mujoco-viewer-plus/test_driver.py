"""Acceptance run of the mujoco-viewer-plus package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): MuJoCo itself is not installed where the gate runs, so nothing here
compares the stand-in with the real engine or a physical G1.  The model file is the card's MJCF in the read-only
clone, and the fake derives its shape from that file.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
#: Operator example data the gate serves too: the model gives no actuator a control range.
EXAMPLE_OVERLAY = HERE / "site-limits.example.json"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
#: One free joint (7 qpos / 6 qvel) plus 29 hinges (g1.xml:133-136, :386-416).
NQ = 36
NV = 35
NU = 29
ZERO = [0.0] * NU
#: Test data: a nonzero control on the first actuator (left_hip_pitch_joint, g1.xml:387).
CTRL = list(ZERO)
CTRL[0] = 1.0
#: The pelvis position is stated in g1.xml:134; the free joint uses an identity quaternion.
RESET_QPOS = [0.0, 0.0, 0.793, 1.0, 0.0, 0.0, 0.0] + [0.0] * (NQ - 7)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MujocoViewerPlusCases(unittest.TestCase):
    def serve(self, *, overlay=True):
        server = load(HERE, backend="fake", site_limits=EXAMPLE_OVERLAY if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_card_model(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["qpos"], RESET_QPOS)
        self.assertEqual(state["timestep_ms"], 2.0)          # placeholder for the engine default, 0.002 s
        self.assertEqual((state["tick"], state["time_ms"], state["seed"]), (0, 0, 0))

    def test_a_step_moves_an_actuated_joint_and_advances_time(self) -> None:
        client = self.serve()
        receipt = self.step(client, CTRL, ticks=2)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 2)
        state = self.state(client)
        self.assertEqual(state["time_ms"], 4)                # two ticks of the 2 ms placeholder step
        self.assertGreater(state["qpos"][7], 0.0)            # left_hip_pitch_joint is the first hinge
        self.assertEqual(state["ctrl"][0], CTRL[0])

    def test_a_wrong_number_of_controls_is_refused(self) -> None:
        client = self.serve()
        receipt = self.step(client, CTRL[:-1])
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_control_step_needs_an_operator_bound(self) -> None:
        # The model gives no actuator a ctrlrange: without an operator overlay the endpoint refuses every step that
        # sets action.ctrl (LIMITS_UNSET) before the engine runs, and a step without an action still advances.
        client = self.serve(overlay=False)
        refused = self.step(client, ZERO)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["tick"], 0)
        ticked = client.invoke("cap.world.step.v1", {"ticks": 1}, **self.ids)
        self.assertEqual(ticked["status"], "completed", ticked)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_example_overlay_bounds_the_controls(self) -> None:
        client = self.serve()
        refused = self.step(client, [11.0] + ZERO[1:])
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(self.step(client, CTRL)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, CTRL, ticks=3)["status"], "completed")
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 0)        # the bridge's configured seed, not the class input
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qpos"], RESET_QPOS)
        self.assertEqual(state["qvel"], [0.0] * NV)
        self.assertEqual(state["ctrl"], [0.0] * NU)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic:g1", "F0"))
        self.assertFalse(fidelity["snapshot_restore"])
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (2.0, 0, "lockstep"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)
        self.assertIn("NOT COVERED", " ".join(fidelity["gaps"]))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, CTRL)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, CTRL), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
