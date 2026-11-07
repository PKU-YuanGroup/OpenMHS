"""Acceptance run of the G1 MuJoCo package: the gate, plus cases for what is specific to this model.

The cases run on the package's fake ``mujoco`` module (fake.py): MuJoCo is not installed where the gate runs, so
nothing here compares the stand-in with the real engine.  The constants checked below are the model's own
(``g1_description/g1_29dof_rev_1_0.xml:10`` for 0.002 s, ``:52`` for the pelvis start pose) and the upstream control
bound (``deploy_mujoco/config/mujoco.yaml:5-9``); the fake's placeholder integrator is not a fact.
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
N_CTRL = 29
PELVIS_Z = 0.793                                  # g1_29dof_rev_1_0.xml:52
TIMESTEP_MS = 2.0                                 # g1_29dof_rev_1_0.xml:10


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class G1Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake", site_limits=EXAMPLE_OVERLAY)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, ticks=1, ctrl=None):
        fields = {"ticks": ticks}
        if ctrl is not None:
            fields["action"] = {"ctrl": ctrl}
        return client.invoke("cap.world.step.v1", fields, **self.ids)

    def reset(self, client, seed=0):
        return client.invoke("cap.world.reset.v1", {"seed": seed}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_state_is_the_model_integration_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"], state["timestep_ms"]), (0, 0, TIMESTEP_MS))
        self.assertEqual(state["qpos"][:3], [0.0, 0.0, PELVIS_Z])
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (36, 35, N_CTRL))

    def test_a_step_writes_ctrl_and_advances_the_model(self) -> None:
        client = self.serve()
        ctrl = [0.0] * N_CTRL
        ctrl[0] = 8.0                              # inside +-88 (config:5)
        receipt = self.step(client, ticks=3, ctrl=ctrl)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["observation"]["time"]), (3, 0.006))
        self.assertEqual(self.state(client)["ctrl"][0], 8.0)
        self.assertGreater(self.state(client)["qvel"][6], 0.0)   # the first hinge after the free base
        self.assertNotEqual(self.state(client)["qpos"][7], 0.0)

    def test_no_control_limit_is_invented(self) -> None:
        # The model's motors declare no ctrlrange (g1_29dof_rev_1_0.xml:247-277): the driver declares no control
        # bound (not the upstream application's tau_limit, config:5-9), so the bridge publishes action.ctrl
        # operator_required and only an operator overlay bounds it (here the example's illustrative -10..10).
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        bare = client_for(server)
        device_id = bare.hello()["devices"][0]["device_id"]
        step = next(item for item in bare.inspect(device_id)["capabilities"]
                    if item["capability_id"] == "cap.world.step.v1")
        self.assertEqual(step["limits"], {"action.ctrl": "operator_required"})
        client = self.serve()
        ctrl = [0.0] * N_CTRL
        ctrl[0] = 200.0
        receipt = self.step(client, ctrl=ctrl)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["details"]["provenance"]["source"], "operator")
        self.assertEqual(self.state(client)["ctrl"][0], 0.0)

    def test_an_out_of_order_ctrl_array_is_refused(self) -> None:
        client = self.serve()
        refused = self.step(client, ctrl=[0.0] * (N_CTRL - 1))
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        ctrl = [0.0] * N_CTRL
        ctrl[0] = 8.0
        self.step(client, ticks=2, ctrl=ctrl)
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        # A MuJoCo reset restores the model defaults and has no seed parameter; the bridge echoes its configured
        # seed (MujocoDriver._RESET_INPUTS in the SDK, and the fidelity determinism note in driver.py).
        self.assertEqual(receipt["output"]["seed"], 0)
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qpos"][:3], [0.0, 0.0, PELVIS_Z])
        self.assertEqual(state["ctrl"], [0.0] * N_CTRL)

    def test_the_same_sequence_gives_the_same_state_hash(self) -> None:
        def trajectory():
            client = self.serve()
            self.reset(client, seed=0)
            return [self.step(client, ctrl=[1.0] * N_CTRL)["output"]["state_hash"] for _ in range(3)]

        self.assertEqual(trajectory(), trajectory())

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.step(client, ctrl=[0.0] * N_CTRL)
        client.estop("test", **self.ids)
        for refused in (self.step(client, ctrl=[0.0] * N_CTRL), self.reset(client, seed=0)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:g1_29dof_rev_1_0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (TIMESTEP_MS, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)


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
