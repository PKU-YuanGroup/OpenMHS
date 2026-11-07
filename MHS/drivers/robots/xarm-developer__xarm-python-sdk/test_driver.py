"""Acceptance run of the xArm package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): its ``_commands`` list is
what reached the "arm".  Nothing here ran on a real xArm.
"""

import json
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
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
FAULTED = "MHS.DEVICE.FAULTED"
UNKNOWN = "MHS.OUTCOME.UNKNOWN"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
REENABLE = "x-cap.xarm-developer.enable_motion.v1"

JOINT_MIN = [-6.283185307179586, -2.059488, -6.283185307179586, -0.191986, -6.283185307179586, -1.692969,
             -6.283185307179586]
JOINT_MAX = [6.283185307179586, 2.094395, 6.283185307179586, 3.92699, 6.283185307179586, 3.141592653589793,
             6.283185307179586]
HOME = [0.0] * 7


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class XArmCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.arm = driver.native                              # the fake XArmAPI
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.arm._commands[:]                              # forget the set-up (motion_enable, mode 0, state 0)
        return self.client

    def move_joints(self, angles):
        return self.client.invoke("cap.motion.joint_position.v1", {"joint_positions": angles}, **self.ids)

    def move_pose(self, position, orientation=None):
        payload = {"position": position}
        if orientation is not None:
            payload["orientation"] = orientation
        return self.client.invoke("cap.motion.cartesian_pose.v1", payload, **self.ids)

    def jog(self, velocities, duration_s):
        return self.client.invoke("cap.motion.joint_velocity.v1",
                                  {"joint_velocities": velocities, "duration_s": duration_s}, **self.ids)

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def sent(self, name=None):
        return [(command, args) for command, args in self.arm._commands if name is None or command == name]

    def enable(self):
        return self.client.invoke(REENABLE, {}, **self.ids)

    # -- limits ---------------------------------------------------------------------------------------------
    def test_the_joint_limits_are_per_joint(self) -> None:
        self.serve()
        joint2_over = list(HOME)
        joint2_over[1] = 2.1                                    # fine for joint 1 (+-2pi), over the max of joint 2
        refused = self.move_joints(joint2_over)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        details = refused["error"]["details"]
        self.assertEqual((details["path"], details["element_name"], details["bound"]),
                         ("joint_positions[1]", "joint2", 2.094395))
        self.assertEqual(details["provenance"]["ref"], "xarm/core/config/x_config.py:129-137")
        joint4_under = list(HOME)
        joint4_under[3] = -0.2                                  # joint 4 starts at -0.191986
        self.assertEqual(self.move_joints(joint4_under)["error"]["details"]["path"], "joint_positions[3]")
        self.assertEqual(self.sent("set_servo_angle"), [])      # the arm saw none of them
        for target in (JOINT_MIN, JOINT_MAX):                   # both ends of every joint are inside
            self.assertEqual(self.move_joints(target)["status"], "completed", target)

    def test_a_joint_move_goes_out_in_radians_and_waits(self) -> None:
        self.serve()
        target = [0.1, -0.5, 0.2, 1.0, -0.3, 0.4, 0.5]
        receipt = self.move_joints(target)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"reached": True, "joint_positions": target})
        [(name, args)] = self.sent("set_servo_angle")
        self.assertEqual((args["angle"], args["is_radian"], args["wait"], args["timeout"]), (target, True, True, 100))
        self.assertEqual(self.state()["joint_positions"], target)
        # the SDK's default unit is degrees: 0.1 rad is 5.7296 deg
        self.assertAlmostEqual(self.arm.get_servo_angle(is_radian=False)[1][0], 5.729577951, places=8)

    def test_the_cartesian_position_has_nested_limits(self) -> None:
        self.serve()
        for axis, value, bound in (("x", 751, 750), ("x", -751, -750), ("y", 800, 750), ("z", 1001, 1000),
                                   ("z", -401, -400)):
            position = {"x": 300, "y": 0, "z": 250, axis: value}
            refused = self.move_pose(position)
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE), (axis, value))
            self.assertEqual((refused["error"]["details"]["path"], refused["error"]["details"]["bound"]),
                             (f"position.{axis}", bound))
        self.assertEqual(self.sent("set_position"), [])
        edge = self.move_pose({"x": 750, "y": -750, "z": -400})
        self.assertEqual(edge["status"], "completed")
        self.assertEqual(self.sent("set_position")[0][1]["x"], 750)

    def test_a_position_move_keeps_the_orientation(self) -> None:
        self.serve()
        receipt = self.move_pose({"x": 300, "y": 0, "z": 250})
        self.assertEqual(receipt["output"]["position"], {"x": 300, "y": 0, "z": 250})
        [(name, args)] = self.sent("set_position")
        self.assertEqual((args["roll"], args["pitch"], args["yaw"], args["is_radian"], args["wait"]),
                         (None, None, None, True, True))
        self.assertEqual(self.state()["tcp_pose"]["orientation"]["roll"], 3.1415926)    # the SDK's initial roll

    def test_the_orientation_waits_for_the_site(self) -> None:
        self.serve()
        down = {"roll": 3.1, "pitch": 0.0, "yaw": 0.5}
        refused = self.move_pose({"x": 300, "y": 0, "z": 250}, down)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.sent("set_position"), [])
        self.serve(OVERLAY)                                      # the example overlay fills the three bounds
        self.assertEqual(self.move_pose({"x": 300, "y": 0, "z": 250}, down)["status"], "completed")
        [(name, args)] = self.sent("set_position")
        self.assertEqual((args["roll"], args["pitch"], args["yaw"]), (3.1, 0.0, 0.5))
        tilted = dict(down, pitch=0.3)                          # the overlay allows +-0.2 rad of pitch
        self.assertEqual(self.move_pose({"x": 300, "y": 0, "z": 250}, tilted)["error"]["mhs_code"], ENVELOPE)
        narrower = self.move_pose({"x": 450, "y": 0, "z": 250})  # inside the SDK table, outside the example overlay
        self.assertEqual(narrower["error"]["details"]["bound"], 400)

    def test_the_overlay_only_narrows(self) -> None:
        self.serve(OVERLAY)
        joint2 = list(HOME)
        joint2[1] = 2.03                                        # inside the XARM7_X4 table, outside the 1305 table
        refused = self.move_joints(joint2)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(refused["error"]["details"]["bound"], 2.024581)

    # -- return codes -----------------------------------------------------------------------------------------
    def test_a_nonzero_return_code_is_a_failure_with_the_native_code(self) -> None:
        self.serve()
        cases = (
            (1, "failed", FAULTED),            # errors that have not been cleared
            (-1, "failed", FAULTED),           # disconnected
            (-9, "failed", FAULTED),           # emergency stop
            (-2, "failed", PRECONDITION),      # motion not enabled or state not set
            (9, "failed", PRECONDITION),       # state not ready to move
            (-7, "failed", ENVELOPE),          # the arm's own joint limit
            (-8, "failed", ENVELOPE),
            (3, "unknown", UNKNOWN),           # response timeout: the move may have happened
            (100, "unknown", UNKNOWN),         # wait finish timeout
        )
        for code, status, mhs_code in cases:
            self.arm._force_code(code)
            receipt = self.move_joints(HOME)
            self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), (status, mhs_code), code)
            self.assertEqual(receipt["error"]["details"]["native_code"], code)
        self.assertEqual(self.move_joints(HOME)["status"], "completed")     # the hooks were one-shot

    def test_a_read_back_that_fails_after_a_finished_move_is_unknown_not_failed(self) -> None:
        self.serve()
        target = [0.1] * 7
        self.arm._force_read_code(-1)                           # the link drops right after the move
        receipt = self.move_joints(target)
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("unknown", UNKNOWN))
        self.assertEqual(receipt["error"]["details"]["native_code"], -1)
        self.assertEqual(len(self.sent("set_servo_angle")), 1)  # the arm did move, so the client must not retry blindly
        self.assertEqual(self.state()["joint_positions"], target)
        self.arm._force_read_code(1)
        pose = self.move_pose({"x": 300, "y": 0, "z": 250})
        self.assertEqual((pose["status"], pose["error"]["mhs_code"]), ("unknown", UNKNOWN))

    def test_a_move_the_arm_cannot_make_is_refused_by_its_state(self) -> None:
        self.serve()
        self.arm.motion_enable(enable=False)                    # upstream: not enabled, so the code is -2
        refused = self.move_joints(HOME)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(refused["error"]["details"]["native_code"], -2)
        self.arm.motion_enable(enable=True)
        self.arm.set_state(3)                                   # somebody paused the arm: not the driver's to clear
        del self.arm._commands[:]
        paused = self.move_joints(HOME)
        self.assertEqual((paused["status"], paused["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.sent(), [])                       # not even set_state(0)
        self.assertEqual(self.state()["state"], 3)

    # -- velocity and the watchdog --------------------------------------------------------------------------------
    def test_a_velocity_command_waits_for_the_site(self) -> None:
        self.serve()
        refused = self.jog([0.1] * 7, 1.0)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.sent(), [])

    def test_a_velocity_command_carries_the_arms_own_watchdog(self) -> None:
        self.serve(OVERLAY)
        receipt = self.jog([0.1, 0.0, -0.1, 0.0, 0.0, 0.0, 0.5], 1.5)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["applied"], True)
        self.assertEqual([name for name, _ in self.sent()], ["set_mode", "set_state", "vc_set_joint_velocity"])
        self.assertEqual(self.sent("set_mode")[0][1]["mode"], 4)
        args = self.sent("vc_set_joint_velocity")[0][1]
        self.assertEqual((args["is_radian"], args["duration"]), (True, 1.5))        # the duration is the watchdog
        self.assertEqual(self.state()["mode"], 4)
        # the next position move selects mode 0 again
        self.assertEqual(self.move_joints(HOME)["status"], "completed")
        self.assertEqual(self.state()["mode"], 0)
        for refused in (self.jog([0.6] * 7, 1.0), self.jog([0.1] * 7, 2.5), self.jog([0.1] * 7, 0.05)):
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)                # the example overlay bounds

    def test_a_duration_that_never_stops_is_refused(self) -> None:
        site = {"openmhs": "0.9", "devices": {"mhs://localhost/xarm7": {"cap.motion.joint_velocity.v1": {
            "joint_velocities": {"min": -1, "max": 1, "source": "operator"},
            "duration_s": {"min": 0, "max": 5, "source": "operator"}}}}}      # an overlay that allows 0
        self.serve(site)
        receipt = self.jog([0.1] * 7, 0)
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", INPUT_INVALID))
        self.assertEqual(self.sent("vc_set_joint_velocity"), [])

    def test_old_firmware_ignores_the_duration_so_no_velocity_is_sent(self) -> None:
        self.serve(OVERLAY)
        self.arm._set_firmware((1, 7, 9))
        receipt = self.jog([0.1] * 7, 1.0)
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.sent(), [])

    # -- e-stop and reset -----------------------------------------------------------------------------------
    def test_the_estop_stops_the_arm_and_latches(self) -> None:
        self.serve()
        self.client.estop("test", **self.ids)
        self.assertEqual(self.sent("emergency_stop"), [("emergency_stop", {})])
        self.assertEqual(self.arm.state, 4)
        before = len(self.sent())
        for refused in (self.move_joints(HOME), self.move_pose({"x": 300, "y": 0, "z": 250})):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(len(self.sent()), before)              # the latched refusals reached the arm with nothing

    def test_the_reenable_is_refused_while_latched_with_nothing_sent_to_the_arm(self) -> None:
        self.serve()
        self.client.estop("test", **self.ids)
        del self.arm._commands[:]
        refused = self.enable()
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(self.sent(), [])                       # the latched refusal reached the arm with nothing
        self.assertEqual(self.arm.state, 4)

    def test_the_reset_sends_the_arm_nothing_and_names_the_reenable(self) -> None:
        self.serve()
        self.arm._set_error(1)                                  # the Emergency Stop Button is pushed (api_code.md:68)
        self.assertEqual(self.move_joints(HOME)["error"]["details"]["native_code"], 1)
        self.client.estop("test", **self.ids)
        del self.arm._commands[:]
        receipt = self.client.reset(**self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)   # simulated: an agent may reset
        self.assertEqual(receipt["output"]["reenable"], REENABLE)
        self.assertIs(receipt["output"]["resumed"], False)
        self.assertEqual(self.sent(), [])                       # no @reset hook: the reset reaches the arm with nothing
        self.assertEqual((self.arm.state, self.arm.error_code), (4, 1))    # still stopped, the error still there
        stopped = self.move_joints(HOME)
        self.assertEqual((stopped["status"], stopped["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertIn(REENABLE, stopped["error"]["message"])

    def test_the_reenable_clears_errors_readies_the_arm_and_then_a_move_completes(self) -> None:
        self.serve()
        self.arm._set_error(1)
        self.client.estop("test", **self.ids)
        self.assertEqual(self.client.reset(**self.ids)["status"], "completed")
        del self.arm._commands[:]
        enabled = self.enable()
        self.assertEqual(enabled["status"], "completed", enabled)
        self.assertEqual(enabled["output"], {"enabled": True})
        self.assertEqual(self.sent(), [("clean_error", {}), ("clean_warn", {}),
                                       ("motion_enable", {"enable": True, "servo_id": None}), ("set_mode", {"mode": 0}),
                                       ("set_state", {"state": 0})])   # xarm_api.py:1590, 2001-move_joint.py:44-46
        self.assertEqual((self.arm.state, self.arm.error_code), (0, 0))
        self.assertEqual(self.move_joints(HOME)["status"], "completed")

    def test_a_reenable_whose_clean_error_fails_enables_nothing(self) -> None:
        self.serve()
        self.client.estop("test", **self.ids)
        self.assertEqual(self.client.reset(**self.ids)["status"], "completed")
        del self.arm._commands[:]
        original = self.arm.clean_error
        self.arm.clean_error = lambda: (original(), 1)[1]       # the controller still reports an error (code 1)
        failed = self.enable()
        self.assertEqual((failed["status"], failed["error"]["mhs_code"]), ("failed", FAULTED), failed)
        self.assertEqual(failed["error"]["details"]["native_code"], 1)
        self.assertEqual([name for name, _ in self.sent()], ["clean_error"])   # nothing was enabled
        self.assertEqual(self.arm.state, 4)

    def test_the_driver_declares_no_reset_hook(self) -> None:
        driver = load_driver(HERE, backend="fake")
        self.assertIsNone(driver.reset_hook)                    # a re-enable excludes an @reset hook (CORE-086)
        self.assertEqual(type(driver).driver_model().reenable, REENABLE)

    # -- reading, the reference and the loader -----------------------------------------------------------------
    def test_the_state_reads_what_the_sdk_returns(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual(state["joint_positions"], HOME)
        self.assertEqual(state["tcp_pose"], {"position": {"x": 201.5, "y": 0.0, "z": 140.5},
                                              "orientation": {"roll": 3.1415926, "pitch": 0.0, "yaw": 0.0}})
        self.assertEqual((state["state"], state["mode"], state["error_code"], state["warn_code"]), (0, 0, 0, 0))

    def test_the_reference_declares_the_watchdog_and_the_physical_stop(self) -> None:
        reference = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
        safety = reference["safety"]
        self.assertEqual(safety["watchdog_ms"], 60000)
        self.assertEqual(safety["estop"]["native"], "emergency_stop")
        self.assertEqual(safety["estop"]["physical_ref"], "doc/api/xarm_api_code.md:68-70")
        self.assertEqual(safety["estop"]["reenable"], REENABLE)
        self.assertTrue(any("atchdog" in fact["text"] for fact in reference["facts"]))
        unset = sorted((item["name"], item["path"]) for item in safety["operator_required"])
        self.assertEqual(unset, [("jog_joints", "duration_s"), ("jog_joints", "joint_velocities"),
                                 ("move_pose", "orientation.pitch"), ("move_pose", "orientation.roll"),
                                 ("move_pose", "orientation.yaw")])

    def test_the_hardware_backend_is_refused_until_a_human_signs_the_review(self) -> None:
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, backend="hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
