"""Acceptance run of the mjrl swimmer package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); MuJoCo is not installed
where the gate runs, so nothing here compares the stand-in with the real engine or a physical device.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
#: The torso has two slide joints and one hinge joint, then j1 to j4 are hinges: 7 qpos and 7 qvel values
#: (mjrl/envs/assets/swimmer.xml:29-52).  Four motors act on j1 to j4 (mjrl/envs/assets/swimmer.xml:59-63).
NQ = 7
NV = 7
NU = 4
#: Test data: the middle of the derived -1 to 1 control interval (mjrl/envs/assets/swimmer.xml:8).
CTRL = [0.5] * NU


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MjrlSwimmerCases(unittest.TestCase):
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

    def test_the_model_shape_comes_from_the_mjcf(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 5.0)          # <option timestep="0.005"> (swimmer.xml:16)
        self.assertEqual((state["tick"], state["time_ms"], state["seed"]), (0, 0, 0))

    def test_a_step_moves_an_actuated_joint_and_advances_time(self) -> None:
        client = self.serve()
        receipt = self.step(client, CTRL, ticks=2)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["tick"], 2)
        state = self.state(client)
        self.assertEqual(state["time_ms"], 10)               # two 5 ms ticks
        # qpos[3] is joint j1, the target of the first motor (swimmer.xml:38, :60)
        self.assertGreater(state["qpos"][3], 0.0)
        self.assertEqual(state["ctrl"], CTRL)

    def test_fake_motor_controls_are_effort_not_position_targets(self) -> None:
        # Regression for the stand-in's motor semantics, not a MuJoCo trajectory assertion.
        client = self.serve()
        self.step(client, CTRL, ticks=10)
        first = self.state(client)
        self.step(client, CTRL, ticks=10)
        second = self.state(client)
        self.assertGreater(second["qvel"][3], first["qvel"][3])
        self.step(client, [0.0] * NU)
        coast = self.state(client)
        self.assertGreater(coast["qpos"][3], second["qpos"][3])
        self.assertAlmostEqual(coast["qvel"][3], second["qvel"][3])

    def test_a_wrong_number_of_controls_is_refused(self) -> None:
        client = self.serve()
        receipt = self.step(client, CTRL[:-1])
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_control_outside_the_derived_interval_is_refused(self) -> None:
        client = self.serve()
        for ctrl in ([1.5] + CTRL[1:], [-1.5] + CTRL[1:]):
            receipt = self.step(client, ctrl)
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, CTRL, ticks=3)["status"], "completed")
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 0)       # the bridge's configured seed, not the class input
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qpos"], [0.0] * NQ)
        self.assertEqual(state["qvel"], [0.0] * NV)
        self.assertEqual(state["ctrl"], [0.0] * NU)

    def test_the_fidelity_contract_is_published_for_the_fake(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "analytic:stand-in mujoco module (no physics)")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (5.0, 0, "lockstep"))
        self.assertIn("NOT COVERED", " ".join(fidelity["gaps"]))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, CTRL)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, CTRL), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
