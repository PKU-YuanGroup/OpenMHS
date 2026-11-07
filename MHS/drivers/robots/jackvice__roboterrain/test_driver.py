"""Acceptance run of the RoboTerrain RoverEnv package: the gate plus repository-specific cases.

Add cases, never remove the check_driver call.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RoverEnvCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_fake_copies_the_upstream_action_space(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.native.action_space.low, [-1.0, -math.pi])
        self.assertEqual(driver.native.action_space.high, [1.0, math.pi])
        self.assertEqual(driver.native.action_space.shape, (2,))

    def test_reset_and_step_reach_the_fake(self) -> None:
        client = self.serve()
        reset = client.invoke("cap.world.reset.v1", {"seed": 5}, **self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"]["seed"], 5, reset)
        self.assertEqual(set(reset["output"]["observation"]),
                         {"lidar", "pose", "imu", "target", "velocities"}, reset)
        receipt = client.invoke("cap.world.step.v1",
                                {"ticks": 2, "action": {"values": [0.25, 0.0]}}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["tick"], 2, receipt)
        self.assertTrue(receipt["output"]["state_hash"].startswith("sha256:"), receipt)
        state = client.read("world", **self.ids)["state"]
        self.assertEqual(state["tick"], 2, state)
        self.assertEqual(state["observation"]["velocities"]["values"][0], 0.25, state)

    def test_a_seeded_reset_repeats_the_fake_trajectory(self) -> None:
        client = self.serve()
        first = client.invoke("cap.world.reset.v1", {"seed": 42}, **self.ids)
        self.assertEqual(first["status"], "completed", first)
        step = client.invoke("cap.world.step.v1",
                             {"ticks": 1, "action": {"values": [0.5, 0.25]}}, **self.ids)
        self.assertEqual(step["status"], "completed", step)
        second = client.invoke("cap.world.reset.v1", {"seed": 42}, **self.ids)
        self.assertEqual(second["status"], "completed", second)
        again = client.invoke("cap.world.step.v1",
                              {"ticks": 1, "action": {"values": [0.5, 0.25]}}, **self.ids)
        self.assertEqual(again["status"], "completed", again)
        self.assertEqual(first["output"]["observation"], second["output"]["observation"])
        self.assertEqual(step["output"]["observation"], again["output"]["observation"])
        self.assertEqual(step["output"]["reward"], again["output"]["reward"])
        self.assertEqual(step["output"]["tick"], again["output"]["tick"])

    def test_an_out_of_envelope_action_is_refused_before_the_fake(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.reset.v1", {"seed": 3}, **self.ids)["status"], "completed")
        before = client.read("world", **self.ids)["state"]
        receipt = client.invoke("cap.world.step.v1",
                                {"ticks": 1, "action": {"values": [1.5, 0.0]}}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, receipt)
        after = client.read("world", **self.ids)["state"]
        self.assertEqual(before, after)

    def test_the_e_stop_latch_refuses_step(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.reset.v1", {"seed": 4}, **self.ids)["status"], "completed")
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = client.invoke("cap.world.step.v1",
                                {"ticks": 1, "action": {"values": [0.0, 0.0]}}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_close_reaches_the_fake(self) -> None:
        driver = load_driver(HERE, "fake")
        self.assertFalse(driver.native._closed)
        driver.close()
        self.assertTrue(driver.native._closed)


if __name__ == "__main__":
    unittest.main()
