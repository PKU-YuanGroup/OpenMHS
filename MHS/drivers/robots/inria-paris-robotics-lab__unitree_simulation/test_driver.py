"""Acceptance run of the unitree_simulation ROS 2 package: the gate plus cases.

The cases exercise the pinned rosbridge contract through the ROS-free fake:
the /lowcmd publication and its motor_cmd mapping, the /reset and /unlock_base
publications, the /lowstate and /odometry/filtered observations, malformed
replies, transport failure, the operator-required envelope and the
sensed-confirmation stop. Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"

LOWCMD = "x-cap.inria-paris-robotics-lab.lowcmd.v1"
LOWSTATE = "x-cap.inria-paris-robotics-lab.lowstate.v1"
RESET = "x-cap.inria-paris-robotics-lab.reset.v1"
UNLOCK = "x-cap.inria-paris-robotics-lab.unlock_base.v1"


def motor_cmd(q=0.0, dq=0.0, tau=0.0, kp=0.0, kd=0.0):
    """A 12-entry Go2 LowCmd motor_cmd array; test data, not a device state."""
    return [{"q": q, "dq": dq, "tau": tau, "kp": kp, "kd": kd} for _ in range(12)]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UnitreeSimulationCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    @staticmethod
    def published(driver, topic):
        return [message for message in driver.native.sent
                if message.get("op") == "publish" and message.get("topic") == topic]

    def test_lowcmd_is_one_declared_publication_and_reaches_the_fake(self):
        driver = self.driver()
        command = motor_cmd(q=0.1, dq=-0.2, tau=0.3, kp=4.0, kd=0.5)
        receipt = driver.call(LOWCMD, {"motor_cmd": command})
        self.assertEqual(receipt, {"published": True, "confirmed": False})
        self.assertEqual(driver.native.lowcmd_count, 1)
        self.assertEqual(driver.native.last_motor_cmd, command)
        advertised = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(advertised[-1]["topic"], "/lowcmd")
        self.assertEqual(advertised[-1]["type"], "unitree_go/msg/LowCmd")
        sent = self.published(driver, "/lowcmd")[-1]
        self.assertEqual(sent["msg"]["motor_cmd"], command)
        self.assertEqual(len(sent["msg"]["motor_cmd"]), 12)

    def test_lowcmd_requires_the_reviewed_operator_envelope(self):
        client = self.serve()
        refused = client.invoke(LOWCMD, {"motor_cmd": motor_cmd(tau=0.1)}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], UNSET)

    def test_reset_and_unlock_are_empty_publications(self):
        driver = self.driver()
        self.assertEqual(driver.call(RESET, {}), {"published": True, "confirmed": False})
        self.assertEqual(driver.call(UNLOCK, {}), {"published": True, "confirmed": False})
        reset = self.published(driver, "/reset")[-1]
        unlock = self.published(driver, "/unlock_base")[-1]
        self.assertEqual(reset["msg"], {})
        self.assertEqual(unlock["msg"], {})
        advertised = [message for message in driver.native.sent if message.get("op") == "advertise"]
        reset_type = [message["type"] for message in advertised if message["topic"] == "/reset"][-1]
        unlock_type = [message["type"] for message in advertised if message["topic"] == "/unlock_base"][-1]
        self.assertEqual(reset_type, "std_msgs/msg/Empty")
        self.assertEqual(unlock_type, "std_msgs/msg/Empty")
        self.assertEqual(driver.native.reset_count, 1)
        self.assertEqual(driver.native.unlock_count, 1)
        # A reset publication does not clear the fake's last command: the node's
        # receive callback and reset() do not clear last_cmd_msg either.
        self.assertIsNone(driver.native.last_motor_cmd)

    def test_lowstate_observation_selects_the_node_fields(self):
        driver = self.driver()
        state = driver.call(LOWSTATE, {})
        self.assertEqual(set(state), {"motor_mode", "motor_q", "motor_dq", "foot_force",
                                      "imu_quaternion", "imu_gyroscope", "imu_accelerometer"})
        self.assertEqual(len(state["motor_q"]), 12)
        self.assertEqual(len(state["motor_dq"]), 12)
        self.assertEqual(len(state["foot_force"]), 4)
        self.assertEqual(len(state["imu_quaternion"]), 4)
        self.assertEqual(len(state["imu_gyroscope"]), 3)
        self.assertEqual(len(state["imu_accelerometer"]), 3)
        subscription = [message for message in driver.native.sent
                        if message.get("op") == "subscribe" and message.get("topic") == "/lowstate"][-1]
        self.assertEqual(subscription["type"], "unitree_go/msg/LowState")

    def test_a_lowstate_with_more_motor_entries_than_the_node_fills_is_read(self):
        # Reviewer case: the node fills the first 12 entries of a pre-sized motor_state array whose size the
        # unitree_go definition (outside the clone) sets; a longer real message must not be refused.
        driver = self.driver()
        driver.native.extra_motor_entries = 8  # placeholder: unitree_ros2 declares 20 entries
        state = driver.call(LOWSTATE, {})
        self.assertEqual(len(state["motor_q"]), 20)
        self.assertEqual(len(state["motor_mode"]), 20)
        self.assertEqual(state["motor_mode"][12:], [0] * 8)

    def test_odometry_reads_select_pose_and_twist_from_one_topic(self):
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["pose"]["position"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(state["pose"]["orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        self.assertEqual(state["twist"]["linear"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(state["twist"]["angular"], {"x": 0.0, "y": 0.0, "z": 0.0})
        topics = [message.get("topic") for message in driver.native.sent
                  if message.get("op") == "subscribe"]
        self.assertIn("/odometry/filtered", topics)
        self.assertNotIn("/lowcmd", topics)

    def test_a_malformed_lowstate_reply_is_a_failed_observation(self):
        driver = self.driver()
        driver.native.malformed_lowstate = True
        with self.assertRaises(MHSError) as caught:
            driver.call(LOWSTATE, {})
        self.assertIn(caught.exception.code, {"MHS.CAPABILITY.OUTPUT_INVALID", "MHS.RESOURCE.STATE_INVALID",
                                              "MHS.ADAPTER.SHIM_FAILED"})

    def test_a_silent_lowstate_topic_is_a_failed_observation(self):
        driver = self.driver()
        driver.native.silent_lowstate = True
        with self.assertRaises(MHSError) as caught:
            driver.call(LOWSTATE, {})
        self.assertIn(caught.exception.code, {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})

    def test_a_rejected_publication_does_not_report_success(self):
        driver = self.driver()
        driver.native.reject_publish = True
        with self.assertRaises(MHSError) as caught:
            driver.call(RESET, {})
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(driver.native.reset_count, 0)

    def test_the_declaration_is_a_sensed_stop_without_a_safe_state_action(self):
        cls = type(self.driver())
        self.assertEqual(set(cls.safety_bindings), {"sensed_stop"})
        self.assertFalse(any(action.safe_state for action in cls.actions.values()))
        self.assertEqual(cls.estop_latency_ms, 2500)
        sources = cls.safety_bindings["sensed_stop"]["sources"]
        self.assertEqual(sources["lowstate"]["freshness"], "arrival")
        self.assertNotIn("stamp_path", sources["lowstate"])
        self.assertEqual(sources["odom"]["stamp_path"], "header.stamp")


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


class SensedStopCases(unittest.TestCase):
    """SAFE-049: the zero LowCmd proves nothing; only fresh joint and twist samples achieve the stop."""

    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return server, client

    def native(self, server):
        driver = server.drivers[0] if hasattr(server, "drivers") else None
        return driver

    def assert_unreached(self, receipt, reason):
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
        self.assertEqual(details(receipt)["reason"], "bridge_reports_unsafe", receipt)
        self.assertEqual(details(receipt)["sensed"]["reason"], reason, receipt)
        self.assertFalse(receipt["output"]["safe_state_achieved"])

    def test_the_estop_is_confirmed_by_fresh_joint_and_twist_samples(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        receipt = client.estop("test", **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        sensed = receipt["x-vendor"]["sensed_confirmation"]
        self.assertEqual([(step["native"], step["outcome"]) for step in sensed["request"]],
                         [("/lowcmd", "published")])
        self.assertEqual(len(driver.native.last_motor_cmd), 20)
        self.assertTrue(all(entry["kp"] == 0.0 and entry["kd"] == 0.0 and entry["tau"] == 0.0
                            for entry in driver.native.last_motor_cmd))
        refused = client.invoke(LOWCMD, {"motor_cmd": motor_cmd()}, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_reset_reconfirms_without_another_lowcmd(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        self.assertEqual(client.estop("test", **ids)["status"], "completed")
        sent = len(driver.native.sent)
        reset = client.reset(**ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertFalse(reset["output"]["resumed"])
        later = driver.native.sent[sent:]
        self.assertFalse([message for message in later if message.get("op") == "publish"])

    def test_motion_that_continues_is_not_confirmed(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.keep_moving = True
        from mhs.driver import build_server
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        self.assert_unreached(client.estop("test", **ids), "not_confirmed")

    def test_a_moving_base_is_not_confirmed(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.base_moving = True
        from mhs.driver import build_server
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        self.assert_unreached(client.estop("test", **ids), "not_confirmed")

    def test_silent_lowstate_is_sensed_missing(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.silent_lowstate = True
        from mhs.driver import build_server
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        self.assert_unreached(client.estop("test", **ids), "sensed_missing")

    def test_a_repeated_odometry_stamp_is_stale(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.frozen_stamps = True
        from mhs.driver import build_server
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        self.assert_unreached(client.estop("test", **ids), "sensed_stale")

    def test_a_null_joint_velocity_is_invalid(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.null_dq = True
        from mhs.driver import build_server
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        self.assert_unreached(client.estop("test", **ids), "sensed_invalid")

    def test_samples_at_the_500_hz_period_meet_the_declared_span(self):
        """high_level_period is 1/500 s. Three counted samples span 4 ms, which is min_span_ms."""
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        cls = type(driver)
        self.assertEqual(cls.safety_bindings["sensed_stop"]["min_span_ms"], 4)
        from mhs.bridge.ros_sensed import SourceWindow, compile_profile
        from mhs.driver.sensed_stop import declaration
        problems: list[str] = []
        decl = declaration(cls, problems)
        self.assertEqual(problems, [])
        self.assertIsNotNone(decl)
        values = {item.key: 0.05 for item in decl.thresholds}
        profile = compile_profile(decl.bridge_json(cls.ros_version, values))
        period = 1.0 / 500.0
        low = profile.sources["lowstate"]
        low_window = SourceWindow(low, profile.terms_of("lowstate"), profile, not_before=0.0)
        low_message = {"motor_state": [{"dq": 0.0} for _ in range(12)]}
        low_count = profile.consecutive + low.skip
        for index in range(low_count):
            low_window.add(low_message, received_at=index * period)
        self.assertTrue(low_window.confirmed((low_count - 1) * period), low_window.report())
        span_ms = (low_window.counted[-1][1] - low_window.counted[0][1]) * 1000.0
        self.assertGreaterEqual(span_ms, 4)
        self.assertLess(span_ms, 80)
        odom = profile.sources["odom"]
        odom_window = SourceWindow(odom, profile.terms_of("odom"), profile, not_before=0.0)
        step_ns = 2_000_000
        odom_count = profile.consecutive + odom.skip
        for index in range(odom_count):
            ns = 1_000_000_000 + index * step_ns
            odom_window.add({
                "header": {"stamp": {"sec": ns // 1_000_000_000, "nanosec": ns % 1_000_000_000}},
                "twist": {"twist": {
                    "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
                }},
            }, received_at=index * period)
        self.assertTrue(odom_window.confirmed((odom_count - 1) * period), odom_window.report())

    def test_the_estop_confirms_when_lowstate_is_paced_at_500_hz(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.gap_s = 1.0 / 500.0
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        receipt = client.estop("test", **ids)
        self.assertEqual(receipt["status"], "completed", receipt)


if __name__ == "__main__":
    unittest.main()
