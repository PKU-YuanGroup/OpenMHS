"""Acceptance run of the MultiWii ROS 2 package: the stock gate plus repository cases.

The fake is a ROS-free F0 recording transport.  These cases exercise the
declared topic surface, the operator-required RC channel envelope, the
transmission-only publication receipts and the stock e-stop path that has no
acknowledged stop to call.  No ROS graph, flight controller or hardware is
contacted.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import OutcomeUnknown
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
STATE = "x-cap.christianrauch.flight_state.v1"
RC_INPUT = "x-cap.christianrauch.rc_input.v1"
MOTORS = "x-cap.christianrauch.motor_outputs.v1"
ATTITUDE = "x-cap.christianrauch.attitude.v1"
ALTITUDE = "x-cap.christianrauch.altitude.v1"
IMU = "x-cap.christianrauch.imu.v1"
RC_OVERRIDE = "x-cap.christianrauch.rc_override.v1"
RC_OVERRIDE_RAW = "x-cap.christianrauch.rc_override_raw.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"

CHANNELS = [1500, 1500, 1500, 1000, 1000, 1000, 1000, 1000]  # placeholder test input
RAW_CHANNELS = [1500, 1500, 1000, 1000]                     # placeholder test input


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        # The pinned node has no acknowledged stop.  Keep running the full
        # stock gate and require its specific safety refusal rather than a
        # silently weakened package.
        self.assertEqual(report["failed"], ["G3"], report)
        codes = {finding["code"] for gate in report["gates"] for finding in gate["findings"]}
        self.assertIn("G3.STRICT", codes)
        self.assertIn("G3.NO_ESTOP", codes)
        self.assertNotIn("G3.NO_SAFE_STATE", codes)
        strict = [finding for gate in report["gates"] for finding in gate["findings"]
                  if finding["code"] == "G3.STRICT"]
        self.assertTrue(any("SAFE-045" in finding["message"] for finding in strict), strict)


class TopicCases(unittest.TestCase):
    def serve(self, *, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
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

    def test_observation_topics_return_the_fake_samples(self) -> None:
        client = self.serve()
        state = client.invoke(STATE, {}, **self.ids)
        self.assertEqual(state["status"], "completed", state)
        self.assertIs(state["output"]["armed"], False)
        rc_input = client.invoke(RC_INPUT, {}, **self.ids)
        self.assertEqual(rc_input["status"], "completed", rc_input)
        self.assertEqual(rc_input["output"]["channels"], [1500, 1500, 1500, 1000, 1000, 1000, 1000, 1000])
        motors = client.invoke(MOTORS, {}, **self.ids)
        self.assertEqual(motors["status"], "completed", motors)
        self.assertEqual(motors["output"]["channels"], [1000, 1000, 1000, 1000])
        attitude = client.invoke(ATTITUDE, {}, **self.ids)
        self.assertEqual(attitude["status"], "completed", attitude)
        self.assertEqual(attitude["output"]["orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        altitude = client.invoke(ALTITUDE, {}, **self.ids)
        self.assertEqual(altitude["status"], "completed", altitude)
        self.assertEqual(altitude["output"]["altitude_m"], 0.0)
        imu = client.invoke(IMU, {}, **self.ids)
        self.assertEqual(imu["status"], "completed", imu)
        self.assertEqual(imu["output"]["linear_acceleration"], {"x": 0.0, "y": 0.0, "z": 9.80665})
        self.assertEqual(imu["output"]["angular_velocity"], {"x": 0.0, "y": 0.0, "z": 0.0})

    def test_rc_override_is_refused_without_the_operator_overlay(self) -> None:
        client = self.serve()
        receipt = client.invoke(RC_OVERRIDE, {"channels": CHANNELS}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_rc_override_completes_inside_the_example_overlay(self) -> None:
        client = self.serve(site_limits=HERE / "site-limits.example.json")
        receipt = client.invoke(RC_OVERRIDE, {"channels": CHANNELS}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})
        # A publication does not change the armed observation: transmission is
        # not acknowledgement of a flight-controller state transition.
        state = client.read("main", **self.ids)
        self.assertIs(state["state"]["armed"], False)

    def test_short_channel_vector_is_rejected_by_the_schema(self) -> None:
        client = self.serve(site_limits=HERE / "site-limits.example.json")
        receipt = client.invoke(RC_OVERRIDE, {"channels": CHANNELS[:7]}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertNotIn("published", receipt.get("output") or {})

    def test_publication_reaches_the_declared_topic(self) -> None:
        driver = self.driver()
        output = driver.call(RC_OVERRIDE, {"channels": CHANNELS})
        self.assertEqual(output, {"published": True, "confirmed": False})
        self.assertEqual(driver.native.last_aert_channels, CHANNELS)
        publishes = [message for message in driver.native.sent if message.get("op") == "publish"]
        self.assertEqual(len(publishes), 1)
        self.assertEqual(publishes[0]["topic"], "/rc/override")
        self.assertEqual(publishes[0]["msg"]["channels"], CHANNELS)
        self.assertEqual(publishes[0]["msg"]["header"]["stamp"], {"sec": 0, "nanosec": 0})
        advertises = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(len(advertises), 1)
        self.assertEqual(advertises[0]["type"], "mavros_msgs/msg/OverrideRCIn")

    def test_raw_publication_preserves_the_vector_length(self) -> None:
        driver = self.driver()
        output = driver.call(RC_OVERRIDE_RAW, {"channels": RAW_CHANNELS})
        self.assertEqual(output, {"published": True, "confirmed": False})
        self.assertEqual(driver.native.last_raw_channels, RAW_CHANNELS)
        publishes = [message for message in driver.native.sent if message.get("op") == "publish"]
        self.assertEqual(len(publishes), 1)
        self.assertEqual(publishes[0]["topic"], "/rc/override/raw")
        self.assertEqual(publishes[0]["msg"]["channels"], RAW_CHANNELS)

    def test_a_broken_publication_link_is_unknown(self) -> None:
        driver = self.driver()
        driver.native.fail_publish = True
        with self.assertRaises(OutcomeUnknown) as caught:
            driver.call(RC_OVERRIDE, {"channels": CHANNELS})
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(driver.native.override_publishes, 0)

    def test_a_silent_topic_does_not_return_a_stale_value(self) -> None:
        driver = self.driver()
        driver.native.silent_topics.add("/state")
        with self.assertRaises(Exception) as caught:
            driver.call(STATE, {})
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_an_unrelated_event_id_does_not_satisfy_the_read(self) -> None:
        driver = self.driver()
        driver.native.wrong_id_topics.add("/state")
        with self.assertRaises(Exception) as caught:
            driver.call(STATE, {})
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_the_stock_estop_latches_without_claiming_a_stop(self) -> None:
        client = self.serve(site_limits=HERE / "site-limits.example.json")
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["output"]["estop"], "software_only", receipt)
        self.assertIs(receipt["output"]["safe_state_achieved"], False, receipt)
        refused = client.invoke(RC_OVERRIDE, {"channels": CHANNELS}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        # Observations remain available (the latch exempts reads).
        state = client.read("main", **self.ids)
        self.assertIs(state["state"]["armed"], False)


if __name__ == "__main__":
    unittest.main()
