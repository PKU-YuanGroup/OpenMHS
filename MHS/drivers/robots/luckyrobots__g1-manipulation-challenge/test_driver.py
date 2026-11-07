"""Acceptance run of the Lucky Robots G1 package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): MuJoCo itself is not installed and cannot be installed where the gate
runs (no network, no pip), so nothing here compares the stand-in with the real engine.  The model file is the card's
first model, scene.xml, read from the read-only clone; the fake derives its shape from that scene and its g1.xml
include.  The numbers below are test inputs, not device facts.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
#: The scene has two free joints (7 qpos, 6 qvel each) and 43 hinge joints (g1.xml:81-85, scene.xml:80-81).
NQ = 57
NV = 55
#: 29 body position actuators and 14 finger position actuators (g1.xml:400-449).
NU = 43
#: Test controls, not device facts: zero is inside every joint range, and 0.5 is inside the left hip pitch range.
ZERO_CTRL = [0.0] * NU
BODY_TARGET = [0.5] + [0.0] * (NU - 1)
#: The left hip pitch joint range is -2.5307..2.8798 rad (g1.xml:93); 3.0 is outside it.
OUTSIDE_BODY = [3.0] + [0.0] * (NU - 1)
UNDER_BODY = [-3.0] + [0.0] * (NU - 1)
#: A finger control target; the MJCF states no ctrlrange for the 14 finger actuators (g1.xml:435-449), so they are
#: operator_required; the example overlay bounds them by the matching joint range (left thumb 0 is -1.0472..1.0472,
#: g1.xml:254).
FINGER_TARGET = [0.0] * 29 + [0.5] + [0.0] * (NU - 30)
FINGER_OUTSIDE = [0.0] * 29 + [2.0] + [0.0] * (NU - 30)
#: The model defaults of the two free bodies: pelvis at -0.6 0 0.79 (g1.xml:81), red block at 0.0 0.026 0.85
#: (scene.xml:80), both with the identity quaternion.
PELVIS_START = [-0.6, 0.0, 0.79, 1.0, 0.0, 0.0, 0.0]
BLOCK_START = [0.0, 0.026, 0.85, 1.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LuckyRobotsG1Cases(unittest.TestCase):
    def serve(self, overlay=True):
        server = load(HERE, backend="fake", site_limits=HERE / "site-limits.example.json" if overlay else None)
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

    def test_the_model_shape_comes_from_the_card_scene(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (NQ, NV, NU))
        self.assertEqual(state["timestep_ms"], 5.0)          # <option timestep="0.005"> (g1.xml:4)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))

    def test_the_start_pose_is_the_model_default(self) -> None:
        client = self.serve()
        qpos = self.state(client)["qpos"]
        self.assertEqual(qpos[:7], PELVIS_START)             # the g1 free joint (g1.xml:81-85)
        self.assertEqual(qpos[-7:], BLOCK_START)             # the red block free joint (scene.xml:80-81)

    def test_the_control_vector_has_one_element_per_actuator(self) -> None:
        client = self.serve()
        for ctrl in ([0.0] * (NU - 1), [0.0] * (NU + 1)):
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected", len(ctrl))
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, len(ctrl))
        self.assertEqual(self.state(client)["tick"], 0)       # the refused steps changed nothing

    def test_the_body_control_range_is_the_joint_range(self) -> None:
        client = self.serve()
        for outside in (OUTSIDE_BODY, UNDER_BODY):
            refused = self.step(client, outside)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
            self.assertEqual(refused["error"]["details"]["path"], "action.ctrl[0]")
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(self.step(client, BODY_TARGET)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_finger_controls_need_an_operator_bound(self) -> None:
        # the 14 finger actuators have no ctrlrange in the MJCF (g1.xml:435-449): without an overlay a step that
        # sets them is refused LIMITS_UNSET before the engine runs; a step without an action still advances
        bare = self.serve(overlay=False)
        step = next(item for item in bare.inspect(self.ids["device_id"])["capabilities"]
                    if item["capability_id"] == "cap.world.step.v1")
        self.assertEqual(sorted(path for path, rule in step["limits"].items() if rule == "operator_required"),
                         sorted(f"action.ctrl[{index}]" for index in range(29, 43)))
        self.assertEqual(step["limits"]["action.ctrl[0]"]["source"], "upstream_code")
        refused = self.step(bare, ZERO_CTRL)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET", refused)
        ticked = bare.invoke("cap.world.step.v1", {"ticks": 1}, **self.ids)
        self.assertEqual(ticked["status"], "completed", ticked)

    def test_the_example_overlay_bounds_the_finger_controls(self) -> None:
        client = self.serve()
        # the example overlay bounds action.ctrl[29] by the left thumb 0 joint range (operator data)
        refused = self.step(client, FINGER_OUTSIDE)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(refused["error"]["details"]["path"], "action.ctrl[29]")
        self.assertEqual(refused["error"]["details"]["provenance"]["source"], "operator")
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(self.step(client, FINGER_TARGET)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_step_advances_the_integration_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, BODY_TARGET, ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertAlmostEqual(output["observation"]["time"], 0.01, places=9)   # two 0.005 s ticks
        self.assertGreater(output["observation"]["qpos"][7], 0.0)               # left hip pitch moved
        self.assertGreater(output["observation"]["qvel"][6], 0.0)
        state = self.state(client)
        self.assertEqual(state["tick"], 2)
        self.assertEqual(state["time_ms"], 10)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.step(client, BODY_TARGET, ticks=3)
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # the reset input accepts a seed for the class contract, but a MuJoCo reset restores the model defaults and
        # does not use it; the output carries the bridge's configured seed (0)
        self.assertEqual(output["seed"], 0)
        self.assertEqual(output["observation"]["time"], 0.0)
        self.assertEqual(output["observation"]["qpos"][:7], PELVIS_START)
        self.assertEqual(output["observation"]["qpos"][7], 0.0)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:g1_table_red_block", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (5.0, 0, "lockstep"))
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
