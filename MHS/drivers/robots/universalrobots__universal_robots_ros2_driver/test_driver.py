"""Acceptance run of the UR ROS 2 dashboard package: the gate, plus repository cases.

The fake is an F0 recording/contract fixture; these tests exercise the declared
rosbridge services, the application success predicate and the stop safe-state
action.  No ROS graph or hardware is contacted.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
STOP = "x-cap.universalrobots.dashboard_stop.v1"
RUNNING = "x-cap.universalrobots.program_running.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DashboardCases(unittest.TestCase):
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

    def test_program_running_observation_returns_only_the_flag(self) -> None:
        client = self.serve()
        receipt = client.invoke(RUNNING, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"program_running": True})

    def test_stop_is_acknowledged_and_updates_the_observed_state(self) -> None:
        client = self.serve()
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"acknowledged": True})
        state = client.invoke(RUNNING, {}, **self.ids)
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual(state["output"], {"program_running": False})

    def test_recorded_wire_services_have_the_declared_shape(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(STOP, {}), {"acknowledged": True})
        self.assertEqual(driver.call(RUNNING, {}), {"program_running": False})
        calls = [
            (message.get("service"), message.get("type"), message.get("args"))
            for message in driver.native.sent
            if message.get("op") == "call_service"
        ]
        self.assertEqual(
            calls,
            [
                ("/dashboard_client/stop", "std_srvs/srv/Trigger", {}),
                ("/dashboard_client/program_running", "ur_dashboard_msgs/srv/IsProgramRunning", {}),
            ],
        )

    def test_stop_transport_failure_does_not_report_a_stopped_state(self) -> None:
        driver = self.driver()
        driver.native.fail_stop_transport = True
        with self.assertRaises(DriverFailed):
            driver.call(STOP, {})
        self.assertTrue(driver.native.program_running)
        self.assertTrue(driver.call(RUNNING, {})["program_running"])

    def test_stop_application_failure_does_not_report_a_stopped_state(self) -> None:
        driver = self.driver()
        driver.native.fail_stop_application = True
        with self.assertRaises(DriverFailed):
            driver.call(STOP, {})
        self.assertTrue(driver.native.program_running)
        self.assertTrue(driver.call(RUNNING, {})["program_running"])

    def test_stop_reply_missing_success_does_not_report_a_stopped_state(self) -> None:
        driver = self.driver()
        driver.native.stop_missing_success = True
        with self.assertRaises(DriverFailed):
            driver.call(STOP, {})
        self.assertTrue(driver.native.program_running)
        self.assertTrue(driver.call(RUNNING, {})["program_running"])

    def test_program_running_transport_failure_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_running_transport = True
        with self.assertRaises(DriverFailed):
            driver.call(RUNNING, {})

    def test_program_running_application_failure_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_running_application = True
        with self.assertRaises(DriverFailed):
            driver.call(RUNNING, {})

    def test_program_running_missing_success_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.running_missing_success = True
        with self.assertRaises(DriverFailed):
            driver.call(RUNNING, {})

    def test_program_running_missing_field_is_an_output_error(self) -> None:
        driver = self.driver()
        driver.native.running_missing_field = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(RUNNING, {})
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_estop_calls_the_stop_service_and_latches_the_observation(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        refused = client.invoke(RUNNING, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        allowed = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(allowed["status"], "completed", allowed)


if __name__ == "__main__":
    unittest.main()
