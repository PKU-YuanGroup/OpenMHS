"""Acceptance run of the G1 dual-arm package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); its ``_calls`` list is
what reached the "controller".  Nothing here ran on a robot.
"""

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
MOVE = "cap.motion.joint_position.v1"
HOLD = "x-cap.unitreerobotics.hold_position.v1"
START = [0.2] * 14
TARGET = [0.1, -0.1, 0.2, -0.2, 0.3, -0.3, 0.4, 0.5, -0.5, 0.6, -0.6, 0.7, -0.7, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class G1DualArmCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.driver = driver
        self.arm = driver.native
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.arm._calls[:]
        return self.client

    def move(self, positions):
        return self.client.invoke(MOVE, {"joint_positions": positions}, **self.ids)

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def sent(self):
        return list(self.arm._calls)

    def test_reads_report_the_fake_state(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual(state["joint_positions"], [0.0] * 14)
        self.assertEqual(state["joint_velocities"], [0.0] * 14)
        self.assertEqual(state["target_joint_positions"], [0.0] * 14)
        self.assertEqual(state["arm_velocity_limit"], 20.0)
        self.assertIs(state["motion_mode"], False)

    def test_a_joint_move_waits_for_the_site(self) -> None:
        self.serve()
        refused = self.move(TARGET)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.sent(), [])

    def test_a_joint_move_reaches_the_native_target(self) -> None:
        self.serve(OVERLAY)
        receipt = self.move(TARGET)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"reached": False, "joint_positions": [0.0] * 14})
        [(name, args)] = self.sent()
        self.assertEqual(name, "ctrl_dual_arm")
        self.assertEqual(args["q_target"], TARGET)
        self.assertEqual(args["tauff_target"], [0.0] * 14)
        state = self.state()
        self.assertEqual(state["target_joint_positions"], TARGET)
        self.assertEqual(state["joint_positions"], [0.0] * 14)

    def test_an_out_of_envelope_target_is_refused_before_the_native(self) -> None:
        self.serve(OVERLAY)
        target = list(TARGET)
        target[0] = 2.0
        refused = self.move(target)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(refused["error"]["details"]["path"], "joint_positions[0]")
        self.assertEqual(refused["error"]["details"]["bound"], 1.0)
        self.assertEqual(self.sent(), [])

    def test_the_estop_requests_a_hold_but_fails_and_latches(self) -> None:
        self.serve(OVERLAY)
        self.arm._set_joint_positions(START)
        receipt = self.client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
        self.assertTrue(self.sent(), "the e-stop made no native call")
        for name, args in self.sent():
            self.assertEqual(name, "ctrl_dual_arm")
            self.assertEqual(args["q_target"], START)
            self.assertEqual(args["tauff_target"], [0.0] * 14)
        refused = self.move(TARGET)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertFalse(any(args["q_target"] == TARGET for _name, args in self.sent()))

    def test_an_ordinary_hold_is_refused_while_latched(self) -> None:
        self.serve(OVERLAY)
        self.client.estop("test", **self.ids)
        refused = self.client.invoke(HOLD, {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_the_reset_releases_the_latch_without_sending_anything(self) -> None:
        self.serve(OVERLAY)
        self.arm._set_joint_positions(START)
        self.client.estop("test", **self.ids)
        del self.arm._calls[:]
        receipt = self.client.reset(**self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIs(receipt["output"].get("resumed"), False)
        self.assertEqual(self.sent(), [])
        self.assertEqual(self.move(TARGET)["status"], "completed")

    def test_the_ordinary_hold_takes_no_input(self) -> None:
        self.serve(OVERLAY)
        self.arm._set_joint_positions(START)
        receipt = self.client.invoke(HOLD, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"hold_requested": True, "joint_positions": START})
        self.assertEqual(self.sent()[0][1]["q_target"], START)

    def test_the_driver_declares_no_reset_hook(self) -> None:
        driver = load_driver(HERE, backend="fake")
        self.assertIsNone(driver.reset_hook)

    def test_the_hardware_backend_is_refused_until_a_human_signs_the_review(self) -> None:
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, backend="hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
