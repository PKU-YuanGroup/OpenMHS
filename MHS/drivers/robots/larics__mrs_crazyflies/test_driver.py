"""Acceptance run of the MRS Crazyflies ROS 2 package: the gate, plus repository cases.

Add cases, never remove the check_driver call.  The tests use the ROS-free fake
transport only; no ROS graph, rosbridge peer, Gazebo world, CrazySwarm2 node or
hardware is contacted.  The e-stop is a terminal sensed-confirmation stop (SAFE-049,
CORE-087): the /all/emergency acknowledgement proves nothing by itself.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = HERE / "site-limits.example.json"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"

VELOCITY = {
    "linear": {"x": 0.1, "y": -0.1, "z": 0.0},
    "angular": {"x": 0.0, "y": 0.0, "z": 0.1},
}
OUT_OF_ENVELOPE = {
    "linear": {"x": 2.0, "y": -0.1, "z": 0.0},
    "angular": {"x": 0.0, "y": 0.0, "z": 0.1},
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MrsCrazyfliesCases(unittest.TestCase):
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

    def test_the_velocity_publication_reaches_the_fake(self) -> None:
        driver = self.driver()
        before = dict(driver.native.pose)
        self.assertEqual(driver.call("x-cap.larics.cmd_vel.v1", VELOCITY),
                         {"published": True, "confirmed": False})
        self.assertEqual(driver.native.twist_packets[-1], VELOCITY)
        self.assertNotEqual(driver.native.pose, before)

    def test_the_pose_observation_returns_a_position(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertIn("pose", state)
        self.assertEqual(set(state["pose"]), {"x", "y", "z"})

    def test_the_emergency_request_is_acknowledged(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.larics.emergency.v1", {}), {"accepted": True})
        self.assertTrue(driver.native.emergency_requested)
        self.assertEqual(driver.native.emergency_requests, 1)

    def test_a_failed_emergency_service_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_emergency_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.larics.emergency.v1", {})
        self.assertFalse(driver.native.emergency_requested)

    def test_a_malformed_emergency_response_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.malformed_emergency_response = True
        with self.assertRaises(OutcomeUnknown):
            driver.call("x-cap.larics.emergency.v1", {})
        self.assertFalse(driver.native.emergency_requested)

    def test_operator_required_inputs_refuse_without_an_overlay(self) -> None:
        client = self.serve(overlay=False)
        receipt = client.invoke("x-cap.larics.cmd_vel.v1", VELOCITY, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_the_example_overlay_admits_valid_values_and_refuses_out_of_envelope(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.larics.cmd_vel.v1", VELOCITY, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})
        refused = client.invoke("x-cap.larics.cmd_vel.v1", OUT_OF_ENVELOPE, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_declaration_is_a_terminal_sensed_stop(self) -> None:
        cls = type(self.driver())
        self.assertEqual(set(cls.safety_bindings), {"sensed_stop"})
        self.assertEqual(cls.mode, "simulated")
        self.assertTrue(cls.estop_terminal)
        self.assertFalse(any(action.safe_state for action in cls.actions.values()))


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


class SensedStopCases(unittest.TestCase):
    """SAFE-049 and CORE-087: only fresh stamped pose samples on the ground and still achieve the stop."""

    def serve(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=str(OVERLAY))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return driver, client

    def assert_unreached(self, receipt, reason):
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        self.assertEqual(details(receipt)["reason"], "bridge_reports_unsafe", receipt)
        self.assertEqual(details(receipt)["sensed"]["reason"], reason, receipt)
        self.assertFalse(receipt["output"]["safe_state_achieved"])

    def test_the_estop_is_confirmed_by_fresh_pose_samples_on_the_ground(self) -> None:
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        sensed = receipt["x-vendor"]["sensed_confirmation"]
        self.assertEqual(sensed["request"], [{"native": "/all/emergency", "kind": "service",
                                              "outcome": "succeeded"}])
        self.assertGreaterEqual(sensed["sources"]["pose"]["samples"], 3)
        self.assertEqual(driver.native.pose["z"], 0.0)
        refused = client.invoke("x-cap.larics.cmd_vel.v1", VELOCITY, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_the_stop_is_terminal_the_reset_is_refused_without_a_bridge_call(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        sent = len(driver.native.sent)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED", reset)
        self.assertEqual(details(reset)["reason"], "terminal_estop", reset)
        # The bridge's reset never ran: no request and no re-confirmation (the receipt's state read subscribes once).
        later = driver.native.sent[sent:]
        self.assertFalse([message for message in later if message.get("op") == "call_service"], later)
        self.assertLessEqual(len([message for message in later if message.get("op") == "subscribe"]), 1, later)
        refused = client.invoke("x-cap.larics.cmd_vel.v1", VELOCITY, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)   # the latch is kept

    def test_a_second_estop_repeats_the_request_and_stays_confirmed(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("first", **self.ids)["status"], "completed")
        again = client.estop("second", **self.ids)
        self.assertEqual(again["status"], "completed", again)
        self.assertEqual(driver.native.emergency_requests, 2)

    def test_an_acknowledged_emergency_without_a_fall_is_never_confirmed(self) -> None:
        driver, client = self.serve()
        driver.native.no_fall = True
        self.assert_unreached(client.estop("test", **self.ids), "not_confirmed")

    def test_a_vehicle_that_keeps_moving_is_never_confirmed(self) -> None:
        driver, client = self.serve()
        driver.native.drift = True
        self.assert_unreached(client.estop("test", **self.ids), "not_confirmed")

    def test_a_silent_pose_stream_is_sensed_missing(self) -> None:
        driver, client = self.serve()
        driver.native.fail_pose = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_repeated_producer_stamp_is_stale(self) -> None:
        driver, client = self.serve()
        driver.native.frozen_stamps = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_stale")

    def test_a_null_altitude_is_invalid(self) -> None:
        driver, client = self.serve()
        driver.native.null_z = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_invalid")


if __name__ == "__main__":
    unittest.main()
