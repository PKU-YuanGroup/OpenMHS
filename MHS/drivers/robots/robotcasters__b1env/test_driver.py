"""Acceptance run of the Unitree B1 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream module
needs pybullet, gymnasium, pinocchio and bullet_utils, which are not installed where the gate runs, and package code
never imports or runs the clone, so nothing here compares the fake with the upstream simulator.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ZERO = [0.0] * 12
# B1Env/robots/b1_raw.urdf:62: the hip effort bound, the first action element
HIP_MAX = 91.0035
# b1_env.py:39 and fake.py: TIMESTEP_S = 1/240, JOINT_INERTIA = 0.1 (placeholder test dynamics)
DT = 1.0 / 240.0
INERTIA = 0.1


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UnitreeB1Cases(unittest.TestCase):
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

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        for index in (0, 2):
            values = list(ZERO)
            values[index] = 200.0
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
            values[index] = -200.0
            refused = self.step(client, values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_the_action_has_exactly_twelve_joint_torques(self) -> None:
        client = self.serve()
        refused = self.step(client, ZERO[:11])
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_the_reset_is_the_zero_joint_state(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=3)["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), 24)
        self.assertEqual(values, [0.0] * 24)                     # b1_env.py:113-116 resets 12 joints to 0.0
        self.assertEqual(output["seed"], 3)
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(len(state["info"]["q"]), 12)            # b1_env.py:150-156 returns the q/dq info dict
        self.assertEqual(len(state["info"]["dq"]), 12)

    def test_the_first_step_matches_the_kinematic_rule(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        values = list(ZERO)
        values[0] = HIP_MAX
        receipt = self.step(client, values)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # semi-implicit Euler with the placeholder inertia 0.1 and dt = 1/240 s:
        # dq = 91.0035 / 0.1 / 240 = 3.7918125 and q = dq / 240 = 0.01579921875
        observation = output["observation"]["values"]
        self.assertAlmostEqual(observation[12], HIP_MAX / INERTIA * DT, places=9)
        self.assertAlmostEqual(observation[0], observation[12] * DT, places=12)
        self.assertEqual(observation[13:], [0.0] * 11)
        self.assertEqual((output["reward"], output["terminated"], output["truncated"]), (0.0, False, False))
        self.assertEqual(output["tick"], 1)
        self.assertEqual(self.state(client)["info"]["q"][0], observation[0])

    def test_ticks_advance_that_many_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        values = list(ZERO)
        values[0] = HIP_MAX
        output = self.step(client, values, ticks=5)["output"]
        self.assertEqual(output["tick"], 5)
        step_dq = HIP_MAX / INERTIA * DT
        self.assertAlmostEqual(output["observation"]["values"][12], 5 * step_dq, places=9)
        self.assertAlmostEqual(output["observation"]["values"][0], 15 * step_dq * DT, places=11)

    def test_the_velocity_bound_stops_the_stand_in(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        values = list(ZERO)
        values[0] = HIP_MAX
        output = self.step(client, values, ticks=10)["output"]
        self.assertEqual(output["tick"], 10)
        self.assertEqual(output["observation"]["values"][12], 19.69)   # URDF velocity bound, b1_raw.urdf:62

    def test_a_seed_does_not_change_the_reset_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=21)["output"]["observation"]
        second = self.reset(client, seed=22)["output"]["observation"]
        self.assertEqual(first, second)                          # upstream reset draws no random values
        self.assertEqual(first["values"], [0.0] * 24)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        output = self.reset(client)["output"]
        self.assertEqual(output["seed"], 21)
        self.assertEqual(output["observation"]["values"], [0.0] * 24)

    def test_reset_after_motion_returns_to_the_zero_state(self) -> None:
        client = self.serve()
        self.step(client, [HIP_MAX] + [0.0] * 11, ticks=3)
        self.assertNotEqual(self.state(client)["observation"]["values"], [0.0] * 24)
        output = self.reset(client, seed=7)["output"]
        self.assertEqual(output["observation"]["values"], [0.0] * 24)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic:B1Sim-fake", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 240.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("partial", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        state = self.state(client)
        self.assertEqual(state["tick"], 1)                       # readable, and not advanced
        self.assertEqual(len(state["observation"]["values"]), 24)


if __name__ == "__main__":
    unittest.main()
