"""Acceptance run of the DaMiao motor package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): its ``_commands`` list is
what reached the "motor".  Nothing here ran on a motor.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
LATCHED = "MHS.SAFETY.ESTOP_ENGAGED"
FAULTED = "MHS.DEVICE.FAULTED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DMMotorCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.motor = driver.native                              # the fake MotorControl
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.motor._commands[:]                             # forget the set-up (addMotor of the motor identity)
        return self.client

    def move(self, radians):
        return self.client.invoke("cap.motion.joint_position.v1", {"joint_positions": [radians]}, **self.ids)

    def jog(self, radians_per_second, duration_s):
        return self.client.invoke("cap.motion.joint_velocity.v1",
                                  {"joint_velocities": [radians_per_second], "duration_s": duration_s}, **self.ids)

    def configure(self, **patch):
        return self.client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def sent(self, name):
        return [item for item in self.motor._commands if item[0] == name]

    # -- reads and the drive ------------------------------------------------------------------------------------
    def test_the_reads_start_at_rest(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual((state["joint_position"], state["joint_velocity"], state["joint_torque"]), (0.0, 0.0, 0.0))
        self.assertEqual(state["control_mode"], 1)              # a new Motor object starts in MIT mode

    def test_the_enabled_write_reaches_the_drive(self) -> None:
        self.serve()
        self.assertEqual(self.configure(enabled=True)["status"], "completed")
        self.assertTrue(self.motor._enabled)
        self.assertEqual(len(self.sent("enable")), 1)
        self.assertEqual(self.configure(enabled=False)["status"], "completed")
        self.assertFalse(self.motor._enabled)
        self.assertEqual(len(self.sent("disable")), 1)

    # -- the position move ------------------------------------------------------------------------------------------
    def test_a_move_without_an_operator_envelope_is_refused(self) -> None:
        self.serve()
        refused = self.move(0.5)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.sent("control_Pos_Vel"), [])      # the motor saw nothing

    def test_a_move_switches_the_mode_and_arrives(self) -> None:
        self.serve(OVERLAY)
        receipt = self.move(0.5)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"reached": True, "joint_positions": [0.5], "tolerance_rad": 0.02})
        self.assertEqual(self.sent("switchControlMode"), [("switchControlMode", 2)])   # POS_VEL
        self.assertEqual(self.sent("control_Pos_Vel"), [("control_Pos_Vel", 0.5, 0.0)])
        self.assertEqual(self.motor.motors_map[1].getPosition(), 0.5)
        state = self.state()
        self.assertEqual((state["joint_position"], state["control_mode"]), (0.5, 2))

    def test_a_move_outside_the_envelope_is_refused(self) -> None:
        self.serve(OVERLAY)
        for target in (2.5, -2.5):
            refused = self.move(target)
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE), target)
            self.assertEqual(refused["error"]["details"]["path"], "joint_positions[0]")
        self.assertEqual(self.sent("control_Pos_Vel"), [])

    def test_a_mode_the_motor_does_not_confirm_refuses_the_move(self) -> None:
        self.serve(OVERLAY)
        self.motor._refuse_mode_switch()
        refused = self.move(0.5)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("failed", FAULTED))
        self.assertEqual(self.sent("control_Pos_Vel"), [])

    # -- the velocity command ---------------------------------------------------------------------------------------
    def test_a_jog_commands_zero_when_the_duration_is_over(self) -> None:
        self.serve(OVERLAY)
        receipt = self.jog(0.5, 0.05)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"applied": True, "joint_velocities": [0.5]})
        self.assertEqual(self.sent("switchControlMode"), [("switchControlMode", 3)])   # VEL
        self.assertEqual(self.sent("control_Vel"), [("control_Vel", 0.5), ("control_Vel", 0.0)])
        self.assertEqual(self.state()["joint_velocity"], 0.0)

    def test_a_jog_outside_the_envelope_is_refused(self) -> None:
        self.serve(OVERLAY)
        for velocity in (1.5, -1.5):
            refused = self.jog(velocity, 0.1)
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE), velocity)
        self.assertEqual(self.jog(0.5, 2.5)["error"]["details"]["path"], "duration_s")
        self.assertEqual(self.sent("control_Vel"), [])

    # -- safety -----------------------------------------------------------------------------------------------------
    def test_the_estop_switches_the_drive_off_and_latches(self) -> None:
        self.serve(OVERLAY)
        self.assertEqual(self.jog(0.5, 0.05)["status"], "completed")
        estop = self.client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed")
        self.assertEqual(estop["output"]["estop"], "engaged")
        self.assertEqual(len(self.sent("disable")), 1)
        self.assertEqual(self.state()["joint_velocity"], 0.0)
        del self.motor._commands[:]
        self.assertEqual(self.move(0.2)["error"]["mhs_code"], LATCHED)
        self.assertEqual(self.sent("control_Pos_Vel"), [])


if __name__ == "__main__":
    unittest.main()
