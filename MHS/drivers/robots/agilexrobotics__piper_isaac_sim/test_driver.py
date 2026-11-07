"""Acceptance run of the AgileX PiPER Isaac Sim description package: the gate, plus driver-specific cases.

Add cases, never remove the ``check_driver`` call.  The cases run on the fake backend (``fake.py``): MuJoCo itself is
not installed where the gate runs, so nothing here compares the stand-in with the real engine.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: The MJCF has six hinge joints and two slide joints, each one qpos and one qvel
#: (piper_description/mujoco_model/piper_description.xml:18-50), and eight position actuators (:60-69).
NQ = 8
NV = 8
NU = 8
#: placeholder: a target inside joint2's 0..3.14158 control interval.
TARGET = [0.0] * NU
TARGET[1] = 0.5


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PiperIsaacSimCases(unittest.TestCase):
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
        args = {"ticks": ticks}
        if ctrl is not None:
            args["action"] = {"ctrl": list(ctrl)}
        return client.invoke("cap.world.step.v1", args, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_mjcf(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 2.0)          # the MJCF sets no <option>; the stand-in default
        self.assertEqual(state["tick"], 0)

    def test_each_actuator_ctrlrange_is_enforced_before_mutation(self) -> None:
        client = self.serve()
        # One element from each of four ctrlrange groups in the model: joint1 2.618, joint3 -2.697,
        # joint7 0..0.0475 and joint8 -0.0475..0.
        for index, value in ((0, 2.619), (2, 0.001), (6, -0.001), (7, 0.001)):
            ctrl = [0.0] * NU
            ctrl[index] = value
            receipt = self.step(client, ctrl)
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, (index, receipt))
        self.assertEqual(self.state(client)["tick"], 0)      # no refused step advanced the world

    def test_values_on_the_model_ctrlrange_are_accepted(self) -> None:
        client = self.serve()
        ctrl = [2.618, 3.14158, -2.697, 1.832, 1.22, 3.14158, 0.0475, -0.0475]
        receipt = self.step(client, ctrl)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_step_advances_time_and_moves_the_actuated_joint(self) -> None:
        client = self.serve()
        first = self.step(client, TARGET)["output"]["observation"]
        second = self.step(client, TARGET)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertEqual(second["time"], 0.004)              # two ticks of the stand-in's 2 ms step
        self.assertGreater(second["qpos"][1], 0.0)           # joint2 moves toward its positive target
        self.assertEqual(self.state(client)["tick"], 2)

    def test_a_step_without_an_action_is_allowed(self) -> None:
        client = self.serve()
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertEqual(self.state(client)["ctrl"], [0.0] * NU)

    def test_a_short_ctrl_vector_is_refused(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0] * (NU - 1))
        self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, TARGET, ticks=3)
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.reset(client, seed=7)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"], [0.0] * NQ)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["seed"], 0)                  # the bridge's configured seed, not the class input

    def test_a_snapshot_restores_the_advertised_state(self) -> None:
        client = self.serve()
        before = self.state(client)
        saved = client.snapshot(**self.ids)
        self.assertEqual(saved["state"]["world"], before)
        self.step(client, TARGET)
        restored = client.restore(saved, **self.ids)
        self.assertEqual(restored["status"], "completed", restored)
        self.assertEqual(self.state(client), before)

    def test_the_fidelity_contract_is_published(self) -> None:
        # The fake backend is a stand-in with no dynamics, so it publishes the F0 contract; the F1 MuJoCo contract
        # belongs to the real engine path, which was not run (reviewer change).
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:stand-in mujoco module (no physics)", "F0"))
        self.assertEqual(fidelity["timestep_ms"], 2.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        real = type(driver).fidelity
        self.assertEqual((real["engine"], real["fidelity_level"]), ("mujoco:piper_description", "F1"))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * NU)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * NU), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
