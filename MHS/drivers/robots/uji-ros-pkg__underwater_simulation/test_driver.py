"""Acceptance run of the UWSim package: the gate plus repository-specific cases.

The cases exercise the pinned topic contract through the ROS-free fake: the
twist publication and its six operator-required inputs, the joint-state and
range observations, malformed and silent replies, and the missing acknowledged
stop.  Add cases, never remove the ``check_driver`` call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
TWIST = "x-cap.uji-ros-pkg.vehicle_twist.v1"
JOINT_STATE = "x-cap.uji-ros-pkg.joint_state.v1"
RANGE = "x-cap.uji-ros-pkg.range.v1"


def example_overlay():
    return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UnderwaterSimulationCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self, *, overlay=True):
        server = load(HERE, backend="fake", site_limits=example_overlay() if overlay else None)
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

    def test_reads_subscribe_to_joint_state_and_range_and_return_their_shapes(self):
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["joint_names"], ["joint1", "joint2"])
        self.assertEqual(state["joint_positions"], [0.0, 0.0])
        self.assertEqual(state["range"], 0.0)
        subscriptions = [message["topic"] for message in driver.native.sent
                         if message.get("op") == "subscribe"]
        self.assertIn("/uwsim/joint_state", subscriptions)
        self.assertIn("/uwsim/g500/range", subscriptions)
        self.assertNotIn("/g500/twist", subscriptions)

    def test_twist_publication_maps_the_six_axes(self):
        driver = self.driver()
        receipt = driver.call(TWIST, {"linear_x": 0.2, "linear_y": -0.1, "linear_z": 0.05,
                                      "angular_x": 0.01, "angular_y": -0.02, "angular_z": 0.3})
        self.assertEqual(receipt, {"published": True, "confirmed": False})
        advertised = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(advertised[-1]["topic"], "/g500/twist")
        self.assertEqual(advertised[-1]["type"], "geometry_msgs/TwistStamped")
        message = self.publishes(driver, "/g500/twist")[-1]
        self.assertEqual(message["msg"]["twist"]["linear"],
                         {"x": 0.2, "y": -0.1, "z": 0.05})
        self.assertEqual(message["msg"]["twist"]["angular"],
                         {"x": 0.01, "y": -0.02, "z": 0.3})

    def test_joint_state_and_range_observations(self):
        driver = self.driver()
        joints = driver.call(JOINT_STATE, {})
        self.assertEqual(joints, {"names": ["joint1", "joint2"], "positions": [0.0, 0.0]})
        ranged = driver.call(RANGE, {})
        self.assertEqual(ranged, {"range": 0.0})
        subscriptions = {message["topic"] for message in driver.native.sent
                         if message.get("op") == "subscribe"}
        self.assertLessEqual({"/uwsim/joint_state", "/uwsim/g500/range"}, subscriptions)

    def test_the_operator_envelope_admits_and_refuses_both_signs(self):
        # The example overlay (-0.5..0.5 m/s, -1.0..1.0 rad/s) is operator data, not a source.
        client = self.serve()
        ok = client.invoke(TWIST, {"linear_x": 0.2, "linear_y": 0.0, "linear_z": 0.0,
                                   "angular_x": 0.0, "angular_y": 0.0, "angular_z": -0.4}, **self.ids)
        self.assertEqual(ok["status"], "completed", ok)
        for payload in (
            {"linear_x": 0.6, "linear_y": 0.0, "linear_z": 0.0,
             "angular_x": 0.0, "angular_y": 0.0, "angular_z": 0.0},
            {"linear_x": -0.6, "linear_y": 0.0, "linear_z": 0.0,
             "angular_x": 0.0, "angular_y": 0.0, "angular_z": 0.0},
            {"linear_x": 0.0, "linear_y": 0.0, "linear_z": 0.0,
             "angular_x": 0.0, "angular_y": 0.0, "angular_z": -1.1},
        ):
            denied = client.invoke(TWIST, payload, **self.ids)
            self.assertEqual(denied["status"], "rejected", (payload, denied))
            self.assertEqual(denied["error"]["mhs_code"], ENVELOPE, (payload, denied))

    def test_the_publication_is_refused_without_the_operator_overlay(self):
        client = self.serve(overlay=False)
        refused = client.invoke(TWIST, {"linear_x": 0.1, "linear_y": 0.0, "linear_z": 0.0,
                                        "angular_x": 0.0, "angular_y": 0.0, "angular_z": 0.0},
                                **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_clone_exposes_no_acknowledged_stop_binding(self):
        driver = self.driver()
        self.assertEqual(dict(type(driver).safety_bindings), {})
        self.assertIsNone(type(driver).estop_physical_ref)
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        refused = client.invoke(TWIST, {"linear_x": 0.1, "linear_y": 0.0, "linear_z": 0.0,
                                        "angular_x": 0.0, "angular_y": 0.0, "angular_z": 0.0},
                                **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_malformed_joint_state_is_not_silently_accepted(self):
        driver = self.driver()
        driver.native.malformed_joint_state = True
        with self.assertRaises(MHSError) as caught:
            driver.read("main", ["joint_names"])
        self.assertIn(caught.exception.code,
                      {"MHS.DEVICE.NOT_READY", "MHS.RESOURCE.STATE_INVALID"})

    def test_a_silent_range_topic_times_out(self):
        driver = self.driver()
        driver.native.silent_range = True
        with self.assertRaises(MHSError) as caught:
            driver.read("main", ["range"])
        self.assertIn(caught.exception.code,
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_declaration_is_a_simulated_ros1_world_without_a_stop(self):
        driver = self.driver()
        self.assertEqual(type(driver).ros_version, 1)
        self.assertEqual(type(driver).mode, "simulated")
        self.assertEqual(type(driver).risk, "R2")
        self.assertEqual(type(driver).device_kind, "world.sim")
        self.assertEqual(type(driver).backends, {"fake": ".fake:FakeUnderwaterSimulation"})
        self.assertEqual(type(driver).fidelity["fidelity_level"], "F0")


if __name__ == "__main__":
    unittest.main()
