"""Acceptance run of the go_bdx scene package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the stand-in with the real engine.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INVALID = "MHS.CAPABILITY.INPUT_INVALID"
#: go_bdx/go_bdx.xml has one freejoint (7 qpos, 6 qvel) and 16 hinge joints (1 each): qpos = 7 + 16 = 23 and
#: qvel = 6 + 16 = 22.  The scene includes this model at go_bdx/scene.xml:2.
NQ = 23
NV = 22
#: Sixteen <position> actuators, one per hinge joint (go_bdx/go_bdx.xml:163-179).
NU = 16
#: The qpos index of the first actuated joint: the freejoint occupies qpos[0:7].
FIRST_HINGE = 7
#: Test data inside the model's bounded control space.
MID = [0.0] * NU


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GoBdxSceneCases(unittest.TestCase):
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

    def test_the_model_shape_comes_from_the_included_mjcf(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        # The model states no timestep; 2.0 ms is the stand-in's placeholder for MuJoCo's library default.
        self.assertEqual(state["timestep_ms"], 2.0)
        self.assertEqual(state["tick"], 0)

    def test_each_ctrlrange_group_is_refused_before_mutation(self) -> None:
        client = self.serve()
        # One actuator from each ctrlrange group: hip -30..30, head -5.55..5.55, antenna -13.62..13.62 and
        # right ankle -30..30 (go_bdx/go_bdx.xml:164-179).
        for index, bound, delta in ((0, 30.0, 0.01), (6, 5.55, 0.01), (9, 13.62, 0.01), (15, -30.0, -0.01)):
            ctrl = list(MID)
            ctrl[index] = bound + delta
            receipt = self.step(client, ctrl)
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, (index, receipt))
        self.assertEqual(self.state(client)["tick"], 0)      # no refused step advanced the world

    def test_values_on_the_ctrlrange_are_accepted(self) -> None:
        client = self.serve()
        ctrl = list(MID)
        ctrl[0], ctrl[6], ctrl[9], ctrl[15] = 30.0, -5.55, 13.62, -30.0
        receipt = self.step(client, ctrl)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_step_advances_time_and_moves_the_actuated_hinge(self) -> None:
        client = self.serve()
        ctrl = list(MID)
        ctrl[0] = 5.0                                         # placeholder target inside the -30..30 ctrlrange
        first = self.step(client, ctrl)["output"]["observation"]
        second = self.step(client, ctrl)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertAlmostEqual(second["time"], 0.004, places=9)  # two ticks of the 2 ms stand-in step
        self.assertGreater(second["qpos"][FIRST_HINGE], 0.0)     # left_hip_yaw moves toward its positive target
        self.assertEqual(self.state(client)["tick"], 2)

    def test_a_step_without_an_action_is_allowed(self) -> None:
        client = self.serve()
        receipt = self.step(client, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 3)
        self.assertEqual(self.state(client)["ctrl"], [0.0] * NU)

    def test_a_wrong_ctrl_length_is_rejected(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0] * (NU - 1))
        self.assertEqual(receipt["error"]["mhs_code"], INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        ctrl = list(MID)
        ctrl[0] = 5.0
        self.step(client, ctrl, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client, seed=7)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"], [0.0] * NQ)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["seed"], 0)                  # the bridge's configured seed, not the class input

    def test_the_fidelity_contract_is_published(self) -> None:
        # The fake backend is a stand-in with no physics, so it publishes the F0 contract; the F1 MuJoCo contract
        # belongs to the real engine path, which was not run (model review, 2026-11-05).
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:stand-in mujoco module (no physics)", "F0"))
        self.assertEqual(fidelity["timestep_ms"], 2.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        real = type(driver).fidelity
        self.assertEqual((real["engine"], real["fidelity_level"]), ("mujoco:bdx scene", "F1"))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, MID)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, MID), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
