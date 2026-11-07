"""Acceptance run of the Semantic Digital Twin package: the gate, plus cases for what is specific to this driver.

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

#: The scene has 16 qpos values and 15 dof (seven arm hinges, two finger slides and the box's free joint) and 8
#: actuators (seven arm position actuators and one finger general actuator); resources/mjcf/mjx_single_cube_no_mesh.xml
#: lines 47-83, 100-115, 148-153 and 158-159.
NQ = 16
NV = 15
NU = 8
#: In-range controls: joint4 is negative, joint6 and the finger are positive.
MID = [0.0, 0.0, 0.0, -1.5, 0.0, 1.0, 0.0, 0.02]
#: A second in-range vector that asks every actuated joint for a positive or less negative position.
TARGET = [0.1, 0.1, 0.1, -1.4, 0.1, 1.1, 0.1, 0.03]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SemanticDigitalTwinCases(unittest.TestCase):
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

    def test_the_model_shape_comes_from_the_card_scene(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (NQ, NV, NU))
        self.assertEqual(state["timestep_ms"], 5.0)          # mjx_single_cube_no_mesh.xml:118
        self.assertEqual(state["tick"], 0)
        # The reset input seed is accepted by the class contract but the MuJoCo bridge restores the model defaults
        # (mj_resetData) and reports the configured seed (0), so it does not use the input.
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")
        self.assertEqual(self.state(client)["seed"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, MID, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        # actuator2, actuator4 and actuator7 are the narrow or one-sided ranges; actuator8 is the finger.
        for index, value in ((1, 1.9), (3, 0.0), (5, -0.5), (6, 3.0), (7, 0.05)):
            refused = self.step(client, MID[:index] + [value] + MID[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_the_ticks_bound_is_enforced(self) -> None:
        client = self.serve()
        # The class schema carries the 1 to 10000 bound, so the runtime refuses an out-of-schema count as an input
        # error before the step reaches the bridge.
        for ticks in (0, 10001):
            refused = self.step(client, MID, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID", ticks)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_state_follows_the_control_target(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        first = self.step(client, TARGET)["output"]["observation"]
        second = self.step(client, TARGET)["output"]["observation"]
        self.assertGreater(first["qpos"][0], 0.0)             # joint1 moves toward its positive target
        self.assertGreater(second["qpos"][0], first["qpos"][0])
        self.assertAlmostEqual(second["time"], 0.010)         # two ticks of the 5 ms step
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
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:mjx_single_cube_no_mesh", "F1"))
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"]), (5.0, 0))
        self.assertEqual((fidelity["clock"], fidelity["reset"]), ("lockstep", "full"))
        self.assertEqual(fidelity["snapshot_restore"], True)
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertGreaterEqual(len(fidelity["gaps"]), 7)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, MID)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, MID), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
