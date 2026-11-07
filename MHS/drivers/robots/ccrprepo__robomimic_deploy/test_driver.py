"""Acceptance run of the RoboMimic Deploy G1 package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): MuJoCo itself is not installed and cannot be installed where the gate
runs (no network, no pip), so nothing here compares the stand-in with the real engine.  The model file is the
card's scene in the read-only clone, and the fake derives its shape from that file.
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
NQ = 36          # one free joint (7) plus 29 hinges (1 each) in g1_description/g1_29dof_rev_1_0.xml
NV = 35          # the same model: one free joint (6) plus 29 hinges (1 each)
NU = 29          # 29 <motor> elements in g1_description/g1_29dof_rev_1_0.xml:246-274
#: An in-range control vector: the model declares no ctrlrange, so zero is a test input, not a device fact.
ZERO_CTRL = [0.0] * NU
#: A test control that moves the first actuated joint; not a device fact.
FIRST_CTRL = [10.0] + [0.0] * (NU - 1)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RoboMimicG1Cases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl or ZERO_CTRL)}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_card_scene(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (NQ, NV, NU))
        self.assertEqual(state["timestep_ms"], 2.0)           # g1_29dof_rev_1_0.xml:8
        self.assertAlmostEqual(state["qpos"][2], 0.793, places=6)   # pelvis pos, g1_29dof_rev_1_0.xml:50
        self.assertEqual(state["qpos"][3], 1.0)               # the free joint's identity quaternion
        self.assertEqual(state["tick"], 0)

    def test_the_control_vector_has_one_element_per_actuator(self) -> None:
        client = self.serve()
        for ctrl in ([0.0] * (NU - 1), [0.0] * (NU + 1)):
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected", len(ctrl))
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, len(ctrl))
        self.assertEqual(self.state(client)["tick"], 0)       # the refused steps changed nothing

    def test_ticks_are_bounded_by_the_bridge_input(self) -> None:
        client = self.serve()
        for ticks in (0, 10001):
            refused = self.step(client, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            # ticks is a schema bound of the bridge input, not a limit rule; the runtime refuses it as an input
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_step_advances_the_integration_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, FIRST_CTRL, ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertAlmostEqual(output["observation"]["time"], 0.004, places=9)   # two 0.002 s ticks
        self.assertGreater(output["observation"]["qpos"][7], 0.0)                # first hinge after the free joint
        self.assertGreater(output["observation"]["qvel"][6], 0.0)
        state = self.state(client)
        self.assertEqual(state["tick"], 2)
        self.assertEqual(state["time_ms"], 4)

    def test_a_reset_restores_the_model_defaults_and_echoes_the_seed(self) -> None:
        client = self.serve()
        self.step(client, FIRST_CTRL, ticks=3)
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # the reset input accepts a seed for the class contract, but a MuJoCo reset restores the model defaults and
        # does not use it; the output carries the bridge's configured seed (0)
        self.assertEqual(output["seed"], 0)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["observation"]["qpos"][7], 0.0)
        self.assertEqual(self.reset(client)["output"]["observation"], output["observation"])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:g1_scene", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_CTRL)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_CTRL), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
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
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(client.read("world", **ids)["state"]["tick"], 0)
        ticked = client.invoke("cap.world.step.v1", {"ticks": 1}, **ids)
        self.assertEqual(ticked["status"], "completed", ticked)
        self.assertEqual(client.read("world", **ids)["state"]["tick"], 1)

if __name__ == "__main__":
    unittest.main()
