"""Acceptance run of the AutoBio DexHand021 package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): MuJoCo itself is not installed and cannot be installed where the gate
runs (no network, no pip), so nothing here compares the stand-in with the real engine.  The model file is the card's
first model in the read-only clone, and the fake derives its shape from that file.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
NQ = 19          # 19 hinge joints in autobio/model/hand/dexhand021_right.xml:42-144
NV = 19          # the same 19 hinge joints
NU = 12          # 12 position actuators in autobio/model/hand/dexhand021_right.xml:208-220
#: An in-range control vector: the model's actuators all start at zero, so zero is a test input, not a device fact.
ZERO_CTRL = [0.0] * NU
#: A test control that moves the first directly actuated joint (rh_thj1, ctrlrange 0 2.2); not a device fact.
FIRST_CTRL = [1.0] + [0.0] * (NU - 1)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DexhandCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl or ZERO_CTRL)}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_card_model(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (NQ, NV, NU))
        self.assertEqual(state["timestep_ms"], 10.0)          # autobio/model/hand/dexhand021_right.xml:5
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["time_ms"], 0)

    def test_the_control_vector_has_one_element_per_actuator(self) -> None:
        client = self.serve()
        for ctrl in ([0.0] * (NU - 1), [0.0] * (NU + 1)):
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected", len(ctrl))
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, len(ctrl))
        self.assertEqual(self.state(client)["tick"], 0)       # the refused steps changed nothing

    def test_the_control_range_is_the_model_envelope(self) -> None:
        client = self.serve()
        outside = list(ZERO_CTRL)
        outside[0] = -0.1                                    # rh_thj1 ctrlrange is 0 2.2
        refused = self.step(client, outside)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(self.step(client, FIRST_CTRL)["status"], "completed")

    def test_a_step_advances_the_integration_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, FIRST_CTRL, ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertAlmostEqual(output["observation"]["time"], 0.02, places=9)   # two 0.01 s ticks
        self.assertGreater(output["observation"]["qpos"][0], 0.0)               # rh_thj1 moved
        self.assertGreater(output["observation"]["qvel"][0], 0.0)
        state = self.state(client)
        self.assertEqual(state["tick"], 2)
        self.assertEqual(state["time_ms"], 20)

    def test_a_reset_restores_the_model_defaults_and_echoes_the_bridge_seed(self) -> None:
        client = self.serve()
        self.step(client, FIRST_CTRL, ticks=3)
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # the reset input accepts a seed for the class contract, but a MuJoCo reset restores the model defaults and
        # does not use it; the output carries the bridge's configured seed (0)
        self.assertEqual(output["seed"], 0)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["observation"]["qpos"][0], 0.0)
        self.assertEqual(self.reset(client)["output"]["observation"], output["observation"])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:dexhand021_right_sim", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_CTRL)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_CTRL), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
