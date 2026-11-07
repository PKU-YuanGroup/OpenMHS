"""Acceptance run of the Webots ROS 2 Spot package: the gate plus repository-specific cases.

Add cases, never remove the check_driver call. The e-stop is a sensed-confirmation stop (SAFE-049, simulated
devices only). It clears /Spot/float_mode, requests /Spot/lie_down, and is achieved only on fresh
/Spot/odometry samples of a base that is still and inside the lying height band. The plug-in publishes that
topic from defined_motions and again from step. The fake's queue keeps one copy when both arrive
together, and forwards a second copy that arrives after the first was published. That equal stamp
fails closed. Ongoing yaw fails the orientation span, so the stop is not confirmed and reset does
not release the latch.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS = HERE / "site-limits.example.json"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
RESET_REFUSED = "MHS.SAFETY.RESET_REFUSED"
CMD = {"linear_velocity": 0.1, "lateral_velocity": 0.0, "angular_velocity": 0.2}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SpotCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake", site_limits=LIMITS)
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

    def test_the_observations_are_returned_from_the_declared_topics(self) -> None:
        client = self.serve()
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(len(state["joint_positions"]), 16)
        self.assertEqual(set(state["odom_position"]), {"x", "y", "z"})
        self.assertEqual(set(state["odom_orientation"]), {"x", "y", "z", "w"})
        self.assertEqual(set(state["odom_twist"]), {"linear", "angular"})

    def test_the_velocity_publication_reaches_the_cmd_vel_topic(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.maskor.cmd_vel.v1", CMD, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["published"])
        self.assertFalse(receipt["output"]["confirmed"])

    def test_the_velocity_publication_is_refused_without_operator_bounds(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke("x-cap.maskor.cmd_vel.v1", CMD, device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_posture_services_are_reached_and_reported(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.maskor.stand_up.v1", {"override": True}), {"answer": "standing up"})
        self.assertEqual(driver.call("x-cap.maskor.sit_down.v1", {"override": True}), {"answer": "sitting down"})
        self.assertEqual(driver.call("x-cap.maskor.lie_down.v1", {}), {"answer": "lying down"})
        self.assertIn("/Spot/stand_up", driver.native.service_calls)
        self.assertIn("/Spot/sit_down", driver.native.service_calls)
        self.assertIn("/Spot/lie_down", driver.native.service_calls)

    def test_set_height_uses_the_source_bound(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.maskor.set_height.v1", {"height": 0.1}), {"answer": ""})
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.maskor.set_height.v1", {"height": 0.3})

    def test_a_failed_posture_service_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_lie_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.maskor.lie_down.v1", {})

    def test_a_rejected_posture_application_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.reject_lie_application = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.maskor.lie_down.v1", {})

    def test_the_declaration_is_a_sensed_stop_without_a_safe_state_action(self) -> None:
        cls = type(self.driver())
        self.assertEqual(set(cls.safety_bindings), {"sensed_stop"})
        self.assertFalse(any(action.safe_state for action in cls.actions.values()))
        stop = cls.safety_bindings["sensed_stop"]
        self.assertEqual([step["service"] for step in stop["request"]],
                         ["/Spot/float_mode", "/Spot/lie_down"])
        self.assertNotIn("args", stop["request"][0])
        self.assertNotIn("result", stop["request"][0])
        self.assertNotIn("args", stop["request"][1])
        self.assertNotIn("result", stop["request"][1])
        self.assertEqual(stop["sources"]["odom"]["throttle_ms"], 100)
        self.assertEqual(stop["sources"]["odom"]["history"]["durability"], "volatile")
        self.assertFalse(any("twist" in str(term.get("path", "")) for term in stop["predicate"]))
        orientations = [term["path"] for term in stop["predicate"] if "orientation" in term["path"]]
        self.assertEqual(orientations, [
            "pose.pose.orientation.x", "pose.pose.orientation.y",
            "pose.pose.orientation.z", "pose.pose.orientation.w"])
        self.assertTrue(all("span_max" in term for term in stop["predicate"] if "orientation" in term["path"]))


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


class SensedStopCases(unittest.TestCase):
    """SAFE-049: the two requests prove nothing; only fresh odometry of a still, lying base achieves the stop."""

    def serve(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=str(LIMITS))
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

    def test_the_estop_is_confirmed_on_throttled_odometry(self) -> None:
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        sensed = receipt["x-vendor"]["sensed_confirmation"]
        self.assertEqual([(step["native"], step["outcome"]) for step in sensed["request"]],
                         [("/Spot/float_mode", "succeeded"), ("/Spot/lie_down", "succeeded")])
        calls = [message for message in driver.native.sent if message.get("op") == "call_service"]
        self.assertEqual([message["service"] for message in calls], ["/Spot/float_mode", "/Spot/lie_down"])
        self.assertEqual(calls[0]["args"], {"data": False})
        self.assertEqual(calls[1]["args"], {"override": True})
        self.assertFalse([message for message in driver.native.sent if message.get("op") == "publish"])
        subs = [message for message in driver.native.sent
                if message.get("op") == "subscribe" and message.get("topic") == "/Spot/odometry"
                and message.get("throttle_rate") is not None]
        self.assertEqual([message.get("throttle_rate") for message in subs], [100])
        self.assertEqual(subs[0].get("queue_length"), 1)
        stamps = driver.native.last_odom_stamps
        self.assertGreaterEqual(len(stamps), 4)
        self.assertEqual(len(stamps), len(set(stamps)))
        refused = client.invoke("x-cap.maskor.cmd_vel.v1", CMD, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_rotating_base_is_not_confirmed_and_reset_does_not_release(self) -> None:
        driver, client = self.serve()
        driver.native.rotating = True
        self.assert_unreached(client.estop("test", **self.ids), "not_confirmed")
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], RESET_REFUSED, reset)
        held = client.invoke("x-cap.maskor.cmd_vel.v1", CMD, **self.ids)
        self.assertEqual(held["error"]["mhs_code"], ESTOP, held)

    def test_rotation_after_a_stop_refuses_reset(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        driver.native.rotating = True
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], RESET_REFUSED, reset)
        held = client.invoke("x-cap.maskor.cmd_vel.v1", CMD, **self.ids)
        self.assertEqual(held["error"]["mhs_code"], ESTOP, held)

    def test_a_copy_forwarded_after_the_first_stays_stale(self) -> None:
        driver, client = self.serve()
        driver.native.straddle_publish = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_stale")
        stamps = driver.native.last_odom_stamps
        self.assertGreaterEqual(len(stamps), 4)
        self.assertEqual(stamps[0::2], stamps[1::2])
        self.assertGreater(len(set(stamps)), 1)
        held = client.invoke("x-cap.maskor.cmd_vel.v1", CMD, **self.ids)
        self.assertEqual(held["error"]["mhs_code"], ESTOP, held)

    def test_the_queue_model_matches_rosbridge_timing(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        forward = driver.native.forward_queue
        together = forward([(0.0, "a"), (0.0, "b"), (0.1, "c"), (0.1, "d")], 0.1, 1)
        self.assertEqual(together, ["b", "d"])
        delayed = forward([(0.0, "a"), (0.001, "b")], 0.1, 1)
        self.assertEqual(delayed, ["a", "b"])

    def test_duplicate_stamps_without_the_throttle_collapse_stay_stale(self) -> None:
        driver, client = self.serve()
        driver.native.honor_throttle = False
        self.assert_unreached(client.estop("test", **self.ids), "sensed_stale")
        stamps = driver.native.last_odom_stamps
        self.assertGreaterEqual(len(stamps), 4)
        self.assertEqual(len(stamps) % 2, 0)
        self.assertEqual(stamps[0::2], stamps[1::2])
        self.assertGreater(len(set(stamps)), 1)
        refused = client.invoke("x-cap.maskor.cmd_vel.v1", CMD, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_stored_velocity_is_not_cleared_by_the_stop(self) -> None:
        driver, client = self.serve()
        published = client.invoke("x-cap.maskor.cmd_vel.v1", CMD, **self.ids)
        self.assertEqual(published["status"], "completed", published)
        stored = driver.native.previous_cmd_vel
        sent = len(driver.native.sent)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(driver.native.previous_cmd_vel, stored)
        later = [message for message in driver.native.sent[sent:] if message.get("op") == "publish"]
        self.assertEqual(later, [])

    def test_float_mode_left_true_is_not_confirmed(self) -> None:
        driver, client = self.serve()
        driver.native.competing_float = True
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "not_confirmed")
        self.assertEqual([step["outcome"] for step in details(receipt)["sensed"]["request"]],
                         ["succeeded", "succeeded"])
        self.assertTrue(driver.native.float_mode)

    def test_a_failed_lie_service_is_not_confirmed(self) -> None:
        driver, client = self.serve()
        driver.native.fail_lie_service = True
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "not_confirmed")
        self.assertEqual(details(receipt)["sensed"]["request"][1]["outcome"], "refused")

    def test_a_rejected_lie_application_is_not_confirmed(self) -> None:
        driver, client = self.serve()
        driver.native.reject_lie_application = True
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "not_confirmed")
        self.assertEqual(details(receipt)["sensed"]["request"][1]["outcome"], "refused")
        self.assertFalse(driver.native.fixed_motion)

    def test_a_competing_cmd_vel_keeps_the_stop_unconfirmed(self) -> None:
        driver, client = self.serve()
        driver.native.competing_cmd_vel = True
        self.assert_unreached(client.estop("test", **self.ids), "not_confirmed")

    def test_silent_odometry_is_sensed_missing(self) -> None:
        driver, client = self.serve()
        driver.native.silent = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_repeated_producer_stamp_is_stale(self) -> None:
        driver, client = self.serve()
        driver.native.frozen_stamps = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_stale")

    def test_a_null_position_is_invalid(self) -> None:
        driver, client = self.serve()
        driver.native.null_position = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_invalid")

    def test_a_reset_reconfirms_without_a_request(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        sent = len(driver.native.sent)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertFalse(reset["output"]["resumed"])
        later = driver.native.sent[sent:]
        self.assertFalse([message for message in later if message.get("op") in ("publish", "call_service")])

    def test_a_reset_is_refused_while_another_publisher_walks_the_robot(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        driver.native.competing_cmd_vel = True
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], RESET_REFUSED, reset)


if __name__ == "__main__":
    unittest.main()
