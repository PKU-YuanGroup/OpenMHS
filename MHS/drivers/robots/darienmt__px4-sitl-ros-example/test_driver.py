"""Acceptance run of the PX4 SITL ROS package: the gate, plus cases specific to this simulator.

Add cases, never remove the check_driver call.  A /mavros/cmd/land acknowledgement of a LAND request is not a stop
by itself (model review of 2026-11-04); the e-stop is a sensed-confirmation stop (SAFE-049, simulated devices only):
it sends the land and a disarm request.  A ROS 1 producer stamp is not a freshness proof, so the cases below
expect the request to be sent and the confirmation refused on the ROS-free fake.
"""

import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = HERE / "site-limits.example.json"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], ["G6", "G8"], report)


class Px4SitlCases(unittest.TestCase):
    def serve(self, *, overlay: bool = True):
        server = load(HERE, backend="fake", site_limits=str(OVERLAY) if overlay else None)
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

    def test_the_state_observation_returns_mavros_fields(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.darienmt.state.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]), {"connected", "armed", "mode"})
        self.assertIsInstance(receipt["output"]["connected"], bool)
        self.assertIsInstance(receipt["output"]["armed"], bool)
        self.assertIsInstance(receipt["output"]["mode"], str)

    def test_the_altitude_observation_returns_amsl(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.darienmt.altitude.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIsInstance(receipt["output"]["amsl"], (int, float))

    def test_a_position_setpoint_is_refused_without_an_operator_envelope(self) -> None:
        client = self.serve(overlay=False)
        receipt = client.invoke("x-cap.darienmt.setpoint_position.v1",
                                {"x": 0.5, "y": -0.5, "z": 1.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_position_and_velocity_setpoints_reach_the_fake(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.darienmt.setpoint_position.v1",
                                     {"x": 0.5, "y": -0.5, "z": 1.0}),
                         {"published": True, "confirmed": False})
        self.assertEqual(driver.native.altitude_amsl, 1.0)
        self.assertEqual(driver.call("x-cap.darienmt.setpoint_velocity_body.v1",
                                     {"vx": 0.2, "vy": -0.2, "vz": 0.1, "yaw_rate": 0.1}),
                         {"published": True, "confirmed": False})
        self.assertEqual(driver.native.velocity, {"x": 0.2, "y": -0.2, "z": 0.1})
        self.assertEqual(driver.call("x-cap.darienmt.setpoint_velocity_ned.v1",
                                     {"vx": -0.2, "vy": 0.2, "vz": -0.1, "yaw": -0.1}),
                         {"published": True, "confirmed": False})
        published = [item["topic"] for item in driver.native.sent_setpoints]
        self.assertIn("/mavros/setpoint_position/local", published)
        self.assertIn("/mavros/setpoint_raw/local", published)

    def test_the_hover_publication_is_the_fixed_offb_pose(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.darienmt.hover.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.darienmt.hover.v1", {}),
                         {"published": True, "confirmed": False})
        self.assertEqual(driver.native.altitude_amsl, 2.0)

    def test_arm_and_offboard_requests_reach_the_fake_services(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.darienmt.request_arm.v1", {}), {"success": True})
        self.assertTrue(driver.native.armed)
        self.assertEqual(driver.call("x-cap.darienmt.request_offboard.v1", {}), {"mode_sent": True})
        self.assertEqual(driver.native.mode, "OFFBOARD")
        services = [message.get("service") for message in driver.native.sent
                    if message.get("op") == "call_service"]
        self.assertEqual(services, ["/mavros/cmd/arming", "/mavros/set_mode"])

    def test_a_failed_arming_service_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.armed = False  # a disarmed vehicle on the ground (placeholder)
        driver.native.fail_arming_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.darienmt.request_arm.v1", {})
        self.assertFalse(driver.native.armed)

    def test_a_rejected_mode_application_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.mode = "MANUAL"  # placeholder mode before the request
        driver.native.reject_mode_application = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.darienmt.request_offboard.v1", {})
        self.assertEqual(driver.native.mode, "MANUAL")

    def test_the_landing_request_is_acknowledged_but_not_a_touchdown_claim(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.darienmt.request_land.v1", {}), {"success": True})
        self.assertTrue(driver.native.landing_requested)
        # The clone sends a default-constructed CommandTOL request (drone_offboard.cpp:65-67) and reads no
        # landed state afterwards; the receipt carries only the acknowledgement flag.
        calls = [message for message in driver.native.sent if message.get("op") == "call_service"]
        self.assertEqual([(message["service"], message.get("args") or {}) for message in calls],
                         [("/mavros/cmd/land", {})])

    def test_a_malformed_land_response_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.malformed_land_response = True
        with self.assertRaises(OutcomeUnknown):
            driver.call("x-cap.darienmt.request_land.v1", {})
        self.assertFalse(driver.native.landing_requested)

    def test_the_declaration_is_a_sensed_stop_without_an_acknowledged_binding(self) -> None:
        cls = type(self.driver())
        self.assertEqual(set(cls.safety_bindings), {"sensed_stop"})
        self.assertEqual(cls.mode, "simulated")
        self.assertFalse(any(action.safe_state for action in cls.actions.values()))


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


class SensedStopCases(unittest.TestCase):
    """SAFE-049: the request proves nothing, and a ROS 1 producer stamp does not confirm it."""

    def serve(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=str(OVERLAY))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
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
        self.assertEqual([step["native"] for step in sensed["request"]], ["/mavros/cmd/land", "/mavros/cmd/arming"])
        self.assertEqual([step["outcome"] for step in sensed["request"]], ["succeeded", "refused"])
        self.assertEqual(driver.native.altitude_amsl, 0.0)
        self.assertFalse(driver.native.armed)
        for capability, args in (("x-cap.darienmt.request_offboard.v1", {}),
                                 ("x-cap.darienmt.request_land.v1", {}),
                                 ("x-cap.darienmt.setpoint_position.v1", {"x": 0.5, "y": -0.5, "z": 1.0})):
            refused = client.invoke(capability, args, **self.ids)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_second_estop_sends_the_requests_again_and_stays_unconfirmed(self) -> None:
        driver, client = self.serve()
        self.assert_unreached(client.estop("first", **self.ids), "sensed_missing")
        again = client.estop("second", **self.ids)
        self.assert_unreached(again, "sensed_missing")
        sensed = details(again)["sensed"]
        self.assertEqual([step["native"] for step in sensed["request"]], ["/mavros/cmd/land", "/mavros/cmd/arming"])
        # Already on the ground: land is refused (fake.py) and the disarm succeeds.
        self.assertEqual([step["outcome"] for step in sensed["request"]], ["refused", "succeeded"])

    def test_a_reset_cannot_reconfirm_from_ros1_stamps(self) -> None:
        driver, client = self.serve()
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED", reset)
        refused = client.invoke("x-cap.darienmt.request_land.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_reset_is_refused_after_offb_node_rearmed_the_vehicle(self) -> None:
        driver, client = self.serve()
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")
        driver.native.offb_rearm()                         # the shipped offb_node re-arms every 5 s
        self.assertTrue(driver.native.armed)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED", reset)

    def test_an_acknowledged_land_that_does_not_land_is_never_confirmed(self) -> None:
        driver, client = self.serve()
        driver.native.ignore_land = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")
        self.assertTrue(driver.native.armed)

    def test_silent_sources_are_sensed_missing(self) -> None:
        driver, client = self.serve()
        driver.native.silent_sensed = True
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
