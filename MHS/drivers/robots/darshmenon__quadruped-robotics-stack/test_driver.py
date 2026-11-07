"""Acceptance run of the Go2 parkour MuJoCo package: the gate, plus cases for this driver.

The cases run on the fake backend (``fake.py``): MuJoCo itself is not installed where the gate runs, so nothing here
compares the stand-in with the real engine.  The served model is the card's first model,
``training/envs/go2_parkour_scene.xml``; the stand-in derives its shape from that text.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: One free base joint (7 qpos, 6 qvel), twelve leg hinges and seven arm/gripper joints
#: (go2_parkour_scene.xml:24, :127-151).
NQ = 26
NV = 25
#: The actuator block has nineteen position actuators (go2_parkour_scene.xml:164-189).
NU = 19
#: An in-range control vector: the calf range is entirely negative, so its midpoint stands in for zero
#: (go2_parkour_scene.xml:176-179); every other joint includes 0 (go2_parkour_scene.xml:166-189).
NEUTRAL = [0.0, 0.0, 0.0, 0.0,
           0.0, 0.0, 0.0, 0.0,
           -1.78, -1.78, -1.78, -1.78,
           0.0, 0.0, 0.0, 0.0, 0.0,
           0.0, 0.0]
#: Actuator 0 is FL_hip; after the free base its qpos slot is 7.
FL_HIP_QPOS = 7


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Go2ParkourCases(unittest.TestCase):
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
        # The floating base starts at the body pos of go2_parkour_scene.xml:23 with the identity quaternion.
        self.assertEqual(state["qpos"][:3], [0.0, 0.0, 0.42])
        self.assertEqual(state["qpos"][3], 1.0)
        # The scene states an option timestep of 0.005 s (go2_parkour_scene.xml:4); the stand-in reads it.
        self.assertEqual(state["timestep_ms"], 5.0)
        self.assertEqual(state["tick"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, NEUTRAL, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        # hip motors are -1.0472..1.0472, thigh motors reach 3.4907, calf motors stop at -2.7227 and the right
        # finger stops at 0 (go2_parkour_scene.xml:166-189).
        for index, value in ((0, 1.05), (0, -1.05), (4, 3.5), (8, 0.0), (18, 0.001)):
            refused = self.step(client, NEUTRAL[:index] + [value] + NEUTRAL[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_the_state_follows_the_control_target(self) -> None:
        client = self.serve()
        target = list(NEUTRAL)
        target[0] = 0.5
        first = self.step(client, target)["output"]["observation"]
        second = self.step(client, target)["output"]["observation"]
        self.assertEqual(second["time"], 0.01)                 # two ticks of the 0.005 s step
        self.assertGreater(second["qpos"][FL_HIP_QPOS], first["qpos"][FL_HIP_QPOS])
        self.assertGreater(second["qpos"][FL_HIP_QPOS], 0.0)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        target = list(NEUTRAL)
        target[0] = 0.5
        self.step(client, target, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["observation"]["qpos"][:3], [0.0, 0.0, 0.42])
        self.assertEqual(output["observation"]["qpos"][FL_HIP_QPOS], 0.0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:go2_parkour_scene", "F1"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, NEUTRAL)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, NEUTRAL), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
