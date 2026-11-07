"""Acceptance run of the mcp_robot package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): its ``_commands`` list
is what reached the "bus".  Nothing here ran on a real arm, and no hardware was attached.
"""

import json
import math
import tempfile
import unittest
from pathlib import Path

from mhs.adapter import LoadError, load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
FAULTED = "MHS.DEVICE.FAULTED"
REENABLE = "x-cap.itheima1.enable_all_torque.v1"

PI = math.pi
TOLERANCE_RAD = PI / 2048.0
SERVO_IDS = [1, 2, 3, 4, 5, 6]
START_RAD = [math.pi / 2] * 6                       # the fake's placeholder start: every servo at 90 degrees
HOME_RAD = [math.radians(value) for value in (90, 0, 180, 180, 90, 90)]
HOME_POSITIONS = {1: 2048, 2: 1024, 3: 3072, 4: 3072, 5: 2048, 6: 2048}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class McpRobotCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.robot = driver.native                              # the fake ServoControllerStandalone
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.robot._commands[:]
        return self.client

    def move(self, positions):
        return self.client.invoke("cap.motion.joint_position.v1", {"joint_positions": positions}, **self.ids)

    def home(self, **payload):
        return self.client.invoke("cap.motion.home.v1", payload, **self.ids)

    def disable(self):
        return self.client.invoke("x-cap.itheima1.disable_all_torque.v1", {}, **self.ids)

    def enable(self):
        return self.client.invoke(REENABLE, {}, **self.ids)

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def sent(self, name=None):
        return [(command, args) for command, args in self.robot._commands if name is None or command == name]

    # -- reading ---------------------------------------------------------------------------------------------------
    def test_the_read_returns_radians_from_the_servo_degrees(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual(len(state["joint_positions"]), 6)
        for value in state["joint_positions"]:
            self.assertAlmostEqual(value, math.pi / 2, places=12)
        self.assertEqual(self.sent("get_multiple_servo_angles")[0][1]["servo_ids"], SERVO_IDS)
        self.assertAlmostEqual(self.robot.get_servo_angle(1), 90.0, places=12)

    # -- joint motion ----------------------------------------------------------------------------------------------
    def test_a_joint_move_goes_out_in_degrees_and_changes_the_state(self) -> None:
        self.serve()
        target = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        receipt = self.move(target)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertTrue(output["reached"])
        self.assertAlmostEqual(output["tolerance_rad"], TOLERANCE_RAD)
        for actual, wanted in zip(output["joint_positions"], target):
            self.assertAlmostEqual(actual, wanted, delta=TOLERANCE_RAD + 1e-12)
        [(name, args)] = self.sent("set_multiple_servo_angles")
        self.assertEqual(args["speed"], 0)
        for servo_id, wanted in zip(SERVO_IDS, target):
            self.assertAlmostEqual(args["angles"][servo_id], math.degrees(wanted), places=12)
        for actual, wanted in zip(self.state()["joint_positions"], target):
            self.assertAlmostEqual(actual, wanted, delta=TOLERANCE_RAD + 1e-12)

    def test_the_joint_limit_is_per_joint(self) -> None:
        self.serve()
        over = list(START_RAD)
        over[1] = PI + 0.01
        refused = self.move(over)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        details = refused["error"]["details"]
        self.assertEqual((details["path"], details["element_name"]), ("joint_positions[1]", "joint2"))
        self.assertAlmostEqual(details["bound"], PI)
        self.assertEqual(details["provenance"]["ref"], "sources/servo_control_standalone.py:462-471")
        under = list(START_RAD)
        under[0] = -0.01
        self.assertEqual(self.move(under)["error"]["details"]["path"], "joint_positions[0]")
        self.assertEqual(self.move([-0.01] + list(START_RAD[1:]))["status"], "rejected")
        self.assertEqual(self.sent("set_multiple_servo_angles"), [])
        for edge in (0.0, PI):
            receipt = self.move([edge] * 6)
            self.assertEqual(receipt["status"], "completed", receipt)

    def test_the_home_action_writes_the_upstream_pose(self) -> None:
        self.serve()
        receipt = self.home()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["homed"])
        for actual, wanted in zip(receipt["output"]["joint_positions"], HOME_RAD):
            self.assertAlmostEqual(actual, wanted, delta=TOLERANCE_RAD + 1e-12)
        [(name, args)] = self.sent("go_home")
        self.assertEqual(args["speed"], 0)
        [(name, args)] = self.sent("sync_set_positions")
        self.assertEqual(args["positions"], HOME_POSITIONS)
        self.assertEqual(args["speed"], 0)

    def test_the_speed_scale_waits_for_the_site(self) -> None:
        self.serve()
        refused = self.home(speed_scale=0.2)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.sent("go_home"), [])
        self.serve(OVERLAY)                                      # the example overlay fills the fraction
        receipt = self.home(speed_scale=0.2)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.sent("go_home")[-1][1]["speed"], int(round(0.2 * 32767)))
        too_fast = self.home(speed_scale=0.9)                    # inside the class's 0..1, outside the overlay
        self.assertEqual(too_fast["error"]["mhs_code"], ENVELOPE)

    # -- safety ----------------------------------------------------------------------------------------------------
    def test_the_safe_state_action_disables_the_torque(self) -> None:
        self.serve()
        receipt = self.disable()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"disabled": True})
        self.assertFalse(any(self.robot._torque.values()))
        calls = self.sent("sync_disable_torque")
        self.assertTrue(calls)
        self.assertEqual(calls[-1][1]["servo_ids"], SERVO_IDS)

    def test_the_estop_disables_the_torque_and_latches(self) -> None:
        self.serve()
        self.client.estop("test", **self.ids)
        self.assertFalse(any(self.robot._torque.values()))
        self.assertTrue(self.sent("sync_disable_torque"))
        before = len(self.sent("set_multiple_servo_angles"))
        refused = self.move(START_RAD)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(len(self.sent("set_multiple_servo_angles")), before)  # the refusal reached the bus with nothing

    def test_the_reset_rearms_nothing_and_the_declared_reenable_restores_the_torque(self) -> None:
        self.serve()
        self.client.estop("test", **self.ids)
        self.assertFalse(any(self.robot._torque.values()))
        del self.robot._commands[:]
        refused = self.enable()
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(self.sent("sync_enable_torque"), [])      # the latched refusal reached the bus with nothing
        receipt = self.client.reset(**self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)   # simulated: an agent may reset
        self.assertEqual(receipt["output"]["reenable"], REENABLE)
        self.assertIs(receipt["output"]["resumed"], False)
        self.assertFalse(any(self.robot._torque.values()))           # SAFE-042: the reset re-armed nothing
        self.assertEqual(self.sent("sync_enable_torque"), [])
        self.assertEqual(self.sent("enable_torque"), [])
        enabled = self.enable()                                     # the new start command
        self.assertEqual(enabled["status"], "completed", enabled)
        self.assertEqual(enabled["output"], {"enabled": True})
        self.assertTrue(all(self.robot._torque.values()))
        self.assertEqual(self.sent("sync_enable_torque")[-1][1]["servo_ids"], SERVO_IDS)
        self.assertEqual(self.move(HOME_RAD)["status"], "completed")

    def test_the_reenable_is_declared_and_never_a_safe_state_action(self) -> None:
        self.serve()
        manifest = next(item for item in self.client.devices() if item["device_id"] == self.ids["device_id"])
        self.assertEqual(manifest["safety"]["estop"]["reenable"], REENABLE)
        self.assertNotIn(REENABLE, manifest["safety"]["safe_state"]["achieved_by"])

    def test_a_failed_reenable_is_a_failed_receipt(self) -> None:
        self.serve()
        self.disable()
        self.robot._force_failure("sync_enable_torque")
        self.robot._force_failure("enable_torque")           # the upstream fallback: make the per-servo write fail too
        receipt = self.enable()
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", FAULTED))

    # -- native failures -------------------------------------------------------------------------------------------
    def test_a_failed_native_write_is_a_failed_receipt(self) -> None:
        self.serve()
        self.robot._force_failure("set_multiple_servo_angles")
        receipt = self.move(HOME_RAD)
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", FAULTED))
        self.assertEqual(self.state()["joint_positions"], START_RAD)  # the failed write changed nothing
        self.robot._force_failure("go_home")
        self.assertEqual(self.home()["error"]["mhs_code"], FAULTED)
        self.robot._force_failure("sync_disable_torque")
        self.robot._force_failure("disable_torque")          # the upstream fallback: make the per-servo write fail too
        self.assertEqual(self.disable()["error"]["mhs_code"], FAULTED)

    # -- reference and loader --------------------------------------------------------------------------------------
    def test_the_reference_declares_the_bindings_and_the_safe_state(self) -> None:
        reference = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
        self.assertEqual(reference["device"]["id"], "mhs://localhost/mcp-robot")
        self.assertEqual((reference["device"]["kind"], reference["device"]["risk"]), ("robot.arm", "R2"))
        safety = reference["safety"]
        self.assertEqual(safety["estop"]["native"], "sync_disable_torque")
        self.assertEqual(safety["estop"]["reenable"], REENABLE)
        self.assertIsNone(safety["estop"].get("physical_ref"))
        self.assertEqual(safety["safe_state"]["achieved_by"], ["x-cap.itheima1.disable_all_torque.v1"])
        self.assertEqual([(item["name"], item["path"]) for item in safety["operator_required"]],
                         [("home", "speed_scale")])
        actions = {action["cap_id"]: action for action in reference["actions"]}
        self.assertEqual(set(actions), {"cap.motion.joint_position.v1", "cap.motion.home.v1",
                                        "x-cap.itheima1.disable_all_torque.v1", REENABLE})
        joint = actions["cap.motion.joint_position.v1"]["inputs"][0]
        self.assertEqual((joint["name"], joint["length"], joint["unit"]), ("joint_positions", 6, "rad"))
        self.assertEqual(joint["limit"]["min"], [0.0] * 6)
        self.assertEqual(joint["limit"]["max"], [PI] * 6)
        self.assertEqual(joint["limit"]["ref"], "sources/servo_control_standalone.py:462-471")
        measures = {measure["name"]: measure for measure in reference["measures"]}
        self.assertEqual((measures["joint_positions"]["type"], measures["joint_positions"]["length"]),
                         ("array", 6))
        self.assertIsNone(reference["provenance"]["reviewed_by"])

    def test_the_hardware_backend_is_refused_until_a_human_signs_the_review(self) -> None:
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, backend="hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
