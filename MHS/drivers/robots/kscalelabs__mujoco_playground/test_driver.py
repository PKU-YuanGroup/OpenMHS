"""Acceptance run of the K-Bot MuJoCo package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the stand-in with the real engine.

The model shape comes from the card's primary scene, ``playground/kbot/xmls/scene_mjx_feetonly_flat_terrain.xml``,
which includes ``kbot.xml``: one free joint (7 qpos, 6 dof), 20 hinge joints and 20 position actuators
(kbot.xml:64-65, :68-160, :175-196).
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

#: One free joint (7 qpos, 6 dof) plus 20 hinges gives 27 qpos and 26 dof; the actuator section has 20 entries.
NQ = 27
NV = 26
NU = 20
#: MuJoCo's engine default timestep (0.002 s), because kbot.xml declares no <option timestep>.
TIMESTEP_MS = 2.0
#: Model defaults: the free body's XML pose (z 1.08006263, kbot.xml:64) with an identity quaternion (x, y, z, qw,
#: qx, qy, qz), then 20 zero hinge angles.
QPOS0 = [0.0, 0.0, 1.08006263, 1.0, 0.0, 0.0, 0.0] + [0.0] * 20
#: In-range controls for all 20 actuators; actuator 0 drives left_shoulder_pitch_03 (range 0 to 3.141593).
TARGET = [0.2, 0.1, 0.1, -0.1, 0.1, -0.1, 0.1, 0.1, 0.1, 0.1,
          0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, -0.1, 0.1]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class KbotCases(unittest.TestCase):
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
        self.assertEqual(state["qpos"], QPOS0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, TARGET, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        # actuator 0 (left_shoulder_pitch_03) starts at 0, actuator 3 (left_elbow_02) ends at 0, actuator 9
        # (right_wrist_02) ends at 3.141593 and actuator 18 (right_knee_04) ends at 0.
        for index, value in ((0, -0.1), (3, 0.1), (9, 3.2), (18, 0.1)):
            refused = self.step(client, TARGET[:index] + [value] + TARGET[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_the_state_follows_the_control_target(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        first = self.step(client, TARGET)["output"]["observation"]
        second = self.step(client, TARGET)["output"]["observation"]
        self.assertGreater(first["qpos"][7], 0.0)             # left_shoulder_pitch_03 moves toward its target
        self.assertGreater(second["qpos"][7], first["qpos"][7])
        self.assertAlmostEqual(second["time"], 0.004)         # two ticks of the 2 ms step
        self.assertEqual(self.state(client)["ctrl"], TARGET)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, TARGET, ticks=3)
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(receipt["output"]["observation"]["qpos"], QPOS0)
        self.assertEqual(receipt["output"]["observation"]["time"], 0.0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:kbot_feetonly_flat_terrain", "F1"))
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"]), (TIMESTEP_MS, 0))
        self.assertEqual((fidelity["clock"], fidelity["reset"]), ("lockstep", "full"))
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertTrue(fidelity["snapshot_restore"])
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, TARGET)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, TARGET), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
