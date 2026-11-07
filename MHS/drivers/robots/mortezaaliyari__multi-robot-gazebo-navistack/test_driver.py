"""Acceptance run of the multi-robot TurtleBot3 package: the gate, plus repository cases.

The extra cases exercise the declared endpoints and the negative paths the fake
models: operator-required bounds, out-of-envelope refusal, a malformed laser
reply and a failed publication; and the companion-cited stop (the Gazebo world
pause confirmed by the get_physics_properties read-back), its failure paths,
the latch, the declared resume (zero Twists, then the unpause) and the silence
of odometry and scans while paused.  Add cases, never remove the check_driver
call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
DEVICE = "mhs://localhost/turtlebot3-multi"
CAP_0 = "x-cap.mortezaaliyari.tb3-0-cmd-vel.v1"
CAP_1 = "x-cap.mortezaaliyari.tb3-1-cmd-vel.v1"
ODOM_0 = "x-cap.mortezaaliyari.tb3-0-odom.v1"
SCAN_0 = "x-cap.mortezaaliyari.tb3-0-scan.v1"
ODOM_1 = "x-cap.mortezaaliyari.tb3-1-odom.v1"
SCAN_1 = "x-cap.mortezaaliyari.tb3-1-scan.v1"
RESUME = "x-cap.mortezaaliyari.resume.v1"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"
UNPAUSE = "/gazebo/unpause_physics"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"

#: A test-only operator overlay.  These example bounds are not device facts.
OVERLAY = {
    "$schema": "https://mhs.openai4s.org/schema/0.9/site-limits.schema.json",
    "openmhs": "0.9",
    "site": "driver test overlay",
    "issued_by": {"id": "operator:test"},
    "devices": {
        DEVICE: {
            CAP_0: {
                "linear_velocity": {"min": -0.5, "max": 0.5, "unit": "m/s", "source": "operator",
                                    "reason": "test overlay: example linear bound"},
                "angular_velocity": {"min": -1.5, "max": 1.5, "unit": "rad/s", "source": "operator",
                                     "reason": "test overlay: example angular bound"},
            },
            CAP_1: {
                "linear_velocity": {"min": -0.5, "max": 0.5, "unit": "m/s", "source": "operator",
                                    "reason": "test overlay: example linear bound"},
                "angular_velocity": {"min": -1.5, "max": 1.5, "unit": "rad/s", "source": "operator",
                                     "reason": "test overlay: example angular bound"},
            },
        }
    },
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MultiRobotCases(unittest.TestCase):
    def serve(self, *, overlay: bool = True):
        server = load(HERE, backend="fake", site_limits=OVERLAY if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        ids = {"device_id": device_id, "session_id": session}
        self.server = server
        self.fake = server.devices[device_id].bridge.native
        return client, ids

    def publications(self):
        return [message for message in self.fake.sent if message.get("op") == "publish"]

    def test_scan_and_odometry_reads_are_declared_for_both_robots(self) -> None:
        client, ids = self.serve(overlay=False)
        for capability in (SCAN_0, SCAN_1):
            receipt = client.invoke(capability, {}, **ids)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(len(receipt["output"]["ranges"]), 360)
        for capability in (ODOM_0, ODOM_1):
            receipt = client.invoke(capability, {}, **ids)
            self.assertEqual(set(receipt["output"]["pose"]), {"position", "orientation"})

    def test_the_resource_reads_no_topic_and_answers_while_paused(self) -> None:
        client, ids = self.serve(overlay=False)
        self.fake.paused = True
        self.assertEqual(client.read("main", **ids)["state"], {})

    def test_tb3_0_publication_reaches_the_declared_twist_topic(self) -> None:
        client, ids = self.serve()
        receipt = client.invoke(CAP_0, {"linear_velocity": 0.2, "angular_velocity": 0.1}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False, "sent_linear_velocity": 0.2,
                                             "sent_angular_velocity": 0.1})
        publishes = [message for message in self.publications() if message.get("topic") == "/tb3_0/cmd_vel"]
        self.assertEqual(len(publishes), 1)
        self.assertEqual(publishes[0]["msg"]["linear"]["x"], 0.2)
        self.assertEqual(publishes[0]["msg"]["angular"]["z"], 0.1)

    def test_tb3_1_publication_uses_its_own_topic(self) -> None:
        client, ids = self.serve()
        receipt = client.invoke(CAP_1, {"linear_velocity": -0.1, "angular_velocity": -0.2}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        publishes = self.publications()
        self.assertEqual([message["topic"] for message in publishes], ["/tb3_1/cmd_vel"])
        self.assertEqual(publishes[0]["msg"]["linear"]["x"], -0.1)
        self.assertEqual(publishes[0]["msg"]["angular"]["z"], -0.2)

    def test_operator_required_velocity_bounds_refuse_without_an_overlay(self) -> None:
        client, ids = self.serve(overlay=False)
        before = list(self.publications())
        receipt = client.invoke(CAP_0, {"linear_velocity": 0.2, "angular_velocity": 0.0}, **ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)
        self.assertEqual(self.publications(), before)

    def test_out_of_envelope_velocity_is_refused_before_publication(self) -> None:
        client, ids = self.serve()
        before = list(self.publications())
        receipt = client.invoke(CAP_0, {"linear_velocity": 2.0, "angular_velocity": 0.0}, **ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.publications(), before)

    def test_the_e_stop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        client, ids = self.serve()
        receipt = client.estop("test", **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertTrue(self.fake.paused)
        self.assertEqual(self.fake.service_calls[:2], [PAUSE, READBACK])
        self.assertEqual(self.publications(), [])
        refused = client.invoke(CAP_0, {"linear_velocity": 0.1, "angular_velocity": 0.0}, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_read_back_other_than_pause_true_leaves_the_e_stop_unconfirmed_and_latched(self) -> None:
        for switch in ("unpaused_by_other_client", "fail_readback", "fail_pause"):
            with self.subTest(switch=switch):
                client, ids = self.serve()
                setattr(self.fake, switch, True)
                receipt = client.estop("test", **ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
                self.assertTrue(receipt["output"]["latched"])
                refused = client.invoke(CAP_0, {"linear_velocity": 0.1, "angular_velocity": 0.0}, **ids)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_the_resume_is_refused_while_latched_then_zeroes_both_robots_and_unpauses(self) -> None:
        client, ids = self.serve()
        self.assertEqual(client.invoke(CAP_0, {"linear_velocity": 0.2, "angular_velocity": 0.0}, **ids)["status"],
                         "completed")
        self.assertEqual(client.estop("test", **ids)["status"], "completed")
        refused = client.invoke(RESUME, {}, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertNotIn(UNPAUSE, self.fake.service_calls)
        reset = client.reset(**ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"]["reenable"], RESUME)
        self.assertTrue(self.fake.paused)  # the reset never unpauses (SAFE-042)
        self.assertEqual(self.fake.last_cmd_vel["tb3_0"], (0.2, 0.0))  # the plugin still holds the command
        mark = len(self.fake.sent)
        receipt = client.invoke(RESUME, {}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"acknowledged": True, "zero_commands_published": True})
        after = [(message.get("op"), message.get("topic") or message.get("service"))
                 for message in self.fake.sent[mark:] if message.get("op") in ("publish", "call_service")]
        self.assertEqual(after, [("publish", "/tb3_0/cmd_vel"), ("publish", "/tb3_1/cmd_vel"),
                                 ("call_service", UNPAUSE)])
        self.assertFalse(self.fake.paused)
        self.assertEqual(self.fake.last_cmd_vel, {"tb3_0": (0.0, 0.0), "tb3_1": (0.0, 0.0)})

    def test_without_the_zeros_an_unpause_would_resume_the_stored_command(self) -> None:
        client, ids = self.serve()
        client.invoke(CAP_0, {"linear_velocity": 0.2, "angular_velocity": 0.0}, **ids)
        self.fake.paused = True
        before = self.fake.poses["tb3_0"]["position"]["x"]
        self.fake.send({"op": "call_service", "service": UNPAUSE, "type": "std_srvs/Empty", "args": {},
                        "id": "other-client"})
        self.assertGreater(self.fake.poses["tb3_0"]["position"]["x"], before)

    def test_odometry_and_scans_are_silent_while_paused(self) -> None:
        client, ids = self.serve(overlay=False)
        self.fake.paused = True
        for capability in (ODOM_0, SCAN_1):
            receipt = client.invoke(capability, {}, deadline_ms=3000, **ids)
            self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)

    def test_a_command_changes_the_odometry_stand_in(self) -> None:
        client, ids = self.serve()
        before = client.invoke(ODOM_0, {}, **ids)["output"]["pose"]
        receipt = client.invoke(CAP_0, {"linear_velocity": 0.2, "angular_velocity": 0.0}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        after = client.invoke(ODOM_0, {}, **ids)["output"]["pose"]
        self.assertNotEqual(before["position"]["x"], after["position"]["x"])

    def test_a_malformed_scan_reply_is_not_a_good_observation(self) -> None:
        client, ids = self.serve(overlay=False)
        self.fake.malformed_scan = True
        receipt = client.invoke(SCAN_0, {}, **ids)
        self.assertEqual(receipt["status"], "failed", receipt)

    def test_a_failed_publication_is_not_reported_as_completed(self) -> None:
        client, ids = self.serve()
        self.fake.fail_publish = True
        receipt = client.invoke(CAP_0, {"linear_velocity": 0.1, "angular_velocity": 0.0}, **ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIn(receipt["error"]["mhs_code"], {"MHS.OUTCOME.UNKNOWN", "MHS.ADAPTER.SHIM_FAILED"})


if __name__ == "__main__":
    unittest.main()
