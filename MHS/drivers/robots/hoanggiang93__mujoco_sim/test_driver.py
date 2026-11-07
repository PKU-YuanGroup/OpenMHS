"""Acceptance run of the mujoco_sim ROS package: the gate, plus cases specific to this simulator.

The package is blocked because the upstream reset service is effectful but the clone
advertises no acknowledged stop.  The gate case therefore records that failure rather
than pretending the package is a completed control integration.  Add cases, never remove
the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MujocoSimCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_object_states_observation_returns_the_object_array(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.hoanggiang93.object_states.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        objects = receipt["output"]["objects"]
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0]["name"], "box")  # placeholder from the fake
        self.assertIn("pose", objects[0])
        self.assertIn("velocity", objects[0])

    def test_robot_joint_states_observation_returns_the_joint_arrays(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.hoanggiang93.robot_joint_states.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["names"], ["joint1"])  # placeholder from the fake
        self.assertEqual(len(output["positions"]), 1)
        self.assertEqual(len(output["velocities"]), 1)
        self.assertEqual(len(output["efforts"]), 1)

    def test_reset_reaches_the_upstream_trigger_service(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        result = driver.call("x-cap.hoanggiang93.reset.v1", {})
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Reset successfully!")  # placeholder from the fake
        self.assertEqual(driver.native.reset_count, 1)
        calls = [message for message in driver.native.sent if message.get("op") == "call_service"]
        self.assertEqual(calls[0]["service"], "/mujoco/reset")
        self.assertEqual(calls[0]["type"], "std_srvs/Trigger")

    def test_observations_subscribe_to_the_upstream_topics(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.call("x-cap.hoanggiang93.object_states.v1", {})
        driver.call("x-cap.hoanggiang93.robot_joint_states.v1", {})
        subscriptions = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual([item["topic"] for item in subscriptions],
                         ["/mujoco/object_states", "/mujoco/robot_joint_states"])
        self.assertEqual([item["type"] for item in subscriptions],
                         ["mujoco_msgs/ObjectStateArray", "sensor_msgs/JointState"])

    def test_a_rejected_reset_application_response_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_reset_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.hoanggiang93.reset.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")
        self.assertEqual(driver.native.reset_count, 1)

    def test_a_failed_reset_service_does_not_report_success(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_reset_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.hoanggiang93.reset.v1", {})
        self.assertEqual(driver.native.reset_count, 0)

    def test_a_malformed_object_state_message_is_an_output_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.omit_object_states = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.hoanggiang93.object_states.v1", {})
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_a_silent_object_state_publisher_fails_before_the_deadline(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.silent_object_states = True
        with self.assertRaises(MHSError) as caught:
            driver.call("x-cap.hoanggiang93.object_states.v1", {},
                        ctx={"deadline_ms": 50})
        self.assertIn(caught.exception.code,
                      {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})

    def test_a_silent_joint_state_publisher_fails_before_the_deadline(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.silent_joint_states = True
        with self.assertRaises(MHSError) as caught:
            driver.call("x-cap.hoanggiang93.robot_joint_states.v1", {},
                        ctx={"deadline_ms": 50})
        self.assertIn(caught.exception.code,
                      {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})

    def test_the_effectful_reset_has_no_confirmed_stop(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
        refused = client.invoke("x-cap.hoanggiang93.object_states.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
