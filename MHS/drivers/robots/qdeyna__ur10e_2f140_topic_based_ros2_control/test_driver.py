"""Acceptance and package-specific cases for the UR10e fake-hardware contract.

The cases exercise the trajectory action and the joint-state reads, the companion-cited stop (the controller
manager's switch that deactivates scaled_joint_trajectory_controller, confirmed by the E4 list-element read-back of
list_controllers), its failure paths, the latch, the reset and the declared re-enable that activates the controller
again.  Add cases, never remove the check_driver call.
"""

import os
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
ACTION = "x-cap.qdeyna.arm_trajectory.v1"
STATE = "x-cap.qdeyna.joint_state.v1"
REENABLE = "x-cap.qdeyna.activate_controller.v1"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
SWITCH = "/controller_manager/switch_controller"
LIST = "/controller_manager/list_controllers"
JOINTS = [
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
]


def trajectory(positions, sec=1, nanosec=0):
    return {"points": [{"positions": list(positions),
                        "time_from_start": {"sec": sec, "nanosec": nanosec}}]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        # The real work/companions LOCK.json lists these pins for another package only.
        # MHS_DRIVER_GATE_COMPANIONS points at the widened local view when this unit runs the gate.
        root = os.environ.get("MHS_DRIVER_GATE_COMPANIONS")
        options = {"companions_root": root} if root else {}
        report = check_driver(HERE, backend="fake", **options)
        self.assertEqual(report["failed"], [], report)


class Ur10eArmCases(unittest.TestCase):
    def serve(self, *, overlay=True):
        server = load(HERE, backend="fake", site_limits=OVERLAY if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_trajectory_action_updates_the_joint_state(self) -> None:
        client = self.serve()
        target = [0.1, -0.2, 0.3, -0.4, 0.5, -0.6]
        receipt = client.invoke(ACTION, trajectory(target), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["error_code"], 0)
        self.assertEqual(receipt["output"]["error_string"], "")
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(state["joint_positions"], target)
        self.assertEqual(len(state["joint_velocities"]), 6)

    def test_the_joint_state_observation_returns_the_publisher_arrays(self) -> None:
        client = self.serve()
        receipt = client.invoke(STATE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["name"], JOINTS)
        self.assertEqual(len(receipt["output"]["position"]), 6)
        self.assertEqual(len(receipt["output"]["velocity"]), 6)

    def test_an_out_of_envelope_joint_position_is_refused_before_the_fake(self) -> None:
        client = self.serve()
        receipt = client.invoke(ACTION, trajectory([7.0, 0.0, 0.0, 0.0, 0.0, 0.0]), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_operator_required_bounds_are_refused_without_the_overlay(self) -> None:
        client = self.serve(overlay=False)
        receipt = client.invoke(ACTION, trajectory([0.0] * 6), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_the_overlay_fills_the_trajectory_time_envelope(self) -> None:
        client = self.serve()
        receipt = client.invoke(ACTION, trajectory([0.0] * 6, sec=10, nanosec=999999999), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_a_rejected_controller_result_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.reject_goal = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(ACTION, trajectory([0.0] * 6))
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")
        self.assertEqual(driver.native.action_calls, 1)

    def test_a_transport_error_is_an_unknown_outcome(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_transport = True
        with self.assertRaises(OutcomeUnknown):
            driver.call(ACTION, trajectory([0.0] * 6))
        self.assertEqual(driver.native.action_calls, 1)

    def served(self, **switches):
        driver = load_driver(HERE, "fake")
        for name, value in switches.items():
            setattr(driver.native, name, value)
        server = build_server(driver, site_limits=OVERLAY)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    @staticmethod
    def services(native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    def test_the_estop_deactivates_the_controller_and_reads_it_back(self) -> None:
        driver, client = self.served()
        estop = client.estop("package test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        self.assertEqual(estop["output"]["estop"], "engaged")
        self.assertTrue(estop["output"]["safe_state_achieved"], estop)
        self.assertEqual(self.services(driver.native), [SWITCH, LIST])
        self.assertEqual(driver.native.switch_requests[0]["deactivate_controllers"],
                         ["scaled_joint_trajectory_controller"])
        self.assertEqual(driver.native.jtc_state, "inactive")
        receipt = client.invoke(ACTION, trajectory([0.0] * 6), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ESTOP)

    def test_a_failed_switch_or_an_unconfirming_list_leaves_the_estop_unconfirmed(self) -> None:
        for switch in ("fail_switch", "ignore_switch", "duplicate_listing"):
            with self.subTest(switch=switch):
                _driver, client = self.served(**{switch: True})
                estop = client.estop("package test", **self.ids)
                self.assertEqual(estop["status"], "failed", estop)
                self.assertEqual(estop["error"]["mhs_code"], UNREACHED)
                self.assertTrue(estop["output"]["latched"], estop)

    def test_the_reenable_is_refused_while_latched_and_holds_position_after_the_reset(self) -> None:
        driver, client = self.served()
        self.assertEqual(client.invoke(ACTION, trajectory([0.1] * 6), **self.ids)["status"], "completed")
        self.assertEqual(client.estop("package test", **self.ids)["status"], "completed")
        refused = client.invoke(REENABLE, {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(driver.native.jtc_state, "inactive")  # the reset re-activates nothing (SAFE-042)
        receipt = client.invoke(REENABLE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"acknowledged": True})
        self.assertEqual(driver.native.jtc_state, "active")
        self.assertEqual(driver.native.switch_requests[-1]["activate_controllers"],
                         ["scaled_joint_trajectory_controller"])
        self.assertEqual(driver.native.joint_positions, [0.1] * 6)  # holds where it is; nothing resumes
        moved = client.invoke(ACTION, trajectory([0.2] * 6), **self.ids)
        self.assertEqual(moved["status"], "completed", moved)

    def test_an_inactive_controller_rejects_a_goal(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.jtc_state = "inactive"
        with self.assertRaises(DriverFailed):
            driver.call(ACTION, trajectory([0.0] * 6))


if __name__ == "__main__":
    unittest.main()
