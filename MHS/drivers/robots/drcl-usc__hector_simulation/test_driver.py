"""Acceptance and contract cases for the pinned HECTOR Gazebo simulation.

The cases exercise the observable contract, the publication path, the companion-cited stop (the Gazebo world pause
confirmed by the get_physics_properties read-back), its failure paths, the latch, the reset that leaves the world
paused, the absence of an unpause and the silence of /gazebo/model_states while paused.  They do not claim that a
MotorCmd publication was applied or that the robot moved.  Add cases, never remove check_driver.
"""

import json
import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
MODEL_STATES = "x-cap.drcl-usc.model_states.v1"
LEFT_HIP = "x-cap.drcl-usc.left_hip_command.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
SAFE_STATE_UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
RESUME = "x-cap.drcl-usc.resume.v1"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"
UNPAUSE = "/gazebo/unpause_physics"


def example_overlay():
    return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


def hip_command(**overrides):
    payload = {
        "position": 10.0,
        "velocity": 0.0,
        "torque": 0.0,
        "position_stiffness": 10.0,
        "velocity_stiffness": 1.0,
    }
    payload.update(overrides)
    return payload


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HectorSimulationCases(unittest.TestCase):
    def serve(self, *, overlay=True):
        server = load(HERE, backend="fake", site_limits=example_overlay() if overlay else None)
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

    def served_driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=example_overlay())
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def test_the_model_states_observation_returns_all_models(self) -> None:
        client = self.serve()
        receipt = client.invoke(MODEL_STATES, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIn("hector_gazebo", receipt["output"]["model_names"])
        self.assertEqual(len(receipt["output"]["model_poses"]),
                         len(receipt["output"]["model_names"]))
        self.assertEqual(len(receipt["output"]["model_twists"]),
                         len(receipt["output"]["model_names"]))

    def test_the_resource_reads_no_topic_and_answers_while_paused(self) -> None:
        driver, fake = self.direct()
        fake.paused = True
        self.assertEqual(driver.read("simulation"), {})

    def test_a_publication_reaches_the_left_hip_command_topic_and_is_not_confirmed(self) -> None:
        driver, fake = self.direct()
        result = driver.call(LEFT_HIP, hip_command())
        self.assertEqual(result, {"published": True, "confirmed": False, "sent_position": 10.0,
                                  "sent_velocity": 0.0, "sent_torque": 0.0, "sent_position_stiffness": 10.0,
                                  "sent_velocity_stiffness": 1.0})
        topic = "/hector_gazebo/L_hip_controller/command"
        self.assertIn(topic, fake.last_commands)
        message = fake.last_commands[topic]
        self.assertEqual(message["mode"], 10)
        self.assertAlmostEqual(message["q"], math.radians(10.0), places=6)
        self.assertAlmostEqual(message["Kp"], 10.0)
        self.assertIn({"op": "publish", "topic": topic},
                      [{key: sent.get(key) for key in ("op", "topic")} for sent in fake.sent])

    def test_a_command_without_the_operator_overlay_is_refused(self) -> None:
        client = self.serve(overlay=False)
        receipt = client.invoke(LEFT_HIP, hip_command(), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_a_silent_model_state_subscription_fails_rather_than_reusing_a_value(self) -> None:
        driver, fake = self.direct()
        fake.silent_model_states = True
        with self.assertRaises(MHSError):
            driver.call(MODEL_STATES, {})

    def test_the_e_stop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        driver, client = self.served_driver()
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        self.assertTrue(estop["output"]["safe_state_achieved"], estop)
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.native.service_calls[:2], [PAUSE, READBACK])
        refused = client.invoke(LEFT_HIP, hip_command(), **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_read_back_other_than_pause_true_leaves_the_e_stop_unconfirmed_and_latched(self) -> None:
        for switch in ("unpaused_by_other_client", "fail_readback", "fail_pause"):
            with self.subTest(switch=switch):
                driver, client = self.served_driver()
                setattr(driver.native, switch, True)
                estop = client.estop("test", **self.ids)
                self.assertEqual(estop["status"], "failed", estop)
                self.assertEqual(estop["error"]["mhs_code"], SAFE_STATE_UNREACHED)
                refused = client.invoke(LEFT_HIP, hip_command(), **self.ids)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_the_package_offers_no_unpause_and_the_reset_leaves_the_world_paused(self) -> None:
        driver, client = self.served_driver()
        self.assertNotIn(RESUME, type(driver).commands)
        for spec in type(driver).commands.values():
            self.assertNotIn("unpause", str(spec.get("service", "")) + str(spec.get("topic", "")))
        for action in type(driver).actions.values():
            self.assertFalse(getattr(action, "reenable", False))
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertNotIn("reenable", reset["output"])
        self.assertFalse(reset["output"]["resumed"])
        self.assertTrue(driver.native.paused)
        self.assertNotIn(UNPAUSE, driver.native.service_calls)
        before = driver.native.model_poses[1]["position"]["x"]
        receipt = client.invoke(LEFT_HIP, hip_command(position=5.0), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(driver.native.paused)
        self.assertIn("/hector_gazebo/L_hip_controller/command", driver.native.last_commands)
        self.assertEqual(driver.native.model_poses[1]["position"]["x"], before)
        self.assertNotIn(UNPAUSE, driver.native.service_calls)

    def test_model_states_are_silent_while_paused(self) -> None:
        driver, fake = self.direct()
        fake.paused = True
        with self.assertRaises(MHSError):
            driver.call(MODEL_STATES, {})


if __name__ == "__main__":
    unittest.main()
