"""Acceptance run of the FDCL-GWU UAV package: the gate plus cases for this simulator.

The cases exercise the pinned ROS 2 topic contract through the ROS-free fake:
the state and IMU observations, the /uav/mode publication, the input-free
motors-off publication, and the sensed-confirmation stop (SAFE-049, simulated
only).  The Bool false proves nothing; only fresh stamped /uav/gps poses that
are at or below the landed band and still achieve the e-stop.  Add cases,
never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.driver import DriverFailed
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
STATE = "x-cap.fdcl-gwu.state.v1"
IMU = "x-cap.fdcl-gwu.imu.v1"
MODE = "x-cap.fdcl-gwu.mode.v1"
MOTORS_OFF = "x-cap.fdcl-gwu.motors_off.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UavCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
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

    def test_the_state_observation_returns_the_five_native_fields(self) -> None:
        client = self.serve()
        receipt = client.invoke(STATE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(set(output),
                         {"position", "velocity", "acceleration", "attitude", "angular_velocity"})
        self.assertEqual(len(output["position"]), 3)
        self.assertEqual(len(output["attitude"]), 9)

    def test_the_imu_observation_returns_orientation_rates_and_acceleration(self) -> None:
        client = self.serve()
        receipt = client.invoke(IMU, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(set(output), {"orientation", "angular_velocity", "linear_acceleration"})
        self.assertEqual(set(output["orientation"]), {"x", "y", "z", "w"})

    def test_the_mode_publication_reaches_uav_mode_and_is_not_confirmed(self) -> None:
        driver, fake = self.direct()
        result = driver.call(MODE, {"mode": 2})
        self.assertTrue(result["published"])
        self.assertFalse(result["confirmed"])
        self.assertEqual(fake.last_mode, 2)
        self.assertEqual(fake.last_mode_message["x_offset"], [0.0, 0.0, 0.0])
        self.assertEqual(fake.last_mode_message["yaw_offset"], 0.0)
        self.assertIn({"op": "publish", "topic": "/uav/mode"},
                      [{key: message.get(key) for key in ("op", "topic")} for message in fake.sent])

    def test_motors_off_publishes_bool_false_with_no_input(self) -> None:
        driver, fake = self.direct()
        self.assertIs(fake.motors_on, True)
        result = driver.call(MOTORS_OFF, {})
        self.assertEqual(result, {"published": True, "confirmed": False})
        self.assertIs(fake.last_motors_on, False)
        published = [message for message in fake.sent
                     if message.get("op") == "publish" and message.get("topic") == "/uav/motors_on"]
        self.assertEqual(published[-1]["msg"], {"data": False})
        again = driver.call(MOTORS_OFF, {})
        self.assertEqual(again, {"published": True, "confirmed": False})
        self.assertIs(fake.last_motors_on, False)

    def test_mode_six_is_outside_the_six_dispatch_indices(self) -> None:
        client = self.serve()
        receipt = client.invoke(MODE, {"mode": 6}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_a_silent_state_topic_is_reported_as_a_failure(self) -> None:
        driver, fake = self.direct()
        fake.silent_state = True
        with self.assertRaises((DriverFailed, MHSError)) as caught:
            driver.call(STATE, {})
        self.assertIn(getattr(caught.exception, "code", None),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY", "MHS.CAPABILITY.OUTPUT_INVALID"})

    def test_a_malformed_state_message_is_reported_as_a_failure(self) -> None:
        driver, fake = self.direct()
        fake.malformed_state = True
        with self.assertRaises((DriverFailed, MHSError)) as caught:
            driver.call(STATE, {})
        self.assertIn(getattr(caught.exception, "code", None),
                      {"MHS.CAPABILITY.OUTPUT_INVALID", "MHS.ADAPTER.SHIM_FAILED",
                       "MHS.RESOURCE.STATE_INVALID", "MHS.DEVICE.NOT_READY"})

    def test_the_mode_publication_is_visible_in_the_resource_state(self) -> None:
        client = self.serve()
        before = client.read("main", **self.ids)
        self.assertEqual(before["state"]["mode"], 0)
        self.assertIs(before["state"]["motors_on"], True)
        receipt = client.invoke(MODE, {"mode": 2}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        after = client.read("main", **self.ids)
        self.assertEqual(after["state"]["mode"], 2)

    def test_the_stop_declares_no_motors_on_command_and_no_reenable(self) -> None:
        driver, _fake = self.direct()
        cls = type(driver)
        self.assertEqual(set(cls.safety_bindings), {"sensed_stop"})
        self.assertEqual({source["topic"] for source in cls.safety_bindings["sensed_stop"]["sources"].values()},
                         {"/uav/gps"})
        self.assertEqual(cls.safety_bindings["sensed_stop"]["request"][0]["message"], {"data": False})
        self.assertNotIn("x-cap.fdcl-gwu.motors_on.v1", cls.commands)
        self.assertIn(MOTORS_OFF, cls.commands)
        self.assertTrue(all(action.reenable is not True for action in cls.actions.values()))
        self.assertIsNone(cls.estop_terminal)
        self.assertEqual(cls.estop_latency_ms, 6000)
        self.assertEqual(cls.risk, "R2")
        self.assertEqual(cls.actions[MODE].risk, "R2")
        self.assertEqual(cls.actions[MOTORS_OFF].risk, "R2")


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


class SensedStopCases(unittest.TestCase):
    """SAFE-049: the Bool false proves nothing; only fresh stamped /uav/gps poses that are landed and still do."""

    def serve(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver)
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

    def test_the_estop_publishes_bool_false_and_is_confirmed_by_fresh_gps(self):
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        sensed = receipt["x-vendor"]["sensed_confirmation"]
        self.assertEqual(sensed["request"],
                         [{"native": "/uav/motors_on", "kind": "topic", "outcome": "published"}])
        published = [message for message in driver.native.sent
                     if message.get("op") == "publish" and message.get("topic") == "/uav/motors_on"]
        self.assertEqual(published[-1]["msg"], {"data": False})
        self.assertIs(driver.native.motors_on, False)
        self.assertLessEqual(driver.native.gps_z, 0.5)
        self.assertEqual(driver.native.gps_vx, 0.0)
        refused = client.invoke(MODE, {"mode": 2}, **self.ids)
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
        self.assertIs(driver.native.motors_on, False)

    def test_a_reset_is_refused_while_another_publisher_rearms_the_motors(self):
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        driver.native.competing_publisher = True
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED", reset)

    def test_a_competing_publisher_keeps_the_stop_unconfirmed(self):
        driver, client = self.serve()
        driver.native.competing_publisher = True
        self.assert_unreached(client.estop("test", **self.ids), "not_confirmed")

    def test_silent_gps_is_sensed_missing(self):
        driver, client = self.serve()
        driver.native.silent_gps = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_repeated_producer_stamp_is_stale(self):
        driver, client = self.serve()
        driver.native.frozen_stamps = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_stale")

    def test_a_null_position_field_is_invalid(self):
        driver, client = self.serve()
        driver.native.null_position = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_invalid")


if __name__ == "__main__":
    unittest.main()
