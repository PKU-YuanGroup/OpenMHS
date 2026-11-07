"""Acceptance run of the Kortex ROS 1 stop package: the gate plus repository-specific cases.

The cases exercise the real wire shapes cited in ``driver.py``: the nested
Empty request/response, the ROS service ``result`` flag and the application
predicate.  A service acknowledgement is not treated as a stopped-state
measurement.  Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
STOP = "/my_gen3/base/stop"
APPLY = "/my_gen3/base/apply_emergency_stop"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class KortexCases(unittest.TestCase):
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

    def calls(self, driver):
        return [message for message in driver.native.sent if message.get("op") == "call_service"]

    def test_stop_uses_the_nested_empty_request_and_acknowledges(self):
        driver = self.driver()
        receipt = driver.call("x-cap.kinovarobotics.stop.v1", {})
        self.assertEqual(receipt, {"acknowledged": True})
        calls = self.calls(driver)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["service"], STOP)
        self.assertEqual(calls[0]["type"], "kortex_driver/Stop")
        self.assertEqual(calls[0]["args"], {"input": {}})
        self.assertEqual(driver.native.services_called, [STOP])

    def test_apply_emergency_stop_uses_the_nested_empty_request_and_acknowledges(self):
        driver = self.driver()
        receipt = driver.call("x-cap.kinovarobotics.apply_emergency_stop.v1", {})
        self.assertEqual(receipt, {"acknowledged": True})
        calls = self.calls(driver)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["service"], APPLY)
        self.assertEqual(calls[0]["type"], "kortex_driver/ApplyEmergencyStop")
        self.assertEqual(calls[0]["args"], {"input": {}})

    def test_a_failed_stop_service_result_is_not_success(self):
        driver = self.driver()
        driver.native.fail_stop_service = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.kinovarobotics.stop.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_a_missing_stop_output_is_not_success(self):
        driver = self.driver()
        driver.native.fail_stop_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.kinovarobotics.stop.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_a_wrong_stop_output_is_not_success(self):
        driver = self.driver()
        driver.native.wrong_stop_output = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.kinovarobotics.stop.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_a_failed_emergency_stop_reply_is_not_success(self):
        driver = self.driver()
        driver.native.fail_emergency_stop_service = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.kinovarobotics.apply_emergency_stop.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_native_estop_rejects_service_failure_and_malformed_empty_output(self):
        for failure in ("fail_emergency_stop_service", "fail_emergency_stop_application",
                        "wrong_emergency_stop_output"):
            with self.subTest(failure=failure):
                driver = self.driver()
                setattr(driver.native, failure, True)
                with self.assertRaises(DriverFailed) as caught:
                    driver.estop("negative-path test")
                self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_driver_estop_reaches_apply_emergency_stop_only(self):
        driver = self.driver()
        receipt = driver.estop("test")
        self.assertEqual(receipt["estop"], "engaged")
        self.assertEqual([message["service"] for message in self.calls(driver)], [APPLY])

    def test_the_stop_is_latched_but_the_apply_emergency_stop_stays_callable(self):
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        refused = client.invoke("x-cap.kinovarobotics.stop.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        allowed = client.invoke("x-cap.kinovarobotics.apply_emergency_stop.v1", {}, **self.ids)
        self.assertEqual(allowed["status"], "completed", allowed)
        self.assertEqual(allowed["output"], {"acknowledged": True})

    def test_the_package_exposes_only_the_two_acknowledged_services(self):
        driver = self.driver()
        self.assertEqual(set(type(driver).commands),
                         {"x-cap.kinovarobotics.stop.v1",
                          "x-cap.kinovarobotics.apply_emergency_stop.v1"})
        self.assertEqual(set(type(driver).actions), set(type(driver).commands))
        self.assertEqual(type(driver).parameters, {})
        self.assertEqual(type(driver).reads, {})
        self.assertEqual(set(type(driver).safety_bindings), {"estop"})
        self.assertEqual(type(driver).ros_version, 1)
        self.assertEqual(type(driver).mode, "hardware")
        self.assertEqual(type(driver).risk, "R2")
        serialized = repr((type(driver).commands, type(driver).actions,
                           type(driver).safety_bindings)).lower()
        self.assertNotIn("clear_faults", serialized)
        self.assertNotIn("play_joint_trajectory", serialized)


if __name__ == "__main__":
    unittest.main()
