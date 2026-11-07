"""Acceptance run of the FastSwarmSim time-coordinator package: the gate plus local cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FastSwarmSimCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_clock_observation_returns_a_clock_sample(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.shupx.clock.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]["sim_time"]), {"sec", "nanosec"})

    def test_the_status_observation_reports_running_and_the_factor(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.shupx.clock_status.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        status = receipt["output"]["status"]
        self.assertIs(status["running"], True)
        self.assertEqual(status["max_real_time_factor"], 0.5)
        self.assertEqual(set(status["sim_time"]), {"sec", "nanosec"})
        self.assertIn("participant_count", status)

    def test_pause_stops_the_clock_and_pause_and_resume_reach_the_service(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.call("x-cap.shupx.pause.v1", {}), {"acknowledged": True})
        self.assertFalse(driver.native.running)
        self.assertEqual(driver.call("x-cap.shupx.resume.v1", {"max_real_time_factor": 2.5}),
                         {"acknowledged": True})
        self.assertTrue(driver.native.running)
        self.assertEqual(driver.native.max_real_time_factor, 2.5)
        calls = [message for message in driver.native.sent if message.get("op") == "call_service"]
        self.assertEqual([message.get("service") for message in calls],
                         ["/fss/clock_control", "/fss/clock_control"])
        self.assertEqual(calls[0]["args"], {"running": False, "max_real_time_factor": 0.0})
        self.assertEqual(calls[1]["args"], {"running": True, "max_real_time_factor": 2.5})

    def test_pause_keeps_the_placeholder_clock_sample_visible(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("x-cap.shupx.pause.v1", {}, **self.ids)["status"], "completed")
        status = client.invoke("x-cap.shupx.clock_status.v1", {}, **self.ids)["output"]["status"]
        self.assertIs(status["running"], False)
        self.assertEqual(status["max_real_time_factor"], 0.0)
        # The coordinator republishes /clock from its 200 ms status tick, so a
        # paused sample is still observable; it is not fresh trajectory evidence.
        clock = client.invoke("x-cap.shupx.clock.v1", {}, **self.ids)
        self.assertEqual(clock["status"], "completed", clock)
        self.assertEqual(set(clock["output"]["sim_time"]), {"sec", "nanosec"})

    def test_resume_needs_the_operator_envelope(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.shupx.resume.v1", {"max_real_time_factor": 2.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_lets_resume_set_the_factor(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke("x-cap.shupx.resume.v1", {"max_real_time_factor": 2.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        status = client.invoke("x-cap.shupx.clock_status.v1", {}, **self.ids)["output"]["status"]
        self.assertIs(status["running"], True)
        self.assertEqual(status["max_real_time_factor"], 2.0)

    def test_a_rejected_application_response_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_clock_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.shupx.pause.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_a_failed_ros_service_does_not_report_pause_success(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_clock_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.shupx.pause.v1", {})
        self.assertTrue(driver.native.running)

    def test_the_simulator_stop_pauses_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        # Observational extension actions remain latched after an e-stop.
        refused_status = client.invoke("x-cap.shupx.clock_status.v1", {}, **self.ids)
        self.assertEqual(refused_status["status"], "rejected", refused_status)
        self.assertEqual(refused_status["error"]["mhs_code"], ESTOP)
        refused = client.invoke("x-cap.shupx.resume.v1", {"max_real_time_factor": 2.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
