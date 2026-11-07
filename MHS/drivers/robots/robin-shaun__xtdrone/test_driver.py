"""Acceptance cases for the XTDrone position bridge and its world-pause e-stop.

The stock harness call is kept. The extra cases exercise the declared
position-setpoint and target/pose wire shapes, the operator-required position
envelope, the pause confirmed by get_physics_properties, the three fail-closed
switches, a reset that leaves the world paused, and a safety_status poll that
keeps the cached confirmation after an external unpause. They contact no ROS graph,
simulator, MAVROS node or hardware.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))
TARGET = "x-cap.robin-shaun.target.v1"
POSITION = "x-cap.robin-shaun.position.v1"
SETPOINT = "x-cap.robin-shaun.setpoint_position.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"
UNPAUSE = "/gazebo/unpause_physics"
#: Values inside the example overlay; they are test data, not a device bound.
SAMPLE = {"x": 1.0, "y": 2.0, "z": 3.0}
LATER = {"x": 4.0, "y": 5.0, "z": 6.0}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class XtdroneTyphoonCases(unittest.TestCase):
    def serve(self, *, overlay=None):
        server = load(HERE, backend="fake", site_limits=overlay)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def served(self, **switches):
        driver = load_driver(HERE, "fake")
        for name, value in switches.items():
            setattr(driver.native, name, value)
        server = build_server(driver, site_limits=OVERLAY)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    @staticmethod
    def services(native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    def test_target_observation_returns_a_target_sample(self) -> None:
        client = self.serve()
        receipt = client.invoke(TARGET, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]), {"target_x", "target_y", "target_z"})

    def test_position_observation_returns_a_position_sample(self) -> None:
        client = self.serve()
        receipt = client.invoke(POSITION, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]), {"position_x", "position_y", "position_z"})

    def test_position_setpoint_is_transmission_only(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        result = driver.call(SETPOINT, dict(SAMPLE))
        self.assertEqual(result["published"], True)
        self.assertEqual(result["confirmed"], False)
        self.assertEqual(result["sent_x"], SAMPLE["x"])
        self.assertEqual(result["sent_y"], SAMPLE["y"])
        self.assertEqual(result["sent_z"], SAMPLE["z"])
        sends = [message for message in driver.native.sent
                 if message.get("op") == "publish" and message.get("topic")
                 == "/typhoon_h480_0/mavros/setpoint_position/local"]
        self.assertEqual(len(sends), 1, driver.native.sent)
        body = sends[0]["msg"]
        self.assertEqual(body["pose"]["position"], SAMPLE)
        self.assertEqual(driver.native.last_target, SAMPLE)
        self.assertEqual(driver.native.retained_setpoint, SAMPLE)

    def test_target_observation_reflects_the_published_setpoint(self) -> None:
        client = self.serve(overlay=OVERLAY)
        receipt = client.invoke(SETPOINT, dict(SAMPLE), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["sent_x"], 1.0)
        self.assertEqual(receipt["output"]["published"], True)
        self.assertEqual(receipt["output"]["confirmed"], False)
        target = client.invoke(TARGET, {}, **self.ids)
        self.assertEqual(target["status"], "completed", target)
        self.assertEqual(target["output"], {"target_x": 1.0, "target_y": 2.0, "target_z": 3.0})

    def test_operator_required_position_is_refused_without_overlay(self) -> None:
        client = self.serve()
        receipt = client.invoke(SETPOINT, dict(SAMPLE), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_example_overlay_admits_a_bounded_position_and_refuses_the_outside(self) -> None:
        client = self.serve(overlay=OVERLAY)
        inside = client.invoke(SETPOINT, dict(SAMPLE), **self.ids)
        self.assertEqual(inside["status"], "completed", inside)
        outside = client.invoke(SETPOINT, {"x": 11.0, "y": 2.0, "z": 3.0}, **self.ids)
        self.assertEqual(outside["status"], "rejected", outside)
        self.assertEqual(outside["error"]["mhs_code"], ENVELOPE)

    def test_the_e_stop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        driver, client = self.served()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        self.assertTrue(driver.native.paused)
        self.assertEqual(self.services(driver.native)[:2], [PAUSE, READBACK])

    def test_safety_status_keeps_the_cached_confirmation_after_an_external_unpause(self) -> None:
        driver, client = self.served()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        sent = len(driver.native.sent)
        driver.native.paused = False
        status = client.safety_status(self.ids["device_id"])
        self.assertTrue(status["estop"]["engaged"], status)
        self.assertTrue(status["estop"]["confirmed"], status)
        self.assertTrue(status["status"]["safe_state"]["achieved"], status)
        self.assertEqual(len(driver.native.sent), sent)
        self.assertNotIn(READBACK, self.services(driver.native)[2:])

    def test_a_failed_pause_or_read_back_leaves_the_e_stop_unconfirmed_and_latched(self) -> None:
        for switch in ("fail_pause", "fail_readback", "ignore_pause"):
            with self.subTest(switch=switch):
                _driver, client = self.served(**{switch: True})
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
                refused = client.invoke(SETPOINT, dict(SAMPLE), **self.ids)
                self.assertEqual(refused["status"], "rejected", refused)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_reset_keeps_the_world_paused_and_a_new_setpoint_is_not_observed(self) -> None:
        driver, client = self.served()
        first = client.invoke(SETPOINT, dict(SAMPLE), **self.ids)
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(driver.native.last_target, SAMPLE)
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        refused = client.invoke(SETPOINT, dict(LATER), **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        receipt = client.invoke(SETPOINT, dict(LATER), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["sent_x"], LATER["x"])
        self.assertEqual(receipt["output"]["sent_y"], LATER["y"])
        self.assertEqual(receipt["output"]["sent_z"], LATER["z"])
        self.assertEqual(driver.native.last_target, SAMPLE)
        self.assertEqual(driver.native.retained_setpoint, LATER)
        target = client.invoke(TARGET, {}, deadline_ms=500, **self.ids)
        self.assertIn(target["status"], {"failed", "unknown"}, target)
        pose = client.invoke(POSITION, {}, deadline_ms=500, **self.ids)
        self.assertIn(pose["status"], {"failed", "unknown"}, pose)
        self.assertNotIn(UNPAUSE, self.services(driver.native))

    def test_the_package_offers_no_unpause(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(set(type(driver).commands), {TARGET, POSITION, SETPOINT})
        self.assertIsNone(driver._model.reenable)
        self.assertEqual(set(type(driver).safety_bindings), {"estop", "safe_state"})
        services = {spec["service"] for spec in type(driver).safety_bindings.values()}
        self.assertEqual(services, {PAUSE, READBACK})

    def test_the_resource_reads_no_topic(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.read("vehicle"), {})
        self.assertEqual([message for message in driver.native.sent if message.get("op") == "subscribe"], [])
        driver.native.paused = True
        self.assertEqual(driver.read("vehicle"), {})

    def test_silent_target_topic_fails_the_observation(self) -> None:
        driver, client = self.served(silent_target=True)
        receipt = client.invoke(TARGET, {}, deadline_ms=500, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIsNone(receipt.get("output"))
        self.assertGreaterEqual(driver.native.target_calls, 1)

    def test_malformed_target_reply_fails_the_observation(self) -> None:
        _driver, client = self.served(malformed_target=True)
        receipt = client.invoke(TARGET, {}, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)

    def test_failed_setpoint_publication_does_not_report_completion(self) -> None:
        driver, client = self.served(fail_publish=True)
        receipt = client.invoke(SETPOINT, dict(SAMPLE), **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        publishes = [message for message in driver.native.sent
                     if message.get("op") == "publish"]
        self.assertEqual(publishes, [])


if __name__ == "__main__":
    unittest.main()
