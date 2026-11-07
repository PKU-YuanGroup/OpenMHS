"""Acceptance run of the Webots demo ROS package: the gate plus repository-specific cases.

Add cases, never remove the check_driver call.
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
STEP = "x-cap.jackymao1999.step.v1"
STOP = "x-cap.jackymao1999.stop.v1"
GPS = "x-cap.jackymao1999.gps.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WebotsDemoCases(unittest.TestCase):
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

    def test_step_sends_the_fixed_time_step_request(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(STEP, {}), {"advanced": True})
        sent = [message for message in driver.native.sent if message.get("op") == "call_service"]
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["service"], "/robot/robot/time_step")
        self.assertEqual(sent[0]["type"], "webots_ros/set_int")
        self.assertEqual(sent[0]["args"], {"value": 32})
        self.assertEqual(driver.native.steps, 1)

    def test_stop_sends_the_quit_request_and_is_observable(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(STOP, {}), {"acknowledged": True})
        sent = [message for message in driver.native.sent if message.get("op") == "call_service"]
        self.assertEqual(sent[-1]["service"], "/robot/robot/time_step")
        self.assertEqual(sent[-1]["args"], {"value": 0})
        self.assertTrue(driver.native.stopped)

    def test_gps_observation_returns_a_point_and_frame(self) -> None:
        driver = self.driver()
        output = driver.call(GPS, {})
        self.assertEqual(set(output["point"]), {"x", "y", "z"})
        self.assertIsInstance(output["frame_id"], str)
        subscribe = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual(subscribe[0]["topic"], "/robot/gps/values")
        self.assertEqual(subscribe[0]["type"], "geometry_msgs/PointStamped")

    def test_service_failure_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_service = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(STEP, {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")
        self.assertEqual(driver.native.steps, 0)

    def test_application_rejection_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(STEP, {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")
        self.assertEqual(driver.native.steps, 0)

    def test_a_missing_gps_sample_does_not_return_a_stale_value(self) -> None:
        driver = self.driver()
        driver.native.omit_gps = True
        with self.assertRaises(MHSError) as caught:
            driver.call(GPS, {})
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")

    def test_the_e_stop_latches_but_does_not_claim_a_safe_state(self) -> None:
        # The 0 time_step request has no effect shown in the clone
        # (include/webots_ros.h:135-141): no binding sends it.
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        refused = client.invoke(STEP, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        # The 0 request is an ordinary action now: it is refused while latched.
        zero = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(zero["status"], "rejected", zero)
        self.assertEqual(zero["error"]["mhs_code"], ESTOP)

    def test_the_e_stop_sends_no_time_step_request(self) -> None:
        driver = self.driver()
        before = len([m for m in driver.native.sent if m.get("op") == "call_service"])
        driver.estop("test")  # the driver-level stop has no native binding to call
        after = len([m for m in driver.native.sent if m.get("op") == "call_service"])
        self.assertEqual(after, before)
        self.assertFalse(driver.native.stopped)

    def test_the_declaration_has_no_stop_binding_or_safe_state_action(self) -> None:
        cls = type(self.driver())
        self.assertFalse(any(action.safe_state for action in cls.actions.values()))
        self.assertNotIn("estop", dict(cls.safety_bindings or {}))

    def test_the_step_and_stop_share_the_source_backed_service(self) -> None:
        driver = self.driver()
        driver.call(STEP, {})
        driver.call(STOP, {})
        services = [message.get("service") for message in driver.native.sent
                    if message.get("op") == "call_service"]
        self.assertEqual(services, ["/robot/robot/time_step", "/robot/robot/time_step"])
        self.assertEqual(driver.native.steps, 1)
        self.assertTrue(driver.native.stopped)


if __name__ == "__main__":
    unittest.main()
