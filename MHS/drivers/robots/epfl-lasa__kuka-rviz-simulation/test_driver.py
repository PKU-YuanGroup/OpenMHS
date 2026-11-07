"""Acceptance and package-specific cases for the KUKA LWR simulation fake.

Add cases, never remove the check_driver call.  The zero-velocity publication is
not a stop by itself (SAFE-049): the e-stop is achieved only on fresh stamped
/r_arm_vel/state samples whose applied desired velocities and measured joint
velocities are inside the operator bounds.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
JOINT_STATES = "x-cap.epfl-lasa.joint_states.v1"
JOINT_VELOCITY = "x-cap.epfl-lasa.joint_velocity.v1"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
OVERLAY = HERE / "site-limits.example.json"
ZEROS = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

VELOCITIES = [0.1, 0.0, -0.1, 0.0, 0.0, 0.0, 0.0]  # placeholder test input


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class KukaRvizSimulationCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def direct(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    @staticmethod
    def example_overlay():
        return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))

    def test_the_joint_state_observation_returns_the_publisher_arrays(self) -> None:
        driver = self.direct()
        output = driver.call(JOINT_STATES, {})
        sample = output["joint_state"]
        self.assertEqual(set(sample["header"]), {"seq", "stamp", "frame_id"})
        self.assertEqual(set(sample["header"]["stamp"]), {"secs", "nsecs"})
        self.assertEqual(sample["name"], [f"right_arm_{number}_joint" for number in range(7)])
        self.assertEqual(len(sample["position"]), 7)
        self.assertEqual(len(sample["velocity"]), 7)
        self.assertEqual(len(sample["effort"]), 7)

    def test_a_velocity_publication_reaches_the_fake_topic(self) -> None:
        driver = self.direct()
        output = driver.call(JOINT_VELOCITY, {"joint_velocities": list(VELOCITIES)})
        self.assertEqual(output, {"published": True, "confirmed": False})
        self.assertEqual(driver.native.commanded_velocities, VELOCITIES)

    def test_a_velocity_is_refused_until_an_operator_envelope_exists(self) -> None:
        client = self.serve()
        receipt = client.invoke(JOINT_VELOCITY, {"joint_velocities": list(VELOCITIES)}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_the_example_overlay_admits_and_bounds_the_velocity_array(self) -> None:
        client = self.serve(site_limits=self.example_overlay())
        receipt = client.invoke(JOINT_VELOCITY, {"joint_velocities": list(VELOCITIES)}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        rejected = client.invoke(JOINT_VELOCITY,
                                 {"joint_velocities": [0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
                                 **self.ids)
        self.assertEqual(rejected["status"], "rejected", rejected)
        self.assertEqual(rejected["error"]["mhs_code"], ENVELOPE)

    def test_a_missing_joint_state_sample_is_a_failure_not_a_hold(self) -> None:
        driver = self.direct()
        driver.native.silent_joint_states = True
        with self.assertRaises(Exception) as caught:  # noqa: BLE001 - the bridge reports a bounded read failure
            driver.call(JOINT_STATES, {})
        code = getattr(caught.exception, "code", "")
        self.assertIn(code, {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_a_joint_state_reply_without_position_is_not_completed_with_invented_data(self) -> None:
        driver = self.direct()
        driver.native.omit_joint_state_position = True
        output = driver.call(JOINT_STATES, {})
        self.assertNotIn("position", output["joint_state"])

    def test_the_declaration_is_a_sensed_stop_without_a_safe_state_action(self) -> None:
        cls = type(self.direct())
        self.assertEqual(set(cls.safety_bindings), {"sensed_stop"})
        self.assertFalse(any(action.safe_state for action in cls.actions.values()))
        stop = cls.safety_bindings["sensed_stop"]
        self.assertNotIn("history", stop["sources"]["arm_state"])
        self.assertEqual(stop["request"][0]["message"]["velocity"], ZEROS)
        self.assertEqual(stop["consecutive"], 2)
        self.assertEqual(cls.estop_latency_ms, 1300)


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


class SensedStopCases(unittest.TestCase):
    """SAFE-049: the zero publication proves nothing; only fresh /r_arm_vel/state samples achieve the stop."""

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
        self.assertTrue(receipt["output"]["latched"])

    def test_the_estop_is_confirmed_by_fresh_controller_state_samples(self) -> None:
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        sensed = receipt["x-vendor"]["sensed_confirmation"]
        self.assertEqual([(step["native"], step["outcome"]) for step in sensed["request"]],
                         [("/r_arm_vel/command", "published")])
        self.assertEqual(driver.native.commanded_velocities, ZEROS)
        refused = client.invoke(JOINT_VELOCITY, {"joint_velocities": list(VELOCITIES)}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_reset_reconfirms_without_a_further_publication(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        sent = len(driver.native.sent)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertFalse(reset["output"]["resumed"])
        later = driver.native.sent[sent:]
        self.assertFalse([message for message in later if message.get("op") == "publish"])

    def test_a_reset_is_refused_while_another_publisher_commands_the_arm(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        driver.native.competing_command = True
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED", reset)

    def test_a_competing_publisher_keeps_the_stop_unconfirmed(self) -> None:
        driver, client = self.serve()
        driver.native.competing_command = True
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "not_confirmed")
        self.assertEqual(driver.native.commanded_velocities, ZEROS)
        self.assertEqual(details(receipt)["sensed"]["sources"]["arm_state"]["last_reset"], "term")

    def test_a_zero_desired_velocity_with_unsettled_actual_velocity_is_not_confirmed(self) -> None:
        driver, client = self.serve()
        driver.native.unsettled_actual = True
        receipt = client.estop("test", **self.ids)
        self.assert_unreached(receipt, "not_confirmed")
        self.assertEqual(details(receipt)["sensed"]["sources"]["arm_state"]["last_reset"], "term")

    def test_silent_controller_state_is_sensed_missing(self) -> None:
        driver, client = self.serve()
        driver.native.silent_arm_state = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_missing")

    def test_a_repeated_producer_stamp_is_stale(self) -> None:
        driver, client = self.serve()
        driver.native.frozen_stamps = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_stale")

    def test_a_null_measured_velocity_is_invalid(self) -> None:
        driver, client = self.serve()
        driver.native.null_actual_velocity = True
        self.assert_unreached(client.estop("test", **self.ids), "sensed_invalid")


if __name__ == "__main__":
    unittest.main()
