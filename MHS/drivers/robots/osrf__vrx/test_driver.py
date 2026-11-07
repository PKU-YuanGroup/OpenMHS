"""Acceptance run of the VRX package: the gate plus repository-specific cases.

The fake is a ROS-free F0 canned transport.  These cases exercise the two
competition-bridge observations, the four thruster publications and their
receipts, operator bounds, malformed/silent observations, the companion-cited
stop (the gz-sim world pause confirmed by the E2 read-back of
WorldStatistics.paused in fresh samples), its failure paths, a reset that
leaves the world paused, the absence of an unpause and the operator bridges.
No Gazebo process, ROS graph or hardware is contacted.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.bridge.base import BridgeContext
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CLOCK = "x-cap.osrf.clock.v1"
TASK_INFO = "x-cap.osrf.task-info.v1"
LEFT_THRUST = "x-cap.osrf.left-thrust.v1"
RIGHT_THRUST = "x-cap.osrf.right-thrust.v1"
LEFT_POS = "x-cap.osrf.left-thrust-position.v1"
RIGHT_POS = "x-cap.osrf.right-thrust-position.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
CONTROL = "/world/sydney_regatta/control"
STATS = "/world/sydney_regatta/stats"

#: Test-only operator overlay.  The numbers are local test data, not device
#: facts and not a recommendation for a deployment envelope.
OVERLAY = {
    "$schema": "https://openmhs.invalid/schema/0.9/site-limits.schema.json",
    "openmhs": "0.9",
    "site": "unit-test overlay",
    "issued_by": {"id": "operator:test"},
    "devices": {
        "mhs://localhost/vrx": {
            LEFT_THRUST: {"thrust": {"min": -1000.0, "max": 1000.0, "unit": "1",
                                     "source": "operator", "reason": "test overlay"}},
            RIGHT_THRUST: {"thrust": {"min": -1000.0, "max": 1000.0, "unit": "1",
                                      "source": "operator", "reason": "test overlay"}},
            LEFT_POS: {"position": {"min": -1.0, "max": 1.0, "unit": "1",
                                    "source": "operator", "reason": "test overlay"}},
            RIGHT_POS: {"position": {"min": -1.0, "max": 1.0, "unit": "1",
                                     "source": "operator", "reason": "test overlay"}},
        }
    },
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class VrxCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self):
        server = load(HERE, backend="fake", site_limits=OVERLAY)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_clock_observation_returns_a_clock_sample(self) -> None:
        output = self.driver().call(CLOCK, {})
        self.assertEqual(set(output["sim_time"]), {"sec", "nanosec"})  # ROS 2 builtin_interfaces/Time

    def test_the_task_info_observation_returns_param_entries(self) -> None:
        output = self.driver().call(TASK_INFO, {})
        self.assertIsInstance(output["params"], list)
        self.assertTrue(output["params"])
        self.assertEqual(set(output["params"][0]), {"name", "value"})
        types = {item["name"]: item["value"]["type"] for item in output["params"]}
        self.assertEqual((types["state"], types["timed_out"], types["num_collisions"], types["score"]), (4, 1, 2, 3))

    def test_a_silent_clock_is_an_observation_timeout_not_a_held_value(self) -> None:
        driver = self.driver()
        driver.native.withhold_clock = True
        with self.assertRaises(Exception) as caught:
            driver.call(CLOCK, {}, BridgeContext(deadline_ms=50))
        self.assertIn("MHS.", str(caught.exception))

    def test_a_silent_task_info_is_an_observation_timeout(self) -> None:
        driver = self.driver()
        driver.native.withhold_task_info = True
        with self.assertRaises(Exception) as caught:
            driver.call(TASK_INFO, {}, BridgeContext(deadline_ms=50))
        self.assertIn("MHS.", str(caught.exception))

    def test_a_malformed_clock_reply_is_a_failure_not_a_sample(self) -> None:
        driver = self.driver()
        driver.native.malformed_clock = True
        with self.assertRaises(MHSError) as caught:
            driver.call(CLOCK, {})
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.STATE_INVALID")

    def test_each_thruster_publication_is_transmission_only(self) -> None:
        driver = self.driver()
        driver.call(LEFT_THRUST, {"thrust": 1.0})
        driver.call(RIGHT_THRUST, {"thrust": -1.0})
        driver.call(LEFT_POS, {"position": 0.1})
        driver.call(RIGHT_POS, {"position": -0.1})
        self.assertEqual(driver.native.last_thrust["/wamv/thrusters/left/thrust"], 1.0)
        self.assertEqual(driver.native.last_thrust["/wamv/thrusters/right/thrust"], -1.0)
        self.assertEqual(driver.native.last_thrust["/wamv/thrusters/left/pos"], 0.1)
        self.assertEqual(driver.native.last_thrust["/wamv/thrusters/right/pos"], -0.1)

    def test_a_thruster_publication_reports_what_it_sent_and_no_execution_confirmation(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(LEFT_THRUST, {"thrust": 1.0}),
                         {"published": True, "confirmed": False, "sent_thrust": 1.0})
        self.assertEqual(driver.call(RIGHT_POS, {"position": -0.2}),
                         {"published": True, "confirmed": False, "sent_position": -0.2})
        self.assertEqual(driver.read("main"), {})  # the device resource reads no topic

    def test_a_thruster_command_is_refused_until_the_operator_supplies_bounds(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke(LEFT_THRUST, {"thrust": 1.0},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

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
        refused = client.invoke(LEFT_THRUST, {"thrust": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

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
        receipt = client.invoke(LEFT_THRUST, {"thrust": 0.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)  # stored by the Thruster system for an unpause
        self.assertEqual([control.get("pause") for control in driver.native.controls], [True])
        with self.assertRaises(MHSError):
            driver.call(TASK_INFO, {}, BridgeContext(deadline_ms=300))  # the scoring plugin is silent while paused
        self.assertEqual(set(driver.call(CLOCK, {})["sim_time"]), {"sec", "nanosec"})

    def test_the_declaration_names_the_operator_run_bridges(self) -> None:
        cls = type(self.driver())
        self.assertEqual([item["args"].split("@")[0] for item in cls.operator_bridges], [CONTROL, STATS])
        self.assertEqual(cls.estop_latency_ms, 1500)
        reference = json.loads((HERE / "reference.json").read_text())
        self.assertEqual(len(reference["safety"]["operator_bridges"]), 2)
        self.assertIn("## Operator must run", (HERE / "REFERENCE.md").read_text())


if __name__ == "__main__":
    unittest.main()
