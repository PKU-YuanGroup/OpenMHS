"""Acceptance run of the Webots gym_env ROS package: the gate, plus cases specific to this bridge.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
OBSERVE = "x-cap.alexanderkeijzer.joint_observation.v1"
ACT = "x-cap.alexanderkeijzer.action_step.v1"
STEP = "x-cap.alexanderkeijzer.step.v1"
RESET = "x-cap.alexanderkeijzer.reset.v1"
REWARD = "x-cap.alexanderkeijzer.reward.v1"
ACTIONS = [0.1, -0.1, 0.2, -0.2, 0.3, -0.3, 0.4, -0.4, 0.5]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GymEnvWebotsCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
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

    @staticmethod
    def wire(driver):
        return [(message.get("op"), message.get("topic") or message.get("service")) for message in driver.native.sent]

    def test_the_joint_observation_returns_nine_positions(self) -> None:
        client = self.serve()
        receipt = client.invoke(OBSERVE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(len(receipt["output"]["observations"]), 9)

    def test_act_and_step_publishes_then_steps_then_reads_a_fresh_sample(self) -> None:
        driver = self.driver()
        output = driver.call(ACT, {"actions": list(ACTIONS)})
        self.assertTrue(output["published"])
        self.assertFalse(output["confirmed"])
        self.assertTrue(output["stepped"])
        self.assertEqual(driver.native.published_actions[-1], ACTIONS)
        self.assertEqual(driver.native.step_calls, 1)
        wire = self.wire(driver)
        publish = wire.index(("publish", "/joint_actuators/value"))
        step = wire.index(("call_service", "/webots/step"))
        subscribe = wire.index(("subscribe", "/joint_sensors/value"))
        self.assertLess(publish, step)
        self.assertLess(step, subscribe)
        # The fake applies the node's arithmetic: motorRange * action / 20 from the zero setpoint.
        self.assertEqual(output["observations"], driver.native.set_points)
        self.assertGreater(output["observations"][0], 0.0)
        self.assertLess(output["observations"][1], 0.0)

    def test_the_observation_depends_on_the_action(self) -> None:
        client = self.serve()
        first = client.invoke(ACT, {"actions": [0.5] * 9}, **self.ids)
        second = client.invoke(ACT, {"actions": [-0.5] * 9}, **self.ids)
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(second["status"], "completed", second)
        self.assertNotEqual(first["output"]["observations"], second["output"]["observations"])

    def test_a_completed_receipt_does_not_prove_the_action_was_applied_before_the_step(self) -> None:
        # Live, the publication and the step call reach the node on different ROS connections; the fake's switch
        # runs the step first, so the receipt completes with an observation that predates the action.
        driver = self.driver()
        driver.native.action_after_step = True
        before = list(driver.native.joint_positions)
        output = driver.call(ACT, {"actions": [0.5] * 9})
        self.assertTrue(output["stepped"])
        self.assertFalse(output["confirmed"])
        self.assertEqual(output["observations"], before, "the observation predates the action")
        self.assertNotEqual(driver.native.set_points, before, "the node applied the action after the step")
        # The next step moves the joints to the late action's targets.
        self.assertEqual(driver.call(STEP, {}), {"stepped": True})
        self.assertEqual(driver.native.joint_positions, driver.native.set_points)

    def test_the_action_envelope_is_enforced_without_a_native_call(self) -> None:
        client = self.serve()
        receipt = client.invoke(ACT, {"actions": [1.5] + [0.0] * 8}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_a_failed_step_after_the_publication_is_unknown_not_failed(self) -> None:
        driver = self.driver()
        driver.native.fail_step_service = True
        with self.assertRaises(OutcomeUnknown):
            driver.call(ACT, {"actions": list(ACTIONS)})
        self.assertEqual(driver.native.published_actions[-1], ACTIONS)
        self.assertNotIn(("subscribe", "/joint_sensors/value"), self.wire(driver))

    def test_a_rejected_step_after_the_publication_is_unknown(self) -> None:
        # A step the node refuses after the action went out must not invite a blind retry: the node holds the setpoint.
        driver = self.driver()
        driver.native.reject_step_application = True
        with self.assertRaises(OutcomeUnknown):
            driver.call(ACT, {"actions": list(ACTIONS)})
        self.assertEqual(driver.native.published_actions[-1], ACTIONS)

    def test_no_sample_after_the_step_is_unknown(self) -> None:
        driver = self.driver()
        driver.native.silent_sensors = True
        with self.assertRaises(OutcomeUnknown):
            driver.call(ACT, {"actions": list(ACTIONS)}, {"deadline_ms": 300})
        self.assertEqual(driver.native.step_calls, 1)

    def test_act_and_step_is_refused_while_latched_with_nothing_sent(self) -> None:
        client = self.serve()
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        refused = client.invoke(ACT, {"actions": list(ACTIONS)}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_step_calls_the_webots_step_service(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(STEP, {}), {"stepped": True})
        self.assertGreaterEqual(driver.native.step_calls, 1)
        services = [message.get("service") for message in driver.native.sent
                    if message.get("op") == "call_service"]
        self.assertIn("/webots/step", services)

    def test_the_reset_calls_the_webots_reset_service_and_keeps_the_setpoints(self) -> None:
        driver = self.driver()
        driver.call(ACT, {"actions": list(ACTIONS)})
        kept = list(driver.native.set_points)
        self.assertEqual(driver.call(RESET, {}), {"reset": True})
        self.assertGreaterEqual(driver.native.reset_calls, 1)
        services = [message.get("service") for message in driver.native.sent
                    if message.get("op") == "call_service"]
        self.assertIn("/webots/reset", services)
        # Faithful to the node: resetCallback never clears motorSetPoints.
        self.assertEqual(driver.native.set_points, kept)

    def test_the_reward_is_a_number(self) -> None:
        client = self.serve()
        receipt = client.invoke(REWARD, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIsInstance(receipt["output"]["reward"], (int, float))

    def test_a_failed_step_service_is_not_reported_as_completed(self) -> None:
        driver = self.driver()
        driver.native.fail_step_service = True
        with self.assertRaises(DriverFailed):
            driver.call(STEP, {})

    def test_a_rejected_step_application_is_not_reported_as_completed(self) -> None:
        driver = self.driver()
        driver.native.reject_step_application = True
        with self.assertRaises(DriverFailed):
            driver.call(STEP, {})

    def test_a_failed_reset_service_is_not_reported_as_completed(self) -> None:
        driver = self.driver()
        driver.native.fail_reset_service = True
        with self.assertRaises(DriverFailed):
            driver.call(RESET, {})

    def test_the_e_stop_runs_the_reset_safe_state_and_latches(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        refused = client.invoke(STEP, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
