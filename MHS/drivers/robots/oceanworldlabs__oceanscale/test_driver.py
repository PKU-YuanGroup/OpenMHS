"""Acceptance run of the OceanScale package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream simulator,
its CUDA stack and the sim backend were not run, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = [0.0] * 6


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OceanScaleCases(unittest.TestCase):
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

    def step(self, client, values=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values or ZERO_ACTION}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 6)["status"], "completed")
        refused = self.step(client, [1.5, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused = self.step(client, [0.0] * 5)                                # six elements are required
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(self.state(client)["tick"], 1)                       # the refused steps changed nothing

    def test_the_first_step_advances_the_observation_and_the_reward(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, [0.0] * 6)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), 26)                                     # rov_env.py:62-70
        self.assertEqual(output["tick"], 1)
        self.assertGreater(output["reward"], 0.0)                            # rov_env.py:777 and :789
        self.assertLessEqual(output["reward"], 1.0)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))

    def test_a_seed_repeats_the_reset_noise(self) -> None:
        def observation(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return self.reset(client, seed=seed)["output"]["observation"]

        self.assertEqual(observation(11), observation(11))
        self.assertNotEqual(observation(11), observation(12))

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_reset_option_replaces_the_target(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1, options={"target_position": [1.0, 2.0, -3.0]})["status"],
                         "completed")
        self.assertEqual(self.state(client)["info"]["target_position"], [1.0, 2.0, -3.0])   # rov_env.py:299-303

    def test_the_episode_truncates_at_max_episode_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, ZERO_ACTION, ticks=1000)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))       # rov_env.py:414-416
        self.assertEqual(output["tick"], 1000)
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")

    def test_a_full_action_terminates_out_of_bounds(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0], ticks=1000)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertTrue(output["terminated"])                                 # rov_env.py:418-421
        self.assertFalse(output["truncated"])
        self.assertLess(output["tick"], 1000)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("oceanscale.rov_env:ROVEnv", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "statistical")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 240.0, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
