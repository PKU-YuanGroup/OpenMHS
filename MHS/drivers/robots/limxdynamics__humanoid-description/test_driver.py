"""Acceptance run of the LimX HU_D03 description package: the gate, plus cases specific to this driver.

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
#: The MJCF has one free root joint (7 qpos, 6 qvel), 37 hinges (1 each) and six ball joints (4 qpos, 3 qvel):
#: qpos = 7 + 37 + 24 = 68 and qvel = 6 + 37 + 18 = 61 (HU_D03_description/xml/HU_D03_03.xml:90-403).
NQ = 68
NV = 61
#: One motor for each of the 31 actuated joints (HU_D03_description/xml/HU_D03_03.xml:406-443).
NU = 31
#: Test data inside the model's bounded control space.
MID = [0.0] * NU
#: placeholder: torque for the first motor (hip_pitch_left), inside its -120..120 ctrlrange.
TARGET = [0.0] * NU
TARGET[0] = 5.0
#: The qpos index of the first actuated joint: the free root joint occupies qpos[0:7].
FIRST_HINGE = 7


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HumanoidDescriptionCases(unittest.TestCase):
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

    def test_the_model_shape_comes_from_the_mjcf(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 1.0)          # the model sets timestep="0.001"
        self.assertEqual(state["tick"], 0)

    def test_each_motor_ctrlrange_is_enforced_before_mutation(self) -> None:
        client = self.serve()
        # One motor from each ctrlrange group in the model: hip -120..120, ankle -45..45, waist -45..45,
        # head -18..18, shoulder -30..30 and hand -18..18.
        for index, bound in ((0, 120.0), (4, 45.0), (12, 45.0), (15, 18.0), (17, 30.0), (30, -18.0)):
            ctrl = list(MID)
            ctrl[index] = bound + (1.0 if bound > 0 else -1.0)
            receipt = self.step(client, ctrl)
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, (index, receipt))
        self.assertEqual(self.state(client)["tick"], 0)      # no refused step advanced the world

    def test_values_on_the_model_ctrlrange_are_accepted(self) -> None:
        client = self.serve()
        ctrl = list(MID)
        ctrl[0], ctrl[4], ctrl[12], ctrl[15], ctrl[17], ctrl[30] = 120.0, -45.0, 45.0, -18.0, 30.0, -18.0
        receipt = self.step(client, ctrl)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_step_advances_time_and_moves_the_actuated_joint(self) -> None:
        client = self.serve()
        first = self.step(client, TARGET)["output"]["observation"]
        second = self.step(client, TARGET)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertEqual(second["time"], 0.002)              # two ticks of the 1 ms model step
        self.assertGreater(second["qpos"][FIRST_HINGE], 0.0)  # a positive torque moves hip_pitch_left positively
        self.assertEqual(self.state(client)["tick"], 2)

    def test_a_step_without_an_action_is_allowed(self) -> None:
        client = self.serve()
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertEqual(self.state(client)["ctrl"], [0.0] * NU)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        initial = self.state(client)["qpos"]
        # qpos0: the free joint at the base_link pose with an identity quaternion (HU_D03_03.xml:90-92).
        self.assertEqual(initial[:7], [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0])
        self.step(client, TARGET, ticks=3)
        self.assertNotEqual(self.state(client)["qpos"], initial)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client, seed=7)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"], initial)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["seed"], 0)                  # the bridge's configured seed, not the class input

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        # The fake backend publishes the stand-in's own F0 contract, not the real engine's F1 (model review).
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:stand-in mujoco module (no physics)", "F0"))
        self.assertEqual(fidelity["timestep_ms"], 1.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
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
