"""Acceptance run of the OmniIsaacGymEnvs Cartpole package: the gate, plus cases for what is specific here.

The cases run on the fake backend (fake.py): Isaac Sim is not installed where the gate runs, so nothing here compares
the fake with the simulator.  The reward, the reset ranges and the 500-step limit come from the clone and are cited in
driver.py and facts.md.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
RESET_DIST = 3.0
MAX_EPISODE_LENGTH = 500


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CartpoleCases(unittest.TestCase):
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

    def step(self, client, value, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": [value]}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1.0)["status"], "completed")
        for value in (-1.5, 1.5):
            refused = self.step(client, value)
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        # the bridge derives a one-element Box from the environment, so a wrong length is a shape error, not a bound
        wrong = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"values": [0.0, 0.0]}}, **self.ids)
        self.assertEqual((wrong["status"], wrong["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_the_reward_is_the_cartpole_formula(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")
        receipt = self.step(client, 0.0)                          # action 0 freezes the fake: velocities become zero
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["values"]
        # cartpole.py:153-156 with zero velocities: 1 - pole_pos^2, and no failure threshold is crossed
        self.assertAlmostEqual(output["reward"], 1.0 - values[2] * values[2], places=7)
        self.assertEqual(len(values), 4)
        self.assertEqual((values[1], values[3]), (0.0, 0.0))
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, False, 1))

    def test_a_constant_push_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        output = None
        for _ in range(MAX_EPISODE_LENGTH):
            output = self.step(client, 1.0)["output"]
            if output["terminated"]:
                break
        self.assertIsNotNone(output)
        self.assertTrue(output["terminated"])
        # the pole passes pi/2 well before the 500-step limit (cartpole.py:160-163); failure pays -2 (cartpole.py:156)
        self.assertLess(output["tick"], MAX_EPISODE_LENGTH)
        self.assertEqual(output["reward"], -2.0)
        self.assertGreater(abs(output["observation"]["values"][2]), math.pi / 2)
        restarted = self.step(client, 0.0)                        # the upstream resets on the next step; the bridge
        self.assertEqual(restarted["status"], "completed")        # follows it with autoreset=True
        self.assertEqual((restarted["output"]["terminated"], restarted["output"]["tick"]), (False, 1))

    def test_the_episode_is_capped_at_500_steps(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=4)["output"]["observation"]["values"]
        receipt = self.step(client, 0.0, ticks=MAX_EPISODE_LENGTH)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # cartpole.py:44 and :163: progress >= 500 flags a reset; action 0 never crosses a position threshold
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 500))
        values = output["observation"]["values"]
        self.assertEqual((values[0], values[2]), (observation[0], observation[2]))   # positions do not move
        self.assertEqual((values[1], values[3]), (0.0, 0.0))
        self.assertAlmostEqual(output["reward"], 500.0 * (1.0 - observation[2] * observation[2]), places=6)
        restarted = self.step(client, 0.0)
        self.assertEqual((restarted["output"]["terminated"], restarted["output"]["tick"]), (False, 1))

    def test_a_seed_repeats_the_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        second = self.reset(client, seed=11)["output"]
        self.assertEqual(first["seed"], 11)
        self.assertEqual(first["observation"], second["observation"])
        other = self.reset(client, seed=12)["output"]
        self.assertNotEqual(other["observation"], first["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"note": "the upstream reset ignores options"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(len(receipt["output"]["observation"]["values"]), 4)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertTrue(fidelity["engine"].startswith("analytic:"), fidelity["engine"])
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (16.6, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1.0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1.0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)           # readable, and not advanced

    def test_the_reset_dist_threshold_is_used(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        # push until the episode ends and check the failure is on a documented threshold (cartpole.py:161-162)
        for _ in range(MAX_EPISODE_LENGTH):
            output = self.step(client, 1.0)["output"]
            if output["terminated"]:
                break
        values = output["observation"]["values"]
        self.assertTrue(abs(values[0]) > RESET_DIST or abs(values[2]) > math.pi / 2)


if __name__ == "__main__":
    unittest.main()
