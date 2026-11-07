"""Acceptance run of the Sphero ROS 2 package: the gate plus repository-specific cases.

The cases exercise the pinned topic contract through the ROS-free fake: the
subscriptions and their message shapes, each publication and its mapped
fields, the operator-required envelope, and the explicit absence of an
acknowledged ROS stop.  Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SpheroRos2Cases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    @staticmethod
    def publishes(driver, topic):
        return [message for message in driver.native.sent
                if message.get("op") == "publish" and message.get("topic") == topic]

    def test_reads_subscribe_to_the_pinned_topics_and_return_their_shapes(self):
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["odom_pose"]["position"],
                         {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(state["odom_pose"]["orientation"],
                         {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        self.assertEqual(state["odom_twist"]["linear"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(state["imu_orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        self.assertEqual(state["imu_linear_acceleration"], {"x": 0.0, "y": 0.0, "z": 9.8})
        self.assertEqual(state["collision"]["speed"], 0)
        self.assertEqual(state["battery_status"], "Battery OK")
        subscriptions = [message["topic"] for message in driver.native.sent
                         if message.get("op") == "subscribe"]
        for topic in ("/odom", "/imu", "/collision", "/diagnostics"):
            self.assertIn(topic, subscriptions)
        self.assertNotIn("/cmd_vel", subscriptions)

    def test_cmd_vel_publication_maps_only_the_two_consumed_twist_axes(self):
        driver = self.driver()
        receipt = driver.call("x-cap.athackst.cmd_vel.v1", {"linear_x": 4.0, "linear_y": 2.0})
        self.assertEqual(receipt, {"published": True, "confirmed": False})
        advertised = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(advertised[-1]["topic"], "/cmd_vel")
        self.assertEqual(advertised[-1]["type"], "geometry_msgs/msg/Twist")
        message = self.publishes(driver, "/cmd_vel")[-1]
        self.assertEqual(message["msg"]["linear"], {"x": 4.0, "y": 2.0, "z": 0.0})
        self.assertEqual(message["msg"]["angular"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(driver.read("main", ["odom_twist"])["odom_twist"]["linear"],
                         {"x": 4.0, "y": 2.0, "z": 0.0})

    def test_led_and_heading_publications_use_their_declared_types(self):
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.athackst.set_color.v1",
                                     {"red": 0.1, "green": 0.2, "blue": 0.3}),
                         {"published": True, "confirmed": False})
        color = self.publishes(driver, "/set_color")[-1]
        self.assertEqual((color["msg"]["r"], color["msg"]["g"], color["msg"]["b"]),
                         (0.1, 0.2, 0.3))

        self.assertEqual(driver.call("x-cap.athackst.set_back_led.v1", {"brightness": 42}),
                         {"published": True, "confirmed": False})
        self.assertEqual(self.publishes(driver, "/set_back_led")[-1]["msg"], {"data": 42.0})

        self.assertEqual(driver.call("x-cap.athackst.disable_stabilization.v1", {"disabled": True}),
                         {"published": True, "confirmed": False})
        self.assertEqual(self.publishes(driver, "/disable_stabilization")[-1]["msg"], {"data": True})

        self.assertEqual(driver.call("x-cap.athackst.set_heading.v1", {"heading_rad": 1.0}),
                         {"published": True, "confirmed": False})
        self.assertEqual(self.publishes(driver, "/set_heading")[-1]["msg"], {"data": 1.0})

        self.assertEqual(driver.call("x-cap.athackst.set_angular_velocity.v1",
                                     {"angular_velocity_rad": 2.0}),
                         {"published": True, "confirmed": False})
        self.assertEqual(self.publishes(driver, "/set_angular_velocity")[-1]["msg"], {"data": 2.0})

    def test_stop_is_an_ordinary_zero_publication_not_a_safe_state(self):
        driver = self.driver()
        receipt = driver.call("x-cap.athackst.stop.v1", {})
        self.assertEqual(receipt, {"published": True, "confirmed": False})
        message = self.publishes(driver, "/cmd_vel")[-1]
        self.assertEqual(message["msg"]["linear"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(message["msg"]["angular"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(dict(type(driver).safety_bindings), {})
        self.assertIsNone(type(driver).estop_physical_ref)

    def test_operator_required_inputs_refuse_without_an_overlay(self):
        client = self.serve()
        receipt = client.invoke("x-cap.athackst.cmd_vel.v1",
                                {"linear_x": 1.0, "linear_y": 0.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)
        receipt = client.invoke("x-cap.athackst.set_color.v1",
                                {"red": 0.1, "green": 0.2, "blue": 0.3}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_example_overlay_narrows_the_operator_inputs(self):
        client = self.serve(HERE / "site-limits.example.json")
        ok = client.invoke("x-cap.athackst.cmd_vel.v1",
                           {"linear_x": 10.0, "linear_y": 0.0}, **self.ids)
        self.assertEqual(ok["status"], "completed", ok)
        denied = client.invoke("x-cap.athackst.cmd_vel.v1",
                               {"linear_x": 101.0, "linear_y": 0.0}, **self.ids)
        self.assertEqual(denied["status"], "rejected", denied)
        self.assertEqual(denied["error"]["mhs_code"], ENVELOPE)
        denied = client.invoke("x-cap.athackst.set_color.v1",
                               {"red": 1.5, "green": 0.2, "blue": 0.3}, **self.ids)
        self.assertEqual(denied["status"], "rejected", denied)
        self.assertEqual(denied["error"]["mhs_code"], ENVELOPE)

    def test_sourced_back_led_bound_is_enforced(self):
        client = self.serve()
        ok = client.invoke("x-cap.athackst.set_back_led.v1", {"brightness": 100}, **self.ids)
        self.assertEqual(ok["status"], "completed", ok)
        denied = client.invoke("x-cap.athackst.set_back_led.v1", {"brightness": 256}, **self.ids)
        self.assertEqual(denied["status"], "rejected", denied)
        self.assertEqual(denied["error"]["mhs_code"], ENVELOPE)

    def test_malformed_observation_is_not_silently_accepted(self):
        driver = self.driver()
        driver.native.malformed_odom = True
        with self.assertRaises(MHSError) as caught:
            driver.read("main")
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")

    def test_declaration_is_ros2_hardware_r2_and_has_no_stop_binding(self):
        self.assertEqual(type(self.driver()).ros_version, 2)
        self.assertEqual(type(self.driver()).mode, "hardware")
        self.assertEqual(type(self.driver()).risk, "R2")
        self.assertEqual(type(self.driver()).backends, {"fake": ".fake:FakeSpheroRos2"})
        self.assertEqual(dict(type(self.driver()).safety_bindings), {})


if __name__ == "__main__":
    unittest.main()
