"""Acceptance run of the gym_px4 package: the gate plus environment-specific cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GymPx4Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_step_advances_the_tick_and_changes_the_observation(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.step.v1",
                                {"ticks": 2, "action": {"values": [1.0]}}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertEqual(len(output["observation"]["values"]), 2)
        self.assertNotEqual(output["observation"]["values"], [0.0, 0.0])
        self.assertTrue(output["state_hash"].startswith("sha256:"))

    def test_reset_returns_a_legacy_observation_and_the_requested_seed(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.reset.v1", {"seed": 7}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 7)
        # The upstream reset returns once the altitude error and the speed are below 0.2
        # (gymPX4_env.py:183); the fake's exact start state is only one such observation.
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), 2)
        self.assertTrue(all(abs(value) < 0.2 for value in values), values)

    def test_seed_is_recorded_for_the_next_reset(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.seed.v1", {"seed": 11}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"seed": 11, "accepted": True})

    def test_an_out_of_envelope_thrust_is_refused_before_the_fake_steps(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        with self.assertRaises(MHSError) as caught:
            driver.call("cap.world.step.v1", {"ticks": 1, "action": {"values": [1.5]}})
        self.assertEqual(caught.exception.code, ENVELOPE)
        self.assertEqual(driver.native.steps, 0)

    def test_the_fake_preserves_the_legacy_gym_surface(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        native = driver.native
        self.assertEqual(native.action_space.low, 0.0)
        self.assertEqual(native.action_space.high, 1.0)
        self.assertEqual(native.action_space.shape, (1,))
        observation = native.reset()
        self.assertEqual(len(observation), 2)
        with self.assertRaises(TypeError):   # upstream reset(self) takes no seed (gymPX4_env.py:143)
            native.reset(seed=1)
        result = native.step([0.5])
        self.assertEqual(len(result), 4)
        observation, reward, done, info = result
        self.assertEqual(len(observation), 2)
        self.assertIsInstance(reward, float)
        self.assertIs(done, False)
        self.assertEqual(set(info), {"state", "action", "reward", "step", "step length", "reset reason"})


if __name__ == "__main__":
    unittest.main()
