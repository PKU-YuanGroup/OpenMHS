"""Acceptance run of the Dobot V4 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): its ``_commands`` list is
what reached the "arm", and every one of them is a dashboard command line.  Nothing here ran on a real arm.
"""

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

#: placeholder test input (rad); inside site-limits.example.json
TARGET_RAD = [0.1, -0.5, 0.2, 1.0, -0.3, 0.4]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DobotCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.arm = driver.native                              # the fake DobotConnection
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.arm._commands[:]                              # forget the set-up (RequestControl)
        return self.client

    def move_joints(self, positions, **extra):
        payload = {"joint_positions": positions}
        payload.update(extra)
        return self.client.invoke("cap.motion.joint_position.v1", payload, **self.ids)

    def move_pose(self, position, orientation=None):
        payload = {"position": position}
        if orientation is not None:
            payload["orientation"] = orientation
        return self.client.invoke("cap.motion.cartesian_pose.v1", payload, **self.ids)

    def stop(self):
        return self.client.invoke("cap.motion.stop.v1", {}, **self.ids)

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def commands(self, prefix=""):
        return [command for command in self.arm._commands if command.startswith(prefix)]

    # -- motion ---------------------------------------------------------------------------------------------
    def test_a_joint_move_sends_the_documented_movj_command(self) -> None:
        self.serve(OVERLAY)
        receipt = self.move_joints(TARGET_RAD)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIs(receipt["output"]["reached"], True)
        self.assertEqual(self.commands("MovJ("),
                         ["MovJ(joint={5.729578,-28.647890,11.459156,57.295780,-17.188734,22.918312})"])
        for got, expected in zip(receipt["output"]["joint_positions"], TARGET_RAD):
            self.assertAlmostEqual(got, expected, places=6)
        self.assertEqual(receipt["output"]["tolerance_rad"], math.radians(0.01))
        # the read-back is the device's own degrees, reported as it answered
        for got, expected in zip(self.state()["joint_positions"], TARGET_RAD):
            self.assertAlmostEqual(got, math.degrees(expected), places=5)

    def test_a_cartesian_move_keeps_the_current_orientation(self) -> None:
        self.serve(OVERLAY)
        receipt = self.move_pose({"x": 500, "y": 100, "z": 350})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIs(receipt["output"]["reached"], True)
        self.assertEqual(self.commands("MovL("),
                         ["MovL(pose={500.000000,100.000000,350.000000,180.000000,0.000000,0.000000})"])
        self.assertEqual(receipt["output"]["position"], {"x": 500.0, "y": 100.0, "z": 350.0})

    def test_a_cartesian_move_converts_the_orientation_to_degrees(self) -> None:
        self.serve(OVERLAY)
        receipt = self.move_pose({"x": 400, "y": 0, "z": 300},
                                 {"roll": 3.141592653589793, "pitch": 0.0, "yaw": 0.5})
        self.assertEqual(receipt["status"], "completed", receipt)
        [text] = self.commands("MovL(")
        self.assertTrue(text.startswith("MovL(pose={400.000000,0.000000,300.000000,180.000000,0.000000,28.647890})"),
                        text)

    def test_the_motion_envelope_waits_for_the_site(self) -> None:
        self.serve()                                            # no overlay: the bounds are operator_required
        refused = self.move_joints(TARGET_RAD)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        refused = self.move_pose({"x": 500, "y": 0, "z": 300})
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.commands("MovJ("), [])            # nothing reached the arm
        self.assertEqual(self.commands("MovL("), [])

    def test_the_example_overlay_narrows_the_envelope(self) -> None:
        self.serve(OVERLAY)
        too_far = list(TARGET_RAD)
        too_far[2] = 3.0                                        # the overlay allows 2.96706 rad
        refused = self.move_joints(too_far)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(refused["error"]["details"]["bound"], 2.96706)
        self.assertEqual(self.commands("MovJ("), [])
        outside = self.move_pose({"x": 900, "y": 0, "z": 300})   # the overlay allows 800 mm of X
        self.assertEqual(outside["status"], "rejected")
        self.assertEqual(outside["error"]["details"]["bound"], 800)

    # -- reads ----------------------------------------------------------------------------------------------
    def test_the_reads_report_the_controllers_units(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual(state["joint_positions"], [0.0, 0.0, 90.0, 0.0, 90.0, 0.0])
        self.assertEqual(state["tcp_pose"], {"position": {"x": 400.0, "y": 0.0, "z": 300.0},
                                             "orientation": {"rx": 180.0, "ry": 0.0, "rz": 0.0}})
        self.assertEqual(state["robot_mode"], 4)
        self.assertEqual(state["error_ids"], [])

    def test_the_error_list_is_read_from_the_controller(self) -> None:
        self.serve()
        self.arm._set_error_ids([1537, 2048])
        self.assertEqual(self.state()["error_ids"], [1537, 2048])

    # -- refusals -------------------------------------------------------------------------------------------
    def test_a_controller_error_id_is_a_failure_with_the_native_code(self) -> None:
        self.serve()
        self.arm._force_error(2048)
        receipt = self.stop()
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", FAULTED))
        self.assertEqual(receipt["error"]["details"]["native_code"], 2048)

    def test_an_unparsable_reply_is_a_failure_not_a_success(self) -> None:
        self.serve()

        def garbage(text, recv_size=1024):
            self.arm._commands.append(text)
            return "the arm said something unexpected"

        self.arm.send_receive_text = garbage
        receipt = self.stop()
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", FAULTED))

    # -- stop and e-stop ------------------------------------------------------------------------------------
    def test_the_stop_action_sends_the_stop_command(self) -> None:
        self.serve()
        receipt = self.stop()
        self.assertEqual(receipt["status"], "completed")
        self.assertIs(receipt["output"]["stopped"], True)
        self.assertEqual(self.commands("Stop()"), ["Stop()"])

    def test_the_estop_presses_the_controllers_emergency_stop_and_latches(self) -> None:
        self.serve(OVERLAY)
        self.client.estop("test", **self.ids)
        self.assertEqual(self.commands("EmergencyStop("), ["EmergencyStop(1)"])
        self.assertTrue(self.arm._estop_pressed)
        refused = self.move_joints(TARGET_RAD)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        # a stop is never latched out: the safety stop still reaches the arm
        self.assertEqual(self.stop()["status"], "completed")
        self.assertEqual(self.commands("MovJ("), [])            # the latched refusal reached the arm with nothing
        self.assertEqual(self.commands("Stop()"), ["Stop()"])

if __name__ == "__main__":
    unittest.main()
