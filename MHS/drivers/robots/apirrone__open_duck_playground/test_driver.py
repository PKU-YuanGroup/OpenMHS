"""Acceptance run of the Open Duck Mini V2 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the stand-in with the real engine.  The expected counts
come from the served scene and its included robot model, not from the fake's placeholder dynamics.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: The backlash robot has 31 qpos (free base 7 + 14 actuated hinges + 10 backlash hinges) and 30 qvel (free base 6).
NQ = 31
NV = 30
#: One position actuator per actuated hinge joint (open_duck_mini_v2_backlash.xml:497-512).
NU = 14
#: Test data inside the derived control ranges.
ZERO = [0.0] * NU
TARGET = [0.0] * NU
TARGET[0] = 0.3           # left_hip_yaw
TARGET[3] = 0.5           # left_knee


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OpenDuckMiniV2Cases(unittest.TestCase):
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

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_scene_and_its_include(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 2.0)          # the model sets no timestep: the library default
        self.assertEqual(state["tick"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, ZERO, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        for index, value in ((0, 0.6), (3, 1.8), (5, -0.4), (6, 0.9), (7, 3.0), (9, -0.6), (13, 1.7)):
            refused = self.step(client, ZERO[:index] + [value] + ZERO[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_a_step_moves_the_actuated_joints_and_advances_time(self) -> None:
        client = self.serve()
        first = self.step(client, TARGET)["output"]["observation"]
        second = self.step(client, TARGET)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertEqual(second["time"], 0.004)              # two ticks of the 2 ms step
        self.assertGreater(second["qpos"][7], 0.0)           # left_hip_yaw moves toward its positive target
        self.assertEqual(self.state(client)["tick"], 2)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, TARGET, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client, seed=7)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"], [0.0] * NQ)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["seed"], 0)                  # the bridge's configured seed, not the class input

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:open_duck_mini_v2_rough_terrain_backlash", "F1"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
