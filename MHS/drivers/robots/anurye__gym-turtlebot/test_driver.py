"""Acceptance run of the gym-turtlebot package: the gate, plus cases specific to this simulator.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ACTION_REF = "src/tb4_drl_navigation/tb4_drl_navigation/envs/diffdrive/turtlebot4.py:187-191"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GymTurtlebotCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, values, ticks=1):
        return client.invoke(
            "cap.world.step.v1",
            {"ticks": ticks, "action": {"values": values}},
            **self.ids,
        )

    def test_upstream_action_space_is_the_derived_step_limit(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        step = next(item for item in device["capabilities"]
                    if item["capability_id"] == "cap.world.step.v1")
        rule = step["limits"]["action.values"]
        self.assertEqual(rule["min"], [0.0, -1.0])
        self.assertEqual(rule["max"], [1.0, 1.0])
        self.assertEqual(rule["source"], "upstream_code")
        self.assertEqual(rule["ref"], ACTION_REF)

    def test_step_applies_the_action_for_each_tick(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.5, 0.25], ticks=2)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["tick"], 2)
        self.assertEqual(receipt["output"]["observation"]["action"]["values"], [0.5, 0.25])

    def test_step_rejects_values_outside_the_upstream_action_space(self) -> None:
        client = self.serve()
        receipt = self.step(client, [-0.1, 0.0])
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_seed_and_reset_change_the_reported_observation(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 7}, **self.ids)
        self.assertEqual(seeded["status"], "completed", seeded)
        self.assertEqual(seeded["output"], {"seed": 7, "accepted": True})
        first = client.invoke("cap.world.reset.v1", {"seed": 7}, **self.ids)
        second = client.invoke("cap.world.reset.v1", {"seed": 8}, **self.ids)
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(second["status"], "completed", second)
        self.assertEqual(first["output"]["seed"], 7)
        self.assertEqual(second["output"]["seed"], 8)
        first_distance = first["output"]["observation"]["dist_to_goal"]["values"][0]
        second_distance = second["output"]["observation"]["dist_to_goal"]["values"][0]
        self.assertNotEqual(first_distance, second_distance)

    def test_estop_refuses_steps_and_reset_releases_the_latch(self) -> None:
        client = self.serve()
        stopped = client.estop("package test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertIn(stopped["output"]["estop"], {"software_only", "engaged"})
        refused = self.step(client, [0.5, 0.0])
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        released = client.reset(**self.ids)
        self.assertEqual(released["status"], "completed", released)
        allowed = self.step(client, [0.5, 0.0])
        self.assertEqual(allowed["status"], "completed", allowed)

    def test_manifest_discloses_recording_fidelity_and_no_native_stop(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R2")
        self.assertEqual(device["fidelity"]["fidelity_level"], "F0")
        self.assertTrue(device["fidelity"]["gaps"])
        self.assertIsNone(device["safety"]["estop"]["native"])


if __name__ == "__main__":
    unittest.main()
