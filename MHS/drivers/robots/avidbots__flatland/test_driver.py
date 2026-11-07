"""Acceptance run of the Flatland ROS package: the gate, plus cases specific to this simulator.

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


class FlatlandCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_clock_observation_returns_a_clock_sample(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.avidbots.clock.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]["sim_time"]), {"secs", "nsecs"})

    def test_stock_pause_resume_do_not_wait_for_a_paused_clock_snapshot(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("x-cap.avidbots.pause.v1", {}, **self.ids)["status"], "completed")
        self.assertEqual(client.invoke("x-cap.avidbots.resume.v1", {}, **self.ids)["status"], "completed")

    def test_clock_observation_has_no_fresh_sample_while_paused(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("x-cap.avidbots.pause.v1", {}, **self.ids)["status"], "completed")
        receipt = client.invoke("x-cap.avidbots.clock.v1", {}, deadline_ms=50, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIn(receipt["error"]["mhs_code"], {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})
        self.assertIsNone(receipt.get("output"))

    def test_pause_and_resume_reach_the_upstream_services(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.call("x-cap.avidbots.pause.v1", {}), {"acknowledged": True})
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.call("x-cap.avidbots.resume.v1", {}), {"acknowledged": True})
        self.assertFalse(driver.native.paused)
        services = [message.get("service") for message in driver.native.sent
                    if message.get("op") == "call_service"]
        self.assertEqual(services, ["/pause", "/resume"])

    def test_a_rejected_application_response_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_pause_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.avidbots.pause.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_a_failed_ros_service_does_not_report_pause_success(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_pause_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.avidbots.pause.v1", {})
        self.assertFalse(driver.native.paused)

    def test_the_simulator_stop_pauses_and_latches(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        refused = client.invoke("x-cap.avidbots.resume.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
