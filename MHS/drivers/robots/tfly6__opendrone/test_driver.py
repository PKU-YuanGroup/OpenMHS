"""Acceptance run of the OpenDrone base-controller package: the gate plus cases.

Add cases, never remove the check_driver call.  The /land callback acknowledgement of a LAND mode request is not a
stop by itself (model review of 2026-11-04); the e-stop is a sensed-confirmation stop (SAFE-049, simulated devices
only): it sends /land and a disarm request.  A ROS 1 producer stamp is not a freshness proof, so the cases below
expect the request to be sent and the confirmation refused on the ROS-free fake.
"""

import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"

VALID_POINTS = [
    {"position": {"x": 2.0, "y": 1.0, "z": 2.5}, "yaw": 0.5, "valid_mask": 33},
]
OTHER_POINTS = [
    {"position": {"x": 3.0, "y": -1.0, "z": 2.0}, "yaw": -0.5, "valid_mask": 33},
]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], ["G6", "G8"], report)


class OpendroneCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, "fake")
        server = build_server(driver)
        self.addCleanup(driver.close)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def test_target_pose_is_published_and_visible_in_the_resource(self) -> None:
        driver, client = self.serve()
        receipt = client.invoke("x-cap.tfly6.target_pose.v1", {"points": VALID_POINTS}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["published"])
        self.assertFalse(receipt["output"]["confirmed"])
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(state["position"], {"x": 2.0, "y": 1.0, "z": 2.5})
        observed = client.invoke("x-cap.tfly6.setpoint.v1", {}, **self.ids)
        self.assertEqual(observed["status"], "completed", observed)
        self.assertEqual(observed["output"]["position"], {"x": 2.0, "y": 1.0, "z": 2.5})
        self.assertEqual(driver.native.published_points[0]["position"], {"x": 2.0, "y": 1.0, "z": 2.5})
        publishes = [message for message in driver.native.sent
                     if message.get("op") == "publish" and message.get("topic") == "/planner/output"]
        self.assertEqual(len(publishes), 1)
        self.assertEqual(publishes[0]["msg"]["points"], VALID_POINTS)
        # Exactly the PlannerOutput fields (opendrone/msg/PlannerOutput.msg:1-7); rosbridge refuses unknown ones.
        self.assertEqual(set(publishes[0]["msg"]),
                         {"header", "trajectory_id", "is_horizon", "trajectory_start_time", "points"})

    def test_a_second_target_changes_the_observed_target(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.invoke("x-cap.tfly6.target_pose.v1", {"points": VALID_POINTS},
                                       **self.ids)["status"], "completed")
        self.assertEqual(client.invoke("x-cap.tfly6.target_pose.v1", {"points": OTHER_POINTS},
                                       **self.ids)["status"], "completed")
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(state["position"], {"x": 3.0, "y": -1.0, "z": 2.0})

    def test_setpoint_observation_is_not_an_automatic_resource_field(self) -> None:
        driver, client = self.serve()
        driver.native.silent_setpoint = True
        receipt = client.invoke("x-cap.tfly6.setpoint.v1", {}, deadline_ms=50, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIn(receipt["error"]["mhs_code"],
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"}, receipt)
        state = client.read("main", **self.ids)["state"]
        self.assertIn("position", state)
        self.assertNotIn("setpoint", state)

    def test_normal_landing_request_does_not_engage_the_latch(self) -> None:
        driver, client = self.serve()
        receipt = client.invoke("x-cap.tfly6.land.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["success"])
        self.assertTrue(driver.native.landing_requested)
        after = client.invoke("x-cap.tfly6.target_pose.v1", {"points": VALID_POINTS}, **self.ids)
        self.assertEqual(after["status"], "completed", after)

    def test_a_failed_land_service_does_not_report_success(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_land_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.tfly6.land.v1", {})
        self.assertFalse(driver.native.landing_requested)

    def test_a_rejected_application_response_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_land_application = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.tfly6.land.v1", {})
        self.assertFalse(driver.native.landing_requested)

    def test_a_malformed_land_reply_is_not_a_success(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.malformed_land_response = True
        with self.assertRaises((DriverFailed, OutcomeUnknown)):
            driver.call("x-cap.tfly6.land.v1", {})

    def test_the_declaration_is_a_sensed_stop_without_an_acknowledged_binding(self) -> None:
        cls = type(load_driver(HERE, "fake"))
        self.assertEqual(set(cls.safety_bindings), {"sensed_stop"})
        self.assertEqual(cls.mode, "simulated")
        self.assertFalse(cls.actions["x-cap.tfly6.land.v1"].safe_state)
        sources = {source["topic"] for source in cls.safety_bindings["sensed_stop"]["sources"].values()}
        # /flight_state reports LANDED on mode_sent alone (base.cpp:269-271): never a sensed source.
        self.assertEqual(sources, {"/mavros/state", "/mavros/local_position/pose"})


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


class SensedStopCases(unittest.TestCase):
    """SAFE-049: the request proves nothing, and a ROS 1 producer stamp does not confirm it."""

    def serve(self):
        driver = load_driver(HERE, "fake")
        server = build_server(driver)
        self.addCleanup(driver.close)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.server = server
        return driver, client

    def services(self, driver, name):
        return [message for message in driver.native.sent
                if message.get("op") == "call_service" and message.get("service") == name]

    def assert_unreached(self, receipt, reason):
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        self.assertEqual(details(receipt)["reason"], "bridge_reports_unsafe", receipt)
        self.assertEqual(details(receipt)["sensed"]["reason"], reason, receipt)
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertTrue(receipt["output"]["latched"])

    def test_the_estop_request_is_sent_but_ros1_stamps_do_not_confirm(self) -> None:
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "sensed_missing")
        sensed = details(receipt)["sensed"]
        self.assertEqual([step["native"] for step in sensed["request"]], ["/land", "/mavros/cmd/arming"])
        # PX4 refuses the disarm in the air: recorded, never a confirmation.
        self.assertEqual([step["outcome"] for step in sensed["request"]], ["succeeded", "refused"])
        self.assertEqual(driver.native.position["z"], 0.0)
        self.assertFalse(driver.native.armed)
        self.assertTrue(driver.native.landing_locked)
        refused = client.invoke("x-cap.tfly6.target_pose.v1", {"points": VALID_POINTS}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_second_estop_sends_the_request_again_and_stays_unconfirmed(self) -> None:
        driver, client = self.serve()
        self.assert_unreached(client.estop("first", **self.ids), "sensed_missing")
        again = client.estop("second", **self.ids)
        self.assert_unreached(again, "sensed_missing")
        sensed = details(again)["sensed"]
        self.assertEqual([step["native"] for step in sensed["request"]], ["/land", "/mavros/cmd/arming"])
        # The second /land is still acknowledged, and disarm succeeds once z is 0.
        self.assertEqual([step["outcome"] for step in sensed["request"]], ["succeeded", "succeeded"])

    def test_a_reset_cannot_reconfirm_from_ros1_stamps(self) -> None:
        driver, client = self.serve()
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED", reset)
        refused = client.invoke("x-cap.tfly6.land.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_reset_is_refused_when_the_vehicle_moved_again(self) -> None:
        driver, client = self.serve()
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")
        driver.native.takeoff()                            # another MAVROS client re-armed and climbed
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED", reset)
        refused = client.invoke("x-cap.tfly6.land.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)   # the latch is kept

    def test_an_acknowledged_landing_that_does_not_land_is_never_confirmed(self) -> None:
        driver, client = self.serve()
        driver.native.ignore_land = True
        driver.native.flight_state_lies = True             # /flight_state says LANDED; it is not a source
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "sensed_missing")
        self.assertEqual(client.read("main", **self.ids)["state"]["flight_state"], 5)
        self.assertEqual(driver.native.position["z"], 2.0)

    def test_silent_sources_are_sensed_missing(self) -> None:
        driver, client = self.serve()
        driver.native.silent_topics = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_repeated_producer_stamp_is_not_a_freshness_proof(self) -> None:
        driver, client = self.serve()
        driver.native.frozen_stamps = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_null_altitude_is_not_counted_on_ros1(self) -> None:
        driver, client = self.serve()
        driver.native.null_altitude = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_background_retry_cannot_confirm_from_ros1_stamps(self) -> None:
        driver, client = self.serve()
        driver.native.no_auto_disarm = True
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "sensed_missing")
        self.assertTrue(details(receipt)["retrying"])
        time.sleep(2.5)
        confirmations = [item for item in self.server.export_evidence()["receipts"]
                         if (item.get("output") or {}).get("confirms") == receipt["command_id"]
                         and item.get("status") == "completed"]
        self.assertEqual(confirmations, [])


if __name__ == "__main__":
    unittest.main()
