"""Acceptance run of the gym-gazebo driver package: the gate, plus simulator-specific cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ACTION_REF = "gym_gazebo/envs/turtlebot/gazebo_circuit_turtlebot_lidar.py:26"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GazeboCircuitCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, index, ticks=1):
        return client.invoke(
            "cap.world.step.v1",
            {"ticks": ticks, "action": {"index": index}},
            **self.ids,
        )

    def test_the_discrete_action_limit_is_derived_from_upstream(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        step = next(item for item in device["capabilities"]
                    if item["capability_id"] == "cap.world.step.v1")
        rule = step["limits"]["action.index"]
        self.assertEqual(rule["min"], 0)
        self.assertEqual(rule["max"], 2)
        self.assertEqual(rule["source"], "upstream_code")
        self.assertEqual(rule["ref"], ACTION_REF)

    def test_reset_returns_the_five_sector_observation(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.reset.v1", {"seed": 7}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 7)
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), 5, receipt)
        self.assertTrue(all(isinstance(value, int) for value in values), receipt)

    def test_a_forward_step_rewards_five_and_advances_the_tick(self) -> None:
        client = self.serve()
        receipt = self.step(client, 0)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["tick"], 1, receipt)
        self.assertEqual(receipt["output"]["reward"], 5.0, receipt)
        self.assertFalse(receipt["output"]["terminated"], receipt)
        self.assertEqual(len(receipt["output"]["observation"]["values"]), 5, receipt)

    def test_an_action_outside_the_discrete_space_is_refused(self) -> None:
        client = self.serve()
        receipt = self.step(client, 3)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, receipt)

    def test_the_fourth_forward_step_is_terminal_and_requires_a_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.reset.v1", {"seed": 1}, **self.ids)["status"],
                         "completed")
        terminal = None
        for _ in range(6):
            receipt = self.step(client, 0)
            self.assertEqual(receipt["status"], "completed", receipt)
            if receipt["output"]["terminated"]:
                terminal = receipt
                break
        self.assertIsNotNone(terminal, "the placeholder sectors never reached the collision threshold")
        self.assertEqual(terminal["output"]["reward"], -200.0, terminal)
        refused = self.step(client, 0)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET", refused)
        reset = client.invoke("cap.world.reset.v1", {"seed": 2}, **self.ids)
        self.assertEqual(reset["status"], "completed", reset)

    def test_seed_is_used_by_the_next_reset(self) -> None:
        # Fake-only behaviour (model review): this checks the bridge's seed bookkeeping and the fake's seed
        # extension; the upstream reset() takes no seed, so no seeded repeat is an upstream property.
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 11}, **self.ids)
        self.assertEqual(seeded["status"], "completed", seeded)
        self.assertEqual(seeded["output"], {"seed": 11, "accepted": True})
        reset = client.invoke("cap.world.reset.v1", {}, **self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"]["seed"], 11, reset)

    def test_estop_latches_steps_and_the_safety_reset_releases_them(self) -> None:
        client = self.serve()
        stopped = client.estop("package test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        refused = self.step(client, 0)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
        released = client.reset(**self.ids)
        self.assertEqual(released["status"], "completed", released)
        allowed = self.step(client, 0)
        self.assertEqual(allowed["status"], "completed", allowed)

    def test_the_manifest_discloses_simulated_f0_and_no_native_stop(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R2")
        self.assertEqual(device["fidelity"]["fidelity_level"], "F0")
        self.assertEqual(device["fidelity"]["timestep_ms"], 0)
        self.assertFalse(device["fidelity"]["snapshot_restore"])
        self.assertTrue(device["fidelity"]["gaps"])
        self.assertIsNone(device["safety"]["estop"]["native"])


if __name__ == "__main__":
    unittest.main()
