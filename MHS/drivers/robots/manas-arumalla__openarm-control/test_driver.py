"""Acceptance run of the OpenArm unscrew package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the stand-in with the real engine.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

#: The served scene has 20 qpos and 20 dof: nine per arm (seven hinges and two finger slides), cap_turn and
#: cap_lift (unscrew_scene.xml:86-87), and 17 position actuators: the 16 arm actuators (openarm_v20_bimanual.xml:
#: 349-365) plus cap_lift_drive (unscrew_scene.xml:82).
NQ = 20
NU = 17
#: In-range controls: joint4 starts at 0 so it takes 1.2 rad, the left finger takes 0.4 and the right finger -0.4
#: (both inside 0..0.7854 and -0.7854..0), and cap_lift takes 0.1 m inside 0..0.12.
TARGET = [0.1, 0.1, 0.1, 1.2, 0.1, 0.1, 0.1, 0.4, 0.1, 0.1, 1.2, 0.1, 0.1, 0.1, 0.1, -0.4, 0.1]
MID = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.3, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, -0.3, 0.05]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OpenArmUnscrewCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
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
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NQ))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 2.0)          # unscrew_scene.xml:18
        self.assertEqual(state["tick"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, MID, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        # left joint1, right joint1, left finger, right finger and cap_lift, each outside its own ctrlrange
        for index, value in ((0, -3.6), (8, 3.6), (7, 0.9), (15, -0.9), (16, 0.13)):
            refused = self.step(client, MID[:index] + [value] + MID[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_the_state_follows_the_control_target(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        first = self.step(client, TARGET)["output"]["observation"]
        second = self.step(client, TARGET)["output"]["observation"]
        self.assertGreater(first["qpos"][0], 0.0)             # joint1 moves toward the positive target
        self.assertGreater(second["qpos"][0], first["qpos"][0])
        self.assertAlmostEqual(second["time"], 0.004)         # two ticks of the 2 ms step
        self.assertEqual(self.state(client)["ctrl"], TARGET)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, TARGET, ticks=3)
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"], [0.0] * NQ)
        self.assertEqual(output["observation"]["time"], 0.0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:openarm_v20_unscrew", "F1"))
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"]), (2.0, 0))
        self.assertEqual((fidelity["clock"], fidelity["reset"]), ("lockstep", "full"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, MID)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, MID), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
