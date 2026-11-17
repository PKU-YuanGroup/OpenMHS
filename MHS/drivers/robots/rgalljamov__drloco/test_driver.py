"""Acceptance run of the drloco package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the ``check_driver`` call.  The cases run on the fake backend (fake.py): MuJoCo
itself is not installed where the gate runs, so nothing here compares the stand-in with the real engine.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: The MJCF has three COM slide joints, three trunk hinge joints and four leg joints per side
#: (drloco/mujoco/xml/walker3d_flat_feet.xml:18-59), and eight motor actuators (:71-80).
NQ = 14
NV = 14
NU = 8
#: placeholder: a control inside the model's -300..300 default motor range.
PUSH = [100.0] * NU
ZERO = [0.0] * NU


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DrlocoWalkerCases(unittest.TestCase):
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
        self.assertEqual(state["timestep_ms"], 1.0)              # the MJCF's own 0.001 s (model:11)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["qpos"][2], 1.08)                # com_z ref (model:20)

    def test_the_default_motor_range_is_enforced_before_mutation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [300.0] * NU)["status"], "completed")
        self.assertEqual(self.step(client, [-300.0] * NU)["status"], "completed")
        for index, value in ((0, 300.5), (3, -300.5), (7, 301.0)):
            ctrl = ZERO[:index] + [value] + ZERO[index + 1:]
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)         # the refused steps changed nothing

    def test_the_control_vector_has_one_value_per_actuator(self) -> None:
        client = self.serve()
        for ctrl in (ZERO[:-1], ZERO + [0.0]):
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_a_step_advances_the_integration_state(self) -> None:
        client = self.serve()
        first = self.step(client, PUSH, ticks=2)["output"]
        self.assertEqual(first["tick"], 2)
        self.assertEqual(first["observation"]["time"], 0.002)    # two ticks of the model's 0.001 s step
        self.assertGreater(first["observation"]["qpos"][6], 0.0)  # the first actuated joint moves
        self.assertEqual(self.state(client)["time_ms"], 2)

    def test_a_step_without_an_action_keeps_the_controls(self) -> None:
        client = self.serve()
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertEqual(self.state(client)["ctrl"], ZERO)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, PUSH, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client, seed=7)["output"]
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["time_ms"], 0)
        self.assertEqual(state["qpos"][2], 1.08)
        self.assertEqual(state["qpos"][:2] + state["qpos"][3:], [0.0] * (NQ - 1))
        self.assertEqual(state["qvel"], [0.0] * NV)
        self.assertEqual(state["ctrl"], ZERO)
        self.assertEqual(output["seed"], 0)                     # the bridge's configured seed, not the input

    def test_a_snapshot_restores_the_advertised_state(self) -> None:
        client = self.serve()
        before = self.state(client)
        saved = client.snapshot(**self.ids)
        self.assertEqual(saved["state"]["world"], before)
        self.step(client, PUSH)
        restored = client.restore(saved, **self.ids)
        self.assertEqual(restored["status"], "completed", restored)
        self.assertEqual(self.state(client), before)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:stand-in mujoco module (no physics)", "F0"))
        self.assertEqual(fidelity["timestep_ms"], 1.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        real = type(driver).fidelity
        self.assertEqual((real["engine"], real["fidelity_level"]), ("mujoco:walker3d_flat_feet", "F1"))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)         # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
