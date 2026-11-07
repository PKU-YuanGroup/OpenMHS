"""Acceptance run of the UR5 grasp Gazebo package: the gate plus repository cases.

The cases exercise the pinned wire shapes: the two Gazebo ``std_srvs/Empty``
physics services, the two explicit observation subscriptions, the failure
paths through the actual native stop, and the latch.  Service
acknowledgements are not measured arrival or quiescence.  Add cases, never
remove ``check_driver``.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import DriverFailed, build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PAUSE = "x-cap.zzy5510.pause.v1"
RESUME = "x-cap.zzy5510.resume.v1"
CLOCK = "x-cap.zzy5510.clock.v1"
JOINT_STATE = "x-cap.zzy5510.joint_state.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Ur5GraspKinectCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    @staticmethod
    def calls(driver):
        return [message for message in driver.native.sent if message.get("op") == "call_service"]

    @staticmethod
    def subscriptions(driver):
        return [message for message in driver.native.sent if message.get("op") == "subscribe"]

    def test_clock_observation_subscribes_and_maps_the_clock_message(self) -> None:
        driver = self.driver()
        receipt = driver.call(CLOCK, {})
        self.assertEqual(set(receipt["sim_time"]), {"secs", "nsecs"})
        last = self.subscriptions(driver)[-1]
        self.assertEqual(last["topic"], "/clock")
        self.assertEqual(last["type"], "rosgraph_msgs/Clock")

    def test_joint_state_observation_subscribes_and_maps_the_message(self) -> None:
        driver = self.driver()
        receipt = driver.call(JOINT_STATE, {})
        self.assertEqual(len(receipt["joint_names"]), 8)
        self.assertEqual(len(receipt["joint_positions"]), 8)
        self.assertEqual(len(receipt["joint_velocities"]), 8)
        self.assertEqual(len(receipt["joint_efforts"]), 8)
        last = self.subscriptions(driver)[-1]
        self.assertEqual(last["topic"], "/joint_states")
        self.assertEqual(last["type"], "sensor_msgs/JointState")

    def test_pause_and_resume_reach_the_gazebo_services(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(PAUSE, {}), {"acknowledged": True})
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.call(RESUME, {}), {"acknowledged": True})
        self.assertFalse(driver.native.paused)
        self.assertEqual([call["service"] for call in self.calls(driver)],
                         ["/gazebo/pause_physics", "/gazebo/unpause_physics"])

    def test_clock_observation_has_no_fresh_sample_while_paused(self) -> None:
        _, client = self.serve()
        self.assertEqual(client.invoke(PAUSE, {}, **self.ids)["status"], "completed")
        receipt = client.invoke(CLOCK, {}, deadline_ms=50, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIn(receipt["error"]["mhs_code"], {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})
        self.assertIsNone(receipt.get("output"))

    def test_native_estop_reaches_pause_and_reports_engaged(self) -> None:
        driver = self.driver()
        receipt = driver.estop("test")
        self.assertEqual(receipt["estop"], "engaged")
        self.assertTrue(driver.native.paused)
        self.assertIn("/gazebo/pause_physics", [call["service"] for call in self.calls(driver)])

    def test_native_estop_refuses_failed_refused_and_malformed_pause_replies(self) -> None:
        for failure in ("fail_pause_service", "reject_pause_application", "malformed_pause_response"):
            with self.subTest(failure=failure):
                driver = self.driver()
                setattr(driver.native, failure, True)
                with self.assertRaises(DriverFailed) as caught:
                    driver.estop("negative-path test")
                self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_server_estop_latches_and_reset_leaves_the_world_paused(self) -> None:
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        refused = client.invoke(RESUME, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        # SAFE-042: reset releases only the software latch.  Unpausing would let
        # a pending controller goal continue, so the world stays paused until
        # the explicit resume command.
        self.assertTrue(driver.native.paused)
        self.assertNotIn("/gazebo/unpause_physics", [call["service"] for call in self.calls(driver)])
        resumed = client.invoke(RESUME, {}, **self.ids)
        self.assertEqual(resumed["status"], "completed", resumed)
        self.assertFalse(driver.native.paused)
        self.assertEqual([call["service"] for call in self.calls(driver)][-1],
                         "/gazebo/unpause_physics")

    def test_resume_service_failure_is_a_failure_and_leaves_the_world_paused(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(PAUSE, {}), {"acknowledged": True})
        driver.native.fail_resume_service = True
        with self.assertRaises(DriverFailed):
            driver.call(RESUME, {})
        self.assertTrue(driver.native.paused)


if __name__ == "__main__":
    unittest.main()
