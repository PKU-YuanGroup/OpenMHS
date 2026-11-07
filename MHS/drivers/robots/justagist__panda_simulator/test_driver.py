"""Acceptance run of the panda_simulator gripper package: the gate, plus cases specific to this simulator.

Add cases, never remove the check_driver call.
"""

import json
import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
MOVE = "x-cap.justagist.move.v1"
GRASP = "x-cap.justagist.grasp.v1"
STOP = "x-cap.justagist.stop.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PandaGripperCases(unittest.TestCase):
    def serve(self, **options):
        server = load(HERE, backend="fake", **options)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def overlay(self):
        return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))

    def test_the_move_action_reports_its_terminal_result(self) -> None:
        client = self.serve(site_limits=self.overlay())
        receipt = client.invoke(MOVE, {"width": 0.03, "speed": 0.05}, deadline_ms=5000,
                                wait=True, wait_timeout_s=5, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["success"], receipt)

    def test_the_move_goal_carries_width_and_speed(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.call(MOVE, {"width": 0.03, "speed": 0.05})
        goals = [message for message in driver.native.sent
                 if message.get("op") == "publish"
                 and message.get("topic", "").endswith("/franka_gripper/move/goal")]
        self.assertEqual(len(goals), 1, driver.native.sent)
        self.assertEqual(goals[0]["msg"]["goal"]["width"], 0.03)
        self.assertEqual(goals[0]["msg"]["goal"]["speed"], 0.05)
        advertised = [message for message in driver.native.sent
                      if message.get("op") == "advertise"
                      and message.get("topic", "").endswith("/franka_gripper/move/goal")]
        self.assertEqual(advertised[0]["type"], "franka_gripper/MoveActionGoal")
        self.assertEqual(driver.native.positions, [0.015, 0.015])

    def test_the_grasp_goal_fixes_the_ignored_force_and_epsilon(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.call(GRASP, {"width": 0.02, "speed": 0.05})
        goals = [message for message in driver.native.sent
                 if message.get("op") == "publish"
                 and message.get("topic", "").endswith("/franka_gripper/grasp/goal")]
        self.assertEqual(len(goals), 1, driver.native.sent)
        goal = goals[0]["msg"]["goal"]
        self.assertEqual(goal["width"], 0.02)
        self.assertEqual(goal["speed"], 0.05)
        self.assertEqual(goal["force"], 0.0)
        self.assertEqual(goal["epsilon"], {"inner": 0.0, "outer": 0.0})

    def test_the_joint_state_read_returns_two_fingers(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        state = driver.read("main")
        self.assertEqual(state["finger_positions"], [0.0, 0.0], state)

    def test_a_failed_move_result_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_move_result = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(MOVE, {"width": 0.03, "speed": 0.05})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_a_malformed_result_does_not_complete_the_goal(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        fake = driver.native
        fake.malformed_result = True
        events = fake.handler({
            "op": "publish",
            "topic": "/franka_gripper/move/goal",
            "id": "goal-check",
            "msg": {"goal_id": {"id": "goal-check"}, "goal": {"width": 0.03, "speed": 0.05}},
        })
        self.assertTrue(any(event.get("topic", "").endswith("/status") for event in events))
        self.assertFalse(any(event.get("topic", "").endswith("/result") for event in events))

    def test_operator_required_bounds_refuse_until_the_site_overlay(self) -> None:
        bare = self.serve()
        refused = bare.invoke(MOVE, {"width": 0.03, "speed": 0.05}, deadline_ms=2000, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], UNSET, refused)

        overlaid = self.serve(site_limits=self.overlay())
        accepted = overlaid.invoke(MOVE, {"width": 0.03, "speed": 0.05}, deadline_ms=5000,
                                   wait=True, wait_timeout_s=5, **self.ids)
        self.assertEqual(accepted["status"], "completed", accepted)
        outside = overlaid.invoke(MOVE, {"width": 0.05, "speed": 0.05}, deadline_ms=2000, **self.ids)
        self.assertEqual(outside["status"], "rejected", outside)
        self.assertEqual(outside["error"]["mhs_code"], ENVELOPE, outside)

    def test_the_stop_action_is_the_estop_and_latches(self) -> None:
        client = self.serve(site_limits=self.overlay())
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        self.assertEqual(estop["output"]["estop"], "engaged", estop)
        self.assertTrue(estop["output"]["safe_state_achieved"], estop)
        refused = client.invoke(MOVE, {"width": 0.03, "speed": 0.05}, deadline_ms=2000, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_an_estop_during_a_running_move_is_not_confirmed(self) -> None:
        # The pinned move callback keeps waiting and never checks is_preempt_requested
        # (panda_gripper_controller.cpp:242-258): the stop is sent, but the running goal
        # leaves the e-stop unconfirmed and the latch held.
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        fake = driver.native
        fake.hold_goals = True
        server = build_server(driver, site_limits=self.overlay())
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        ids = {"device_id": device_id, "session_id": session}
        box = {}

        def move() -> None:
            box["move"] = client.invoke(MOVE, {"width": 0.03, "speed": 0.05}, deadline_ms=8000, **ids)

        worker = threading.Thread(target=move, daemon=True)
        worker.start()

        def sent(topic):
            return [message for message in list(fake.sent)
                    if message.get("op") == "publish" and message.get("topic") == topic]

        until = time.monotonic() + 5
        while not sent("/franka_gripper/move/goal") and time.monotonic() < until:
            time.sleep(0.01)
        self.assertTrue(sent("/franka_gripper/move/goal"), fake.sent)
        estop = client.estop("test", **ids)
        worker.join(10)
        self.assertEqual(estop["status"], "failed", estop)
        self.assertEqual(estop["error"]["mhs_code"], UNREACHED, estop)
        self.assertEqual(estop["output"]["estop"], "engaged", estop)
        self.assertFalse(estop["output"]["safe_state_achieved"], estop)
        self.assertTrue(sent("/franka_gripper/stop/goal"), fake.sent)
        self.assertEqual(box["move"]["status"], "unknown", box)
        refused = client.invoke(MOVE, {"width": 0.03, "speed": 0.05}, deadline_ms=2000, **ids)
        self.assertEqual(refused["status"], "rejected", refused)


if __name__ == "__main__":
    unittest.main()
