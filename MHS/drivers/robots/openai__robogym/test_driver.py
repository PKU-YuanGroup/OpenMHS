"""Acceptance run of the robogym ShadowHand package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the fake with the engine or with a physical hand.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ShadowHandCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.client = client
        return client

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": ctrl}}, **self.ids)

    def test_the_served_contract_is_the_card_model(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        self.assertEqual(device["mode"], "simulated")
        fidelity = device["fidelity"]
        self.assertEqual(fidelity["engine"], "mujoco:shadowhand")
        self.assertEqual(fidelity["fidelity_level"], "F1")
        self.assertEqual(fidelity["timestep_ms"], 8.0)                 # assets.xml:14
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertTrue(fidelity["snapshot_restore"])
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_a_step_writes_ctrl_and_advances_the_model(self) -> None:
        client = self.serve()
        state = self.state(client)
        nu = len(state["ctrl"])
        receipt = self.step(client, [0.0] * nu, ticks=2)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["tick"], 2)
        state = self.state(client)
        self.assertEqual(state["tick"], 2)
        self.assertEqual(state["time_ms"], 16)                         # two 8 ms steps (assets.xml:14)
        self.assertEqual(len(state["qpos"]), len(state["qvel"]) + 1)   # one free joint adds a quaternion

    def test_an_actuated_joint_moves_toward_its_control(self) -> None:
        client = self.serve()
        state = self.state(client)
        nu = len(state["ctrl"])
        ctrl = [0.0] * nu
        ctrl[0] = 0.1396                                              # A_WRJ1 max (joint_position_actuation.xml:72)
        before = list(state["qpos"])
        self.assertEqual(self.step(client, ctrl)["status"], "completed")
        after = self.state(client)["qpos"]
        self.assertNotEqual(before, after)
        self.assertGreater(sum(abs(a - b) for a, b in zip(before, after)), 0.0)

    def test_a_ctrl_outside_the_model_range_is_refused(self) -> None:
        client = self.serve()
        state = self.state(client)
        nu = len(state["ctrl"])
        ctrl = [0.0] * nu
        ctrl[0] = 1.0e6                                               # far outside every ctrlrange of the model
        refused = self.step(client, ctrl)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)                # the refused step changed nothing

    def test_a_short_ctrl_vector_is_an_input_error(self) -> None:
        client = self.serve()
        nu = len(self.state(client)["ctrl"])
        refused = self.step(client, [0.0] * (nu - 1))
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertNotEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_reset_restores_the_start_state(self) -> None:
        client = self.serve()
        nu = len(self.state(client)["ctrl"])
        self.assertEqual(self.step(client, [0.0] * nu, ticks=3)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 3)
        receipt = client.invoke("cap.world.reset.v1", {"seed": 5}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        # the seed is accepted for the class contract but a MuJoCo reset restores the model defaults and does not
        # use it (MujocoDriver._RESET_INPUTS); the output reports the bridge's configured seed
        self.assertEqual(receipt["output"]["seed"], 0)
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        nu = len(self.state(client)["ctrl"])
        self.assertEqual(self.step(client, [0.0] * nu)["status"], "completed")
        tick = self.state(client)["tick"]
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * nu),
                        client.invoke("cap.world.reset.v1", {"seed": 1}, **self.ids)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], tick)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
