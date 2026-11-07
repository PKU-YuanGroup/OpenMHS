"""Acceptance run of the Adam-Lite MuJoCo package: the gate, plus cases for what is specific to this driver.

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
NQ = 30          # one free base (7) plus 23 hinge joints (adam_lite.xml:100 and :294-319)
NV = 29          # one free base (6) plus 23 hinge joints
NU = 23          # 12 leg, 3 waist and 4 per arm motor actuators (adam_lite.xml:294-319)
TIMESTEP_MS = 1.0  # scene.xml:18 sets option timestep 0.001 s
#: An in-range control vector: all commands zero (every ctrlrange of the model contains zero).
MID = [0.0] * NU
#: A control vector that moves the left hip pitch a little inside its +-230 range.
TARGET = [10.0] + [0.0] * (NU - 1)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AdamLiteCases(unittest.TestCase):
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
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], TIMESTEP_MS)
        self.assertEqual(state["tick"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, MID, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        # hipPitch +-230, hipRoll +-160, waist +-110, shoulder +-65, elbow +-30
        for index, value in ((0, 231.0), (1, 161.0), (12, 111.0), (15, 66.0), (18, 31.0)):
            refused = self.step(client, MID[:index] + [value] + MID[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_a_ctrl_vector_of_the_wrong_length_is_refused(self) -> None:
        client = self.serve()
        refused = self.step(client, MID[:-1])
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_state_follows_the_control_command(self) -> None:
        client = self.serve()
        first = self.step(client, TARGET)["output"]["observation"]
        second = self.step(client, TARGET)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertEqual(second["time"], 0.002)               # two ticks of the 1 ms step
        self.assertGreater(second["qpos"][7], 0.0)            # first hinge after the 7-value free base

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, TARGET, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"], [0.0] * NQ)
        self.assertEqual(output["observation"]["time"], 0.0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:adam_lite", "F1"))
        self.assertEqual(fidelity["timestep_ms"], TIMESTEP_MS)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, MID)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, MID), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
