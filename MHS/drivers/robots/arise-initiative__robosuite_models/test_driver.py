"""Acceptance run of the robosuite_models Aloha package: the gate, plus cases for what is specific to this driver.

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
#: The served robot.xml has 12 hinge joints (six per arm) and 12 motor actuators (robot.xml:92-116, 139-164,
#: 188-201); these are model counts, not limits.
NQ = 12
NU = 12
#: An in-range control vector: waist +-5, shoulder +-50, elbow +-50, forearm_roll +-5, wrist_angle +-1,
#: wrist_rotate +-1, repeated for the left arm (robot.xml:189-201).
TARGET = [1.0, 10.0, -10.0, 1.0, 0.5, -0.5] * 2


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AlohaCases(unittest.TestCase):
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
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (NQ, NQ, NU))
        self.assertEqual(state["tick"], 0)
        # The model sets no timestep (robot.xml:2-4); the stand-in uses MuJoCo's library default of 2 ms as a
        # placeholder (fake.py), and the bridge publishes the stand-in's value.
        self.assertEqual(state["timestep_ms"], 2.0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, TARGET, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        for index, value in ((0, 5.5), (1, 50.5), (4, 1.5), (11, -1.5)):
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
        self.assertAlmostEqual(second["time"], 0.004, places=9)   # two ticks of the 2 ms step
        self.assertGreater(second["qpos"][0], 0.0)               # the joint moves toward its positive control
        self.assertLess(second["qpos"][2], 0.0)                  # and the negative one toward its negative control

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
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:aloha", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertEqual(fidelity["timestep_ms"], 2.0)
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
