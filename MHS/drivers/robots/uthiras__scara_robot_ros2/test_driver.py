"""Acceptance run of the SCARA/RRP ROS 2 package: the gate plus repository cases.

The cases exercise the pinned wire contract through the ROS-free fake: the
effort publication and its receipt, the joint-state and h_mat subscriptions,
the observational Fvel service, the source-backed limits, the companion-cited
stop (the Gazebo world pause confirmed by the E1 stall read-back of
get_model_list), its failure paths, a reset that leaves the world paused, that
the package offers no unpause, and the declaration itself.  Add cases, never
remove the ``check_driver`` call.
"""

import os
import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
EFFORT = "x-cap.uthiras.effort_command.v1"
JOINT_STATES = "x-cap.uthiras.joint_states.v1"
H_MAT = "x-cap.uthiras.forward_kinematics.v1"
FVEL = "x-cap.uthiras.forward_velocity.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        # The workspace LOCK.json does not list this package until the reviewed needed_by widening is applied.
        # MHS_DRIVER_GATE_COMPANIONS points at that view (the same variable the gate's G9 child receives).
        root = os.environ.get("MHS_DRIVER_GATE_COMPANIONS")
        options = {"companions_root": root} if root else {}
        report = check_driver(HERE, backend="fake", **options)
        self.assertEqual(report["failed"], [], report)


class ScaraRobotCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self, site_limits=None, **switches):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        for name, value in switches.items():
            setattr(driver.native, name, value)
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    @staticmethod
    def publications(driver):
        return [message for message in driver.native.sent
                if message.get("op") == "publish"
                and message.get("topic") == "/forward_effort_controller/commands"]

    @staticmethod
    def services(native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    def test_effort_publication_maps_three_values_and_reports_what_it_sent(self):
        driver = self.driver()
        receipt = driver.call(EFFORT, {"efforts": [1.5, -2.5, 3.5]})
        self.assertEqual(receipt, {"published": True, "confirmed": False, "sent_efforts": [1.5, -2.5, 3.5]})
        advertise = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(advertise[-1]["topic"], "/forward_effort_controller/commands")
        self.assertEqual(advertise[-1]["type"], "std_msgs/msg/Float64MultiArray")
        self.assertEqual(self.publications(driver)[-1]["msg"]["data"], [1.5, -2.5, 3.5])
        self.assertEqual(driver.native.published_efforts[-1], [1.5, -2.5, 3.5])

    def test_joint_state_subscription_returns_a_fresh_sample(self):
        driver = self.driver()
        receipt = driver.call(JOINT_STATES, {})
        self.assertEqual(receipt["names"], ["joint1", "joint2", "joint3"])
        self.assertEqual(receipt["positions"], [0.0, 0.0, 0.0])
        self.assertEqual(receipt["velocities"], [0.0, 0.0, 0.0])
        subscriptions = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual(subscriptions[-1]["topic"], "/joint_states")
        self.assertEqual(subscriptions[-1]["type"], "sensor_msgs/msg/JointState")

    def test_h_mat_subscription_returns_the_fk_string(self):
        driver = self.driver()
        receipt = driver.call(H_MAT, {})
        self.assertIn("homogeneous_matrix", receipt)
        self.assertEqual(receipt["homogeneous_matrix"], driver.native.homogeneous_matrix)
        subscriptions = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual(subscriptions[-1]["topic"], "/h_mat")
        self.assertEqual(subscriptions[-1]["type"], "std_msgs/msg/String")

    def test_forward_velocity_service_maps_inputs_and_outputs(self):
        driver = self.driver()
        receipt = driver.call(FVEL, {"joint1_vel": 1.0, "joint2_vel": 0.5, "joint3_vel": -0.25})
        self.assertEqual(receipt, {"endeff_vel_x": 0.0, "endeff_vel_y": 0.0, "endeff_vel_z": 0.0})
        calls = [message for message in driver.native.sent if message.get("op") == "call_service"]
        self.assertEqual(calls[-1]["service"], "/Forward_Velocity_Kinematics")
        self.assertEqual(calls[-1]["type"], "ikinterface/srv/Fvel")
        self.assertEqual(calls[-1]["args"],
                         {"joint1_vel": 1.0, "joint2_vel": 0.5, "joint3_vel": -0.25})

    def test_a_source_backed_effort_above_the_interface_is_refused_before_publication(self):
        driver, client = self.serve()
        refused = client.invoke(EFFORT, {"efforts": [101.0, 0.0, 0.0]}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.publications(driver), [])

    def test_a_source_backed_fvel_input_above_the_velocity_interface_is_refused(self):
        driver, client = self.serve()
        refused = client.invoke(FVEL, {"joint1_vel": 11.0, "joint2_vel": 0.0, "joint3_vel": 0.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        calls = [message for message in driver.native.sent if message.get("op") == "call_service"]
        self.assertEqual(calls, [])

    def test_the_main_resource_reads_no_topic(self):
        driver = self.driver()
        self.assertEqual(driver.read("main"), {})
        self.assertEqual([message for message in driver.native.sent if message.get("op") == "subscribe"], [])

    def test_a_failed_service_response_is_not_reported_as_read(self):
        driver = self.driver()
        driver.native.fail_service = True
        with self.assertRaises(MHSError) as caught:
            driver.call(FVEL, {"joint1_vel": 0.0, "joint2_vel": 0.0, "joint3_vel": 0.0})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_a_malformed_service_response_is_not_silently_accepted(self):
        driver = self.driver()
        driver.native.malformed_service = True
        with self.assertRaises(MHSError) as caught:
            driver.call(FVEL, {"joint1_vel": 0.0, "joint2_vel": 0.0, "joint3_vel": 0.0})
        self.assertIn(caught.exception.code,
                      {"MHS.CAPABILITY.OUTPUT_INVALID", "MHS.ADAPTER.SHIM_FAILED",
                       "MHS.OUTCOME.UNKNOWN"})

    def test_a_silent_topic_subscription_times_out(self):
        driver = self.driver()
        driver.native.silent_topics = True
        with self.assertRaises(MHSError) as caught:
            driver.call(JOINT_STATES, {})
        self.assertIn(caught.exception.code, {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_a_rejected_publication_is_not_reported_completed(self):
        driver = self.driver()
        driver.native.reject_publish = True
        with self.assertRaises(MHSError) as caught:
            driver.call(EFFORT, {"efforts": [0.0, 0.0, 0.0]})
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.UNKNOWN")

    def test_the_e_stop_pauses_and_confirms_a_frozen_sim_time(self):
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.services(driver.native), ["/pause_physics", "/get_model_list", "/get_model_list"])
        refused = client.invoke(EFFORT, {"efforts": [0.0, 0.0, 0.0]}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.publications(driver), [])

    def test_a_running_world_or_a_failed_call_leaves_the_e_stop_unconfirmed_and_latched(self):
        for switch in ("ignore_pause", "fail_pause", "fail_model_list"):
            with self.subTest(switch=switch):
                _driver, client = self.serve(**{switch: True})
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
                self.assertTrue(receipt["output"]["latched"], receipt)

    def test_the_sim_time_advances_while_the_world_runs(self):
        driver = self.driver()
        first = driver.native._respond({"op": "call_service", "service": "/get_model_list", "id": "a"})
        second = driver.native._respond({"op": "call_service", "service": "/get_model_list", "id": "b"})
        self.assertNotEqual(first["values"]["header"]["stamp"], second["values"]["header"]["stamp"])

    def test_the_reset_keeps_the_world_paused_and_offers_no_unpause(self):
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        receipt = client.invoke(EFFORT, {"efforts": [0.0, 0.0, 0.0]}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)  # latch released; the world stays paused
        self.assertNotIn("/unpause_physics", self.services(driver.native))
        self.assertIsNone(driver._model.reenable)
        with self.assertRaises(MHSError):
            driver.call(JOINT_STATES, {})  # the gzserver joint_state_broadcaster is silent while paused
        self.assertEqual(driver.read("main"), {})  # the resource reads no topic

    def test_a_joint_state_sample_while_paused_is_not_a_stopped_state(self):
        # The launch's standalone ros2_control_node may publish /joint_states on the system clock (not settled by
        # the source): a sample can still arrive while the world is paused, and it says nothing about the stop.
        driver, client = self.serve(wall_clock_joint_states=True)
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.call(JOINT_STATES, {})["names"], ["joint1", "joint2", "joint3"])

    def test_declaration_is_a_simulated_ros2_arm_with_the_companion_stop(self):
        driver = self.driver()
        self.assertEqual(type(driver).ros_version, 2)
        self.assertEqual(type(driver).mode, "simulated")
        self.assertEqual(type(driver).risk, "R2")
        self.assertEqual(type(driver).device_kind, "robot.arm")
        self.assertEqual(type(driver).backends, {"fake": ".fake:FakeScaraRobotRos2"})
        self.assertEqual(type(driver).fidelity["fidelity_level"], "F0")
        self.assertEqual(type(driver).estop_latency_ms, 1500)
        self.assertEqual(sorted(type(driver).safety_bindings), ["estop", "safe_state"])
        self.assertEqual(type(driver).safety_bindings["estop"]["service"], "/pause_physics")
        self.assertEqual(type(driver).safety_bindings["safe_state"]["stall"]["samples"], 2)
        self.assertIn("confirmation window", type(driver).safe_state)
        self.assertIn("cached confirmation", type(driver).safe_state)
        self.assertIn("No unpause is offered", type(driver).safe_state)

    def test_safety_status_returns_the_cached_confirmation_after_an_external_resume(self):
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        before = len(driver.native.sent)
        driver.native.paused = False
        driver.native.sim_ns += 1_000_000
        status = client.safety_status(self.ids["device_id"])
        self.assertTrue(status["estop"]["confirmed"], status)
        self.assertEqual(driver.native.sent[before:], [])
        self.assertFalse(driver.native.paused)


if __name__ == "__main__":
    unittest.main()
