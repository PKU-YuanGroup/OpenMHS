"""Acceptance run of the SPARC pick-and-place ROS 2 package: the gate plus cases.

The cases exercise the pinned wire contract through the ROS-free fake: the
/target_point publication, the /pick_place_status subscription, the per-element
operator envelope, the source-backed box values, the missing acknowledged stop
and the declaration itself.  Add cases, never remove ``check_driver``.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
TARGET = "x-cap.sahilrajpurkar03.target_point.v1"
STATUS = "x-cap.sahilrajpurkar03.pick_place_status.v1"
TARGET_TOPIC = "/target_point"
STATUS_TOPIC = "/pick_place_status"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"

_OVERLAY = {
    "openmhs": "0.9",
    "site": "test-only target envelope; not a device limit",
    "devices": {
        "mhs://localhost/nlp-pnp-robotic-arm": {
            TARGET: {
                "target_point[0]": {"min": -1.0, "max": 1.0, "source": "operator"},
                "target_point[1]": {"min": -1.0, "max": 1.0, "source": "operator"},
                "target_point[2]": {"min": -3.14, "max": 3.14, "source": "operator"},
            },
        },
    },
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SparcPickPlaceCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self, site_limits=None):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    @staticmethod
    def published(driver):
        return [message for message in driver.native.sent
                if message.get("op") == "publish" and message.get("topic") == TARGET_TOPIC]

    def test_target_point_publication_maps_the_four_values_in_data_order(self):
        driver = self.driver()
        receipt = driver.call(TARGET, {"target_point": [0.3, -0.1, 0.5, 1.0]})
        self.assertEqual(receipt, {"published": True, "confirmed": False})
        advertise = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(advertise[-1]["topic"], TARGET_TOPIC)
        self.assertEqual(advertise[-1]["type"], "std_msgs/msg/Float64MultiArray")
        self.assertEqual(self.published(driver)[-1]["msg"]["data"], [0.3, -0.1, 0.5, 1.0])

    def test_status_subscription_returns_a_fresh_string_sample(self):
        driver = self.driver()
        self.assertEqual(driver.call(STATUS, {}), {"status": "IDLE"})
        subscriptions = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual(subscriptions[-1]["topic"], STATUS_TOPIC)
        self.assertEqual(subscriptions[-1]["type"], "std_msgs/msg/String")
        self.assertEqual(driver.call(TARGET, {"target_point": [0.3, -0.1, 0.5, 1.0]}),
                         {"published": True, "confirmed": False})
        # The fake's ACTIVE after a publication is a placeholder echo, not proof of motion.
        self.assertEqual(driver.call(STATUS, {}), {"status": "ACTIVE"})

    def test_without_a_site_envelope_the_three_operator_bounds_are_unset(self):
        driver, client = self.serve()
        refused = client.invoke(TARGET, {"target_point": [0.3, -0.1, 0.5, 1.0]}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.published(driver), [])

    def test_a_source_backed_box_outside_one_or_two_is_refused_before_publication(self):
        driver, client = self.serve(_OVERLAY)
        refused = client.invoke(TARGET, {"target_point": [0.3, -0.1, 0.5, 3.0]}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.published(driver), [])

    def test_the_operator_envelope_admits_a_target_and_the_publication_is_only_transmission(self):
        driver, client = self.serve(_OVERLAY)
        receipt = client.invoke(TARGET, {"target_point": [0.3, -0.1, 0.5, 1.0]}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})
        self.assertEqual(self.published(driver)[-1]["msg"]["data"], [0.3, -0.1, 0.5, 1.0])

    def test_a_rejected_publication_is_not_reported_completed(self):
        driver = self.driver()
        driver.native.reject_publish = True
        with self.assertRaises(MHSError) as caught:
            driver.call(TARGET, {"target_point": [0.3, -0.1, 0.5, 1.0]})
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.UNKNOWN")
        # The attempted publish is in the wire transcript, but the fake did not accept it.
        self.assertEqual(driver.native.published_targets, [])

    def test_a_malformed_status_message_is_not_silently_accepted(self):
        driver = self.driver()
        driver.native.malformed_status = True
        with self.assertRaises(MHSError) as caught:
            driver.call(STATUS, {})
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.STATE_INVALID")

    def test_a_silent_status_subscription_times_out(self):
        driver = self.driver()
        driver.native.silent_status = True
        with self.assertRaises(MHSError) as caught:
            driver.call(STATUS, {})
        self.assertIn(caught.exception.code, {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_a_silent_target_topic_makes_the_resource_read_not_ready(self):
        # Model review (2026-11-05): only clients publish /target_point, so in a real graph the resource
        # subscription normally gets no sample: the publication still completes, the snapshot does not.
        driver, client = self.serve(site_limits=_OVERLAY)
        driver.native.silent_target = True
        receipt = client.invoke(TARGET, {"target_point": [0.3, -0.1, 0.5, 1.0]}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(len(self.published(driver)), 1)
        with self.assertRaises(MHSError) as caught:
            client.read("main", **self.ids)
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")

    def test_the_main_resource_state_tracks_the_command_and_status_topics(self):
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["status"], "IDLE")
        self.assertEqual(state["target_point"], [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(driver.call(TARGET, {"target_point": [0.3, -0.1, 0.5, 1.0]}),
                         {"published": True, "confirmed": False})
        state = driver.read("main")
        self.assertEqual(state["status"], "ACTIVE")
        self.assertEqual(state["target_point"], [0.3, -0.1, 0.5, 1.0])
        self.assertEqual(driver.call(TARGET, {"target_point": [0.35, 0.0, 0.6, 2.0]}),
                         {"published": True, "confirmed": False})
        self.assertEqual(driver.read("main")["target_point"], [0.35, 0.0, 0.6, 2.0])

    def test_the_clone_exposes_no_acknowledged_stop_binding(self):
        driver, client = self.serve()
        self.assertEqual(dict(type(driver).safety_bindings), {})
        self.assertIsNone(getattr(type(driver), "estop_physical_ref", None))
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        refused = client.invoke(TARGET, {"target_point": [0.3, -0.1, 0.5, 1.0]}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.published(driver), [])
        # An extension read is not a catalogue read class; the latch still applies.
        read = client.invoke(STATUS, {}, **self.ids)
        self.assertEqual(read["status"], "rejected", read)
        self.assertEqual(read["error"]["mhs_code"], ESTOP)

    def test_declaration_is_a_simulated_ros2_arm_without_a_stop(self):
        driver = self.driver()
        self.assertEqual(type(driver).ros_version, 2)
        self.assertEqual(type(driver).mode, "simulated")
        self.assertEqual(type(driver).risk, "R2")
        self.assertEqual(type(driver).device_kind, "robot.arm")
        self.assertEqual(type(driver).backends, {"fake": ".fake:FakeNlpPnpRoboticArm"})
        self.assertEqual(type(driver).fidelity["fidelity_level"], "F0")


if __name__ == "__main__":
    unittest.main()
