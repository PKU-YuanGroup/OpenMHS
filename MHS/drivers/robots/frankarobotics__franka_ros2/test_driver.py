"""Acceptance run of the Franka TMR spine and battery package.

The fake is an F0 recording/contract fixture; these tests exercise the declared
rosbridge topics, services and ROS 2 action, the operator-required move
envelope, the switch-off safe state, the declared switch-on re-enable after a
safety reset and the battery observation.  No ROS graph or hardware is
contacted.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
MOVE = "x-cap.frankarobotics.spine_move.v1"
HALT = "x-cap.frankarobotics.spine_halt.v1"
SWITCH_OFF = "x-cap.frankarobotics.spine_switch_off.v1"
SWITCH_ON = "x-cap.frankarobotics.spine_switch_on.v1"
BATTERY = "x-cap.frankarobotics.battery_state.v1"
CHARGE_START = "x-cap.frankarobotics.wireless_charge_start.v1"
CHARGE_STOP = "x-cap.frankarobotics.wireless_charge_stop.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
MOVE_INPUT = {"position": 0.2, "velocity": 0.1, "acceleration": 0.2, "deceleration": 0.2}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SpineCases(unittest.TestCase):
    def serve(self, *, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
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

    def test_state_reads_use_the_spine_topics(self) -> None:
        driver = self.driver()
        state = driver.read("main", ["position", "state"])
        self.assertAlmostEqual(state["position"], 0.25)
        self.assertEqual(state["state"], "SwitchedOn")

    def test_move_action_publishes_a_ros2_native_goal(self) -> None:
        driver = self.driver()
        output = driver.call(MOVE, dict(MOVE_INPUT))
        self.assertEqual(output, {"reached": True, "stop_by": "Finished", "error": ""})
        goals = [message for message in driver.native.sent if message.get("op") == "send_action_goal"]
        self.assertEqual(len(goals), 1)
        goal = goals[0]
        self.assertEqual(goal["action"], "/franka_spine_node/move_absolute")
        self.assertEqual(goal["action_type"], "franka_spine_msgs/action/MoveAbsolute")
        self.assertEqual(goal["args"], MOVE_INPUT)
        self.assertEqual(driver.read("main", ["position"])["position"], 0.2)

    def test_move_is_refused_without_the_operator_overlay(self) -> None:
        client = self.serve()
        receipt = client.invoke(MOVE, dict(MOVE_INPUT), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_move_is_accepted_inside_the_example_overlay(self) -> None:
        client = self.serve(site_limits=HERE / "site-limits.example.json")
        receipt = client.invoke(MOVE, dict(MOVE_INPUT), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["reached"], True)

    def test_estop_switches_off_and_latches_ordinary_motion(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        refused = client.invoke(HALT, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        allowed = client.invoke(SWITCH_OFF, {}, **self.ids)
        self.assertEqual(allowed["status"], "completed", allowed)
        self.assertEqual(allowed["output"]["switched_off"], True)

    def test_switch_off_transport_failure_does_not_report_a_safe_state(self) -> None:
        driver = self.driver()
        driver.native.fail_switch_off_transport = True
        with self.assertRaises(DriverFailed):
            driver.call(SWITCH_OFF, {})

    def test_switch_off_application_failure_does_not_report_a_safe_state(self) -> None:
        driver = self.driver()
        driver.native.fail_switch_off_application = True
        with self.assertRaises(DriverFailed):
            driver.call(SWITCH_OFF, {})

    def test_estop_transport_failure_is_reported_through_the_native_stop(self) -> None:
        driver = self.driver()
        driver.native.fail_switch_off_transport = True
        with self.assertRaises(DriverFailed) as caught:
            driver.estop("test")
        self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_estop_application_failure_is_reported_through_the_native_stop(self) -> None:
        driver = self.driver()
        driver.native.fail_switch_off_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.estop("test")
        self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_halt_rearms_while_switch_off_disables(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(HALT, {})["state"], "SwitchedOn")
        self.assertEqual(driver.call(SWITCH_OFF, {})["state"], "SwitchedOff")

    def test_switch_on_is_the_declared_reenable(self) -> None:
        client = self.serve()
        manifest = next(item for item in client.devices() if item["device_id"] == self.ids["device_id"])
        self.assertEqual(manifest["safety"]["estop"]["reenable"], SWITCH_ON)
        self.assertNotIn(SWITCH_ON, manifest["safety"]["safe_state"]["achieved_by"])

    def test_switch_on_calls_the_private_switch_on_service(self) -> None:
        driver = self.driver()
        driver.call(SWITCH_OFF, {})
        output = driver.call(SWITCH_ON, {})
        self.assertEqual(output, {"switched_on": True, "state": "SwitchedOn", "message": "Switch on successful"})
        calls = [message for message in driver.native.sent
                 if message.get("op") == "call_service" and message.get("service") == "/franka_spine_node/switch_on"]
        self.assertEqual(len(calls), 1)

    def test_reset_never_rearms_and_switch_on_recovers_motion(self) -> None:
        client = self.serve(site_limits=HERE / "site-limits.example.json")
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = client.invoke(SWITCH_ON, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"]["reenable"], SWITCH_ON)
        # The reset re-armed nothing: the drive is still SwitchedOff and the move fails at the device.
        still_off = client.invoke(MOVE, dict(MOVE_INPUT), **self.ids)
        self.assertEqual(still_off["status"], "failed", still_off)
        enabled = client.invoke(SWITCH_ON, {}, **self.ids)
        self.assertEqual(enabled["status"], "completed", enabled)
        self.assertEqual(enabled["output"]["state"], "SwitchedOn")
        moved = client.invoke(MOVE, dict(MOVE_INPUT), **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"]["reached"], True)

    def test_switch_on_transport_failure_is_not_a_reenable(self) -> None:
        driver = self.driver()
        driver.call(SWITCH_OFF, {})
        driver.native.fail_switch_on_transport = True
        with self.assertRaises(DriverFailed):
            driver.call(SWITCH_ON, {})
        self.assertEqual(driver.native.state, "SwitchedOff")

    def test_switch_on_application_failure_is_not_a_reenable(self) -> None:
        driver = self.driver()
        driver.call(SWITCH_OFF, {})
        driver.native.fail_switch_on_application = True
        with self.assertRaises(DriverFailed):
            driver.call(SWITCH_ON, {})
        self.assertEqual(driver.native.state, "SwitchedOff")


class BatteryCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_battery_state_observation_reports_the_published_sample(self) -> None:
        driver = self.driver()
        output = driver.call(BATTERY, {})
        self.assertAlmostEqual(output["percentage"], 0.73)
        self.assertAlmostEqual(output["temperature"], 24.0)
        self.assertEqual(output["power_supply_status"], 2)
        self.assertEqual(output["location"], "")

    def test_charge_controls_are_acknowledged_and_reflected_in_the_sample(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(CHARGE_START, {}), {"accepted": True, "message": "charge command accepted"})
        self.assertEqual(driver.call(BATTERY, {})["power_supply_status"], 1)
        self.assertEqual(driver.call(CHARGE_STOP, {}), {"accepted": True, "message": "charge command accepted"})
        self.assertEqual(driver.call(BATTERY, {})["power_supply_status"], 2)


if __name__ == "__main__":
    unittest.main()
