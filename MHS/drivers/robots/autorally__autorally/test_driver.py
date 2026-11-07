"""Acceptance run of the AutoRally simulation package: the gate plus local cases.

Add cases, never remove the check_driver call.  The e-stop is a sensed-confirmation
stop (SAFE-049, simulated only).  It publishes a zero speedCommand and a fixed
openmhs runstop, and it is achieved only on fresh stamped /wheelSpeeds samples.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
RESET_REFUSED = "MHS.SAFETY.RESET_REFUSED"
SPEED = "x-cap.autorally.speed_command.v1"
RELEASE = "x-cap.autorally.release_runstop.v1"
RUNSTOP = "x-cap.autorally.runstop.v1"
CHASSIS = "x-cap.autorally.chassis_state.v1"
WHEELS = "x-cap.autorally.wheel_speeds.v1"
OVERLAY = HERE / "site-limits.example.json"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AutoRallyCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake", site_limits=OVERLAY)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_chassis_state_observation_returns_the_selected_fields(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call(CHASSIS, {})
        self.assertEqual(
            set(output),
            {"runstop_motion_enabled", "autonomous_enabled", "steering", "throttle",
             "front_brake", "steering_commander", "throttle_commander",
             "front_brake_commander"},
        )
        self.assertIs(output["runstop_motion_enabled"], True)

    def test_the_wheel_speeds_observation_returns_all_four_wheels(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call(WHEELS, {})
        self.assertEqual(set(output), {"lf_speed", "rf_speed", "lb_speed", "rb_speed"})
        self.assertGreater(abs(output["lf_speed"]), 0.05)

    def test_the_speed_command_publication_reaches_the_native_topic(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call(SPEED, {"target_speed_mps": 1.25})
        self.assertEqual(output, {"published": True, "confirmed": False})
        self.assertEqual(driver.native.last_speed_command, {"data": 1.25})
        published = [message for message in driver.native.sent
                     if message.get("op") == "publish"
                     and message.get("topic") == "/constantSpeedController/speedCommand"]
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].get("msg"), {"data": 1.25})

    def test_the_free_sender_runstop_capability_is_gone(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        cls = type(driver)
        self.assertNotIn(RUNSTOP, cls.commands)
        self.assertNotIn(RUNSTOP, cls.actions)
        self.assertNotIn(RELEASE, cls.commands)
        self.assertNotIn(RELEASE, cls.actions)
        self.assertFalse(any(item.reenable for item in cls.actions.values()))
        self.assertEqual(set(cls.safety_bindings), {"sensed_stop"})
        request = cls.safety_bindings["sensed_stop"]["request"]
        self.assertEqual(request[0]["message"], {"data": 0.0})
        self.assertEqual(request[1]["message"], {"sender": "openmhs", "motionEnabled": False})
        self.assertFalse(any(item.safe_state for item in cls.actions.values()))

    def test_the_speed_command_is_refused_until_the_operator_supplies_a_bound(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke(SPEED, {"target_speed_mps": 1.25},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_latched_speed_command_is_refused_after_the_e_stop(self) -> None:
        client = self.serve()
        first = client.estop("test", **self.ids)
        self.assertEqual(first["status"], "completed", first)
        receipt = client.invoke(SPEED, {"target_speed_mps": 1.25}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ESTOP)

    def test_a_withheld_chassis_state_sample_is_an_observation_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.withhold_chassis_state = True
        with self.assertRaises(Exception):
            driver.read("main")

    def test_a_withheld_wheel_speeds_sample_is_an_observation_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.withhold_wheel_speeds = True
        with self.assertRaises(Exception) as caught:
            driver.call(WHEELS, {})
        self.assertIn("MHS.DEVICE.NOT_READY", str(caught.exception))


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


def publishes(messages):
    return [message for message in messages if message.get("op") == "publish"]


class SensedStopCases(unittest.TestCase):
    """SAFE-049: the two publications prove nothing; only fresh wheel speeds achieve the stop."""

    def serve(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=str(OVERLAY))
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

    def test_the_estop_is_confirmed_by_fresh_wheel_speeds(self) -> None:
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        sensed = receipt["x-vendor"]["sensed_confirmation"]
        self.assertEqual([(step["native"], step["outcome"]) for step in sensed["request"]],
                         [("/constantSpeedController/speedCommand", "published"),
                          ("/runstop", "published")])
        sent = publishes(driver.native.sent)
        self.assertEqual([message.get("topic") for message in sent[:2]],
                         ["/constantSpeedController/speedCommand", "/runstop"])
        self.assertEqual(sent[0].get("msg"), {"data": 0.0})
        self.assertEqual(sent[1].get("msg"), {"sender": "openmhs", "motionEnabled": False})
        self.assertEqual(driver.native.target_speed_mps, 0.0)
        self.assertFalse(driver.native.runstop_motion_enabled())
        refused = client.invoke(SPEED, {"target_speed_mps": 1.25}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_reset_reconfirms_without_a_request(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        sent = len(driver.native.sent)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertFalse(reset["output"]["resumed"])
        later = driver.native.sent[sent:]
        self.assertFalse([message for message in later if message.get("op") in ("publish", "call_service")])

    def test_a_reset_is_refused_while_another_publisher_keeps_the_wheels_fast(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        driver.native.competing_speed = True
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], RESET_REFUSED, reset)

    def test_a_competing_publisher_keeps_the_stop_unconfirmed(self) -> None:
        driver, client = self.serve()
        driver.native.competing_speed = True
        self.assert_unreached(client.estop("test", **self.ids), "not_confirmed")

    def test_silent_sources_are_sensed_missing(self) -> None:
        driver, client = self.serve()
        driver.native.silent = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_repeated_producer_stamp_is_stale(self) -> None:
        driver, client = self.serve()
        driver.native.frozen_stamps = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_stale")

    def test_a_null_wheel_speed_is_invalid(self) -> None:
        driver, client = self.serve()
        driver.native.null_lf = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_invalid")

    def test_a_joystick_false_sender_keeps_the_and_false(self) -> None:
        driver, client = self.serve()
        driver.native.runstops["joystick"] = False
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertFalse(driver.native.runstop_motion_enabled())
        state = client.invoke(CHASSIS, {}, **self.ids)
        self.assertEqual(state["status"], "completed", state)
        self.assertIs(state["output"]["runstop_motion_enabled"], False)
        self.assertNotIn(RELEASE, type(driver).commands)

    def test_a_speed_stored_while_the_runstop_holds_does_not_move_the_wheels(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        commanded = client.invoke(SPEED, {"target_speed_mps": 1.25}, **self.ids)
        self.assertEqual(commanded["status"], "completed", commanded)
        held = client.invoke(WHEELS, {}, **self.ids)
        self.assertEqual(held["status"], "completed", held)
        self.assertLessEqual(abs(held["output"]["lf_speed"]), 0.05)
        self.assertEqual(driver.native.target_speed_mps, 1.25)
        self.assertFalse(driver.native.runstop_motion_enabled())
        self.assertNotIn(RELEASE, type(driver).commands)

    def test_a_lost_speed_zero_still_holds_and_mhs_has_no_reenable(self) -> None:
        driver, client = self.serve()
        driver.native.drop_speed_zero = True
        before = driver.native.target_speed_mps
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(driver.native.target_speed_mps, before)
        sent = publishes(driver.native.sent)
        self.assertEqual(sent[0].get("msg"), {"data": 0.0})
        self.assertEqual(sent[1].get("msg"), {"sender": "openmhs", "motionEnabled": False})
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        held = client.invoke(WHEELS, {}, **self.ids)
        self.assertEqual(held["status"], "completed", held)
        self.assertLessEqual(abs(held["output"]["lf_speed"]), 0.05)
        self.assertEqual(driver.native.target_speed_mps, before)
        self.assertFalse(driver.native.runstop_motion_enabled())
        self.assertNotIn(RELEASE, type(driver).commands)
        self.assertFalse(any(item.reenable for item in type(driver).actions.values()))

    def test_an_overwritten_speed_zero_stays_held_without_a_reenable(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(driver.native.target_speed_mps, 0.0)
        # README.md:170 documents a recurring speedCommand publisher. Another node restores its target.
        driver.native.target_speed_mps = 3.0
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        held = client.invoke(WHEELS, {}, **self.ids)
        self.assertEqual(held["status"], "completed", held)
        self.assertLessEqual(abs(held["output"]["lf_speed"]), 0.05)
        self.assertEqual(driver.native.target_speed_mps, 3.0)
        self.assertFalse(driver.native.runstop_motion_enabled())
        self.assertNotIn(RELEASE, type(driver).commands)
        # Enabling motion outside MHS would resume that retained target. This driver has no such command.
        driver.native.runstops["openmhs"] = True
        moving = client.invoke(WHEELS, {}, **self.ids)
        self.assertEqual(moving["status"], "completed", moving)
        self.assertGreater(abs(moving["output"]["lf_speed"]), 0.05)

    def test_wheels_that_are_already_still_still_confirm(self) -> None:
        driver, client = self.serve()
        driver.native.wheel_speed = 0.0
        driver.native.runstops["joystick"] = False
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"])


if __name__ == "__main__":
    unittest.main()
