"""Acceptance run for the Tetheria Aero Hand Open package: the gate, plus device cases.

Add cases, never remove the check_driver call.  The fake's values and the test
inputs below are test data, not device facts.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AeroHandCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.server = server
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def native(self):
        return self.server.devices[self.ids["device_id"]].bridge.native

    # -- feedback ---------------------------------------------------------------------------------------------
    def test_the_five_feedback_reads_return_seven_values(self) -> None:
        client = self.serve()
        state = self.state(client)
        for field in ("actuations", "joint_positions_compact", "actuator_speeds",
                      "actuator_currents", "actuator_temperatures"):
            self.assertIn(field, state)
            self.assertEqual(len(state[field]), 7, (field, state))

    def test_a_missing_actuation_reply_is_a_read_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_actuations = True
        with self.assertRaises(DriverFailed) as caught:
            driver.read("main", ["actuations"])
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")

    # -- motion -----------------------------------------------------------------------------------------------
    def test_the_joint_action_reaches_the_native_position_write(self) -> None:
        client = self.serve()
        targets = [float(index) for index in range(16)]
        receipt = client.invoke("x-cap.tetheria.joint_position.v1",
                                {"joint_positions": targets}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["commanded"])
        self.assertEqual(receipt["output"]["commanded_joint_positions"], targets)
        self.assertEqual(len(receipt["output"]["actuations"]), 7)
        self.assertEqual(self.native()._joints,
                         [targets[0], targets[1], targets[2], targets[4], targets[7], targets[10], targets[13]])

    def test_an_out_of_envelope_joint_target_changes_nothing(self) -> None:
        client = self.serve()
        before = self.state(client)["joint_positions_compact"]
        targets = [0.0] * 16
        targets[0] = 101.0
        refused = client.invoke("x-cap.tetheria.joint_position.v1",
                                {"joint_positions": targets}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["joint_positions_compact"], before)

    def test_the_actuation_action_reaches_the_native_actuation_write(self) -> None:
        client = self.serve()
        targets = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        receipt = client.invoke("x-cap.tetheria.actuation.v1", {"actuations": targets}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["commanded"])
        self.assertEqual(receipt["output"]["commanded_actuations"], targets)
        self.assertEqual(self.native()._actuations, targets)

    def test_an_out_of_envelope_actuation_changes_nothing(self) -> None:
        client = self.serve()
        before = self.state(client)["actuations"]
        targets = [0.0, 0.0, 248.0, 0.0, 0.0, 0.0, 0.0]
        refused = client.invoke("x-cap.tetheria.actuation.v1", {"actuations": targets}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["actuations"], before)

    def test_a_native_joint_write_failure_is_not_completed(self) -> None:
        client = self.serve()
        self.native().fail_joint_write = True
        receipt = client.invoke("x-cap.tetheria.joint_position.v1",
                                {"joint_positions": [0.0] * 16}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotEqual(receipt["status"], "completed")

    def test_a_swallowed_write_timeout_still_completes_the_move(self) -> None:
        # Upstream behaviour the driver cannot see (model review): set_joint_positions prints a
        # SerialTimeoutException and returns, so the action completes although nothing was written.
        client = self.serve()
        before = list(self.native()._joints)
        self.native().timeout_write = True
        receipt = client.invoke("x-cap.tetheria.joint_position.v1",
                                {"joint_positions": [10.0] * 16}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["commanded"])
        self.assertEqual(self.native()._joints, before)

    # -- configuration ----------------------------------------------------------------------------------------
    def test_the_speed_and_torque_writes_reach_the_native_setters(self) -> None:
        client = self.serve()
        speeds = [100, 200, 300, 400, 500, 600, 700]
        torque = [10, 20, 30, 40, 50, 60, 70]
        applied = client.invoke("cap.device.configure.v1", {"speed": speeds}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(self.native()._speeds, speeds)
        applied = client.invoke("cap.device.configure.v1", {"max_torque": torque}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(self.native()._torques, torque)

    def test_a_speed_above_the_sdk_bound_is_refused(self) -> None:
        client = self.serve()
        before = list(self.native()._speeds)
        refused = client.invoke("cap.device.configure.v1", {"speed": [0, 0, 0, 0, 0, 0, 32767]}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.native()._speeds, before)

    def test_a_torque_above_the_sdk_bound_is_refused(self) -> None:
        client = self.serve()
        before = list(self.native()._torques)
        refused = client.invoke("cap.device.configure.v1",
                                {"max_torque": [0, 0, 0, 0, 0, 0, 1001]}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.native()._torques, before)

    # -- calibration ------------------------------------------------------------------------------------------
    def test_calibrate_mid_reaches_the_native_command(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.tetheria.calibrate_mid.v1", {"servo_id": 3}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["servo_id"], 3)
        self.assertIsInstance(receipt["output"]["present_raw"], int)

    def test_calibrate_mid_refuses_servo_seven(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.tetheria.calibrate_mid.v1", {"servo_id": 7}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_a_failed_calibration_is_not_completed(self) -> None:
        client = self.serve()
        self.native().fail_calibrate = True
        receipt = client.invoke("x-cap.tetheria.calibrate_mid.v1", {"servo_id": 0}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)

    # -- safe state -------------------------------------------------------------------------------------------
    def test_the_open_hand_action_sends_the_lower_limits_and_reads_back(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call("x-cap.tetheria.open_hand.v1", {})
        self.assertEqual(output["joint_positions"], [0.0] * 7)
        self.assertEqual(len(output["actuations"]), 7)

    def test_a_normal_open_action_does_not_latch(self) -> None:
        client = self.serve()
        opened = client.invoke("x-cap.tetheria.open_hand.v1", {}, **self.ids)
        self.assertEqual(opened["status"], "completed", opened)
        moved = client.invoke("x-cap.tetheria.joint_position.v1",
                              {"joint_positions": [0.0] * 16}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)

    def test_estop_reports_failure_when_the_native_open_write_fails(self) -> None:
        client = self.serve()
        self.native().fail_joint_write = True
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertIs(receipt["output"]["safe_state_achieved"], False, receipt)

    def test_estop_reports_failure_when_the_write_timeout_is_swallowed(self) -> None:
        client = self.serve()
        self.native().timeout_write = True
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertIs(receipt["output"]["safe_state_achieved"], False, receipt)

    def test_estop_sends_the_open_command_but_does_not_claim_a_safe_state(self) -> None:
        # Model review: CTRL_POS is unacknowledged and the firmware has no stop opcode, so the e-stop
        # writes the open pose and still reports SAFE_STATE_UNREACHED with the latch held.
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        self.assertIs(receipt["output"]["safe_state_achieved"], False, receipt)
        self.assertEqual(self.native()._joints, [0.0] * 7)
        for capability, arguments in (("x-cap.tetheria.joint_position.v1", {"joint_positions": [0.0] * 16}),
                                      ("x-cap.tetheria.open_hand.v1", {})):
            refused = client.invoke(capability, arguments, **self.ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
