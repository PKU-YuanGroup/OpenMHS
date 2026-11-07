"""Acceptance run of the robotiq-ur5 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo and mujoco-py are
not installed where the gate runs, so nothing here compares the stand-in with the real engine or a physical robot.
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
#: Six arm hinges and eight finger hinges are 14 one-DOF joints; four target bodies add three slides + one ball each,
#: so qpos is 14 + 4 * (3 + 4) = 42 and qvel is 14 + 4 * (3 + 3) = 38 (xmls/lab_env.xml:74-207).
NQ = 42
NV = 38
#: Twelve active motor actuators; the velocity and position blocks are XML comments (xmls/lab_env.xml:216-245).
NU = 12
#: Test data: zero everywhere except joint1_motor, actuator index 6 (xmls/lab_env.xml:232-243).
CTRL = [0.0] * NU
CTRL[6] = 0.5


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RobotiqUR5Cases(unittest.TestCase):
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

    def test_the_model_shape_comes_from_the_scene(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 20.0)          # <option timestep="0.02"> (lab_env.xml:4)
        self.assertEqual((state["tick"], state["time_ms"], state["seed"]), (0, 0, 0))

    def test_a_step_moves_an_actuated_joint_and_advances_time(self) -> None:
        client = self.serve()
        receipt = self.step(client, CTRL, ticks=2)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 2)
        state = self.state(client)
        self.assertEqual(state["time_ms"], 40)                # two ticks of the 20 ms step
        self.assertGreater(state["qpos"][0], 0.0)             # joint1_motor drives qpos[0]
        self.assertEqual(state["ctrl"][6], CTRL[6])

    def test_a_wrong_number_of_controls_is_refused(self) -> None:
        client = self.serve()
        receipt = self.step(client, CTRL[:-1])
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, CTRL, ticks=3)
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 0)        # the bridge's configured seed, not the class input
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qpos"], [0.0] * NQ)
        self.assertEqual(state["qvel"], [0.0] * NV)
        self.assertEqual(state["ctrl"], [0.0] * NU)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:ur5", "F1"))
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)
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
