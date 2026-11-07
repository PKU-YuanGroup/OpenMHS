"""Acceptance run of the robot-unitree-g1 package: the gate, plus cases for what is specific to this driver.

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
NQ = 83          # 3 scene free joints (7 each), 2 drawer slides, the robot free base (7) and 53 robot hinges
NV = 79          # 3 scene free joints (6 each), 2 drawer slides, the robot free base (6) and 53 robot hinges
NU = 53          # the 53 motor actuators of resources/g1/g1_53dof.xml:812-887
ZERO = [0.0] * NU
#: A positive control on actuator 0 (left_hip_pitch_joint) and zero on the other 52 motors.
PUSH = [1.0] + [0.0] * (NU - 1)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UnitreeG1Cases(unittest.TestCase):
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
        payload = {"ticks": ticks}
        if ctrl is not None:
            payload["action"] = {"ctrl": list(ctrl)}
        return client.invoke("cap.world.step.v1", payload, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_card_scene(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 2.0)                 # deploy/config/g1_53.yaml:8
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        # resources/g1/g1_53dof.xml:96: the robot pelvis is at 0.80 -1.55 0.763.
        self.assertEqual(state["qpos"][0:3], [0.80, -1.55, 0.763])
        self.assertEqual(state["qpos"][3:7], [1.0, 0.0, 0.0, 0.0])
        # resources/g1/scene53.xml:39,56,132: the scene's three free bodies.
        self.assertEqual(state["qpos"][60:63], [1.20, -1.65, 0.87])
        self.assertEqual(state["qpos"][67:70], [1.20, -1.45, 0.87])
        self.assertEqual(state["qpos"][76:79], [1.85, -1.41, 1.1])

    def test_the_control_vector_has_one_value_per_actuator(self) -> None:
        client = self.serve()
        for ctrl in (ZERO[:-1], ZERO + [0.0]):
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_step_advances_the_integration_state(self) -> None:
        client = self.serve()
        first = self.reset(client)["output"]
        self.assertEqual(first["observation"]["time"], 0.0)
        self.assertEqual(first["observation"]["qpos"][0:3], [0.80, -1.55, 0.763])
        receipt = self.step(client, PUSH, ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertEqual(output["observation"]["time"], 0.004)      # two ticks of the deployed 0.002 s step
        self.assertGreater(output["observation"]["qpos"][7], 0.0)   # left_hip_pitch_joint moves with actuator 0
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (2, 4))
        self.assertEqual(state["ctrl"][0], 1.0)
        self.assertEqual(state["ctrl"][1:], [0.0] * (NU - 1))

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        initial = self.state(client)["qpos"]
        self.assertEqual(self.step(client, PUSH, ticks=3)["status"], "completed")
        self.assertEqual(self.reset(client)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qpos"], initial)
        self.assertEqual(state["qvel"], [0.0] * NV)
        self.assertEqual(state["ctrl"], ZERO)

    def test_the_reset_seed_does_not_change_the_model(self) -> None:
        client = self.serve()
        first = self.reset(client)["output"]
        seeded = client.invoke("cap.world.reset.v1", {"seed": 7}, **self.ids)
        self.assertEqual(seeded["status"], "completed")
        self.assertEqual(seeded["output"]["observation"], first["observation"])
        self.assertEqual(seeded["output"]["seed"], first["seed"])    # the bridge returns its configured seed

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:g1_53dof scene", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, PUSH)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, PUSH), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)             # readable, and not advanced


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
