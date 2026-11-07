"""Acceptance run of the LTAMP simulated PR2 driver: the gate, plus repository-specific cases.

Add cases, never remove the check_driver call.  The fake is an in-memory PBController stand-in; every number below is
test data, except the soft limits cited from control_tools/common.py.
"""

import threading
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import Cancelled, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
MOVE = "cap.motion.joint_position.v1"
#: Inside every soft limit of control_tools/common.py:19-30 (left arm first, then right arm).
POSE = [0.2, 0.1, 0.3, -1.0, 0.5, -1.0, 0.7,
        -0.2, 0.1, -0.3, -1.0, -0.5, -1.0, -0.7]
#: The PR2 safety-controller soft limits of control_tools/common.py, written out here (not imported from driver.py) so
#: that a changed bound in the driver fails a case: element of the 14-element arm command -> (lower, upper).
SOFT_LIMITS = {
    0: (-0.564601836603, 2.1353981634),     # l_shoulder_pan_joint, common.py:26
    1: (-0.3536, 1.2963),                   # l_shoulder_lift_joint, common.py:27
    2: (-0.65, 3.75),                       # l_upper_arm_roll_joint, common.py:28
    3: (-2.1213, -0.15),                    # l_elbow_flex_joint, common.py:29
    5: (-2.0, -0.1),                        # l_wrist_flex_joint, common.py:30
    7: (-2.1353981634, 0.564601836603),     # r_shoulder_pan_joint, common.py:19
    8: (-0.3536, 1.2963),                   # r_shoulder_lift_joint, common.py:20
    9: (-3.75, 0.65),                       # r_upper_arm_roll_joint, common.py:21
    10: (-2.1213, -0.15),                   # r_elbow_flex_joint, common.py:22
    12: (-2.0, -0.1),                       # r_wrist_flex_joint, common.py:23
}
#: How far past a bound the refused values lie (test data).
PAST = 1e-3


class _CancellingLock:
    """A lock that sets the operation's cancel event as it is entered (the e-stop's cancel, landing meanwhile)."""

    def __init__(self, event):
        self._lock = threading.Lock()
        self._event = event

    def __enter__(self):
        self._event.set()
        self._lock.acquire()
        return self

    def __exit__(self, *exc):
        self._lock.release()
        return False

class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LtampPR2Cases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def test_move_sets_both_arms_and_reads_them_back(self) -> None:
        client, fake = self.serve()
        moved = client.invoke(MOVE, {"joint_positions": POSE}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertTrue(moved["output"]["reached"])
        self.assertEqual(moved["output"]["joint_positions"], POSE)
        self.assertEqual([entry[1] for entry in fake._commands], ["l", "r"])
        self.assertEqual(fake._commands[0][3], 1.0)        # the upstream executor's timeout (execution.py:94)
        self.assertEqual(client.read("main", **self.ids)["state"]["joint_positions"], POSE)

    def test_soft_limits_refuse_before_the_controller(self) -> None:
        client, fake = self.serve()
        outside = list(POSE)
        outside[0] = 2.2          # l_shoulder_pan above 2.1353981634 (common.py:26)
        refused = client.invoke(MOVE, {"joint_positions": outside}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        outside = list(POSE)
        outside[10] = 0.7         # r_elbow_flex above -0.15 (common.py:22)
        refused = client.invoke(MOVE, {"joint_positions": outside}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(fake._commands, [])

    def test_continuous_roll_joints_have_no_bound(self) -> None:
        client, fake = self.serve()
        pose = list(POSE)
        pose[4], pose[6], pose[11], pose[13] = 7.0, -7.0, 7.0, -7.0    # forearm and wrist roll joints
        moved = client.invoke(MOVE, {"joint_positions": pose}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)

    def test_torso_write_is_read_back(self) -> None:
        client, fake = self.serve()
        written = client.write("main", {"torso_position": 0.2}, **self.ids)
        self.assertEqual(written["status"], "completed", written)
        self.assertEqual(client.read("main", **self.ids)["state"]["torso_position"], 0.2)
        refused = client.write("main", {"torso_position": 0.4}, **self.ids)     # above 0.325 (common.py:14)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_motor_control_mode_is_refused(self) -> None:
        client, fake = self.serve()
        fake.execute_motor_control = True
        refused = client.invoke(MOVE, {"joint_positions": POSE}, **self.ids)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(fake._commands, [])

    def test_estop_switches_motor_control_off_and_latches(self) -> None:
        client, fake = self.serve()
        fake.execute_motor_control = True       # as the upstream's plan runner sets it (run_simulation.py:79)
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"]["estop"], "engaged")
        self.assertIs(fake.execute_motor_control, False)
        refused = client.invoke(MOVE, {"joint_positions": POSE}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
        refused = client.write("main", {"torso_position": 0.2}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(fake._commands, [])

    def test_estop_fails_when_motor_control_does_not_read_back_off(self) -> None:
        loaded = load_driver(HERE, backend="fake")

        class Stuck(type(loaded.native)):
            @property
            def execute_motor_control(self):
                return True

            @execute_motor_control.setter
            def execute_motor_control(self, value):
                pass

        driver = type(loaded)(backend="fake", native=Stuck())
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        stopped = client.estop("stuck flag", device_id=device_id, session_id=session)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
    def test_a_move_cancelled_while_it_waits_for_the_world_sets_nothing(self) -> None:
        driver = load_driver(HERE, backend="fake")
        fake = driver.native
        event = threading.Event()
        driver._pb_world_lock = _CancellingLock(event)
        with self.assertRaises(Cancelled):
            driver.call(MOVE, {"joint_positions": POSE}, {"cancel_event": event})
        self.assertEqual(fake._commands, [])

    # -- review round 1 (Sonnet safety finding F2) -------------------------------------------------------------------
    def test_a_torso_write_cancelled_while_it_waits_for_the_world_sets_nothing(self) -> None:
        driver = load_driver(HERE, backend="fake")
        fake = driver.native
        event = threading.Event()
        driver._pb_world_lock = _CancellingLock(event)
        with self.assertRaises(Cancelled):
            driver.write("main", {"torso_position": 0.2}, {"cancel_event": event})
        self.assertEqual(fake._commands, [])
        self.assertEqual(fake.get_joint_positions(["torso_lift_joint"]), [0.1])     # the fake's placeholder start

    def test_every_arm_bound_refuses_just_past_it_and_accepts_it(self) -> None:
        client, fake = self.serve()
        for index, (lower, upper) in SOFT_LIMITS.items():
            for value, accepted in ((lower - PAST, False), (upper + PAST, False), (lower, True), (upper, True)):
                with self.subTest(element=index, value=value):
                    pose = list(POSE)
                    pose[index] = value
                    receipt = client.invoke(MOVE, {"joint_positions": pose}, **self.ids)
                    if accepted:
                        self.assertEqual(receipt["status"], "completed", receipt)
                    else:
                        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
        self.assertEqual(len(fake._commands), 2 * 2 * len(SOFT_LIMITS))   # two arms per accepted move, none refused
        self.assertEqual(sorted(SOFT_LIMITS), [0, 1, 2, 3, 5, 7, 8, 9, 10, 12])   # the four roll joints are unbounded

if __name__ == "__main__":
    unittest.main()
