"""Acceptance run of the humanoid_hanoi package: the gate, plus cases for what is specific to this driver.

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
#: The model's joint tree: 82 qpos and 72 qvel coordinates (base 3 slides + 1 ball, three boxes 9 slides + 3 balls,
#: 30 hinges + 6 balls) and 20 motor actuators (sim/digit_sim/digit-v3-box-tower-of-hanoi.xml:89-423).
NQ, NV, NU = 82, 72, 20
#: An in-range control vector: every actuator ctrlrange includes 0 and 0.5 (the widest is the knee +-14.4573).
MID = [0.0] * NU
TARGET = [0.5] * NU


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DigitHanoiCases(unittest.TestCase):
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
        self.assertEqual(state["timestep_ms"], 0.5)          # the model sets timestep='0.0005' at line 3
        self.assertEqual((state["time_ms"], state["tick"], state["seed"]), (0, 0, 0))

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, MID, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        for index, value in ((0, 2.0), (2, 20.0), (5, -1.0)):
            refused = self.step(client, MID[:index] + [value] + MID[index + 1:])
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)       # the refused steps changed nothing

    def test_a_step_moves_the_actuated_joints(self) -> None:
        client = self.serve()
        initial = self.state(client)["qpos"]
        receipt = self.step(client, TARGET, ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        observation = output["observation"]
        self.assertEqual(output["tick"], 2)
        self.assertAlmostEqual(observation["time"], 0.001)    # two ticks of the 0.0005 s model step
        self.assertNotEqual(observation["qpos"], initial)
        state = self.state(client)
        self.assertEqual(state["ctrl"], TARGET)
        self.assertEqual(state["time_ms"], 1)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        initial = self.state(client)["qpos"]
        self.step(client, TARGET, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client)["output"]
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qpos"], initial)
        self.assertEqual(state["qvel"], [0.0] * NV)
        self.assertEqual(state["ctrl"], [0.0] * NU)
        self.assertEqual(output["observation"]["qpos"], initial)
        self.assertEqual(output["seed"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:digit", "F1"))
        self.assertEqual(fidelity["timestep_ms"], 0.5)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertEqual((fidelity["determinism"]["kind"], fidelity["determinism"]["seed_control"]),
                         ("seeded", "none"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, MID)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, MID), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
