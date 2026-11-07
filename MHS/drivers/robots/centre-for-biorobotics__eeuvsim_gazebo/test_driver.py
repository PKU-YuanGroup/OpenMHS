"""Acceptance run of the eeUVsim UCAT package: the gate plus repository cases.

The cases exercise the pinned ROS 2 topic contract through the ROS-free fake:
the two observations, the four-flipper command, the operator-required envelope,
the reset publication, malformed state, and the sensed-confirmation stop.  Add
cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = HERE / "site-limits.example.json"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


def _fin_payload(amplitude=0.2):
    return {"flippers": [
        {"amplitude": amplitude, "frequency": 2.0, "zero_direction": 0.0, "phase_offset": 0.0},
        {"amplitude": amplitude, "frequency": 2.0, "zero_direction": 0.0, "phase_offset": 3.14159},
        {"amplitude": amplitude, "frequency": 2.0, "zero_direction": 0.0, "phase_offset": 0.0},
        {"amplitude": amplitude, "frequency": 2.0, "zero_direction": 0.0, "phase_offset": 3.14159},
    ]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class EeuvSimUcatCases(unittest.TestCase):
    def driver(self, *, overlay=True):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        if overlay:
            server = build_server(driver, site_limits=str(OVERLAY))
            self.addCleanup(close_server, server)
            return driver, server
        return driver, None

    @staticmethod
    def client(server):
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, {"device_id": device_id, "session_id": session}

    def test_state_observation_returns_entity_state_fields(self):
        driver, server = self.driver()
        self.assertIsNotNone(server)
        client, ids = self.client(server)
        receipt = client.invoke("x-cap.centre-for-biorobotics.auv_state.v1", {}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]), {"name", "pose", "twist", "reference_frame"})
        self.assertEqual(set(receipt["output"]["pose"]), {"position", "orientation"})
        self.assertEqual(set(receipt["output"]["twist"]), {"linear", "angular"})
        subscriptions = {message["topic"] for message in driver.native.sent
                         if message.get("op") == "subscribe"}
        self.assertIn("/ucat/state", subscriptions)
        self.assertNotIn("/hw/flippers_cmd", subscriptions)

    def test_fin_feedback_observation_returns_four_named_flippers(self):
        driver, server = self.driver()
        self.assertIsNotNone(server)
        client, ids = self.client(server)
        receipt = client.invoke("x-cap.centre-for-biorobotics.fin_feedback.v1", {}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]),
                         {"flipper_fr", "flipper_br", "flipper_bl", "flipper_fl"})
        for name in ("flipper_fr", "flipper_br", "flipper_bl", "flipper_fl"):
            self.assertEqual(set(receipt["output"][name]), {"angular_pos", "angular_vel", "angular_acc"})

    def test_fin_command_is_refused_without_the_operator_envelope(self):
        driver, server = self.driver(overlay=False)
        self.assertIsNone(server)
        server = build_server(driver, site_limits=None)
        self.addCleanup(close_server, server)
        client, ids = self.client(server)
        receipt = client.invoke("x-cap.centre-for-biorobotics.fin_oscillation.v1",
                                _fin_payload(), **ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)
        self.assertFalse([message for message in driver.native.sent if message.get("op") == "publish"])

    def test_fin_command_publishes_the_four_flipper_objects(self):
        driver, server = self.driver()
        client, ids = self.client(server)
        receipt = client.invoke("x-cap.centre-for-biorobotics.fin_oscillation.v1",
                                _fin_payload(amplitude=0.4), **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})
        self.assertEqual(len(driver.native.fin_commands), 1)
        flippers = driver.native.fin_commands[0]["flippers"]
        self.assertEqual(len(flippers), 4)
        self.assertEqual([item["amplitude"] for item in flippers], [0.4, 0.4, 0.4, 0.4])
        self.assertEqual([item["frequency"] for item in flippers], [2.0, 2.0, 2.0, 2.0])
        self.assertEqual([item["phase_offset"] for item in flippers],
                         [0.0, 3.14159, 0.0, 3.14159])
        published = [message for message in driver.native.sent
                     if message.get("op") == "publish" and message.get("topic") == "/hw/flippers_cmd"]
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["msg"]["flippers"], flippers)

    def test_out_of_envelope_fin_command_is_refused_before_the_publication(self):
        driver, server = self.driver()
        client, ids = self.client(server)
        receipt = client.invoke("x-cap.centre-for-biorobotics.fin_oscillation.v1",
                                _fin_payload(amplitude=1.0), **ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)
        self.assertFalse([message for message in driver.native.sent if message.get("op") == "publish"])

    def test_reset_is_a_bool_publication_without_an_acknowledgement(self):
        driver, server = self.driver()
        client, ids = self.client(server)
        receipt = client.invoke("x-cap.centre-for-biorobotics.reset.v1", {}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})
        self.assertEqual(driver.native.reset_requests, [{"data": True}])

    def test_a_transport_failure_is_not_reported_as_published(self):
        driver, server = self.driver()
        client, ids = self.client(server)
        driver.native.fail_publish = True
        receipt = client.invoke("x-cap.centre-for-biorobotics.fin_oscillation.v1",
                                _fin_payload(), **ids)
        self.assertIn(receipt["status"], ("failed", "unknown"), receipt)
        self.assertNotEqual(receipt.get("output"), {"published": True, "confirmed": False})

    def test_malformed_state_is_not_silently_accepted(self):
        driver, _server = self.driver(overlay=False)
        driver.native.malformed_state = True
        with self.assertRaises(MHSError) as caught:
            driver.read("main")
        self.assertIn(caught.exception.code,
                      {"MHS.DEVICE.NOT_READY", "MHS.RESOURCE.STATE_INVALID"})

    def test_declaration_is_a_simulated_ros2_world(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(type(driver).ros_version, 2)
        self.assertEqual(type(driver).mode, "simulated")
        self.assertEqual(type(driver).risk, "R2")
        self.assertEqual(set(type(driver).safety_bindings), {"sensed_stop"})
        self.assertEqual(type(driver).device_kind, "world.sim")
        self.assertEqual(type(driver).backends, {"fake": ".fake:FakeEeuvSimUcat"})
        self.assertEqual(type(driver).fidelity["fidelity_level"], "F0")
        self.assertNotIn("/ucat/reset",
                         [step.get("topic") for step in type(driver).safety_bindings["sensed_stop"]["request"]])


def details(receipt):
    return (receipt.get("error") or {}).get("details") or {}


class SensedStopCases(unittest.TestCase):
    def pair(self, **flags):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        for name, value in flags.items():
            setattr(driver.native, name, value)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return driver, client, ids

    def assert_unreached(self, receipt, reason):
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        self.assertEqual(details(receipt)["sensed"]["reason"], reason, receipt)

    def test_the_estop_is_confirmed_by_a_settled_twist(self):
        driver, client, ids = self.pair()
        receipt = client.estop("test", **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        sensed = receipt["x-vendor"]["sensed_confirmation"]
        self.assertEqual(sensed["request"][0]["native"], "/hw/flippers_cmd")
        amplitudes = [item["amplitude"] for item in driver.native.fin_commands[-1]["flippers"]]
        self.assertEqual(amplitudes, [0.0, 0.0, 0.0, 0.0])
        refused = client.invoke("x-cap.centre-for-biorobotics.fin_oscillation.v1", _fin_payload(), **ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_reset_reconfirms_without_another_flipper_command(self):
        driver, client, ids = self.pair()
        self.assertEqual(client.estop("test", **ids)["status"], "completed")
        sent = len(driver.native.sent)
        reset = client.reset(**ids)
        self.assertEqual(reset["status"], "completed", reset)
        later = [message for message in driver.native.sent[sent:] if message.get("op") == "publish"]
        self.assertEqual(later, [])

    def test_fins_that_keep_swimming_are_not_confirmed(self):
        _driver, client, ids = self.pair(keep_swimming=True)
        self.assert_unreached(client.estop("test", **ids), "not_confirmed")

    def test_silent_state_is_sensed_missing(self):
        _driver, client, ids = self.pair(silent_state=True)
        self.assert_unreached(client.estop("test", **ids), "sensed_missing")

    def test_a_null_twist_component_is_invalid(self):
        _driver, client, ids = self.pair(null_twist=True)
        self.assert_unreached(client.estop("test", **ids), "sensed_invalid")

    def test_twist_samples_at_the_10_ms_period_meet_the_declared_span(self):
        """dt is 0.01 s and fast_forward is 1. Three counted samples span just under 20 ms; min_span_ms is 19."""
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        cls = type(driver)
        self.assertEqual(cls.safety_bindings["sensed_stop"]["min_span_ms"], 19)
        from mhs.bridge.ros_sensed import SourceWindow, compile_profile
        from mhs.driver.sensed_stop import declaration
        problems: list[str] = []
        decl = declaration(cls, problems)
        self.assertEqual(problems, [])
        self.assertIsNotNone(decl)
        values = {item.key: 0.05 for item in decl.thresholds}
        profile = compile_profile(decl.bridge_json(cls.ros_version, values))
        source = profile.sources["state"]
        window = SourceWindow(source, profile.terms_of("state"), profile, not_before=0.0)
        message = {"twist": {
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
        }}
        period = 0.01
        count = profile.consecutive + source.skip
        for index in range(count):
            window.add(message, received_at=index * period)
        self.assertTrue(window.confirmed((count - 1) * period), window.report())
        span_ms = (window.counted[-1][1] - window.counted[0][1]) * 1000.0
        self.assertGreaterEqual(span_ms, 19)
        self.assertLess(span_ms, 20)
        self.assertLess(span_ms, 30)

    def test_the_estop_confirms_when_state_is_paced_at_10_ms(self):
        _driver, client, ids = self.pair(gap_s=0.01)
        receipt = client.estop("test", **ids)
        self.assertEqual(receipt["status"], "completed", receipt)


if __name__ == "__main__":
    unittest.main()
