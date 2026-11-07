"""Acceptance run of the UR5/Robotiq driver: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): PyBullet is not
installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

#: An in-envelope end-effector action (the envelope is the slider range of env.py:40-46).
ACTION = {
    "x": 0.0,
    "y": 0.0,
    "z": 0.5,
    "roll": 0.0,
    "pitch": 0.0,
    "yaw": 0.0,
    "gripper_opening_length": 0.04,
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UR5RobotiqCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client):
        return client.invoke("cap.world.reset.v1", {}, **self.ids)

    def step(self, client, ticks=1, **fields):
        action = dict(ACTION)
        action.update(fields)
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_reset_returns_the_observation_and_zero_seed(self) -> None:
        client = self.serve()
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["seed"], 0)
        self.assertIn("positions", output["observation"])
        self.assertIn("velocities", output["observation"])
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"]), (0, 1))

    def test_a_step_applies_the_end_effector_target(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, x=0.1, y=-0.1, z=0.5)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["observation"]["ee_pos"], [0.1, -0.1, 0.5])
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        self.assertEqual(output["reward"], 0.0)
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_ticks_advance_the_tick_count(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, ticks=3, z=0.25)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 3)
        self.assertEqual(self.state(client)["tick"], 3)

    def test_every_action_bound_is_refused(self) -> None:
        client = self.serve()
        self.reset(client)
        outside = {
            "x": 0.225,
            "y": -0.225,
            "z": 1.01,
            "roll": 3.15,
            "pitch": -3.15,
            "yaw": 1.58,
            "gripper_opening_length": 0.086,
        }
        for name, value in outside.items():
            refused = self.step(client, **{name: value})
            self.assertEqual(refused["status"], "rejected", name)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, name)
        self.assertEqual(self.state(client)["tick"], 0)  # no refused step reached the backend

    def test_a_reset_starts_the_next_episode(self) -> None:
        client = self.serve()
        self.reset(client)
        self.step(client, x=0.1)
        second = self.reset(client)
        self.assertEqual(second["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"]), (0, 2))
        self.assertEqual(state["observation"]["ee_pos"], [0.0, 0.0, 0.5])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("pybullet:ClutteredPushGrasp", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.step(client, x=0.1)
        client.estop("test", **self.ids)
        for refused in (self.step(client, x=0.2), self.reset(client)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
