"""Acceptance run of the StrideSim package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim and Isaac Lab
are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ACTION = [0.2, -0.1, 0.0, 0.3, 0.1, -0.2, 0.0, 0.2, -0.1, 0.1, 0.0, -0.2]   # placeholder action values
ZERO_ACTION = [0.0] * 12                                                      # placeholder action values


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StrideSimCases(unittest.TestCase):
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

    def test_a_step_advances_the_declared_number_of_ticks(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=7)
        self.assertEqual(reset["status"], "completed")
        self.assertEqual(reset["output"]["seed"], 7)
        receipt = self.step(client, ACTION, ticks=3)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertEqual(len(output["observation"]["values"]), 48)      # flat task: 235 minus the height scan
        self.assertIsInstance(output["reward"], float)
        self.assertEqual(self.state(client)["tick"], 3)

    def test_the_reset_draws_the_command_from_the_configured_range(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=5)["output"]
        command = self.state(client)["info"]["command"]
        self.assertEqual(len(command), 3)
        self.assertTrue(all(-1.0 <= value <= 1.0 for value in command), command)   # velocity_env_cfg.py:99
        self.assertEqual(self.state(client)["observation"], output["observation"])

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, ACTION)["output"]["state_hash"] for _ in range(3)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        invoked = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(invoked["status"], "completed")
        self.assertEqual(invoked["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_truncates_at_the_configured_horizon(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        # decimation 4 at sim.dt 0.005 s and episode_length_s 20.0 give 1000 control steps (velocity_env_cfg.py:295-298)
        output = self.step(client, ZERO_ACTION, ticks=1001)["output"]
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        self.assertEqual(output["tick"], 1000)
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_an_action_that_does_not_fit_the_space_is_refused(self) -> None:
        client = self.serve()
        refused = self.step(client, [0.1, 0.2, 0.3])                 # the fake declares 12 action channels
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertIn("INPUT_INVALID", refused["error"]["mhs_code"])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["engine"], "isaac:Template-Isaac-Velocity-Flat-Anymal-D-v0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
