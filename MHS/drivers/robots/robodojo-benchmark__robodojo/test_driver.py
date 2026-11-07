"""Acceptance run of the RoboDojo package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab and
the downloaded assets are not available where the gate runs, so nothing here compares the fake with the upstream
environment.  The fake's numbers are placeholder test data, not facts or limits of this package.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


def action(left_arm=None, left_gripper=0.5, right_arm=None, right_gripper=0.5):
    return {
        "left_arm_joint_state": list(left_arm or [0.0] * 6),
        "left_ee_joint_state": [left_gripper],
        "right_arm_joint_state": list(right_arm or [0.0] * 6),
        "right_ee_joint_state": [right_gripper],
    }


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RoboDojoCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, value=None, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": value if value is not None else action()},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, action([0.1, 0, 0, 0, 0, 0]))["status"], "completed")
        for bad in (action(left_gripper=1.5), action(left_gripper=-0.5), action(right_gripper=2.0)):
            refused = self.step(client, bad)
            self.assertEqual(refused["status"], "rejected", bad)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, bad)
        wrong_length = self.step(client, action([0.0] * 5))
        self.assertEqual((wrong_length["status"], wrong_length["error"]["mhs_code"]),
                         ("rejected", "MHS.CAPABILITY.INPUT_INVALID"))
        self.assertEqual(self.state(client)["tick"], 1)                      # the refused steps changed nothing

    def test_a_seed_repeats_the_initial_state(self) -> None:
        def observation(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return self.reset(client, seed=seed)["output"]["observation"]

        first = observation(7)
        self.assertEqual(observation(7), first)
        self.assertNotEqual(observation(8), first)

    def test_a_step_applies_the_joint_command_and_the_tick(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        before = self.state(client)["observation"]
        command = action([0.25, 0, 0, 0, 0, 0], left_gripper=0.1,
                         right_arm=[0, 0, 0, 0, 0, -0.2], right_gripper=0.9)
        receipt = self.step(client, command, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertIsInstance(output["reward"], (int, float))
        values = output["observation"]["values"]
        self.assertEqual((values[0], values[6], values[12], values[13]), (0.25, 0.1, -0.2, 0.9))
        after = self.state(client)["observation"]
        self.assertNotEqual(before, after)
        self.assertEqual(self.state(client)["tick"], 3)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual(fidelity["engine"], "robodojo:TaskEnv/dual-x5")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (4.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
