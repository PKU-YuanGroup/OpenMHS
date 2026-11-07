"""Acceptance run and repository-specific cases for the will0103 ROS 2 package.

The action cases exercise the pinned ROS 2 native action wire through the
package's ROS-free recording fake.  The e-stop cases exercise the companion
gz-sim world pause confirmed by the E2 read-back of WorldStatistics.paused in
fresh samples, its four failure switches, a reset that leaves the world paused,
and the absence of an unpause.  They are fake-only contract checks; no ROS
graph, rosbridge server, Gazebo world or hardware is contacted.

``test_gate`` reads lock companions from ``MHS_DRIVER_GATE_COMPANIONS`` when
that variable is set, and otherwise from ``work/companions``.  The needed_by
widening for this package lives in the unit's companions root until the
orchestrator applies it.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CAP = "x-cap.will0103.move-robot.v1"
ACTION = "/move_robot"
ACTION_TYPE = "my_robot_interfaces/action/MoveRobot"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
CONTROL = "/world/empty/control"
STATS = "/world/empty/stats"

#: The committed example overlay.  Its numbers are example envelopes, not device facts.
OVERLAY = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MoveRobotCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    @staticmethod
    def payload(linear=0.0, angular=0.0, duration=1.0):
        return {"linear_vel_x": linear, "angular_vel_z": angular, "duration": duration}

    def test_move_robot_sends_the_pinned_goal_and_reports_what_it_sent(self) -> None:
        driver = self.driver()
        receipt = driver.call(CAP, self.payload(0.2, -0.3, 1.0))
        self.assertEqual(receipt, {
            "success": True,
            "message": "robot arrived destination !",
            "sent_linear_vel_x": 0.2,
            "sent_angular_vel_z": -0.3,
            "sent_duration": 1.0,
        })
        goals = [message for message in driver.native.sent if message.get("op") == "send_action_goal"]
        self.assertEqual(len(goals), 1, goals)
        self.assertEqual(goals[0]["action"], ACTION)
        self.assertEqual(goals[0]["action_type"], ACTION_TYPE)
        self.assertEqual(goals[0]["args"], {"linear_vel_x": 0.2, "angular_vel_z": -0.3, "duration": 1.0})

    def test_operator_required_goal_is_refused_without_an_overlay(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke(CAP, self.payload(0.2, 0.0, 1.0),
                                device_id=device_id, session_id=session_id)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")

    def test_application_failure_is_not_hidden(self) -> None:
        driver = self.driver()
        driver.native.fail_application = True
        with self.assertRaises(DriverFailed):
            driver.call(CAP, self.payload())

    def test_protocol_error_is_not_hidden(self) -> None:
        driver = self.driver()
        driver.native.fail_protocol = True
        with self.assertRaises(Exception):
            driver.call(CAP, self.payload())

    def test_cancellation_leaves_a_queued_goal_running(self) -> None:
        driver = self.driver()
        driver.native.hold_goals = True
        first = {"op": "send_action_goal", "action": ACTION, "action_type": ACTION_TYPE,
                 "id": "goal-1", "args": self.payload(duration=5.0)}
        second = {"op": "send_action_goal", "action": ACTION, "action_type": ACTION_TYPE,
                  "id": "goal-2", "args": self.payload(duration=5.0)}
        self.assertIsNone(driver.native._respond(first))
        self.assertIsNone(driver.native._respond(second))
        cancelled = driver.native._respond({"op": "cancel_action_goal", "action": ACTION, "id": "goal-1"})
        self.assertEqual(cancelled["status"], 5, cancelled)   # ROS 2 CANCELED
        self.assertEqual(driver.native.active["message"]["id"], "goal-2")
        self.assertEqual(driver.native.cancel_with_queued, 1)
        self.assertEqual(driver.native.cancelled, 1)
        self.assertEqual(driver.native.completed, 0)
        driver.native.hold_goals = False
        completed = driver.native.release_goal()
        self.assertEqual(completed["status"], 4, completed)   # the queued goal survived and ran
        self.assertEqual(driver.native.completed, 1)
        self.assertEqual(driver.native.zero_twists, 2)

    def served(self, **switches):
        driver = self.driver()
        for name, value in switches.items():
            setattr(driver.native, name, value)
        server = build_server(driver, site_limits=OVERLAY)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def test_the_e_stop_pauses_the_world_and_confirms_it_from_fresh_statistics(self) -> None:
        driver, client = self.served()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(driver.native.controls, [{"pause": True}])
        self.assertTrue(driver.native.paused)
        wire = [(message.get("op"), message.get("service") or message.get("topic")) for message in driver.native.sent
                if message.get("op") in ("call_service", "subscribe", "unsubscribe")]
        self.assertEqual(wire, [("call_service", CONTROL), ("subscribe", STATS), ("unsubscribe", STATS)])
        refused = client.invoke(CAP, self.payload(0.2, 0.0, 1.0), **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_safety_status_keeps_the_retained_confirmation_after_an_external_unpause(self) -> None:
        driver, client = self.served()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        before = len(driver.native.sent)
        driver.native.paused = False
        status = client.safety_status(self.ids["device_id"])
        self.assertEqual(len(driver.native.sent), before, driver.native.sent[before:])
        self.assertTrue(status["estop"]["confirmed"], status)
        self.assertTrue(status["status"]["safe_state"]["achieved"], status)
        self.assertFalse(driver.native.paused)

    def test_an_unanswered_or_failed_pause_a_running_world_or_no_statistics_leave_the_e_stop_unconfirmed(self):
        for switch in ("fail_control", "reject_control", "ignore_pause", "silent_stats"):
            with self.subTest(switch=switch):
                _driver, client = self.served(**{switch: True})
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
                self.assertTrue(receipt["output"]["latched"], receipt)

    def test_the_reset_keeps_the_world_paused_and_offers_no_unpause(self) -> None:
        driver, client = self.served()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        self.assertIsNone(driver._model.reenable)
        receipt = client.invoke(CAP, self.payload(0.2, -0.3, 1.0), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["sent_linear_vel_x"], 0.2)
        self.assertEqual(receipt["output"]["sent_angular_vel_z"], -0.3)
        self.assertEqual(receipt["output"]["sent_duration"], 1.0)
        self.assertEqual([control.get("pause") for control in driver.native.controls], [True])

    def test_two_goals_report_different_transmitted_requests(self) -> None:
        driver, client = self.served()
        first = client.invoke(CAP, self.payload(0.1, 0.0, 1.0), **self.ids)
        second = client.invoke(CAP, self.payload(0.2, 0.4, 2.0), **self.ids)
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(second["status"], "completed", second)
        self.assertNotEqual(first["output"], second["output"])
        self.assertEqual(first["output"]["sent_linear_vel_x"], 0.1)
        self.assertEqual(second["output"]["sent_duration"], 2.0)

    def test_the_declaration_names_the_operator_run_bridges(self) -> None:
        cls = type(self.driver())
        self.assertEqual([item["args"].split("@")[0] for item in cls.operator_bridges], [CONTROL, STATS])
        self.assertEqual(cls.estop_latency_ms, 1500)
        self.assertIsNone(cls.safety_bindings.get("reenable") if isinstance(cls.safety_bindings, dict)
                          else None)
        self.assertNotIn("reenable", cls.safety_bindings)
        reference = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
        self.assertEqual(len(reference["safety"]["operator_bridges"]), 2)
        self.assertIn("## Operator must run", (HERE / "REFERENCE.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
