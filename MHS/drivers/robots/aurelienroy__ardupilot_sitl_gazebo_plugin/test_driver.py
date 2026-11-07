"""Acceptance run of the ArduPilot SITL Gazebo ROS package: the gate, plus cases specific to this interface.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ArdupilotSitlGazeboCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_motor_speed_observation_returns_the_published_array(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.aurelienroy.motor_speed.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        speeds = receipt["output"]["motor_speed"]
        self.assertIsInstance(speeds, list)
        self.assertTrue(speeds)
        self.assertTrue(all(isinstance(value, (int, float)) for value in speeds))

    def test_take_and_release_reach_the_upstream_services(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.call("x-cap.aurelienroy.take_lapse_lock.v1", {}), {"nb_holders": 1})
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.native.holders, 1)
        self.assertEqual(driver.call("x-cap.aurelienroy.release_lapse_lock.v1", {}), {"nb_holders": 0})
        self.assertFalse(driver.native.paused)
        self.assertEqual(driver.native.holders, 0)
        self.assertEqual(driver.native.take_requests[-1],
                         {"process_id": "mhs-driver", "max_duration": 1.0})
        self.assertEqual(driver.native.release_requests[-1], {"process_id": "mhs-driver"})
        services = [message.get("service") for message in driver.native.sent
                    if message.get("op") == "call_service"]
        self.assertEqual(services, ["/fdmUDP/take_apm_lapseLock",
                                    "/fdmUDP/release_apm_lapseLock"])

    def test_a_failed_take_service_does_not_report_a_pause(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_take_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.aurelienroy.take_lapse_lock.v1", {})
        self.assertFalse(driver.native.paused)
        self.assertEqual(driver.native.holders, 0)

    def test_a_take_application_failure_is_not_a_pause_success(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.reject_take_application = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.aurelienroy.take_lapse_lock.v1", {})
        self.assertTrue(driver.native.paused)
        self.assertGreater(driver.native.holders, 1)

    def test_a_malformed_take_response_is_an_unknown_outcome(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.malformed_take_response = True
        with self.assertRaises(OutcomeUnknown):
            driver.call("x-cap.aurelienroy.take_lapse_lock.v1", {})
        self.assertFalse(driver.native.paused)

    def test_a_release_while_another_holder_remains_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.call("x-cap.aurelienroy.take_lapse_lock.v1", {}), {"nb_holders": 1})
        driver.native.reject_release_application = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.aurelienroy.release_lapse_lock.v1", {})
        self.assertEqual(driver.native.holders, 1)
        self.assertTrue(driver.native.paused)

    def test_no_fresh_motor_sample_while_the_lapse_lock_is_held(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("x-cap.aurelienroy.take_lapse_lock.v1", {}, **self.ids)["status"],
                         "completed")
        receipt = client.invoke("x-cap.aurelienroy.motor_speed.v1", {}, deadline_ms=50, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIn(receipt["error"]["mhs_code"],
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})
        self.assertIsNone(receipt.get("output"))
        self.assertEqual(client.invoke("x-cap.aurelienroy.release_lapse_lock.v1", {},
                                       **self.ids)["status"], "completed")

    def test_the_e_stop_takes_the_lapse_lock_and_keeps_the_latch(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        receipt = driver.estop("test")
        self.assertEqual(receipt["estop"], "engaged", receipt)
        self.assertTrue(receipt["safe_state_achieved"])
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.native.holders, 1)
        self.assertEqual(driver.native.take_requests[-1]["max_duration"],
                         3.4028234663852886e38)

    def test_the_e_stop_pauses_the_motor_speed_observation(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        refused = client.invoke("x-cap.aurelienroy.take_lapse_lock.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        read = client.invoke("x-cap.aurelienroy.motor_speed.v1", {}, deadline_ms=50, **self.ids)
        self.assertIn(read["status"], {"failed", "unknown", "rejected"}, read)
        self.assertIsNone(read.get("output"))

    def test_an_e_stop_with_another_holder_is_unconfirmed_and_keeps_the_latch(self) -> None:
        # Review case: another lock holder makes take_apm_lapseLock return nb_holders above 1. The exact
        # predicate cannot confirm the pause, so the e-stop is not reported achieved and the latch stays held,
        # although the (placeholder) loop is paused.
        driver = load_driver(HERE, "fake")
        driver.native.reject_take_application = True
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        receipt = client.estop("test", **ids)
        self.assertNotEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
        self.assertTrue(driver.native.paused)
        self.assertGreater(driver.native.holders, 1)
        refused = client.invoke("x-cap.aurelienroy.take_lapse_lock.v1", {}, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
