"""Acceptance run of the OMY tabletop package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): MuJoCo itself is not installed and cannot be installed where the gate
runs (no network, no pip), so nothing here compares the stand-in with the real engine.  The model file is the card's
first model in the read-only clone, and the fake derives its shape from that file.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CLONE = HERE.parents[3] / "robots" / "jeongeun980906" / "lerobot-mujoco-tutorial"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
NQ = 10          # ten hinge joints: joint1-joint6 and rh_r1, rh_r2, rh_l1, rh_l2
NV = 10          # the same ten hinge joints
NU = 10          # ten position actuators in asset/robotis_omy/omy.xml:106-117
#: An in-range control vector: every actuator target starts at zero, so zero is a test input, not a device fact.
ZERO_CTRL = [0.0] * NU
#: A test target for the first arm actuator (ctrlrange -6.28319 to 6.28319); not a device fact.
FIRST_CTRL = [0.5] + [0.0] * (NU - 1)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OmySceneCases(unittest.TestCase):
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
        self.assertEqual(state["timestep_ms"], 2.0)
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
        outside[0] = -6.29                                   # the arm ctrlrange starts at -6.28319
        refused = self.step(client, outside)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)
        outside = list(ZERO_CTRL)
        outside[6] = -0.1                                    # the rh_r1 ctrlrange starts at 0
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
        self.assertAlmostEqual(output["observation"]["time"], 0.004, places=12)   # two 2 ms ticks
        self.assertGreater(output["observation"]["qpos"][0], 0.0)
        self.assertGreater(output["observation"]["qvel"][0], 0.0)
        state = self.state(client)
        self.assertEqual(state["tick"], 2)
        self.assertEqual(state["time_ms"], 4)

    def test_a_reset_restores_the_model_defaults(self) -> None:
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

    def test_the_fake_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:stand-in mujoco module (no MuJoCo engine)", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, FIRST_CTRL)["status"], "completed")
        before = self.state(client)
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        for refused in (self.step(client, ZERO_CTRL), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["ctrl"], FIRST_CTRL)
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        after_release = self.state(client)
        for field in ("tick", "time_ms", "qpos", "qvel", "ctrl"):
            self.assertEqual(after_release[field], before[field], field)
        # The latch did not clear stored targets.  Only this new explicit step resumes integration.
        resumed = client.invoke("cap.world.step.v1", {"ticks": 1}, **self.ids)
        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(self.state(client)["ctrl"], FIRST_CTRL)
        self.assertGreater(self.state(client)["qpos"][0], before["qpos"][0])

    def test_the_card_entry_symbols_exist_in_the_readonly_clone(self) -> None:
        first = (CLONE / "mujoco_env" / "y_env.py").read_text(encoding="utf-8").splitlines()
        second = (CLONE / "mujoco_env" / "y_env2.py").read_text(encoding="utf-8").splitlines()
        self.assertEqual(first[12], "class SimpleEnv:")
        self.assertEqual(second[12], "class SimpleEnv2:")
        self.assertTrue((CLONE / "asset" / "robotis_omy" / "scene.xml").is_file())


if __name__ == "__main__":
    unittest.main()
