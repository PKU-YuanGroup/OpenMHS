"""Acceptance run of the ToddlerBot 2XC package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the stand-in with the real engine.  The model file is the
card's MJCF scene in the read-only clone, and the fake derives its shape from that file.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
NQ = 51          # toddlerbot_2xc.xml:35 free joint (7) plus the 44 hinge joints under worldbody
NV = 50          # the same joints: 6 + 44
NU = 30          # toddlerbot_2xc.xml:562-593, thirty <motor> actuators
CTRL_LOW = -10.0  # toddlerbot_2xc.xml:31, the main default ctrlrange "-10 10"
CTRL_HIGH = 10.0  # the same line


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ToddlerBotCases(unittest.TestCase):
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

    def test_the_model_shape_comes_from_the_card_model(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertGreater(state["timestep_ms"], 0.0)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))

    def test_a_step_is_bounded_by_the_actuator_control_range(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, [0.0] * NU, ticks=2)["status"], "completed")
        for index, value in ((0, CTRL_LOW - 0.5), (NU - 1, CTRL_HIGH + 0.5)):
            ctrl = [0.0] * NU
            ctrl[index] = value
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", index)
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_the_state_follows_the_control(self) -> None:
        client = self.serve()
        first = self.step(client, [0.0] * NU)["output"]["observation"]
        ctrl = [0.0] * NU
        ctrl[0] = 5.0                                        # the first actuator drives neck_yaw_drive
        second = self.step(client, ctrl)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertGreater(second["qpos"][7], 0.0)            # qpos[7] is the first hinge joint after the free joint
        self.assertEqual(second["qvel"][6], 5.0 * 0.01)       # placeholder stand-in dynamics, not MuJoCo
        timestep_s = self.state(client)["timestep_ms"] / 1000.0
        self.assertAlmostEqual(second["time"], 2 * timestep_s, places=9)
        self.assertEqual(second["time"], self.state(client)["time_ms"] / 1000.0)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, [0.0] * NU, ticks=3)
        self.assertGreater(self.state(client)["tick"], 0)
        self.assertEqual(self.reset(client)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qpos"][3], 1.0)               # the free joint starts at the identity quaternion
        self.assertEqual(state["qpos"][0:3], [0.0, 0.0, 0.315053])   # toddlerbot_2xc.xml:34, the torso body pos
        self.assertEqual(state["qvel"], [0.0] * NV)

    def test_the_seed_is_recorded_but_does_not_change_the_reset(self) -> None:
        client = self.serve()
        first = self.reset(client)["output"]
        seeded = self.reset(client)
        self.assertEqual(seeded["status"], "completed")
        # the reset input is metadata of the bridge: it restores the model defaults and draws no random state
        self.assertEqual(seeded["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:toddlerbot_2xc_scene", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual(fidelity["reset"], "full")
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * NU)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * NU), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
