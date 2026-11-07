"""Acceptance run of the mujoco_ros ROS package: the gate, plus cases specific to this stop path.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MujocoRosCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
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

    def test_get_sim_info_returns_a_paused_flag(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.ubi-agni.sim_info.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIs(receipt["output"]["paused"], False)

    def test_pause_sends_the_fixed_pause_request(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.ubi-agni.pause.v1", {}), {"acknowledged": True})
        sent = [message for message in driver.native.sent if message.get("op") == "call_service"]
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["service"], "/mujoco_server/set_pause")
        self.assertEqual(sent[0]["type"], "mujoco_ros_msgs/SetPause")
        self.assertEqual(sent[0]["args"], {"paused": True, "admin_hash": ""})

    def test_pause_is_observable_through_get_sim_info(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.ubi-agni.pause.v1", {}), {"acknowledged": True})
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.call("x-cap.ubi-agni.sim_info.v1", {}), {"paused": True})
        info = [message for message in driver.native.sent
                if message.get("service") == "/mujoco_server/get_sim_info"]
        self.assertTrue(info)
        self.assertEqual(info[-1]["type"], "mujoco_ros_msgs/GetSimInfo")

    def test_pause_application_rejection_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_pause_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.ubi-agni.pause.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")
        self.assertFalse(driver.native.paused)

    def test_pause_service_failure_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_pause_service = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.ubi-agni.pause.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")
        self.assertFalse(driver.native.paused)

    def test_missing_state_paused_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.omit_paused = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.ubi-agni.sim_info.v1", {})
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_get_sim_info_service_failure_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_info_service = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.ubi-agni.sim_info.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_the_simulator_stop_pauses_and_latches(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        observation = client.invoke("x-cap.ubi-agni.sim_info.v1", {}, **self.ids)
        self.assertEqual(observation["status"], "rejected", observation)
        self.assertEqual(observation["error"]["mhs_code"], ESTOP)
        # pause is the declared safe-state action, so the stop path stays
        # available during the latch; the ordinary observation does not.
        stop_again = client.invoke("x-cap.ubi-agni.pause.v1", {}, **self.ids)
        self.assertEqual(stop_again["status"], "completed", stop_again)


if __name__ == "__main__":
    unittest.main()
