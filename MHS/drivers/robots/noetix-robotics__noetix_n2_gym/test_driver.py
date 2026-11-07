"""Acceptance run of the Noetix N2 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the stand-in with the real engine.
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
NQ = 25          # 7 values of the free base plus 18 hinge joints (n2_18dof.xml:43-47,52-156)
NV = 24          # 6 velocities of the free base plus 18 hinge joints
NU = 18          # eighteen motor actuators (n2_18dof.xml:169-191)
#: The model states no ctrlrange for its motors (n2_18dof.xml:169-191), so any finite vector is in its envelope.
ZERO = [0.0] * NU


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class N2Cases(unittest.TestCase):
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

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_card_model(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 2.0)            # n2_18dof.yaml:8 and sim2sim.py:91
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["qpos"][0:3], [0.0, 0.0, 0.75])  # base_link pos (n2_18dof.xml:43)
        self.assertEqual(state["qpos"][3:7], [1.0, 0.0, 0.0, 0.0])  # the free joint's identity quaternion

    def test_a_step_advances_the_integration_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, ZERO, ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertEqual(output["observation"]["time"], 0.004)  # two ticks of the 0.002 s step
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (2, 4))

    def test_a_control_value_moves_its_actuated_joint(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        push = ZERO[:]
        push[0] = 1.0                                          # L_arm_shoulder_pitch motor
        receipt = self.step(client, push)
        self.assertEqual(receipt["status"], "completed")
        # qpos[7] is the first hinge joint after the seven free-base values; the stand-in moves it with its control
        self.assertGreater(receipt["output"]["observation"]["qpos"][7], 0.0)

    def test_the_control_vector_has_one_value_per_actuator(self) -> None:
        client = self.serve()
        for ctrl in (ZERO[:-1], ZERO + [0.0]):
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_the_model_declares_no_control_range(self) -> None:
        # Not a safety claim: the MJCF sets no ctrlrange or ctrllimited (n2_18dof.xml:169-191), so the bound is the
        # operator's (here the example overlay's illustrative -10..10) and the driver invents none.
        client = self.serve()
        receipt = self.step(client, [1e6] * NU)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(receipt["error"]["details"]["provenance"]["source"], "operator")

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        push = [0.5] * NU
        self.assertEqual(self.step(client, push, ticks=3)["status"], "completed")
        self.assertEqual(self.reset(client)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qpos"], [0.0, 0.0, 0.75, 1.0, 0.0, 0.0, 0.0] + [0.0] * 18)
        self.assertEqual(state["qvel"], [0.0] * NV)
        self.assertEqual(state["ctrl"], [0.0] * NU)

    def test_the_reset_seed_is_accepted_but_does_not_change_the_model(self) -> None:
        client = self.serve()
        first = self.reset(client)["output"]
        seeded = self.reset(client, seed=7)
        self.assertEqual(seeded["status"], "completed")
        self.assertEqual(seeded["output"]["observation"], first["observation"])
        self.assertEqual(seeded["output"]["seed"], 0)          # the class seed; a MuJoCo reset does not use it

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:N2", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)         # readable, and not advanced


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
