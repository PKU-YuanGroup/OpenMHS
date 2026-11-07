"""Acceptance run of the Go2 MuJoCo simulator package: the gate, plus cases specific to this ROS surface.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent

#: Placeholder motor commands, in the simulator's actuator order FR, FL, RR, RL.
MOTOR_CMD = [
    {"q": 0.1, "kp": 30.0, "kd": 0.75},
    {"q": 0.8, "kp": 30.0, "kd": 0.75},
    {"q": -1.5, "kp": 30.0, "kd": 0.75},
    {"q": -0.1, "kp": 30.0, "kd": 0.75},
    {"q": 0.8, "kp": 30.0, "kd": 0.75},
    {"q": -1.5, "kp": 30.0, "kd": 0.75},
    {"q": 0.1, "kp": 30.0, "kd": 0.75},
    {"q": 1.0, "kp": 30.0, "kd": 0.75},
    {"q": -1.5, "kp": 30.0, "kd": 0.75},
    {"q": -0.1, "kp": 30.0, "kd": 0.75},
    {"q": 1.0, "kp": 30.0, "kd": 0.75},
    {"q": -1.5, "kp": 30.0, "kd": 0.75},
]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], ["G6", "G8"], report)


class Go2MujocoSimCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_low_state_observation_returns_the_published_arrays(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.glowing-torch.lowstate.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(len(output["quaternion"]), 4)
        self.assertEqual(len(output["gyroscope"]), 3)

    def test_the_qpos_observation_returns_the_published_vector(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.glowing-torch.qpos.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(len(receipt["output"]["qpos"]), 19)
        self.assertEqual(receipt["output"]["qpos"][2], 0.28)

    def test_the_resource_snapshot_reads_the_base_height(self) -> None:
        client = self.serve()
        resource = client.read("main", **self.ids)
        self.assertEqual(resource["state"]["base_height"], 0.28, resource)

    def test_a_joint_command_reaches_the_lowcmd_topic_unchanged(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        receipt = driver.call("x-cap.glowing-torch.lowcmd.v1", {"motor_cmd": MOTOR_CMD})
        self.assertTrue(receipt["published"])
        self.assertFalse(receipt["confirmed"])
        self.assertEqual(driver.native.command_count, 1)
        self.assertEqual(driver.native.last_command, MOTOR_CMD)
        published = [message for message in driver.native.sent
                     if message.get("op") == "publish" and message.get("topic") == "/mujoco/lowcmd"]
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["msg"]["motor_cmd"], MOTOR_CMD)

    def test_a_silent_state_topic_does_not_return_a_stale_sample(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.publish_state = False
        with self.assertRaises(Exception) as caught:
            driver.call("x-cap.glowing-torch.lowstate.v1", {})
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.DEVICE.NOT_READY")

    def test_a_malformed_motor_command_is_rejected_before_the_transport(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.glowing-torch.lowcmd.v1", {"motor_cmd": MOTOR_CMD[:11]}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")

    def test_the_declaration_is_a_sensed_stop(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        cls = type(driver)
        self.assertEqual(set(cls.safety_bindings), {"sensed_stop"})
        self.assertEqual(cls.risk, "R2")
        self.assertEqual(cls.safety_bindings["sensed_stop"]["sources"]["lowstate"]["freshness"], "arrival")
        self.assertEqual(cls.safety_bindings["sensed_stop"]["sources"]["pos"]["freshness"], "arrival")


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
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
        self.assertEqual(details(receipt)["sensed"]["reason"], reason, receipt)

    def test_settled_joints_do_not_confirm_without_a_passive_exclusion_sample(self):
        driver, client, ids = self.pair()
        receipt = client.estop("test", **ids)
        self.assert_unreached(receipt, "not_confirmed")
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        command = driver.native.last_command
        self.assertEqual(len(command), 20)
        self.assertTrue(all(entry["kp"] == 0.0 and entry["kd"] == 0.0 and entry["tau"] == 0.0 for entry in command))
        refused = client.invoke("x-cap.glowing-torch.qpos.v1", {}, **ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED", refused)

    def test_a_reset_is_refused_without_a_passive_exclusion_sample(self):
        driver, client, ids = self.pair()
        self.assert_unreached(client.estop("test", **ids), "not_confirmed")
        reset = client.reset(**ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED", reset)
        refused = client.invoke("x-cap.glowing-torch.qpos.v1", {}, **ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED", refused)

    def test_a_republished_gain_is_not_confirmed(self):
        _driver, client, ids = self.pair(republish=True)
        self.assert_unreached(client.estop("test", **ids), "not_confirmed")

    def test_a_walking_base_is_not_confirmed(self):
        _driver, client, ids = self.pair(base_moving=True)
        self.assert_unreached(client.estop("test", **ids), "not_confirmed")

    def test_silent_topics_are_sensed_missing(self):
        _driver, client, ids = self.pair(publish_state=False)
        self.assert_unreached(client.estop("test", **ids), "sensed_missing")

    def test_a_null_joint_velocity_is_invalid(self):
        _driver, client, ids = self.pair(null_dq=True)
        self.assert_unreached(client.estop("test", **ids), "sensed_invalid")

    def test_an_unbounded_motor_command_is_rejected_and_sends_nothing(self):
        for index in (0, 11):
            driver = load_driver(HERE, "fake")
            self.addCleanup(driver.close)
            server = build_server(driver)
            self.addCleanup(close_server, server)
            client = client_for(server)
            device_id = client.hello()["devices"][0]["device_id"]
            ids = {"device_id": device_id,
                   "session_id": client.open_session(device_ids=[device_id])["session_id"]}
            command = [{"q": 0.0, "kp": 0.0, "kd": 0.0} for _ in range(12)]
            command[index] = {"q": 1e100, "kp": -1e100, "kd": -1e100}
            receipt = client.invoke("x-cap.glowing-torch.lowcmd.v1", {"motor_cmd": command}, **ids)
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET", receipt)
            published = [message for message in driver.native.sent
                         if message.get("op") == "publish" and message.get("topic") == "/mujoco/lowcmd"]
            self.assertEqual(published, [])
            self.assertEqual(driver.native.command_count, 0)

    def test_a_stationary_holding_controller_is_not_confirmed(self):
        driver, client, ids = self.pair(stationary_hold=True)
        receipt = client.estop("test", **ids)
        self.assert_unreached(receipt, "not_confirmed")
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        command = driver.native.last_command
        self.assertEqual(len(command), 20)
        self.assertTrue(all(entry["kp"] == 50.0 and entry["kd"] == 1.0 for entry in command))

    def test_samples_at_the_2_ms_timer_meet_the_declared_span(self):
        """publish_sensor_data runs every 2 ms. Three counted samples of each source span 4 ms."""
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        cls = type(driver)
        self.assertEqual(cls.safety_bindings["sensed_stop"]["min_span_ms"], 4)
        from mhs.bridge.ros_sensed import SourceWindow, compile_profile
        from mhs.driver.sensed_stop import declaration
        problems: list[str] = []
        decl = declaration(cls, problems)
        self.assertEqual(problems, [])
        self.assertIsNotNone(decl)
        values = {item.key: 0.05 for item in decl.thresholds}
        profile = compile_profile(decl.bridge_json(cls.ros_version, values))
        period = 0.002
        messages = {
            "lowstate": {"motor_state": [{"dq": 0.0} for _ in range(12)]},
            "pos": {"data": [0.0, 0.0, 0.28] + [0.0] * 16},
        }
        for name, message in messages.items():
            source = profile.sources[name]
            window = SourceWindow(source, profile.terms_of(name), profile, not_before=0.0)
            count = profile.consecutive + source.skip
            for index in range(count):
                window.add(message, received_at=index * period)
            self.assertTrue(window.confirmed((count - 1) * period), window.report())
            span_ms = (window.counted[-1][1] - window.counted[0][1]) * 1000.0
            self.assertGreaterEqual(span_ms, 4)
            self.assertLess(span_ms, 30)

    def test_paced_samples_do_not_confirm_without_a_passive_exclusion_sample(self):
        _driver, client, ids = self.pair(gap_s=0.002)
        receipt = client.estop("test", **ids)
        self.assert_unreached(receipt, "not_confirmed")

    def _observer_case(self, denial):
        driver, client, ids = self.pair(stationary_hold=True, gap_s=0.002)
        original = driver.native.handler

        def handler(message):
            if message.get("op") == "subscribe" and message.get("topic") == "/mujoco/lowcmd":
                if denial:
                    return {"op": "status", "id": message["id"], "level": "error",
                            "msg": "subscription denied"}
                return None
            return original(message)

        driver.native.handler = handler
        receipt = client.estop("observer", **ids)
        self.assert_unreached(receipt, "not_confirmed")
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        command = driver.native.last_command
        self.assertEqual(len(command), 20)
        self.assertTrue(all(entry["kp"] == 50.0 and entry["kd"] == 1.0 for entry in command))

    def test_a_silent_exclusion_stream_is_not_proof_of_exclusion(self):
        self._observer_case(False)

    def test_a_denied_exclusion_subscription_must_fail_closed(self):
        self._observer_case(True)


if __name__ == "__main__":
    unittest.main()
