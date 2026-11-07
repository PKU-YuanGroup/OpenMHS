"""Acceptance run of the mujoco_ros_sim package: the gate, plus repository cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
SAFE_STATE_UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
JOINT_SET = "/mujoco_ros_interface/joint_set"
POSITION = "x-cap.saga0619.joint_position_command.v1"
TORQUE = "x-cap.saga0619.joint_torque_command.v1"
JOINT_STATES = "x-cap.saga0619.joint_states.v1"
SENSOR_STATES = "x-cap.saga0619.sensor_states.v1"
SIM_TIME = "x-cap.saga0619.sim_time.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MujocoCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def serve_driver(self):
        driver = load_driver(HERE, "fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver

    def test_a_position_command_is_published_in_position_mode(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call(POSITION, {"sim_time": 1.0, "positions": [0.1, 0.2]})
        self.assertEqual(output, {"published": True, "confirmed": False})
        messages = [message for message in driver.native.sent
                    if message.get("op") == "publish" and message.get("topic") == JOINT_SET]
        self.assertEqual(messages[-1]["msg"]["MODE"], 0)
        self.assertEqual(messages[-1]["msg"]["time"], 1.0)
        self.assertEqual(messages[-1]["msg"]["position"], [0.1, 0.2])

    def test_a_torque_command_is_published_in_torque_mode(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call(TORQUE, {"sim_time": 2.0, "torques": [3.0, 4.0]})
        self.assertEqual(output, {"published": True, "confirmed": False})
        messages = [message for message in driver.native.sent
                    if message.get("op") == "publish" and message.get("topic") == JOINT_SET]
        self.assertEqual(messages[-1]["msg"]["MODE"], 1)
        self.assertEqual(messages[-1]["msg"]["torque"], [3.0, 4.0])

    def test_the_missing_command_time_is_refused_before_publication(self) -> None:
        client, driver = self.serve_driver()
        receipt = client.invoke(POSITION, {"positions": [0.0]}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertIn(receipt["error"]["mhs_code"],
                      {"MHS.CAPABILITY.INPUT_INVALID", "MHS.SAFETY.ENVELOPE_VIOLATION"})
        self.assertFalse([message for message in driver.native.sent
                          if message.get("op") == "publish"])

    def test_the_joint_state_observation_returns_the_published_shape(self) -> None:
        client = self.serve()
        receipt = client.invoke(JOINT_STATES, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["names"], ["joint_0", "joint_1"])
        self.assertEqual(output["positions"], [0.0, 0.0])
        self.assertEqual(output["velocities"], [0.0, 0.0])
        self.assertEqual(output["efforts"], [0.0, 0.0])

    def test_the_sensor_state_observation_includes_the_user_information_entry(self) -> None:
        client = self.serve()
        receipt = client.invoke(SENSOR_STATES, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        sensors = receipt["output"]["sensors"]
        self.assertEqual([item["name"] for item in sensors], ["sensor_0", "user information"])
        self.assertEqual(sensors[1]["data"], [0.0, 0.0])

    def test_the_sim_time_observation_returns_one_float_sample(self) -> None:
        client = self.serve()
        receipt = client.invoke(SIM_TIME, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["sim_time"], 0.5)

    def test_a_malformed_joint_state_reply_is_a_failure(self) -> None:
        client, driver = self.serve_driver()
        driver.native.malformed_joint_states = True
        receipt = client.invoke(JOINT_STATES, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertIn(receipt["error"]["mhs_code"],
                      {"MHS.CAPABILITY.OUTPUT_INVALID", "MHS.ADAPTER.SHIM_FAILED"})

    def test_a_silent_joint_state_topic_times_out(self) -> None:
        client, driver = self.serve_driver()
        driver.native.drop_joint_states = True
        receipt = client.invoke(JOINT_STATES, {}, deadline_ms=50, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIn(receipt["error"]["mhs_code"],
                      {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})

    def test_a_transport_failure_is_not_hidden(self) -> None:
        client, driver = self.serve_driver()
        driver.native.fail_next_send = True
        receipt = client.invoke(POSITION, {"sim_time": 1.0, "positions": [0.0]}, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIn(receipt["error"]["mhs_code"],
                      {"MHS.OUTCOME.UNKNOWN", "MHS.ADAPTER.SHIM_FAILED", "MHS.TRANSPORT.CLOSED"})

    def test_the_upstream_has_no_acknowledged_stop(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], SAFE_STATE_UNREACHED)
        refused = client.invoke(POSITION, {"sim_time": 1.0, "positions": [0.0]}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_direct_call_with_a_short_deadline_reports_not_ready(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.drop_joint_states = True
        with self.assertRaises(MHSError) as caught:
            driver.call(JOINT_STATES, {}, {"deadline_ms": 50})
        self.assertIn(caught.exception.code, {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})


if __name__ == "__main__":
    unittest.main()
