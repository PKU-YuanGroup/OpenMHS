"""Acceptance run of the map_simulator ROS package: the gate plus simulator cases.

The stop is a sensed confirmation (SAFE-049, simulated only).  A zero Twist on
/robot1/cmd_vel proves nothing; the e-stop is achieved only when fresh stamped
/robot1/odom samples stay inside the operator pose and twist bounds.  The
check_driver call is kept.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
SPAWN = "x-cap.okermorgant.spawn.v1"
TWIST = "x-cap.okermorgant.twist.v1"
ODOMETRY = "x-cap.okermorgant.odometry.v1"
SCAN = "x-cap.okermorgant.scan.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
RESET_REFUSED = "MHS.SAFETY.RESET_REFUSED"

SPAWN_INPUT = {
    "robot_namespace": "/robot1",
    "x": 0.0,
    "y": 0.0,
    "theta": 0.0,
    "radius": 1.0,
    "shape": 1,
    "size": [1.0, 1.0, 0.0],
}
TWIST_INPUT = {"linear_x": 0.2, "linear_y": 0.0, "angular_z": 0.1}
_ZERO_TWIST = {"linear": {"x": 0.0, "y": 0.0, "z": 0.0},
               "angular": {"x": 0.0, "y": 0.0, "z": 0.0}}


def example_overlay():
    return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MapSimulatorCases(unittest.TestCase):
    def serve(self, *, overlay=True):
        server = load(HERE, backend="fake", site_limits=example_overlay() if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def direct(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver, driver.native

    def test_the_spawn_action_calls_the_upstream_service(self) -> None:
        driver, fake = self.direct()
        result = driver.call(SPAWN, SPAWN_INPUT)
        self.assertEqual(result, {"acknowledged": True})
        calls = [message for message in fake.sent
                 if message.get("op") == "call_service" and message.get("service") == "/simulator/spawn"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].get("type"), "map_simulator/srv/Spawn")
        self.assertEqual(calls[0]["args"]["robot_namespace"], "/robot1")
        self.assertEqual(fake.spawn_calls[-1]["robot_namespace"], "/robot1")

    def test_an_empty_namespace_is_refused_before_the_service(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=example_overlay())
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        bad = dict(SPAWN_INPUT)
        bad["robot_namespace"] = ""
        receipt = client.invoke(SPAWN, bad, device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID, receipt)
        self.assertEqual(driver.native.spawn_calls, [])

    def test_the_twist_action_publishes_without_confirmation(self) -> None:
        driver, fake = self.direct()
        result = driver.call(TWIST, {"linear_x": 0.25, "linear_y": 0.0, "angular_z": 0.5})
        self.assertTrue(result["published"])
        self.assertFalse(result["confirmed"])
        self.assertEqual(fake.last_cmd_vel["linear"]["x"], 0.25)
        self.assertEqual(fake.last_cmd_vel["angular"]["z"], 0.5)
        published = [message for message in fake.sent
                     if message.get("op") == "publish" and message.get("topic") == "/robot1/cmd_vel"]
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["msg"]["linear"]["x"], 0.25)
        self.assertEqual(published[0]["msg"]["angular"]["z"], 0.5)

    def test_the_twist_is_refused_without_the_operator_overlay(self) -> None:
        client = self.serve(overlay=False)
        receipt = client.invoke(TWIST, TWIST_INPUT, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_odometry_observation_returns_pose_and_twist(self) -> None:
        driver, _fake = self.direct()
        result = driver.call(ODOMETRY, {})
        self.assertIn("position", result["pose"])
        self.assertIn("orientation", result["pose"])
        self.assertIn("linear", result["twist"])
        self.assertIn("angular", result["twist"])

    def test_two_odometry_reads_agree_while_a_command_is_held(self) -> None:
        driver, _fake = self.direct()
        first = driver.call(ODOMETRY, {})
        second = driver.call(ODOMETRY, {})
        self.assertEqual(first["pose"], second["pose"])
        self.assertEqual(first["twist"], second["twist"])
        self.assertEqual(first["twist"]["linear"]["x"], 0.2)

    def test_the_scan_observation_returns_the_declared_fields(self) -> None:
        driver, _fake = self.direct()
        result = driver.call(SCAN, {})
        self.assertEqual(len(result["ranges"]), 100)
        for name in ("angle_min", "angle_max", "angle_increment", "range_min", "range_max"):
            self.assertIn(name, result)

    def test_a_missing_odometry_twist_is_reported_as_a_failure(self) -> None:
        driver, fake = self.direct()
        fake.omit_odom_twist = True
        with self.assertRaises(DriverFailed):
            driver.call(ODOMETRY, {})

    def test_a_failed_spawn_service_is_not_reported_as_success(self) -> None:
        driver, fake = self.direct()
        fake.fail_spawn_service = True
        with self.assertRaises(DriverFailed):
            driver.call(SPAWN, SPAWN_INPUT)

    def test_a_rejected_spawn_application_is_not_reported_as_success(self) -> None:
        driver, fake = self.direct()
        fake.reject_spawn_application = True
        with self.assertRaises(DriverFailed):
            driver.call(SPAWN, SPAWN_INPUT)

    def test_the_stop_is_a_sensed_confirmation_on_a_simulated_ros2_world(self) -> None:
        driver, _fake = self.direct()
        cls = type(driver)
        self.assertEqual(set(cls.safety_bindings), {"sensed_stop"})
        self.assertIsNone(cls.estop_physical_ref)
        self.assertEqual(cls.ros_version, 2)
        self.assertEqual(cls.mode, "simulated")
        self.assertEqual(cls.risk, "R2")
        self.assertEqual(cls.device_kind, "world.sim")
        self.assertEqual(cls.estop_latency_ms, 3500)
        sources = cls.safety_bindings["sensed_stop"]["sources"]
        self.assertEqual({source["topic"] for source in sources.values()}, {"/robot1/odom"})
        self.assertEqual(cls.actions[TWIST].risk, "R2")
        self.assertEqual(cls.actions[SPAWN].risk, "R1")
        self.assertLessEqual(len(cls.safe_state), 500)
        self.assertLessEqual(len(cls.safety_bindings["sensed_stop"]["description"]), 500)


class SensedStopCases(unittest.TestCase):
    """SAFE-049: the zero Twist proves nothing; only fresh stamped /robot1/odom samples that stay still achieve it."""

    def serve(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=example_overlay())
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

    def test_the_estop_publishes_a_zero_twist_and_is_confirmed_by_fresh_odometry(self):
        driver, client = self.serve()
        before = client.invoke(ODOMETRY, {}, **self.ids)
        self.assertEqual(before["status"], "completed", before)
        self.assertEqual(before["output"]["twist"]["linear"]["x"], 0.2)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        sensed = receipt["x-vendor"]["sensed_confirmation"]
        self.assertEqual(sensed["request"], [
            {"native": "/robot1/cmd_vel", "kind": "topic", "outcome": "published"}])
        zero = [message for message in driver.native.sent
                if message.get("op") == "publish" and message.get("topic") == "/robot1/cmd_vel"][-1]
        self.assertEqual(zero["msg"], _ZERO_TWIST)
        # One burst is the confirmation: its first sample is the pre-request
        # twist (discarded) and the later samples are the zero command.  A
        # later read, after that zero is stored, is all zeros.
        snap = [burst for burst in driver.native.odom_bursts
                if burst and burst[0] == 0.2 and burst[1] == 0.0 and burst[-1] == 0.0]
        self.assertEqual(len(snap), 1, driver.native.odom_bursts)
        stamps = driver.native.last_odom_stamps_ns
        self.assertGreaterEqual(len(stamps), 4, stamps)
        self.assertEqual(stamps[-1] - stamps[-3], 100_000_000)
        # A latched invoke of the odometry capability is refused.  The stored
        # fake state is the observation: the zero command was kept, and the
        # pose was not teleported.
        self.assertEqual(driver.native.published["linear"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(driver.native.published["angular"]["z"], 0.0)
        self.assertEqual(driver.native.pose, before["output"]["pose"])
        refused = client.invoke(TWIST, TWIST_INPUT, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_reset_reconfirms_without_a_request_and_resumes_nothing(self):
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        published = len([message for message in driver.native.sent if message.get("op") == "publish"])
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertFalse(reset["output"]["resumed"])
        self.assertEqual(len([message for message in driver.native.sent if message.get("op") == "publish"]),
                         published)
        self.assertEqual(driver.native.published["linear"]["x"], 0.0)

    def test_a_reset_is_refused_while_another_publisher_moves_the_robot(self):
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        driver.native.competing_publisher = True
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], RESET_REFUSED, reset)

    def test_a_competing_publisher_keeps_the_stop_unconfirmed(self):
        driver, client = self.serve()
        driver.native.competing_publisher = True
        self.assert_unreached(client.estop("test", **self.ids), "not_confirmed")

    def test_silent_odometry_is_sensed_missing(self):
        driver, client = self.serve()
        driver.native.silent_odom = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_repeated_producer_stamp_is_stale(self):
        driver, client = self.serve()
        driver.native.frozen_stamps = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_stale")

    def test_a_null_pose_field_is_invalid(self):
        driver, client = self.serve()
        driver.native.null_pose = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_invalid")


if __name__ == "__main__":
    unittest.main()
