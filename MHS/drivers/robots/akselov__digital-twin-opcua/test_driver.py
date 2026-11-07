"""Acceptance run of the KUKA KVP package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): its ``_commands`` list is
what reached the "controller".  Nothing here ran on a robot.
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
CAP = "x-cap.akselov.joint_position.v1"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
TARGET = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class KukaCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.driver = driver
        self.fake = driver.native
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.fake._commands[:]
        return self.client

    def move(self, values):
        return self.client.invoke(CAP, {"joint_positions": values}, **self.ids)

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def writes(self):
        return [command for command in self.fake._commands if command[0] == "write"]

    def test_the_state_reads_the_axis_and_motor_arrays(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual(state["joint_positions"], ZERO)
        self.assertEqual(state["motor_velocities"], ZERO)
        self.assertEqual(state["motor_torques"], ZERO)
        self.assertEqual(state["motor_currents"], ZERO)

    def test_a_move_writes_the_e6axis_text_and_changes_the_state(self) -> None:
        self.serve(OVERLAY)
        receipt = self.move(TARGET)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["joint_positions"], TARGET)
        self.assertEqual(receipt["output"]["target_axis_reply"], "1")
        writes = self.writes()
        self.assertEqual(len(writes), 1, writes)
        self.assertEqual(writes[0][1], "TARGET_AXIS")
        self.assertEqual(writes[0][2], "{E6AXIS: A1 1.0, A2 2.0, A3 3.0, A4 4.0, A5 5.0, A6 6.0}")
        self.assertEqual(self.state()["joint_positions"], TARGET)

    def test_the_operator_required_bound_refuses_without_the_overlay(self) -> None:
        self.serve()
        refused = self.move(TARGET)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.writes(), [])

    def test_the_example_overlay_bounds_the_move(self) -> None:
        self.serve(OVERLAY)
        over = list(ZERO)
        over[0] = 11.0
        refused = self.move(over)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(refused["error"]["details"]["path"], "joint_positions[0]")
        self.assertEqual(refused["error"]["details"]["bound"], 10)
        self.assertEqual(self.writes(), [])
        edge = list(ZERO)
        edge[0] = 10.0
        self.assertEqual(self.move(edge)["status"], "completed")
        self.assertEqual(self.writes()[0][2], "{E6AXIS: A1 10.0, A2 0.0, A3 0.0, A4 0.0, A5 0.0, A6 0.0}")

    def test_the_estop_freezes_the_target_and_latches(self) -> None:
        self.serve(OVERLAY)
        self.assertEqual(self.move(TARGET)["status"], "completed")
        del self.fake._commands[:]
        estop = self.client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        writes = self.writes()
        self.assertEqual(len(writes), 1, writes)
        self.assertEqual(writes[0][1], "TARGET_AXIS")
        self.assertEqual(writes[0][2], "{E6AXIS: A1 1.0, A2 2.0, A3 3.0, A4 4.0, A5 5.0, A6 6.0}")
        before = len(self.writes())
        refused = self.move(ZERO)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(len(self.writes()), before)

    def test_a_failed_native_write_is_a_failed_receipt(self) -> None:
        self.serve(OVERLAY)
        self.fake._force_write_failure()
        receipt = self.move(TARGET)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.ADAPTER.SHIM_FAILED")
        self.assertEqual(len(self.writes()), 1)          # the command reached the fake, then the link failed

    def test_a_read_back_that_fails_after_the_write_is_unknown(self) -> None:
        self.serve(OVERLAY)
        self.fake._corrupt_axis_read_after_write()
        receipt = self.move(TARGET)
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("unknown", "MHS.OUTCOME.UNKNOWN"))
        self.assertEqual(len(self.writes()), 1)

    def test_the_reference_declares_the_physical_stop(self) -> None:
        reference = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
        safety = reference["safety"]
        self.assertEqual(safety["estop"]["native"], "write")
        self.assertEqual(safety["estop"]["physical_ref"], "opcua-control/opcua_ptp_movement.src:9-10")
        self.assertIsNone(safety.get("watchdog_ms"))
        unset = sorted((item["name"], item["path"]) for item in safety["operator_required"])
        self.assertEqual(unset, [("move_joints", "joint_positions")])

    def test_the_hardware_backend_is_refused_until_a_human_signs_the_review(self) -> None:
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, backend="hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
