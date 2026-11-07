"""Acceptance run of the NAO walker package: the gate plus repository-specific cases.

The fake is a ROS-free recording transport.  These cases exercise the declared
ROS 1 topic/stop wire shapes, the command register, the operator-required
envelope, the upstream stop ambiguity and the e-stop latch.  No ROS graph,
NaOqi runtime or hardware is contacted.  Add cases, never remove the
check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = HERE / "site-limits.example.json"
VELOCITY = "x-cap.ros-naoqi.walk_velocity.v1"
POSE = "x-cap.ros-naoqi.walk_pose.v1"
STOP = "x-cap.ros-naoqi.stop_walk.v1"
CLIP = "x-cap.ros-naoqi.clip_footstep.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
PUBLISHED = {"published": True, "confirmed": False}

#: Example values inside site-limits.example.json; test data, not device facts.
VELOCITY_INPUT = {"linear_x": 0.02, "linear_y": -0.01, "angular_z": 0.1}
POSE_INPUT = {"x": 0.1, "y": -0.1, "theta": 0.1}
CLIP_INPUT = {"x": 0.02, "y": -0.1, "theta": 0.1}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertIn("G3", report["failed"], report)
        self.assertFalse(report["passed"], report)


class WalkerCases(unittest.TestCase):
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

    def test_empty_resource_snapshot_does_not_contact_the_transport(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.read("main"), {})
        self.assertEqual(driver.native.sent, [])

    def test_velocity_publication_carries_the_twist_components(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(VELOCITY, VELOCITY_INPUT), PUBLISHED)
        publish = [message for message in driver.native.sent if message.get("op") == "publish"][-1]
        self.assertEqual(publish["topic"], "/cmd_vel")
        self.assertEqual(publish["msg"], {
            "linear": {"x": 0.02, "y": -0.01, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": 0.1},
        })
        self.assertTrue(driver.native.walking)

    def test_pose_publication_carries_the_robot_frame_pose(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(POSE, POSE_INPUT), PUBLISHED)
        publish = [message for message in driver.native.sent if message.get("op") == "publish"][-1]
        self.assertEqual(publish["topic"], "/cmd_pose")
        self.assertEqual(publish["msg"], {"x": 0.1, "y": -0.1, "theta": 0.1})

    def test_publications_update_the_fake_command_state(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.read("main"), {})
        driver.call(VELOCITY, VELOCITY_INPUT)
        self.assertTrue(driver.native.walking)
        driver.call(POSE, POSE_INPUT)
        self.assertEqual(driver.native.last_pose, {"x": 0.1, "y": -0.1, "theta": 0.1})
    def test_clip_service_returns_the_clipped_step(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(CLIP, CLIP_INPUT), {"x": 0.02, "y": -0.1, "theta": 0.1})
        message = driver.native.sent[-1]
        self.assertEqual(message["op"], "call_service")
        self.assertEqual(message["service"], "/clip_footstep_srv")
        self.assertEqual(message["type"], "humanoid_nav_msgs/ClipFootstep")
        self.assertEqual(message["args"], {"step": {"leg": 0, "pose": {
            "x": 0.02, "y": -0.1, "theta": 0.1,
        }}})

    def test_clip_service_clips_an_out_of_range_pose(self) -> None:
        # The direct bridge call bypasses the server envelope; this exercises
        # the fake's model of the upstream clipping helper, not a driver limit.
        driver = self.driver()
        self.assertEqual(driver.call(CLIP, {"x": 1.0, "y": -1.0, "theta": 2.0}),
                         {"x": 0.08, "y": -0.16, "theta": 0.5})

    def test_ordinary_stop_service_does_not_latch_normal_use(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke(STOP, {}, **self.ids)["status"], "completed")
        receipt = client.invoke(VELOCITY, VELOCITY_INPUT, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], PUBLISHED)

    def test_the_stop_action_reaches_the_upstream_service(self) -> None:
        driver = self.driver()
        driver.native.walking = True
        self.assertEqual(driver.call(STOP, {}), {"callback_returned": True})
        self.assertFalse(driver.native.walking)
        self.assertEqual(driver.native.stop_calls, 1)
        message = driver.native.sent[-1]
        self.assertEqual(message["service"], "/stop_walk_srv")
        self.assertEqual(message["type"], "std_srvs/Empty")

    def test_an_e_stop_does_not_invent_an_independent_native_stop(self) -> None:
        driver = self.driver()
        driver.native.walking = True
        receipt = driver.estop("test")
        self.assertEqual(receipt, {})  # Bridge default only engages the local latch
        self.assertTrue(driver.native.walking)
        self.assertEqual(driver.native.stop_calls, 0)

    def test_an_e_stop_refuses_motion_while_latched(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertTrue(receipt["output"]["latched"])
        refused = client.invoke(VELOCITY, VELOCITY_INPUT, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_operator_required_bounds_refuse_without_the_example_overlay(self) -> None:
        client = self.serve(overlay=False)
        refused = client.invoke(VELOCITY, VELOCITY_INPUT, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], UNSET)

    def test_the_example_overlay_admits_an_in_range_motion_command(self) -> None:
        client = self.serve()
        receipt = client.invoke(VELOCITY, VELOCITY_INPUT, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], PUBLISHED)
        receipt = client.invoke(POSE, POSE_INPUT, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], PUBLISHED)
        receipt = client.invoke(CLIP, CLIP_INPUT, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"x": 0.02, "y": -0.1, "theta": 0.1})

    def test_a_value_outside_the_example_overlay_is_refused(self) -> None:
        client = self.serve()
        refused = client.invoke(VELOCITY, {"linear_x": 1.0, "linear_y": 0.0, "angular_z": 0.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused = client.invoke(CLIP, {"x": 1.0, "y": -0.1, "theta": 0.1}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_a_failed_ordinary_stop_service_is_not_completion(self) -> None:
        driver = self.driver()
        driver.native.fail_stop_service = True
        with self.assertRaises(DriverFailed):
            driver.call(STOP, {})

    def test_a_malformed_ordinary_stop_reply_is_not_completion(self) -> None:
        driver = self.driver()
        driver.native.malformed_stop_reply = True
        with self.assertRaises(OutcomeUnknown):
            driver.call(STOP, {})

    def test_an_application_rejection_is_not_completion(self) -> None:
        driver = self.driver()
        driver.native.fail_stop_application = True
        with self.assertRaises(DriverFailed):
            driver.call(STOP, {})

    def test_a_none_upstream_handler_result_is_a_service_failure(self) -> None:
        # The pinned handler returns None after a caught RuntimeError; rospy
        # rejects None rather than manufacturing a successful Empty response.
        driver = self.driver()
        driver.native.walking = True
        driver.native.stop_walk_raised_upstream = True
        with self.assertRaises(DriverFailed):
            driver.call(STOP, {})
        self.assertTrue(driver.native.walking)

    def test_only_declared_topic_and_stop_operations_are_sent(self) -> None:
        driver = self.driver()
        driver.call(VELOCITY, VELOCITY_INPUT)
        driver.call(POSE, POSE_INPUT)
        driver.call(STOP, {})
        driver.call(CLIP, CLIP_INPUT)
        messages = list(driver.native.sent)
        self.assertTrue(messages)
        self.assertEqual([message["op"] for message in messages],
                         ["advertise", "publish", "advertise", "publish", "call_service", "call_service"])
        self.assertEqual(messages[1]["topic"], "/cmd_vel")
        self.assertEqual(messages[3]["topic"], "/cmd_pose")
        self.assertEqual(messages[4]["service"], "/stop_walk_srv")
        self.assertEqual(messages[5]["service"], "/clip_footstep_srv")


if __name__ == "__main__":
    unittest.main()
