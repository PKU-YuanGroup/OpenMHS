"""Acceptance run of the robo-gym package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the external
example_robot_server and Gazebo are not in the clone and were not run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ExampleEnvCases(unittest.TestCase):
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

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        for values in ([1.5, 0.0], [-2.0, -2.0], [0.0, 1.01]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_reset_option_and_the_placeholder_step(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3, options={"position": [1.0, -2.0]})
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["output"]["observation"]["values"], [1.0, -2.0, 0.0, 0.0])
        receipt = self.step(client, [1.0, -1.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # the fake holds the two velocity commands for STEP_S = 0.05 s; these are placeholder test data, not a fact
        self.assertEqual(output["observation"]["values"], [1.05, -2.05, 1.0, -1.0])
        self.assertEqual((output["reward"], output["tick"]), (0.0, 1))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))

    def test_reset_position_needs_two_elements(self) -> None:
        client = self.serve()
        refused = self.reset(client, options={"position": [1.0]})
        self.assertEqual(refused["status"], "failed")

    def test_the_episode_ends_at_300_steps(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0, 0.0], ticks=300)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 300))
        self.assertEqual(output["reward"], 0.0)
        ended = self.step(client, [0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"accepted": True, "seed": 21})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, values)["output"]["state_hash"] for values in
                    ([1.0, 0.0], [0.0, 1.0], [0.0, 0.0], [-1.0, -1.0])]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["engine"], "robo-gym:ExampleEnvSim-v0 (external robot server and Gazebo not "
                                             "included)")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
