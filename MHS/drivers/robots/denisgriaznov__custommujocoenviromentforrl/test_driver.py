"""Acceptance run of the BallBalance package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo is not
installed where the gate runs, so nothing here compares the stand-in with the real engine.  The model shape and the
per-actuator control ranges are read from the clone's MJCF; the start positions are the model's reference
configuration, not invented numbers.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
#: Two hinge joints and one free joint: qpos 2 + 7 = 9, qvel 2 + 6 = 8 (assets/ball_balance.xml:13-20).
NQ = 9
NV = 8
#: Two general actuators, ctrlrange -1 to 1 (assets/ball_balance.xml:25-27).
NU = 2
#: The model reference configuration: hinges at zero, the ball at its body pos .2 .2 .4 with an identity quaternion.
QPOS0 = [0.0, 0.0, 0.2, 0.2, 0.4, 1.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BallBalanceCases(unittest.TestCase):
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
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (NQ, NV, NU))
        self.assertEqual(state["qpos"], QPOS0)
        self.assertEqual(state["qvel"], [0.0] * NV)
        self.assertEqual(state["timestep_ms"], 2.0)          # the model sets no timestep: the library default
        self.assertEqual(state["tick"], 0)

    def test_each_actuator_is_bounded_by_its_ctrlrange(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        for index, value in ((0, 1.5), (0, -2.0), (1, 1.5), (1, -2.0)):
            ctrl = [0.0, 0.0]
            ctrl[index] = value
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 1)       # the refused steps changed nothing

    def test_a_ctrl_of_the_wrong_length_is_refused(self) -> None:
        client = self.serve()
        refused = self.step(client, [0.0])
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_step_advances_time_and_the_hinges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, [0.5, -0.5], ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertAlmostEqual(output["observation"]["time"], 0.004)          # two ticks of the 2 ms step
        self.assertAlmostEqual(output["observation"]["qpos"][0], 0.001)      # placeholder dynamics, test data
        self.assertAlmostEqual(output["observation"]["qpos"][1], -0.001)     # placeholder dynamics, test data
        self.assertEqual(output["observation"]["qpos"][2:4], QPOS0[2:4])      # the ball keeps its x and y
        self.assertLess(output["observation"]["qpos"][4], QPOS0[4])           # and falls along z
        self.assertEqual(output["observation"]["qpos"][5:], [1.0, 0.0, 0.0, 0.0])
        self.assertEqual(self.state(client)["tick"], 2)
        self.assertEqual(self.state(client)["ctrl"], [0.5, -0.5])

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, [0.5, 0.5], ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client, seed=7)["output"]
        self.assertEqual(output["observation"]["qpos"], QPOS0)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["seed"], 0)                  # the bridge's configured seed, not the class input
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:ball_balance", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0]), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
