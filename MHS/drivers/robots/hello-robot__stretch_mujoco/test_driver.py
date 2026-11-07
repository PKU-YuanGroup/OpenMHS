"""Acceptance run of the Stretch MuJoCo package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): MuJoCo itself is not installed where the gate runs, so nothing here
compares the stand-in with the real engine.  The model file is the card's first model, the default scene
``stretch_mujoco/models/scene.xml``, which includes ``stretch.xml`` and ``docking_station.xml``; the fake derives its
shape from that text.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: The served scene has four free joints (two scene objects, the Stretch base and the docking station:
#: scene.xml:2-3, stretch.xml:230, docking_station.xml:45) and 20 hinge/slide joints (stretch.xml:284-465), so
#: qpos = 4*7 + 20 = 48 and qvel = 4*6 + 20 = 44.
NQ = 48
NV = 44
#: The robot actuator block has ten actuators (stretch.xml:524-535).
NU = 10
#: An in-range control vector: every actuator ctrlrange includes 0 (stretch.xml:16-62).
ZERO = [0.0] * NU
#: The lift is the third actuator; its qpos slot follows the robot's free joint and the two wheel hinges.
LIFT = 9


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StretchCases(unittest.TestCase):
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
        # The model states no option timestep (stretch.xml:7-9); the stand-in uses MuJoCo's library default of
        # 2 ms as a placeholder (fake.py), and the bridge publishes the stand-in's value.
        self.assertEqual(state["timestep_ms"], 2.0)
        self.assertEqual(state["tick"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        # wheel -6..6, lift 0..1.1, arm 0..0.52, wrist_yaw -1.39..4.42, wrist_pitch -1.57..0.56,
        # wrist_roll -3.14..3.14, gripper -0.02..0.04, head_pan -4.04..1.73, head_tilt -1.53..0.79
        # (stretch.xml:16-62)
        for index, value in ((0, 6.5), (1, -6.5), (2, 1.2), (3, 0.6), (4, 4.5), (5, 0.7), (6, 3.5), (7, 0.05),
                             (8, 1.8), (9, 0.8)):
            refused = self.step(client, ZERO[:index] + [value] + ZERO[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_the_state_follows_the_control_target(self) -> None:
        client = self.serve()
        target = list(ZERO)
        target[2] = 0.5                                        # lift, in its 0 to 1.1 range (stretch.xml:20-22)
        first = self.step(client, target)["output"]["observation"]
        second = self.step(client, target)["output"]["observation"]
        self.assertEqual(second["time"], 0.004)                # two ticks of the 2 ms step
        self.assertGreater(second["qpos"][LIFT], first["qpos"][LIFT])
        self.assertGreater(second["qpos"][LIFT], 0.0)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, ZERO, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["observation"]["qpos"][LIFT], 0.0)
        self.assertEqual(output["observation"]["qpos"][3], 1.0)   # the free base quaternion is the identity

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:stretch", "F1"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
