"""Acceptance run of the panda_gazebo ROS package: the gate, plus repository cases.

Add cases, never remove the ``check_driver`` call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


def _overlay():
    return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PandaGazeboCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake", site_limits=_overlay())
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_joint_state_read_returns_a_joint_state(self) -> None:
        client = self.serve()
        state = client.read("main", **self.ids)["state"]
        self.assertIn("joint_state", state)
        self.assertEqual(len(state["joint_state"]["name"]), len(state["joint_state"]["position"]))
        self.assertEqual(state["joint_state"]["name"][0], "panda_joint1")

    def test_the_gripper_service_receives_the_doubled_finger_width(self) -> None:
        driver = self.driver()
        output = driver.call(
            "x-cap.rickstaa.gripper_width.v1", {"finger_width": 0.04, "force": 10}
        )
        self.assertTrue(output["accepted"])
        self.assertEqual(driver.native.last_width, 0.08)
        self.assertEqual(driver.native.last_force, 10.0)

    def test_the_trajectory_action_returns_the_error_code(self) -> None:
        client = self.serve()
        receipt = client.invoke(
            "x-cap.rickstaa.follow_joint_trajectory.v1",
            {"points": [{"positions": [0.0, -0.5, 0.0, -2.0, 0.0, 2.0, 0.0]}],
             "time_axis_step": 0.1, "timeout_s": 10},
            **self.ids,
        )
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["error_code"], 0)
        self.assertEqual(receipt["output"]["error_string"], "")

    def test_the_lock_action_reaches_the_world_plugin_service(self) -> None:
        driver = self.driver()
        receipt = driver.call("x-cap.rickstaa.lock_joints.v1", {})
        self.assertEqual(receipt, {"locked": True, "message": "Joint locking successful"})
        self.assertTrue(driver.native.locked)
        self.assertEqual(len(driver.native.locked_joints), 9)

    def test_a_width_outside_the_per_finger_clip_is_refused_before_the_service(self) -> None:
        client = self.serve()
        receipt = client.invoke(
            "x-cap.rickstaa.gripper_width.v1",
            {"finger_width": 0.2, "force": 10},
            **self.ids,
        )
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_a_width_inside_the_upstream_clip_but_beyond_the_finger_limit_is_refused(self) -> None:
        # The wrapper's own clip would pass 0.06 m per finger; the clone's finger joint limit is 0.04 m.
        client = self.serve()
        receipt = client.invoke(
            "x-cap.rickstaa.gripper_width.v1",
            {"finger_width": 0.06, "force": 10},
            **self.ids,
        )
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_a_force_above_the_cited_maximum_is_refused_before_the_service(self) -> None:
        client = self.serve()
        receipt = client.invoke(
            "x-cap.rickstaa.gripper_width.v1",
            {"finger_width": 0.04, "force": 200},
            **self.ids,
        )
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_trajectory_inputs_without_the_operator_envelope_are_unset(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke(
            "x-cap.rickstaa.follow_joint_trajectory.v1",
            {"points": [{"positions": [0.0, -0.5, 0.0, -2.0, 0.0, 2.0, 0.0]}],
             "time_axis_step": 0.1, "timeout_s": 10},
            device_id=device_id, session_id=session,
        )
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")

    def test_a_rejected_lock_application_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_lock_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.rickstaa.lock_joints.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_a_failed_lock_transport_does_not_report_a_lock(self) -> None:
        driver = self.driver()
        driver.native.fail_lock_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.rickstaa.lock_joints.v1", {})
        self.assertFalse(driver.native.locked)

    def _estop_with_native_flag(self, flag):
        driver = load_driver(HERE, "fake")
        setattr(driver.native, flag, True)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client.estop("test", device_id=device_id, session_id=session)

    def test_a_failed_lock_application_fails_the_estop(self) -> None:
        receipt = self._estop_with_native_flag("fail_lock_application")
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_a_malformed_lock_reply_fails_the_estop(self) -> None:
        receipt = self._estop_with_native_flag("malformed_lock_result")
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_the_estop_locks_and_refuses_further_commands(self) -> None:
        driver = load_driver(HERE, "fake")
        server = build_server(driver, site_limits=_overlay())
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        ids = {"device_id": device_id, "session_id": session}
        receipt = client.estop("test", **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        # The served driver's own transport received the lock request for all nine joints.
        self.assertTrue(driver.native.locked)
        self.assertEqual(len(driver.native.locked_joints), 9)
        refused = client.invoke(
            "x-cap.rickstaa.gripper_width.v1",
            {"finger_width": 0.04, "force": 10},
            **ids,
        )
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
