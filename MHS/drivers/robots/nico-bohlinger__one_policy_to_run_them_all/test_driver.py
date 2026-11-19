"""Acceptance run of the one_policy_to_run_them_all package: the gate, plus cases for what is specific to this driver.

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
NQ = 19          # 7 values of the free base plus 12 hinge joints (anymal_b.xml:132,150-314)
NV = 18          # 6 velocities of the free base plus 12 hinge joints
NU = 12          # twelve motors (anymal_b.xml:340-351)
MODEL_QPOS0 = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0] + [0.0] * NU
#: In-range control vector for the twelve motors, whose ctrlrange is -40 to 40 (anymal_b.xml:56).
ZERO = [0.0] * NU
PUSH = [10.0] * NU


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AnymalBCases(unittest.TestCase):
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

    def test_the_model_shape_comes_from_the_card_model(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (NQ, NV, NU))
        self.assertEqual(state["qpos"], MODEL_QPOS0)            # the compiled model defaults of anymal_b.xml
        self.assertEqual(state["timestep_ms"], 2.0)             # MuJoCo's default; the MJCF states no timestep
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, PUSH, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        for index, value in ((0, 40.5), (5, -40.5), (11, 41.0)):
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
        self.assertEqual(first["observation"]["qpos"], MODEL_QPOS0)
        receipt = self.step(client, PUSH, ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertEqual(output["observation"]["time"], 0.004)  # two ticks of the model's 0.002 s step
        self.assertGreater(output["observation"]["qpos"][7], 0.0)  # LF_HAA moves with its positive control
        later = self.step(client, PUSH)
        self.assertNotEqual(later["output"]["state_hash"], output["state_hash"])

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, PUSH, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qpos"], MODEL_QPOS0)
        self.assertEqual(state["qvel"], [0.0] * NV)
        self.assertEqual(state["ctrl"], [0.0] * NU)

    def test_the_reset_seed_is_recorded_but_does_not_change_the_model(self) -> None:
        client = self.serve()
        first = self.reset(client)["output"]
        self.assertEqual(first["observation"]["qpos"], MODEL_QPOS0)
        seeded = self.reset(client, seed=7)
        self.assertEqual(seeded["status"], "completed")
        self.assertEqual(seeded["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:stand-in mujoco module (no physics)", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (2.0, 0, "lockstep"))
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
