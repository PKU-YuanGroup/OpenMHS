"""Acceptance run of the Go2 MuJoCo package: the gate, plus cases for what is specific to this driver.

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
#: The scene/go2.xml model has 19 qpos, 18 dof and 12 motor actuators (models/MJCF/go2/go2.xml:222-235).
NQ = 19
NV = 18
NU = 12
#: In-range controls in the model actuator order FR, FL, RR, RL; the knee range is -2.7227 to -0.83776 rad but
#: the actuator ctrl range is -45.43 to 45.43 (models/MJCF/go2/go2.xml:22-25).
TARGET = [0.5, 0.5, -1.0, 0.4, 0.4, -1.0, 0.3, 0.3, -1.0, 0.2, 0.2, -1.0]
MID = [0.0] * NU


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Go2Cases(unittest.TestCase):
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
        self.assertEqual(state["timestep_ms"], 2.0)          # the model states no timestep: the fake's fallback
        self.assertEqual(state["tick"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, MID, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        for index, value in ((0, 23.8), (2, -45.5), (8, 45.5), (10, 23.8)):
            refused = self.step(client, MID[:index] + [value] + MID[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_the_model_actuator_order_is_fr_fl_rr_rl(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        only_fr_hip = [0.0] * NU
        only_fr_hip[0] = 1.0
        observation = self.step(client, only_fr_hip)["output"]["observation"]
        # The freejoint occupies qpos 0..6, so FL_hip_joint is qpos 7 and FR_hip_joint is qpos 10; the actuator
        # block names FR_hip first (models/MJCF/go2/go2.xml:223-234).
        self.assertGreater(observation["qpos"][10], 0.0)
        self.assertEqual(observation["qpos"][7], 0.0)

    def test_the_state_follows_the_control_target(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        first = self.step(client, TARGET)["output"]["observation"]
        second = self.step(client, TARGET)["output"]["observation"]
        self.assertGreater(first["qpos"][10], 0.0)            # FR_hip_joint moves toward its positive target
        self.assertGreater(second["qpos"][10], first["qpos"][10])
        self.assertLess(first["qpos"][12], 0.0)               # FR_calf_joint moves toward its negative target
        self.assertAlmostEqual(second["time"], 0.004)         # two ticks of the fake's 2 ms step
        self.assertEqual(self.state(client)["ctrl"], TARGET)

    def test_a_reset_restores_the_standin_defaults(self) -> None:
        client = self.serve()
        self.step(client, TARGET, ticks=3)
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"], [0.0] * NQ)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(self.state(client)["ctrl"], [0.0] * NU)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:go2 scene", "F1"))
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"]), (2.0, 0))
        self.assertEqual((fidelity["clock"], fidelity["reset"]), ("lockstep", "full"))
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, MID)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, MID), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
