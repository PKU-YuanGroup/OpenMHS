"""Acceptance run of the UR arm package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
PERMIT = "MHS.SAFETY.PERMIT_INVALID"
FAULTED = "MHS.DEVICE.FAULTED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
MOVE = "cap.motion.joint_position.v1"
PAUSE = "x-cap.ad-sdl.pause_program.v1"
STOP = "x-cap.ad-sdl.stop_program.v1"
POWER_OFF = "x-cap.ad-sdl.power_off.v1"
POWER_ON = "x-cap.ad-sdl.power_on.v1"
TARGET = [0.0, -0.5, 0.0, -1.0, 0.0, 0.5]     # placeholder: inside the example overlay


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UrModuleCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.arm = driver.native                       # the fake UR
        self.dashboard = self.arm.ur_dashboard
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def overlay(self):
        return self.serve(str(HERE / "site-limits.example.json"))

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def code(self, receipt):
        return (receipt.get("error") or {}).get("mhs_code")

    def power_on(self, client):
        permit = client.permit(POWER_ON, {}, device_id=self.ids["device_id"], resource="main")
        return client.invoke(POWER_ON, {}, permit_id=permit["permit_id"], **self.ids)

    def test_the_reads_and_the_operator_bound(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["robot_mode"], "RUNNING")
        self.assertEqual(state["safety_status"], "NORMAL")
        self.assertEqual(state["operational_mode"], "AUTOMATIC")
        self.assertEqual(state["movement_state"], "READY")
        self.assertEqual(state["loaded_program"], "No program loaded")
        self.assertEqual(len(state["joint_positions"]), 6)
        refused = client.invoke(MOVE, {"joint_positions": [0.0] * 6}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(self.code(refused), LIMITS_UNSET)

    def test_a_silent_dashboard_fails_the_read_instead_of_dropping_the_field(self) -> None:
        client = self.serve()
        self.dashboard.silent.add("programState")      # send_command returned None (a swallowed socket error)
        with self.assertRaises(MHSError):
            self.state(client)

    def test_the_example_overlay_moves_and_bounds(self) -> None:
        client = self.overlay()
        moved = client.invoke(MOVE, {"joint_positions": TARGET}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertTrue(moved["output"]["reached"])
        self.assertEqual(self.state(client)["joint_positions"], TARGET)
        refused = client.invoke(MOVE, {"joint_positions": [4.0] * 6}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(self.code(refused), ENVELOPE)
        self.assertEqual(self.state(client)["joint_positions"], TARGET)

    def test_a_failed_move_is_a_failed_receipt(self) -> None:
        client = self.overlay()
        self.arm.fail_moves = True
        failed = client.invoke(MOVE, {"joint_positions": TARGET}, **self.ids)
        self.assertEqual(failed["status"], "failed", failed)
        self.assertEqual(self.code(failed), FAULTED)
        self.assertEqual(self.state(client)["joint_positions"], [0.0] * 6)

    def test_pause_and_stop_complete_only_on_the_manual_answer(self) -> None:
        client = self.serve()
        self.dashboard.program_state = "PLAYING"       # a program started elsewhere (the pendant)
        paused = client.invoke(PAUSE, {}, **self.ids)
        self.assertEqual(paused["status"], "completed", paused)
        self.assertEqual(paused["output"]["response"], "Pausing program")
        self.assertEqual(self.state(client)["program_state"], "PAUSED")
        stopped = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"]["response"], "Stopped")
        self.assertEqual(self.state(client)["program_state"], "STOPPED")

    def test_a_refused_or_unanswered_program_command_is_a_failed_receipt(self) -> None:
        client = self.serve()
        self.dashboard.answers["stop"] = "Failed to execute: stop"
        refused = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(self.code(refused), FAULTED)
        self.dashboard.silent.add("pause")
        silent = client.invoke(PAUSE, {}, **self.ids)
        self.assertEqual(silent["status"], "failed", silent)
        self.assertEqual(self.code(silent), FAULTED)

    def test_the_estop_powers_off_confirms_and_the_reset_does_not_rearm(self) -> None:
        client = self.overlay()
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        self.assertEqual(self.state(client)["robot_mode"], "POWER_OFF")
        self.assertGreaterEqual(self.dashboard.sent.count("power off"), 2)     # the @estop and the safe state
        for capability in (PAUSE, STOP, POWER_ON):
            refused = client.invoke(capability, {}, **self.ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(self.code(refused), ESTOP)
        self.assertNotIn("brake release", self.dashboard.sent)
        reset = client.reset(device_id=self.ids["device_id"], session_id=self.ids["session_id"])
        self.assertEqual(reset.get("status"), "completed", reset)
        self.assertEqual(self.state(client)["robot_mode"], "POWER_OFF")       # the reset releases the latch only
        self.assertNotIn("brake release", self.dashboard.sent)
        moved = client.invoke(MOVE, {"joint_positions": TARGET}, **self.ids)
        self.assertEqual(moved["status"], "failed", moved)                     # the arm is still off
        self.assertEqual(self.code(moved), FAULTED)

    def test_the_reenable_needs_a_permit_and_confirms_running(self) -> None:
        client = self.overlay()
        client.estop("test", **self.ids)
        client.reset(device_id=self.ids["device_id"], session_id=self.ids["session_id"])
        unpermitted = client.invoke(POWER_ON, {}, **self.ids)
        self.assertEqual(unpermitted["status"], "rejected", unpermitted)
        self.assertEqual(self.code(unpermitted), PERMIT)
        self.assertNotIn("brake release", self.dashboard.sent)
        enabled = self.power_on(client)
        self.assertEqual(enabled["status"], "completed", enabled)
        self.assertEqual(enabled["output"]["robot_mode"], "RUNNING")
        self.assertEqual(self.dashboard.sent.count("brake release"), 1)
        moved = client.invoke(MOVE, {"joint_positions": TARGET}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)

    def test_the_reenable_never_clears_a_safety_state(self) -> None:
        client = self.overlay()
        client.estop("test", **self.ids)
        client.reset(device_id=self.ids["device_id"], session_id=self.ids["session_id"])
        self.dashboard.safety_status = "PROTECTIVE_STOP"
        refused = self.power_on(client)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(self.code(refused), PRECONDITION)
        self.assertNotIn("brake release", self.dashboard.sent)
        self.assertEqual(self.state(client)["robot_mode"], "POWER_OFF")

    def test_an_unconfirmed_brake_release_fails_the_reenable(self) -> None:
        client = self.overlay()
        client.estop("test", **self.ids)
        client.reset(device_id=self.ids["device_id"], session_id=self.ids["session_id"])
        self.dashboard.answers["brake release"] = "Failed to execute: brake release"
        failed = self.power_on(client)
        self.assertEqual(failed["status"], "failed", failed)
        self.assertEqual(self.code(failed), FAULTED)
        self.assertEqual(self.state(client)["robot_mode"], "POWER_OFF")

    def test_an_unanswered_power_off_leaves_the_estop_unreached_and_latched(self) -> None:
        client = self.serve()
        self.dashboard.silent.add("power off")
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "failed", estop)
        self.assertEqual(self.code(estop), UNREACHED)
        refused = client.invoke(PAUSE, {}, **self.ids)
        self.assertEqual(self.code(refused), ESTOP)
        self.assertEqual(self.dashboard.robot_mode, "RUNNING")

    def test_a_power_off_without_power_off_mode_leaves_the_estop_unreached(self) -> None:
        client = self.serve()
        self.dashboard.ignore_power_off = True          # answered, but the robot mode stays RUNNING
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "failed", estop)
        self.assertEqual(self.code(estop), UNREACHED)
        refused = client.invoke(PAUSE, {}, **self.ids)
        self.assertEqual(self.code(refused), ESTOP)


if __name__ == "__main__":
    unittest.main()
