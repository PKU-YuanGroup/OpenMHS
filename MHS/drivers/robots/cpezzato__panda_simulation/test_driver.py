"""Acceptance and package-specific cases for the cpezzato Panda simulation fake.

The cases exercise the joint-state and free-energy reads, the effort publications and their receipts, the
companion-cited stop (the Gazebo world pause confirmed by the get_physics_properties read-back), its failure
paths, the latch, a reset that leaves the world paused, and that the package offers no unpause.  One case
records that safety_status keeps the cached confirmation after an external unpause and does not call
get_physics_properties again.  Add cases, never remove the check_driver call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
JOINT_STATE = "x-cap.cpezzato.joint_state.v1"
FREE_ENERGY = "x-cap.cpezzato.free_energy.v1"
JOINT1 = "x-cap.cpezzato.joint1_effort.v1"
JOINT5 = "x-cap.cpezzato.joint5_effort.v1"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
NOT_READY = "MHS.DEVICE.NOT_READY"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"
TOPIC1 = "/robot1/panda_joint1_controller/command"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PandaSimulationCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def serve_driver(self, site_limits=None):
        driver = load_driver(HERE, "fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def direct(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    @staticmethod
    def example_overlay():
        return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))

    @staticmethod
    def services(native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    def test_the_joint_state_observation_returns_the_publisher_arrays(self) -> None:
        client = self.serve()
        receipt = client.invoke(JOINT_STATE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        sample = receipt["output"]["joint_state"]
        # A real ROS 1 JointState carries its std_msgs/Header; the closed output schema must accept it.
        self.assertEqual(set(sample["header"]), {"seq", "stamp", "frame_id"})
        self.assertEqual(set(sample["header"]["stamp"]), {"secs", "nsecs"})
        self.assertEqual(sample["name"], [f"panda_joint{number}" for number in range(1, 8)])
        self.assertEqual(len(sample["position"]), 7)
        self.assertEqual(len(sample["velocity"]), 7)
        self.assertEqual(len(sample["effort"]), 7)

    def test_the_free_energy_observation_returns_a_scalar(self) -> None:
        client = self.serve()
        receipt = client.invoke(FREE_ENERGY, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIsInstance(receipt["output"]["free_energy"], (int, float))

    def test_an_effort_publication_reaches_the_fake_topic_and_reports_what_it_sent(self) -> None:
        driver = self.direct()
        output = driver.call(JOINT1, {"effort": 1.25})
        self.assertEqual(output, {"published": True, "confirmed": False, "sent_effort": 1.25})
        self.assertEqual(driver.native.commanded_efforts[TOPIC1], 1.25)
        self.assertEqual(driver.native.applied_efforts[TOPIC1], 1.25)

    def test_the_resource_reads_no_topic(self) -> None:
        driver = self.direct()
        driver.native.paused = True
        self.assertEqual(driver.read("main"), {})

    def test_an_effort_is_refused_until_an_operator_envelope_exists(self) -> None:
        # Model review 2026-11-05: the xacro effort attribute is unsigned, so the envelope is operator_required.
        client = self.serve()
        receipt = client.invoke(JOINT1, {"effort": 0.5}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_the_example_overlay_admits_and_bounds_an_effort(self) -> None:
        client = self.serve(site_limits=self.example_overlay())
        receipt = client.invoke(JOINT5, {"effort": 0.5}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["sent_effort"], 0.5)
        receipt = client.invoke(JOINT5, {"effort": 1.5}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_a_missing_joint_state_sample_is_a_failure_not_a_hold(self) -> None:
        driver = self.direct()
        driver.native.silent_joint_states = True
        with self.assertRaises(Exception) as caught:  # noqa: BLE001 - the bridge reports a bounded read failure
            driver.call(JOINT_STATE, {})
        code = getattr(caught.exception, "code", "")
        self.assertIn(code, {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_a_joint_state_reply_without_position_is_not_completed_with_invented_data(self) -> None:
        driver = self.direct()
        driver.native.omit_joint_state_position = True
        output = driver.call(JOINT_STATE, {})
        self.assertNotIn("position", output["joint_state"])

    def test_the_estop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        driver, client = self.serve_driver(site_limits=self.example_overlay())
        receipt = client.estop("package test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.services(driver.native), [PAUSE, READBACK])
        self.assertTrue(driver.native.paused)
        refused = client.invoke(JOINT1, {"effort": 0.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_failed_pause_or_read_back_leaves_the_e_stop_unconfirmed_and_latched(self) -> None:
        for switch in ("fail_pause", "fail_readback", "ignore_pause"):
            with self.subTest(switch=switch):
                driver, client = self.serve_driver(site_limits=self.example_overlay())
                setattr(driver.native, switch, True)
                receipt = client.estop("package test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertFalse(receipt["output"]["safe_state_achieved"], receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
                refused = client.invoke(JOINT1, {"effort": 0.0}, **self.ids)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_the_reset_keeps_the_world_paused_and_a_stored_effort_reaches_no_joint(self) -> None:
        driver, client = self.serve_driver(site_limits=self.example_overlay())
        self.assertEqual(client.estop("package test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        receipt = client.invoke(JOINT1, {"effort": 0.5}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["sent_effort"], 0.5)
        self.assertEqual(driver.native.commanded_efforts[TOPIC1], 0.5)  # stored: it acts on the next unpause
        self.assertNotIn(TOPIC1, driver.native.applied_efforts)
        self.assertNotIn("/gazebo/unpause_physics", self.services(driver.native))
        free_energy = client.invoke(FREE_ENERGY, {}, **self.ids)
        self.assertEqual(free_energy["status"], "completed", free_energy)  # the fake still answers while paused
        self.assertEqual(free_energy["output"]["free_energy"], 0.0)
        joint_state = client.invoke(JOINT_STATE, {}, **self.ids)
        self.assertEqual(joint_state["status"], "failed", joint_state)  # silent while paused
        self.assertEqual(joint_state["error"]["mhs_code"], NOT_READY, joint_state)

    def test_safety_status_keeps_the_cached_confirmation_after_an_external_unpause(self) -> None:
        # RosBridge.safety_status returns the retained confirmation and does not call a service again.
        driver, client = self.serve_driver(site_limits=self.example_overlay())
        receipt = client.estop("package test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        before = self.services(driver.native)
        self.assertEqual(before, [PAUSE, READBACK])
        driver.native.paused = False  # another client unpaused; MHS is not told
        status = client.safety_status(self.ids["device_id"])
        self.assertEqual(self.services(driver.native), before)
        self.assertTrue(status["estop"]["confirmed"], status)
        self.assertTrue(status["status"]["safe_state"]["achieved"], status)

    def test_the_package_offers_no_unpause(self) -> None:
        driver = self.direct()
        self.assertIsNone(driver._model.reenable)
        for spec in type(driver).commands.values():
            self.assertNotIn("unpause", str(spec.get("service", "")))
        self.assertNotIn("reset", type(driver).safety_bindings)


if __name__ == "__main__":
    unittest.main()
