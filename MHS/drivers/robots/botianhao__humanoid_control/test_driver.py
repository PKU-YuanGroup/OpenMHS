"""Acceptance run of the botianhao__humanoid_control package: the gate, plus cases for this driver.

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
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
NQ = 19          # 7 values of the free base plus 12 hinge joints (humanoid_legged_control_.xml:71,103-164)
NV = 18          # 6 velocities of the free base plus 12 hinge joints
NU = 12          # twelve motor actuators (humanoid_legged_control_.xml:179-192)
#: In-range control vector for the twelve motors; the smallest ctrlrange is -90 to 90 (lines 184-185,190-191).
PUSH = [50.0] * NU
ZERO = [0.0] * NU
#: mj_resetData restores model.qpos0: the root body position and identity quaternion, then twelve zero hinges.
QPOS0 = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0] + [0.0] * 12


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HumanoidControlCases(unittest.TestCase):
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
        self.assertEqual(state["timestep_ms"], 1.0)            # the MJCF's own timestep 0.001 s (line 4)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["qpos"], QPOS0)                 # freejoint root at the body pose, hinges at zero

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, PUSH, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        for index, value in ((0, -150.5), (0, 150.5), (2, 200.5), (4, 90.5), (11, -90.5)):
            refused = self.step(client, PUSH[:index] + [value] + PUSH[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)         # the refused steps changed nothing

    def test_the_control_vector_has_one_value_per_actuator(self) -> None:
        client = self.serve()
        for ctrl in (ZERO[:-1], ZERO + [0.0]):
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_a_step_advances_the_integration_state(self) -> None:
        client = self.serve()
        first = self.reset(client)["output"]
        self.assertEqual(first["observation"]["time"], 0.0)
        self.assertEqual(first["observation"]["qpos"], QPOS0)
        receipt = self.step(client, PUSH, ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertEqual(output["observation"]["time"], 0.002)  # two ticks of the model's 0.001 s step
        self.assertGreater(output["observation"]["qpos"][7], 0.0)   # leg_l1_joint moves with its positive control
        self.assertEqual(output["observation"]["qvel"][6], 50.0 * 1e-4)  # placeholder gain of the stand-in

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, PUSH, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["time_ms"], 0)
        self.assertEqual(state["qpos"], QPOS0)
        self.assertEqual(state["qvel"], [0.0] * NV)
        self.assertEqual(state["ctrl"], [0.0] * NU)

    def test_the_reset_seed_is_recorded_but_does_not_change_the_model(self) -> None:
        client = self.serve()
        first = self.reset(client)["output"]
        self.assertEqual(first["observation"]["qpos"], QPOS0)
        seeded = client.invoke("cap.world.reset.v1", {"seed": 7}, **self.ids)
        self.assertEqual(seeded["status"], "completed")
        self.assertEqual(seeded["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        # The fake backend is the stand-in module: it publishes its own F0 contract, not the real engine's F1.
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:stand-in mujoco module (no physics)", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (1.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, PUSH)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, PUSH), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)         # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
