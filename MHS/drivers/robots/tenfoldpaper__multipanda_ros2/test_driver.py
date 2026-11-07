"""Acceptance run of the multipanda_ros2 MuJoCo world package.

The gate call is kept unchanged; these cases add repository-specific coverage
for the dual scene.  Every number below is test data, not a bound or a fact of
the model.  The fake backend parses the MJCF but does not run MuJoCo, so these
cases say nothing about the real engine or hardware.

Since the model review of 2026-11-05 the fake reports the model's 44 actuator
channels.  The 28 servo channels declare no ctrlrange, so the bridge publishes
them operator_required: a step that sets them is refused LIMITS_UNSET until an
operator overlay bounds them.  The cases that step with a control vector serve
the package's site-limits.example.json (operator example data), as the gate's
conformance run does.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.driver.loader import driver_class
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
DRIVER = driver_class(HERE)
MODEL_PATH = DRIVER.model_path
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
EXAMPLE_OVERLAY = HERE / "site-limits.example.json"
#: Seven hinges and two finger slides per arm, then the free box joint.
NQ = 25
#: Seven hinges and two finger slides per arm, then the free box joint.
NV = 24
#: The 44 model channels in document order (mj_dual.xml:452-506): per arm seven
#: torque motors, seven position servos, seven velocity servos (no ctrlrange)
#: and one gripper.  Left arm 0-21 (gripper 21), right arm 22-43 (gripper 43).
NU = 44
ZERO = [0.0] * NU
#: Per arm: seven ctrl-limited torque motors, fourteen servos without a ctrlrange, one limited gripper.
LIMITED = ([True] * 7 + [False] * 14 + [True]) * 2
#: The servo channels the bridge publishes operator_required: 7-20 (left) and 29-42 (right).
SERVOS = [index for index, limited in enumerate(LIMITED) if not limited]
#: Test data: zero, except the position targets of joints 4 and 6 (channels 10, 12, 32, 34), which the example
#: overlay bounds by the joint ranges (-3.0421..-0.1518 and 0.5445..4.5169) that exclude zero.
HOLD = list(ZERO)
for _index, _value in ((10, -1.5), (12, 1.5), (32, -1.5), (34, 1.5)):
    HOLD[_index] = _value
#: qpos0 of the free box joint (objects.xml:4-6): its body position and the identity quaternion.
BOX_QPOS0 = [0.5, -0.13, 0.061, 1.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MultipandaWorldCases(unittest.TestCase):
    def serve(self, overlay=True):
        server = load(HERE, backend="fake", site_limits=EXAMPLE_OVERLAY if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"ctrl": list(ctrl)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_comes_from_the_card_model(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (NQ, NV))
        self.assertEqual(len(state["ctrl"]), NU)
        self.assertEqual(state["timestep_ms"], 2.0)  # mj_dual.xml:4
        self.assertEqual(state["tick"], 0)

    def test_a_step_is_bounded_by_the_actuator_control_ranges(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HOLD, ticks=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 2)
        # the model's ranges (torque 0, 4, 22; gripper 21, 43), then the example overlay (servos 7, 14, 42)
        probes = ((0, 88.0), (4, 13.0), (21, 256.0), (21, -1.0), (22, -88.0), (43, 256.0),
                  (7, 2.75), (14, -2.2), (42, 2.62))
        for index, value in probes:
            ctrl = HOLD[:index] + [value] + HOLD[index + 1:]
            refused = self.step(client, ctrl)
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
            self.assertEqual(refused["error"]["details"]["path"], f"action.ctrl[{index}]", (index, value))
        self.assertEqual(self.state(client)["tick"], 2)  # refused steps changed nothing

    def test_the_servo_channels_need_an_operator_bound(self) -> None:
        client = self.serve(overlay=False)
        step = next(item for item in client.inspect(self.ids["device_id"])["capabilities"]
                    if item["capability_id"] == "cap.world.step.v1")
        limits = step["limits"]
        self.assertEqual(sorted(path for path, rule in limits.items() if rule == "operator_required"),
                         sorted(f"action.ctrl[{index}]" for index in SERVOS))
        self.assertEqual((limits["action.ctrl[0]"]["min"], limits["action.ctrl[0]"]["max"]), (-87.0, 87.0))
        self.assertEqual(limits["action.ctrl[21]"]["source"], "upstream_code")
        refused = self.step(client, HOLD)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], UNSET)
        self.assertEqual(self.state(client)["tick"], 0)  # refused before the native step
        ticked = client.invoke("cap.world.step.v1", {"ticks": 2}, **self.ids)  # no action: the controls stay
        self.assertEqual(ticked["status"], "completed", ticked)
        self.assertEqual(self.state(client)["tick"], 2)

    def test_the_fake_reports_every_model_channel_in_document_order(self) -> None:
        fake = DRIVER.backends["fake"]()
        model = fake.MjModel.from_xml_path((HERE / MODEL_PATH).resolve())
        self.assertEqual(model.nu, NU)
        self.assertEqual(list(model.actuator_ctrllimited), LIMITED)
        self.assertEqual([actuator["name"] for actuator in model.actuators][7:9],
                         ["mj_left_act_pos1", "mj_left_act_pos2"])
        self.assertEqual(model.actuator_ctrlrange[7], [0.0, 0.0])    # no ctrlrange, as MuJoCo compiles it
        self.assertEqual(model.actuator_ctrlrange[21], [0.0, 255.0])  # the left gripper

    def test_the_state_follows_the_control_value(self) -> None:
        client = self.serve()
        ctrl = list(HOLD)
        ctrl[0] = 10.0    # left torque 1, ctrlrange -87 87
        ctrl[21] = 128.0  # left gripper, ctrlrange 0 255
        first = self.step(client, ctrl)["output"]["observation"]
        second = self.step(client, ctrl)["output"]["observation"]
        self.assertNotEqual(first["qpos"], second["qpos"])
        self.assertEqual(second["time"], 0.004)
        self.assertGreater(second["qpos"][0], 0.0)

    def test_a_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        initial = self.state(client)["qpos"]
        self.assertEqual(initial, [0.0] * (NQ - 7) + BOX_QPOS0)  # qpos0: zero joints, the box at its body pose
        ctrl = list(HOLD)
        ctrl[0] = 5.0
        self.assertEqual(self.step(client, ctrl, ticks=3)["status"], "completed")
        self.assertNotEqual(self.state(client)["qpos"], initial)
        output = client.invoke("cap.world.reset.v1", {}, **self.ids)["output"]
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(output["observation"]["qpos"], initial)
        self.assertEqual(output["observation"]["time"], 0.0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic:fake-mjcf-parser", "F0"))
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        ctrl = list(HOLD)
        ctrl[0] = 2.0
        self.assertEqual(self.step(client, ctrl)["status"], "completed")
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        for refused in (self.step(client, ctrl), client.invoke("cap.world.reset.v1", {}, **self.ids)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
