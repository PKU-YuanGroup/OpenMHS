"""Acceptance run of the FlyGym fruitfly package: the gate, plus cases for what is specific to this driver.

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
#: The served fruitfly.xml has one free joint (7 qpos, 6 qvel), 102 hinge joints and 78 actuators
#: (fruitfly.xml:299-300, 943-1021); these are model counts, not limits.
NQ = 109
NV = 108
NU = 78
#: An in-range control vector: every actuator ctrlrange in the model contains 0.01 (fruitfly.xml:943-1021).
TARGET = [0.01] * NU


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FruitflyCases(unittest.TestCase):
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
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (NQ, NV, NU))
        self.assertEqual(state["tick"], 0)
        self.assertAlmostEqual(state["timestep_ms"], 0.1, places=9)   # 0.0001 s (fruitfly.xml:4)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, TARGET, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        # head_abduct -0.2..0.2, head_twist -3..3 and the last adhesion actuator 0..1 (fruitfly.xml:943-1021).
        for index, value in ((0, 0.3), (1, 3.5), (NU - 1, 1.5)):
            refused = self.step(client, TARGET[:index] + [value] + TARGET[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_the_state_follows_the_control_value(self) -> None:
        client = self.serve()
        first = self.step(client, TARGET)["output"]["observation"]
        second = self.step(client, TARGET)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertAlmostEqual(second["time"], 0.0002, places=12)   # two ticks of the 0.1 ms step
        self.assertTrue(any(value != 0.0 for value in second["qpos"]))

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, TARGET, ticks=3)
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"], [0.0] * NQ)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["seed"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:fruitfly", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertAlmostEqual(fidelity["timestep_ms"], 0.1, places=9)
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, TARGET)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, TARGET), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)           # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
